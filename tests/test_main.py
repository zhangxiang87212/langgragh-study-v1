"""Tests for the command-line entry point."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langgraph.types import Command

from app.main import main


class MainTests(unittest.TestCase):
    @patch("app.main.save_result", return_value=Path("outputs/result.md"))
    @patch("app.main.ask_for_plan_review", return_value={"action": "approve"})
    @patch("app.main.graph.invoke")
    def test_main_does_not_repeat_report_after_graph_finishes(
        self, invoke, ask_for_plan_review, _save_result
    ) -> None:
        interrupt_value = {
            "question": "请确认研究计划。",
            "plan": ["任务一"],
        }
        invoke.side_effect = [
            {"__interrupt__": [SimpleNamespace(value=interrupt_value)]},
            {"draft": "不应出现在控制台的报告正文"},
        ]
        console_output = StringIO()

        with patch(
            "sys.argv",
            ["app.main", "测试主题", "--thread-id", "test-thread"],
        ):
            with redirect_stdout(console_output):
                main()

        output = console_output.getvalue()
        first_call = invoke.call_args_list[0]
        resume_call = invoke.call_args_list[1]
        invocation_input = first_call.args[0]
        invocation_config = first_call.kwargs["config"]
        self.assertEqual(invocation_input["revision_count"], 0)
        self.assertEqual(invocation_input["review_comment"], "")
        self.assertFalse(invocation_input["plan_approved"])
        self.assertEqual(
            invocation_config,
            {"configurable": {"thread_id": "test-thread"}},
        )
        self.assertIsInstance(resume_call.args[0], Command)
        self.assertEqual(resume_call.args[0].resume, {"action": "approve"})
        self.assertEqual(resume_call.kwargs["config"], invocation_config)
        ask_for_plan_review.assert_called_once_with(interrupt_value)
        self.assertIn("线程 ID：test-thread", output)
        self.assertIn("执行完成", output)
        self.assertIn("outputs/result.md", output)
        self.assertNotIn("不应出现在控制台的报告正文", output)


if __name__ == "__main__":
    unittest.main()
