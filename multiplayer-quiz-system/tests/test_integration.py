"""Socket-level integration tests; no GUI or third-party test packages required."""
from pathlib import Path
import socket
import time
import unittest

from network import JsonConnection
from server import QuizServer


class TestPlayer:
    def __init__(self, host: str, port: int, name: str):
        sock = socket.create_connection((host, port), timeout=2)
        sock.settimeout(3)
        self.conn = JsonConnection(sock)
        self.conn.send({"type": "join", "name": name})
        self.wait_for("welcome")

    def wait_for(self, event_type: str, timeout: float = 4):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                message = self.conn.receive()
            except socket.timeout:
                continue
            if message is None:
                raise AssertionError("Server disconnected unexpectedly")
            if message.get("type") == event_type:
                return message
        raise AssertionError(f"Did not receive event: {event_type}")

    def close(self):
        self.conn.close()


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "questions.json"
        self.server = QuizServer(host="127.0.0.1", port=0, questions_path=path,
                                 question_seconds=0.3, result_seconds=0.15,
                                 tick_seconds=0.02)
        self.server.start()
        self.players = []

    def tearDown(self):
        for player in self.players:
            player.close()
        self.server.close()

    def join(self, name):
        player = TestPlayer("127.0.0.1", self.server.port, name)
        self.players.append(player)
        return player

    def test_two_players_chat_and_answer(self):
        alice = self.join("Alice")
        bob = self.join("Bob")
        alice.conn.send({"type": "chat", "text": "Hello Bob!"})
        chat = bob.wait_for("chat")
        self.assertEqual(chat["text"], "Hello Bob!")
        self.server.start_game()
        state = alice.wait_for("state")
        while state["phase"] != "question":
            state = alice.wait_for("state")
        self.assertNotIn("correct_index", state["question"])
        alice.conn.send({"type": "answer", "choice": 1})
        bob.conn.send({"type": "answer", "choice": 0})
        alice.wait_for("answer_ack")
        result = alice.wait_for("state", timeout=4)
        while result["phase"] != "results":
            result = alice.wait_for("state")
        self.assertEqual(result["result"]["correct_index"], 1)
        self.assertEqual(next(p for p in result["players"] if p["name"] == "Alice")["score"], 10)

    def test_automatic_progression_past_two_questions(self):
        alice = self.join("Alice")
        self.server.start_game()
        seen_questions = set()
        end = time.monotonic() + 5
        while time.monotonic() < end and len(seen_questions) < 4:
            try:
                event = alice.conn.receive()
            except socket.timeout:
                continue
            if event and event.get("type") == "state" and event.get("phase") == "question":
                seen_questions.add(event["question_index"])
        self.assertGreaterEqual(len(seen_questions), 4, "Quiz must progress beyond question 2")

    def test_host_stop_reset_reload(self):
        self.join("Alice")
        self.server.start_game()
        self.server.stop_game()
        self.assertIn("finished", self.server.status())
        self.server.reset_game()
        self.assertIn("lobby", self.server.status())
        self.server.reload_questions()
        self.assertIn("lobby", self.server.status())


if __name__ == "__main__":
    unittest.main()
