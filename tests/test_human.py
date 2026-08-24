"""Tests for collecting a plan decision from the console."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from app.human import ask_for_plan_review


class HumanReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.interrupt_value = {
            "question": "请确认研究计划。",
            "plan": ["任务一", "任务二"],
        }

    @patch("builtins.input", return_value="")
    def test_empty_input_approves_the_plan(self, _input) -> None:
        with redirect_stdout(StringIO()):
            decision = ask_for_plan_review(self.interrupt_value)

        self.assertEqual(decision, {"action": "approve"})

    @patch("builtins.input", return_value="新任务一；新任务二; ")
    def test_semicolon_separated_input_replaces_the_plan(self, _input) -> None:
        with redirect_stdout(StringIO()):
            decision = ask_for_plan_review(self.interrupt_value)

        self.assertEqual(
            decision,
            {"action": "edit", "plan": ["新任务一", "新任务二"]},
        )

    @patch("builtins.input", side_effect=[";;；", "有效任务"])
    def test_empty_revised_plan_is_requested_again(self, _input) -> None:
        with redirect_stdout(StringIO()) as console_output:
            decision = ask_for_plan_review(self.interrupt_value)

        self.assertIn("不能为空", console_output.getvalue())
        self.assertEqual(decision, {"action": "edit", "plan": ["有效任务"]})


if __name__ == "__main__":
    unittest.main()
