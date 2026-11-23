"""Run from repository root: python -m unittest discover -s tests -v"""
import json
from pathlib import Path
import tempfile
import unittest

from quiz_core import Question, QuizEngine, QuizError, load_questions


class QuestionTests(unittest.TestCase):
    def test_questions_load_and_do_not_leak_answers(self):
        path = Path(__file__).resolve().parents[1] / "questions.json"
        questions = load_questions(path)
        self.assertGreaterEqual(len(questions), 15)
        self.assertEqual(len(questions[0].public()["options"]), 4)
        self.assertNotIn("correct_index", questions[0].public())

    def test_rejects_invalid_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps([{"prompt": "Test", "options": ["a", "b"],
                                         "correct_index": 0}]), encoding="utf-8")
            with self.assertRaises(QuizError):
                load_questions(path)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = QuizEngine([
            Question("Q1", ("A", "B", "C", "D"), 1, "Because B"),
            Question("Q2", ("A", "B", "C", "D"), 3, "Because D"),
            Question("Q3", ("A", "B", "C", "D"), 0, "Because A"),
        ])
        self.engine.join("p1", "Alice")
        self.engine.join("p2", "Bob")

    def test_score_and_full_three_question_game(self):
        self.engine.start()
        self.assertEqual(self.engine.phase, "question")
        self.engine.submit("p1", 1)
        self.engine.submit("p2", 0)
        self.assertTrue(self.engine.everyone_answered())
        self.engine.close_question()
        self.assertEqual(self.engine.leaderboard()[0]["score"], 10)
        self.assertEqual(self.engine.advance(), "question")
        self.engine.submit("p1", 3)
        self.engine.submit("p2", 3)
        self.engine.close_question()
        self.assertEqual(self.engine.advance(), "question")
        self.engine.submit("p1", 2)
        self.engine.submit("p2", 0)
        self.engine.close_question()
        self.assertEqual(self.engine.advance(), "finished")
        self.assertEqual(self.engine.players["p1"]["score"], 20)
        self.assertEqual(self.engine.players["p2"]["score"], 20)

    def test_duplicate_answer_is_rejected(self):
        self.engine.start()
        self.engine.submit("p1", 0)
        with self.assertRaisesRegex(QuizError, "already answered"):
            self.engine.submit("p1", 1)

    def test_duplicate_nickname_is_rejected(self):
        with self.assertRaisesRegex(QuizError, "already in use"):
            self.engine.join("p3", "ALICE")

    def test_reset_clears_scores(self):
        self.engine.start()
        self.engine.submit("p1", 1)
        self.engine.close_question()
        self.engine.reset()
        self.assertEqual(self.engine.phase, "lobby")
        self.assertEqual(self.engine.players["p1"]["score"], 0)

    def test_answer_validation(self):
        self.engine.start()
        for invalid in (-1, 4, "2", True):
            with self.subTest(invalid=invalid), self.assertRaises(QuizError):
                self.engine.submit("p1", invalid)

    def test_reload_requires_inactive_game(self):
        self.engine.start()
        with self.assertRaises(QuizError):
            self.engine.replace_questions([Question("New", ("A", "B", "C", "D"), 0)])
        self.engine.stop()
        self.engine.replace_questions([Question("New", ("A", "B", "C", "D"), 0)])
        self.assertEqual(self.engine.phase, "lobby")


if __name__ == "__main__":
    unittest.main()
