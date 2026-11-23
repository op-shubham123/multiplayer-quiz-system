"""Threaded TCP quiz server with terminal-based host controls.

Protocol: one UTF-8 JSON object per line. This is a LAN/demo project, not a
public-internet server (there is no user authentication or transport encryption).
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime
from pathlib import Path
import socket
import threading
import time
import uuid
from typing import Any

from network import JsonConnection
from quiz_core import QuizEngine, QuizError, load_questions

DEFAULT_QUESTIONS = Path(__file__).with_name("questions.json")


class QuizServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5555,
                 questions_path: str | Path = DEFAULT_QUESTIONS,
                 question_seconds: float = 20.0, result_seconds: float = 3.0,
                 tick_seconds: float = 0.1):
        self.host = host
        self.port = port
        self.questions_path = Path(questions_path)
        self.engine = QuizEngine(load_questions(self.questions_path))
        self.question_seconds = question_seconds
        self.result_seconds = result_seconds
        self.tick_seconds = tick_seconds
        self._lock = threading.RLock()
        self._clients: dict[str, JsonConnection] = {}
        self._chat_history: deque[dict[str, Any]] = deque(maxlen=40)
        self._listener: socket.socket | None = None
        self._running = threading.Event()
        self._deadline_mono: float | None = None
        self._deadline_wall: float | None = None
        self._result_until: float | None = None
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._running.is_set():
            return
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self.host, self.port))
            listener.listen(32)
            listener.settimeout(0.25)
        except Exception:
            listener.close()
            raise
        self._listener = listener
        self.port = listener.getsockname()[1]
        self._running.set()
        for target, name in ((self._accept_loop, "quiz-accept"),
                             (self._tick_loop, "quiz-timer")):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)
        print(f"[SERVER] Listening on {self.host}:{self.port}")

    def close(self) -> None:
        if not self._running.is_set():
            return
        self._running.clear()
        if self._listener:
            self._listener.close()
        with self._lock:
            for conn in list(self._clients.values()):
                conn.close()
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(timeout=1.0)

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                assert self._listener is not None
                sock, addr = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            sock.settimeout(15)  # Initial join must arrive promptly.
            thread = threading.Thread(target=self._client_loop, args=(sock, addr), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _client_loop(self, sock: socket.socket, addr: tuple[str, int]) -> None:
        conn = JsonConnection(sock)
        player_id: str | None = None
        try:
            hello = conn.receive()
            if hello is None:
                return
            if hello.get("type") != "join":
                conn.send({"type": "error", "message": "First message must be join"})
                return
            player_id = uuid.uuid4().hex
            with self._lock:
                self.engine.join(player_id, hello.get("name", "") if isinstance(hello.get("name"), str) else "")
                self._clients[player_id] = conn
                conn.send({"type": "welcome", "player_id": player_id,
                           "name": self.engine.players[player_id]["name"],
                           "chat_history": list(self._chat_history)})
                self._broadcast_locked(self._snapshot_locked())
                print(f"[JOIN] {self.engine.players[player_id]['name']} from {addr[0]}")
            sock.settimeout(None)
            while self._running.is_set():
                message = conn.receive()
                if message is None:
                    break
                with self._lock:
                    self._handle_locked(player_id, message)
        except (OSError, ConnectionError):
            pass
        except (QuizError, ValueError) as exc:
            try:
                conn.send({"type": "error", "message": str(exc)})
            except OSError:
                pass
        finally:
            with self._lock:
                if player_id in self._clients:
                    name = self.engine.players[player_id]["name"]
                    self._clients.pop(player_id, None)
                    self.engine.leave(player_id)
                    print(f"[LEAVE] {name}")
                    self._broadcast_locked(self._snapshot_locked())
            conn.close()

    def _handle_locked(self, player_id: str, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == "answer":
            try:
                self.engine.submit(player_id, message.get("choice"))
                self._clients[player_id].send({"type": "answer_ack", "choice": message["choice"]})
                self._broadcast_locked(self._snapshot_locked())
            except QuizError as exc:
                self._clients[player_id].send({"type": "error", "message": str(exc)})
        elif kind == "chat":
            raw = message.get("text")
            if not isinstance(raw, str) or not raw.strip():
                return
            text = raw.strip()[:300]
            chat = {"type": "chat", "name": self.engine.players[player_id]["name"],
                    "text": text, "time": datetime.now().strftime("%H:%M")}
            self._chat_history.append(chat)
            self._broadcast_locked(chat)
        elif kind == "ping":
            self._clients[player_id].send({"type": "pong"})
        else:
            self._clients[player_id].send({"type": "error", "message": "Unknown action"})

    def _snapshot_locked(self) -> dict[str, Any]:
        return self.engine.snapshot(self._deadline_wall)

    def _broadcast_locked(self, message: dict[str, Any]) -> None:
        for conn in list(self._clients.values()):
            try:
                conn.send(message)
            except (OSError, ConnectionError):
                # Client handler will remove it after the connection closes.
                conn.close()

    def start_game(self) -> None:
        with self._lock:
            self.engine.start()
            self._begin_question_locked()
            print(f"[GAME] Started with {len(self.engine.players)} player(s)")

    def _begin_question_locked(self) -> None:
        self._deadline_mono = time.monotonic() + self.question_seconds
        self._deadline_wall = time.time() + self.question_seconds
        self._result_until = None
        self._broadcast_locked(self._snapshot_locked())
        print(f"[QUESTION] {self.engine.question_index + 1}/{len(self.engine.questions)}")

    def _close_question_locked(self) -> None:
        result = self.engine.close_question()
        self._deadline_mono = None
        self._deadline_wall = None
        self._result_until = time.monotonic() + self.result_seconds
        self._broadcast_locked(self._snapshot_locked())
        print(f"[RESULT] Correct option {result['correct_index'] + 1}")

    def next_question(self) -> None:
        with self._lock:
            if self.engine.phase == "question":
                self._close_question_locked()
            elif self.engine.phase == "results":
                self._advance_locked()
            else:
                raise QuizError("No active question or result to advance")

    def _advance_locked(self) -> None:
        phase = self.engine.advance()
        self._result_until = None
        if phase == "finished":
            self._deadline_mono = None
            self._deadline_wall = None
            self._broadcast_locked(self._snapshot_locked())
            print("[GAME] Finished! Type 'reset' for another round.")
        else:
            self._begin_question_locked()

    def stop_game(self) -> None:
        with self._lock:
            self.engine.stop()
            self._deadline_mono = self._deadline_wall = self._result_until = None
            self._broadcast_locked(self._snapshot_locked())
            print("[GAME] Stopped by host")

    def reset_game(self) -> None:
        with self._lock:
            self.engine.reset()
            self._deadline_mono = self._deadline_wall = self._result_until = None
            self._broadcast_locked(self._snapshot_locked())
            print("[GAME] Reset. Scores cleared; players remain connected.")

    def reload_questions(self) -> None:
        questions = load_questions(self.questions_path)
        with self._lock:
            self.engine.replace_questions(questions)
            self._deadline_mono = self._deadline_wall = self._result_until = None
            self._broadcast_locked(self._snapshot_locked())
            print(f"[GAME] Reloaded {len(questions)} questions")

    def status(self) -> str:
        with self._lock:
            return (f"Phase: {self.engine.phase} | Players: {len(self.engine.players)} | "
                    f"Question: {max(0, self.engine.question_index + 1)}/{len(self.engine.questions)} | "
                    f"Scores: {[(p['name'], p['score']) for p in self.engine.leaderboard()]}")

    def _tick_loop(self) -> None:
        while self._running.is_set():
            with self._lock:
                now = time.monotonic()
                if self.engine.phase == "question" and (
                    (self._deadline_mono is not None and now >= self._deadline_mono)
                    or self.engine.everyone_answered()
                ):
                    self._close_question_locked()
                elif (self.engine.phase == "results" and self._result_until is not None
                      and now >= self._result_until):
                    self._advance_locked()
            time.sleep(self.tick_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="QuizVerse multiplayer quiz server")
    parser.add_argument("--host", default="127.0.0.1", help="Use 0.0.0.0 to accept LAN players")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--seconds", type=float, default=20, help="Seconds per question")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    if args.seconds < 1:
        parser.error("Question duration must be at least one second")
    try:
        server = QuizServer(args.host, args.port, args.questions, args.seconds)
        server.start()
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Unable to start server: {exc}\n")
    print("\nHOST COMMANDS: start | next | stop | reset | reload | status | help | quit")
    print("Open client.py in another terminal, join, then type 'start' here.\n")
    try:
        while True:
            try:
                command = input("quiz-host> ").strip().lower()
            except EOFError:
                break
            try:
                if command == "start":
                    server.start_game()
                elif command == "next":
                    server.next_question()
                elif command == "stop":
                    server.stop_game()
                elif command == "reset":
                    server.reset_game()
                elif command == "reload":
                    server.reload_questions()
                elif command == "status":
                    print(server.status())
                elif command in ("help", "?"):
                    print("start=begin quiz, next=skip timer, stop=end, reset=clear scores, "
                          "reload=load updated questions.json, status=show game, quit=exit")
                elif command in ("quit", "exit"):
                    break
                elif command:
                    print("Unknown command. Type 'help'.")
            except (QuizError, OSError, ValueError) as exc:
                print(f"[NOTICE] {exc}")
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
