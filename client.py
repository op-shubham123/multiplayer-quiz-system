"""QuizVerse desktop client: Tkinter GUI + background TCP networking."""
from __future__ import annotations

import argparse
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Any

from network import JsonConnection

BG = "#0B1020"
CARD = "#151E32"
CARD_2 = "#1C2942"
BORDER = "#2A3854"
TEXT = "#F4F7FF"
MUTED = "#9BAAC4"
PURPLE = "#7565F5"
PURPLE_HOVER = "#8B7CFF"
GREEN = "#35D7AE"
RED = "#FB7185"
GOLD = "#F6C56A"
FONT = "Segoe UI"


class NetworkClient:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.connection: JsonConnection | None = None
        self._closing = False
        self._generation = 0

    def connect(self, host: str, port: int, nickname: str) -> None:
        self.disconnect()
        self._closing = False
        self._generation += 1
        generation = self._generation
        thread = threading.Thread(target=self._connect_worker,
                                  args=(host, port, nickname, generation), daemon=True)
        thread.start()

    def _connect_worker(self, host: str, port: int, nickname: str, generation: int) -> None:
        conn: JsonConnection | None = None
        try:
            sock = socket.create_connection((host, port), timeout=6)
            sock.settimeout(None)
            conn = JsonConnection(sock)
            if generation != self._generation:
                conn.close()
                return
            self.connection = conn
            conn.send({"type": "join", "name": nickname})
            while not self._closing and generation == self._generation:
                event = conn.receive()
                if event is None:
                    break
                self.events.put((generation, event))
        except (OSError, ValueError) as exc:
            if not self._closing and generation == self._generation:
                self.events.put((generation, {"type": "connection_error", "message": str(exc)}))
        finally:
            if conn:
                conn.close()
            if generation == self._generation:
                self.connection = None
                if not self._closing:
                    self.events.put((generation, {"type": "connection_lost"}))

    def send(self, message: dict[str, Any]) -> None:
        if not self.connection:
            self.events.put((self._generation, {"type": "error", "message": "Not connected"}))
            return
        try:
            self.connection.send(message)
        except OSError:
            self.events.put((self._generation, {"type": "connection_lost"}))

    def disconnect(self) -> None:
        self._closing = True
        self._generation += 1
        if self.connection:
            self.connection.close()
            self.connection = None


class QuizClientApp:
    def __init__(self, root: tk.Tk, host: str, port: int):
        self.root = root
        self.root.title("QuizVerse | Multiplayer Quiz Arena")
        self.root.geometry("1140x750")
        self.root.minsize(940, 660)
        self.root.configure(bg=BG)
        self.events: queue.Queue = queue.Queue()
        self.network = NetworkClient(self.events)
        self.player_id: str | None = None
        self.connected = False
        self.phase = "lobby"
        self.question_index = -1
        self.question_count = 0
        self.deadline: float | None = None
        self.question: dict[str, Any] | None = None
        self.selected: int | None = None
        self.result: dict[str, Any] | None = None
        self.players: list[dict[str, Any]] = []
        self.answered_count = 0
        self.host_var = tk.StringVar(value=host)
        self.port_var = tk.StringVar(value=str(port))
        self.name_var = tk.StringVar(value="Player1")
        self.chat_var = tk.StringVar()
        self._build_ui()
        self.root.after(80, self._poll)
        self.root.after(200, self._update_clock)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    @staticmethod
    def _label(parent: tk.Widget, text: str, size: int = 11, color: str = TEXT,
               bold: bool = False, **kwargs: Any) -> tk.Label:
        return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                        bg=parent.cget("bg"), fg=color, **kwargs)

    @staticmethod
    def _button(parent: tk.Widget, text: str, command: Any, primary: bool = True,
                width: int | None = None) -> tk.Button:
        bg = PURPLE if primary else CARD_2
        button = tk.Button(parent, text=text, command=command, bg=bg, fg=TEXT,
                           activebackground=PURPLE_HOVER if primary else BORDER,
                           activeforeground=TEXT, bd=0, relief="flat", cursor="hand2",
                           font=(FONT, 10, "bold"), padx=16, pady=10,
                           highlightthickness=0)
        if width is not None:
            button.configure(width=width)
        return button

    @staticmethod
    def _entry(parent: tk.Widget, variable: tk.StringVar, width: int = 14) -> tk.Entry:
        return tk.Entry(parent, textvariable=variable, width=width, bg=CARD_2, fg=TEXT,
                        insertbackground=TEXT, bd=0, relief="flat", font=(FONT, 11),
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=PURPLE)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 14))
        self._label(header, "◆", 23, PURPLE, True).pack(side="left", padx=(0, 10))
        title_area = tk.Frame(header, bg=BG)
        title_area.pack(side="left")
        self._label(title_area, "QUIZVERSE", 20, TEXT, True).pack(anchor="w")
        self._label(title_area, "LIVE MULTIPLAYER QUIZ ARENA", 9, MUTED, True).pack(anchor="w")
        self.connection_label = self._label(header, "●  OFFLINE", 10, MUTED, True)
        self.connection_label.pack(side="right", padx=6)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        body.grid_columnconfigure(0, weight=1, minsize=620)
        body.grid_columnconfigure(1, weight=0, minsize=320)
        body.grid_rowconfigure(1, weight=1)

        join = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        join.grid(row=0, column=0, sticky="ew", padx=(0, 16), pady=(0, 16))
        join_content = tk.Frame(join, bg=CARD)
        join_content.pack(fill="x", padx=18, pady=15)
        self._label(join_content, "CONNECT TO A GAME", 10, MUTED, True).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 10))
        for col, caption in enumerate(("SERVER IP", "PORT", "NICKNAME")):
            self._label(join_content, caption, 9, MUTED, True).grid(
                row=1, column=col, sticky="w", padx=(0, 10))
        self._entry(join_content, self.host_var, 18).grid(row=2, column=0, sticky="ew", padx=(0, 10), ipady=10)
        self._entry(join_content, self.port_var, 7).grid(row=2, column=1, sticky="ew", padx=(0, 10), ipady=10)
        self._entry(join_content, self.name_var, 13).grid(row=2, column=2, sticky="ew", padx=(0, 10), ipady=10)
        self.connect_btn = self._button(join_content, "Connect  →", self._connect)
        self.connect_btn.grid(row=2, column=3, padx=(2, 7), sticky="ew")
        self.disconnect_btn = self._button(join_content, "Leave", self._disconnect, False)
        self.disconnect_btn.grid(row=2, column=4, sticky="ew")
        join_content.grid_columnconfigure(0, weight=3)
        join_content.grid_columnconfigure(2, weight=2)

        quiz = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        quiz.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        quiz_content = tk.Frame(quiz, bg=CARD)
        quiz_content.pack(fill="both", expand=True, padx=26, pady=24)
        quiz_top = tk.Frame(quiz_content, bg=CARD)
        quiz_top.pack(fill="x")
        self.round_label = self._label(quiz_top, "WAITING ROOM", 10, GREEN, True)
        self.round_label.pack(side="left")
        self.timer_label = self._label(quiz_top, "⏱  --:--", 12, GOLD, True)
        self.timer_label.pack(side="right")
        tk.Frame(quiz_content, bg=BORDER, height=1).pack(fill="x", pady=(18, 24))
        self.prompt_label = self._label(quiz_content, "Ready to play?", 22, TEXT, True,
                                        justify="left", wraplength=660, anchor="w")
        self.prompt_label.pack(fill="x", anchor="w", pady=(0, 12))
        self.subtext_label = self._label(quiz_content,
                                         "Enter your nickname, connect to the server, and wait for the host to start.",
                                         11, MUTED, False, wraplength=650, justify="left", anchor="w")
        self.subtext_label.pack(fill="x", pady=(0, 24))
        self.options_frame = tk.Frame(quiz_content, bg=CARD)
        self.options_frame.pack(fill="both", expand=True)
        self.option_buttons: list[tk.Button] = []
        for idx in range(4):
            btn = tk.Button(self.options_frame, text="", command=lambda i=idx: self._answer(i),
                            bg=CARD_2, fg=TEXT, activebackground=PURPLE,
                            activeforeground=TEXT, font=(FONT, 11, "bold"),
                            bd=0, relief="flat", cursor="hand2", anchor="w",
                            justify="left", padx=18, pady=15, wraplength=600,
                            highlightthickness=1, highlightbackground=BORDER)
            btn.pack(fill="x", pady=(0, 10))
            self.option_buttons.append(btn)
        self.feedback_label = self._label(quiz_content, "", 11, MUTED, False,
                                           wraplength=650, justify="left", anchor="w")
        self.feedback_label.pack(fill="x", pady=(4, 0))
        self._set_options([])

        sidebar = tk.Frame(body, bg=BG)
        sidebar.grid(row=0, column=1, rowspan=2, sticky="nsew")
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)
        scores = tk.Frame(sidebar, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        scores.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        score_head = tk.Frame(scores, bg=CARD)
        score_head.pack(fill="x", padx=18, pady=(18, 10))
        self._label(score_head, "LEADERBOARD", 11, TEXT, True).pack(side="left")
        self.player_count_label = self._label(score_head, "0 PLAYERS", 9, MUTED, True)
        self.player_count_label.pack(side="right")
        self.scores_body = tk.Frame(scores, bg=CARD)
        self.scores_body.pack(fill="x", padx=18, pady=(0, 18))
        self._render_scores()

        chat_card = tk.Frame(sidebar, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        chat_card.grid(row=1, column=0, sticky="nsew")
        chat_card.grid_rowconfigure(1, weight=1)
        chat_card.grid_columnconfigure(0, weight=1)
        self._label(chat_card, "LIVE CHAT", 11, TEXT, True).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 12))
        self.chat_log = tk.Text(chat_card, width=26, height=12, bg=CARD, fg=TEXT, font=(FONT, 10), bd=0,
                                relief="flat", wrap="word", state="disabled", cursor="arrow",
                                highlightthickness=0, spacing3=9)
        self.chat_log.grid(row=1, column=0, sticky="nsew", padx=18)
        self.chat_log.tag_configure("name", foreground=GREEN, font=(FONT, 10, "bold"))
        self.chat_log.tag_configure("time", foreground=MUTED, font=(FONT, 9))
        self.chat_log.tag_configure("system", foreground=GOLD)
        chat_input = tk.Frame(chat_card, bg=CARD)
        chat_input.grid(row=2, column=0, sticky="ew", padx=18, pady=16)
        chat_input.grid_columnconfigure(0, weight=1)
        self.chat_entry = self._entry(chat_input, self.chat_var, 14)
        self.chat_entry.grid(row=0, column=0, sticky="ew", ipady=10, padx=(0, 8))
        self.chat_entry.bind("<Return>", lambda _event: self._send_chat())
        self._button(chat_input, "Send", self._send_chat).grid(row=0, column=1)
        self._append_system("Welcome! Connect to join the conversation.")

    def _set_options(self, options: list[str]) -> None:
        for index, button in enumerate(self.option_buttons):
            if index < len(options):
                button.configure(text=f"  {chr(65 + index)}     {options[index]}",
                                 state="normal" if self.connected and self.phase == "question" and
                                 self.selected is None else "disabled")
                button.pack_configure(pady=(0, 10))
                button.configure(bg=CARD_2, disabledforeground=TEXT)
                button.pack(fill="x", pady=(0, 10))
            else:
                button.configure(text="", state="disabled")
                button.pack_forget()

    def _render_scores(self) -> None:
        for child in self.scores_body.winfo_children():
            child.destroy()
        self.player_count_label.configure(text=f"{len(self.players)} PLAYERS")
        if not self.players:
            self._label(self.scores_body, "No players connected yet", 10, MUTED).pack(anchor="w", pady=8)
            return
        for index, player in enumerate(self.players[:12]):
            row = tk.Frame(self.scores_body, bg=CARD_2 if player["id"] == self.player_id else CARD)
            row.pack(fill="x", pady=3)
            medal = ("🥇", "🥈", "🥉")[index] if index < 3 else f"{index + 1:02}"
            self._label(row, medal, 10, GOLD).pack(side="left", padx=(9, 8), pady=8)
            name = player["name"] + (" (you)" if player["id"] == self.player_id else "")
            self._label(row, name[:22], 10, TEXT, True).pack(side="left")
            self._label(row, str(player["score"]), 11, GREEN, True).pack(side="right", padx=12)

    def _append_system(self, text: str) -> None:
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", text + "\n", "system")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def _append_chat(self, event: dict[str, Any]) -> None:
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"{event.get('time', '')}  ", "time")
        self.chat_log.insert("end", f"{event.get('name', 'Player')}: ", "name")
        self.chat_log.insert("end", f"{event.get('text', '')}\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def _connect(self) -> None:
        name = self.name_var.get().strip()
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Invalid port", "Enter a valid TCP port number.")
            return
        if not host or not (1 <= port <= 65535):
            messagebox.showerror("Invalid address", "Enter a server address and port (1–65535).")
            return
        if not 2 <= len(name) <= 20:
            messagebox.showerror("Invalid nickname", "Nickname must be 2–20 characters.")
            return
        self.connected = False
        self.player_id = None
        self.connect_btn.configure(state="disabled")
        self.connection_label.configure(text="●  CONNECTING...", fg=GOLD)
        self.network.connect(host, port, name)

    def _disconnect(self) -> None:
        self.network.disconnect()
        self.connected = False
        self.player_id = None
        self.phase = "lobby"
        self.question_index = -1
        self.question = None
        self.players = []
        self.selected = None
        self.deadline = None
        self._set_options([])
        self._render_scores()
        self.connection_label.configure(text="●  OFFLINE", fg=MUTED)
        self.connect_btn.configure(state="normal")
        self.prompt_label.configure(text="Ready to play?")
        self.subtext_label.configure(text="Connect to the server to join a game.")
        self.feedback_label.configure(text="")

    def _answer(self, choice: int) -> None:
        if not self.connected or self.phase != "question" or self.selected is not None:
            return
        self.selected = choice
        self.network.send({"type": "answer", "choice": choice})
        self.feedback_label.configure(text="Answer submitted. Waiting for the round to finish...", fg=GOLD)
        for index, button in enumerate(self.option_buttons):
            button.configure(state="disabled", bg=PURPLE if index == choice else CARD_2)

    def _send_chat(self) -> None:
        text = self.chat_var.get().strip()
        if not text:
            return
        if not self.connected:
            self._append_system("Connect before sending messages.")
            return
        self.network.send({"type": "chat", "text": text[:300]})
        self.chat_var.set("")

    def _poll(self) -> None:
        for _ in range(80):
            try:
                generation, event = self.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.network._generation:
                continue
            kind = event.get("type")
            if kind == "welcome":
                self.connected = True
                self.player_id = event["player_id"]
                self.connection_label.configure(text="●  CONNECTED", fg=GREEN)
                self.connect_btn.configure(state="normal")
                self._append_system(f"Connected as {event.get('name', 'Player')}.")
                for chat in event.get("chat_history", []):
                    self._append_chat(chat)
            elif kind == "state":
                self._handle_state(event)
            elif kind == "chat":
                self._append_chat(event)
            elif kind == "error":
                self._append_system(f"Notice: {event.get('message', 'Unknown error')}")
            elif kind == "connection_error":
                self._append_system(f"Connection error: {event.get('message', '')}")
                self._disconnect()
            elif kind == "connection_lost":
                self._append_system("Disconnected from server.")
                self._disconnect()
        self.root.after(80, self._poll)

    def _handle_state(self, event: dict[str, Any]) -> None:
        phase = event.get("phase", "lobby")
        index = event.get("question_index", -1)
        changed = phase != self.phase or index != self.question_index
        self.phase = phase
        self.question_index = index
        self.question_count = event.get("question_count", 0)
        self.players = event.get("players", [])
        self.answered_count = event.get("answered_count", 0)
        self.deadline = event.get("deadline")
        self.result = event.get("result")
        self.question = event.get("question")
        self._render_scores()
        if not changed:
            return
        if phase == "lobby":
            self.selected = None
            self.round_label.configure(text="WAITING ROOM")
            self.prompt_label.configure(text="The arena is ready.")
            self.subtext_label.configure(text="Waiting for the host to type 'start' in the server terminal.")
            self.feedback_label.configure(text="Chat with other players while you wait.", fg=MUTED)
            self._set_options([])
        elif phase == "question" and self.question:
            self.selected = None
            self.round_label.configure(text=f"QUESTION {index + 1:02} / {self.question_count:02}")
            self.prompt_label.configure(text=self.question["prompt"])
            self.subtext_label.configure(text="Choose one answer. Correct answers earn 10 points.")
            self.feedback_label.configure(text="", fg=MUTED)
            self._set_options(self.question["options"])
        elif phase == "results":
            self.round_label.configure(text=f"ROUND {index + 1:02} RESULTS")
            self.prompt_label.configure(text="Answer revealed!")
            correct = self.result.get("correct_index") if self.result else None
            self.subtext_label.configure(text=f"Correct answer: {chr(65 + correct)}" if correct is not None else "")
            explanation = self.result.get("explanation", "") if self.result else ""
            self.feedback_label.configure(text=explanation or "Next question coming up...", fg=GREEN)
            for i, btn in enumerate(self.option_buttons):
                btn.configure(state="disabled", bg=GREEN if i == correct else
                              (RED if i == self.selected else CARD_2),
                              disabledforeground=BG if i == correct else TEXT)
        elif phase == "finished":
            self.round_label.configure(text="FINAL RESULTS")
            champion = self.players[0]["name"] if self.players else "Nobody"
            self.prompt_label.configure(text="🏆  Game complete!")
            self.subtext_label.configure(text=f"Champion: {champion}. The host can type 'reset' to play again.")
            self.feedback_label.configure(text="Thanks for playing QuizVerse!", fg=GREEN)
            self._set_options([])

    def _update_clock(self) -> None:
        if self.phase == "question" and self.deadline:
            remaining = max(0, int(self.deadline - time.time() + 0.999))
            self.timer_label.configure(text=f"⏱  00:{remaining:02}" if remaining < 60
                                       else f"⏱  {remaining // 60:02}:{remaining % 60:02}",
                                       fg=RED if remaining <= 5 else GOLD)
        else:
            self.timer_label.configure(text="⏱  --:--", fg=GOLD)
        self.root.after(200, self._update_clock)

    def _on_close(self) -> None:
        self.network.disconnect()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="QuizVerse desktop quiz client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    root = tk.Tk()
    QuizClientApp(root, args.host, args.port)
    root.mainloop()


if __name__ == "__main__":
    main()
