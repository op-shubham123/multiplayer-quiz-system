"""Testable quiz rules. No sockets or GUI dependencies."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class QuizError(ValueError):
    """A recoverable game-rule or input validation error."""


@dataclass(frozen=True)
class Question:
    prompt: str
    options: tuple[str, str, str, str]
    correct_index: int
    explanation: str = ""

    def public(self) -> dict[str, Any]:
        # Do not leak the answer until the round closes.
        return {"prompt": self.prompt, "options": list(self.options)}


def load_questions(path: str | Path) -> list[Question]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise QuizError("questions.json must contain a non-empty array")
    questions: list[Question] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise QuizError(f"Question {index} must be an object")
        prompt = item.get("prompt")
        options = item.get("options")
        correct_index = item.get("correct_index")
        explanation = item.get("explanation", "")
        if not isinstance(prompt, str) or not prompt.strip():
            raise QuizError(f"Question {index}: prompt must be non-empty text")
        if (not isinstance(options, list) or len(options) != 4
                or any(not isinstance(opt, str) or not opt.strip() for opt in options)):
            raise QuizError(f"Question {index}: options must contain four non-empty strings")
        if type(correct_index) is not int or not 0 <= correct_index <= 3:
            raise QuizError(f"Question {index}: correct_index must be 0, 1, 2, or 3")
        if not isinstance(explanation, str):
            raise QuizError(f"Question {index}: explanation must be text")
        questions.append(Question(prompt.strip(), tuple(opt.strip() for opt in options),
                                  correct_index, explanation.strip()))
    return questions


class QuizEngine:
    """Mutated under the server's lock. Stores players, questions, and scoring."""

    def __init__(self, questions: list[Question], points_per_answer: int = 10):
        if not questions:
            raise QuizError("At least one question is required")
        self.questions = questions
        self.points_per_answer = points_per_answer
        self.players: dict[str, dict[str, Any]] = {}
        self.phase = "lobby"
        self.question_index = -1
        self.answers: dict[str, int] = {}
        self.last_result: dict[str, Any] | None = None

    def join(self, player_id: str, name: str) -> None:
        name = name.strip()
        if not (2 <= len(name) <= 20) or any(ord(c) < 32 for c in name):
            raise QuizError("Nickname must contain 2–20 printable characters")
        if any(p["name"].casefold() == name.casefold() for p in self.players.values()):
            raise QuizError("That nickname is already in use")
        self.players[player_id] = {"name": name, "score": 0}

    def leave(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        self.answers.pop(player_id, None)

    def leaderboard(self) -> list[dict[str, Any]]:
        return [dict(id=pid, name=p["name"], score=p["score"])
                for pid, p in sorted(self.players.items(),
                                     key=lambda entry: (-entry[1]["score"], entry[1]["name"].casefold()))]

    def start(self) -> None:
        if self.phase != "lobby":
            raise QuizError("Reset the quiz before starting a new game")
        if not self.players:
            raise QuizError("At least one player must join before starting")
        self.question_index = 0
        self.phase = "question"
        self.answers = {}
        self.last_result = None

    def submit(self, player_id: str, choice: Any) -> None:
        if self.phase != "question":
            raise QuizError("There is no active question")
        if player_id not in self.players:
            raise QuizError("Player not registered")
        if player_id in self.answers:
            raise QuizError("You already answered this question")
        if type(choice) is not int or not 0 <= choice <= 3:
            raise QuizError("Answer must be a number from 0 to 3")
        self.answers[player_id] = choice

    def everyone_answered(self) -> bool:
        return bool(self.players) and all(pid in self.answers for pid in self.players)

    def close_question(self) -> dict[str, Any]:
        if self.phase != "question":
            raise QuizError("No question to close")
        question = self.questions[self.question_index]
        for pid, choice in self.answers.items():
            if pid in self.players and choice == question.correct_index:
                self.players[pid]["score"] += self.points_per_answer
        self.last_result = {
            "question_index": self.question_index,
            "correct_index": question.correct_index,
            "explanation": question.explanation,
            "answers_received": len(self.answers),
        }
        self.phase = "results"
        return self.last_result.copy()

    def advance(self) -> str:
        if self.phase != "results":
            raise QuizError("You can advance only after a question closes")
        if self.question_index + 1 >= len(self.questions):
            self.phase = "finished"
        else:
            self.question_index += 1
            self.phase = "question"
            self.answers = {}
            self.last_result = None
        return self.phase

    def stop(self) -> None:
        if self.phase not in ("question", "results"):
            raise QuizError("No active game to stop")
        self.phase = "finished"

    def reset(self) -> None:
        self.phase = "lobby"
        self.question_index = -1
        self.answers = {}
        self.last_result = None
        for player in self.players.values():
            player["score"] = 0

    def replace_questions(self, questions: list[Question]) -> None:
        if self.phase not in ("lobby", "finished"):
            raise QuizError("Stop the game before reloading questions")
        if not questions:
            raise QuizError("At least one question is required")
        self.questions = questions
        self.reset()

    def snapshot(self, deadline: float | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": "state",
            "phase": self.phase,
            "question_index": self.question_index,
            "question_count": len(self.questions),
            "players": self.leaderboard(),
            "answered_count": len(self.answers),
            "deadline": deadline if self.phase == "question" else None,
            "question": self.questions[self.question_index].public() if self.phase == "question" else None,
            "result": self.last_result if self.phase in ("results", "finished") else None,
        }
        return data
