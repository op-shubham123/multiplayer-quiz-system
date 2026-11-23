"""QuizVerse browser multiplayer API.

Run from the repository root:
    uvicorn web.backend.app:app --reload --port 8000

Rooms are kept in process memory. Deploy exactly one Uvicorn worker/instance;
for multi-instance hosting replace this state store with Redis/pub-sub.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import string
import sys
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from quiz_core import QuizEngine, QuizError, load_questions  # noqa: E402

QUESTIONS_PATH = ROOT / "questions.json"
ALPHABET = string.ascii_uppercase + string.digits
MAX_PLAYERS = 30
MAX_ROOMS = 100
ROOM_IDLE_SECONDS = 60 * 60
QUESTION_SECONDS = float(os.getenv("QUESTION_SECONDS", "20"))
RESULT_SECONDS = float(os.getenv("RESULT_SECONDS", "4"))
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS)).split(",")
    if origin.strip()
}

app = FastAPI(title="QuizVerse Multiplayer API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@dataclass
class Participant:
    player_id: str
    name: str
    session_token: str
    is_host: bool
    websocket: WebSocket | None = None
    last_chat_at: float = 0.0


class Room:
    def __init__(self, code: str, host_token: str) -> None:
        self.code = code
        self.host_token = host_token
        self.engine = QuizEngine(load_questions(QUESTIONS_PATH))
        self.participants: dict[str, Participant] = {}
        self.chat_history: deque[dict[str, Any]] = deque(maxlen=50)
        self.lock = asyncio.Lock()
        self.deadline_mono: float | None = None
        self.deadline_wall: float | None = None
        self.result_until: float | None = None
        self.last_active = time.monotonic()
        self.timer_task: asyncio.Task[None] | None = None

    def connected(self) -> list[Participant]:
        return [p for p in self.participants.values() if p.websocket is not None]

    def snapshot(self, player_id: str) -> dict[str, Any]:
        data = self.engine.snapshot(self.deadline_wall)
        if self.engine.phase == "results" and self.engine.question_index >= 0:
            data["question"] = self.engine.questions[self.engine.question_index].public()
        data.update(
            room_code=self.code,
            your_answer=self.engine.answers.get(player_id),
            players=[
                {**player, "connected": self.participants[player["id"]].websocket is not None,
                 "is_host": self.participants[player["id"]].is_host}
                for player in data["players"]
            ],
        )
        return data

    async def send(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        await asyncio.wait_for(websocket.send_json(message), timeout=3)

    async def broadcast(self, message: dict[str, Any] | None = None) -> None:
        # Caller holds self.lock so changes to game state and broadcasts are ordered.
        for p in self.connected():
            try:
                await self.send(p.websocket, message if message is not None else self.snapshot(p.player_id))
            except Exception:
                # Disconnected clients are marked offline by the websocket handler.
                # A later broadcast will also try them, but no score is lost.
                pass

    def begin_question(self) -> None:
        self.deadline_mono = time.monotonic() + QUESTION_SECONDS
        self.deadline_wall = time.time() + QUESTION_SECONDS
        self.result_until = None

    def close_question(self) -> None:
        self.engine.close_question()
        self.deadline_mono = None
        self.deadline_wall = None
        self.result_until = time.monotonic() + RESULT_SECONDS

    def advance(self) -> None:
        phase = self.engine.advance()
        if phase == "question":
            self.begin_question()
        else:
            self.deadline_mono = None
            self.deadline_wall = None
            self.result_until = None

    def clear_timers(self) -> None:
        self.deadline_mono = None
        self.deadline_wall = None
        self.result_until = None

    def all_connected_answered(self) -> bool:
        connected = self.connected()
        return bool(connected) and all(p.player_id in self.engine.answers for p in connected)

    async def timer_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(0.2)
                async with self.lock:
                    now = time.monotonic()
                    if not self.connected() and now - self.last_active > ROOM_IDLE_SECONDS:
                        break
                    if self.engine.phase == "question" and self.deadline_mono is not None and now >= self.deadline_mono:
                        self.close_question()
                        await self.broadcast()
                    elif self.engine.phase == "results" and self.result_until is not None and now >= self.result_until:
                        self.advance()
                        await self.broadcast()
            async with rooms_lock:
                if rooms.get(self.code) is self:
                    rooms.pop(self.code, None)
        except asyncio.CancelledError:
            return


rooms: dict[str, Room] = {}
rooms_lock = asyncio.Lock()


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "QuizVerse Multiplayer API", "health": "/health"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "mode": "websocket-multiplayer", "active_rooms": len(rooms)}


@app.post("/api/rooms", status_code=201)
async def create_room() -> dict[str, str]:
    async with rooms_lock:
        if len(rooms) >= MAX_ROOMS:
            raise HTTPException(status_code=503, detail="All rooms are busy. Try again later.")
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        while code in rooms:
            code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        host_token = secrets.token_urlsafe(32)
        room = Room(code, host_token)
        rooms[code] = room
        room.timer_task = asyncio.create_task(room.timer_loop())
        return {"room_code": code, "host_token": host_token}


@app.get("/api/rooms/{code}")
async def room_info(code: str) -> dict[str, Any]:
    room = rooms.get(code.upper())
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"room_code": room.code, "phase": room.engine.phase,
            "player_count": len(room.participants), "question_count": len(room.engine.questions)}


async def join_room(room: Room, ws: WebSocket, payload: dict[str, Any]) -> Participant:
    name = payload.get("name")
    if not isinstance(name, str):
        raise QuizError("Enter a nickname to join")
    token = payload.get("session_token")
    if token is not None and not isinstance(token, str):
        raise QuizError("Invalid session token")
    host_token = payload.get("host_token")
    if host_token is not None and not isinstance(host_token, str):
        raise QuizError("Invalid host token")
    async with room.lock:
        if token:
            p = next((p for p in room.participants.values() if secrets.compare_digest(p.session_token, token)), None)
            if p is None:
                raise QuizError("Your session has expired. Join with a new nickname.")
            # A refresh can connect before the old socket's disconnect is processed.
            # The secret session token authorizes taking over that stale connection.
            if p.websocket is not None and p.websocket is not ws:
                try:
                    await asyncio.wait_for(p.websocket.close(code=1000), timeout=1)
                except Exception:
                    pass
        else:
            if len(room.participants) >= MAX_PLAYERS:
                raise QuizError("Room is full (30 players maximum)")
            is_host = False
            if host_token:
                if not secrets.compare_digest(host_token, room.host_token):
                    raise QuizError("Invalid host key")
                if any(p.is_host for p in room.participants.values()):
                    raise QuizError("The host already joined. Reconnect from the original browser.")
                is_host = True
            player_id = uuid4().hex
            room.engine.join(player_id, name)
            p = Participant(player_id, name.strip(), secrets.token_urlsafe(32), is_host)
            room.participants[player_id] = p
        p.websocket = ws
        room.last_active = time.monotonic()
        await room.send(ws, {"type": "welcome", "player_id": p.player_id,
                             "session_token": p.session_token, "name": p.name,
                             "is_host": p.is_host, "room_code": room.code,
                             "chat_history": list(room.chat_history)})
        await room.broadcast()
        return p


async def handle_message(room: Room, p: Participant, message: dict[str, Any]) -> bool:
    """Handle a player message. Returns False if the player intentionally leaves."""
    async with room.lock:
        if room.participants.get(p.player_id) is not p:
            return False
        room.last_active = time.monotonic()
        kind = message.get("type")
        try:
            if kind == "answer":
                choice = message.get("choice")
                room.engine.submit(p.player_id, choice)
                await room.send(p.websocket, {"type": "answer_ack", "choice": choice,
                                              "question_index": room.engine.question_index})
                if room.all_connected_answered():
                    room.close_question()
                await room.broadcast()
            elif kind == "chat":
                raw = message.get("text")
                if not isinstance(raw, str) or not raw.strip():
                    raise QuizError("Message cannot be empty")
                if time.monotonic() - p.last_chat_at < 0.6:
                    raise QuizError("Please wait a moment before sending another message")
                p.last_chat_at = time.monotonic()
                chat = {"type": "chat", "name": p.name, "player_id": p.player_id,
                        "text": raw.strip()[:300], "time": datetime.now(timezone.utc).strftime("%H:%M UTC")}
                room.chat_history.append(chat)
                await room.broadcast(chat)
            elif kind == "host_action":
                if not p.is_host:
                    raise QuizError("Only the room host can control the game")
                action = message.get("action")
                if action == "start":
                    room.engine.start()
                    room.begin_question()
                elif action == "next":
                    if room.engine.phase == "question":
                        room.close_question()
                    elif room.engine.phase == "results":
                        room.advance()
                    else:
                        raise QuizError("No active question to advance")
                elif action == "stop":
                    room.engine.stop()
                    room.clear_timers()
                elif action == "reset":
                    room.engine.reset()
                    room.clear_timers()
                elif action == "reload":
                    room.engine.replace_questions(load_questions(QUESTIONS_PATH))
                    room.clear_timers()
                else:
                    raise QuizError("Unknown host command")
                await room.broadcast()
            elif kind == "leave":
                room.participants.pop(p.player_id, None)
                room.engine.leave(p.player_id)
                # If the host explicitly leaves, give the room to a remaining
                # player so their friends are not stranded without controls.
                if p.is_host and room.participants:
                    next_host = next((q for q in room.participants.values() if q.websocket is not None),
                                     next(iter(room.participants.values())))
                    next_host.is_host = True
                    if next_host.websocket is not None:
                        await room.send(next_host.websocket, {"type": "host_promoted"})
                await room.broadcast()
                return False
            elif kind == "ping":
                await room.send(p.websocket, {"type": "pong"})
            else:
                raise QuizError("Unknown message type")
        except QuizError as exc:
            await room.send(p.websocket, {"type": "error", "message": str(exc)})
        return True


@app.websocket("/ws/{code}")
async def websocket_room(ws: WebSocket, code: str) -> None:
    origin = ws.headers.get("origin")
    if origin and origin.rstrip("/") not in ALLOWED_ORIGINS:
        await ws.close(code=1008, reason="Origin not allowed")
        return
    room = rooms.get(code.upper())
    if room is None:
        await ws.close(code=1008, reason="Room not found")
        return
    await ws.accept()
    p: Participant | None = None
    try:
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=15)
            if not isinstance(first, dict) or first.get("type") != "join":
                raise QuizError("First message must be a join request")
            p = await join_room(room, ws, first)
        except (QuizError, ValueError) as exc:
            await ws.send_json({"type": "error", "message": str(exc)})
            await ws.close(code=1008)
            return
        while True:
            message = await ws.receive_json()
            if p.websocket is not ws:
                break  # Session has been reattached to a newer connection.
            if not isinstance(message, dict) or len(str(message)) > 4096:
                await ws.send_json({"type": "error", "message": "Invalid or oversized message"})
                continue
            if not await handle_message(room, p, message):
                await ws.close(code=1000)
                break
    except (WebSocketDisconnect, RuntimeError, OSError, asyncio.TimeoutError):
        pass
    finally:
        if p is not None:
            async with room.lock:
                if room.participants.get(p.player_id) is p and p.websocket is ws:
                    p.websocket = None
                    room.last_active = time.monotonic()
                    await room.broadcast()
