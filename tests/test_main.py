"""Tests for checkpoint commands exposed by the CLI."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langgraph.types import Command

from app.main import (
    finish_or_report_interrupt,
    parse_arguments,
    resume_research,
    show_status,
    split_plan,
)


class MainTests(unittest.TestCase):
    def test_run_command_accepts_a_topic_and_thread_id(self) -> None:
        arguments = parse_arguments(
            ["run", "测试主题", "--thread-id", "test-thread"]
        )

        self.assertEqual(arguments.command, "run")
        self.assertEqual(arguments.topic, "测试主题")
        self.assertEqual(arguments.thread_id, "test-thread")

    def test_resume_command_builds_an_approval_command(self) -> None:
        graph = Mock()
        graph.get_state.return_value = SimpleNamespace(
            values={"topic": "测试主题"},
            next=("plan_approval",),
        )
        graph.invoke.return_value = {"draft": "测试报告"}

        with patch("app.main.finish_or_report_interrupt") as finish:
            resume_research(
                graph,
                "test-thread",
                approve=True,
                revised_plan=None,
            )

        invocation = graph.invoke.call_args
        self.assertIsInstance(invocation.args[0], Command)
        self.assertEqual(invocation.args[0].resume, {"action": "approve"})
        self.assertEqual(
            invocation.kwargs["config"],
            {"configurable": {"thread_id": "test-thread"}},
        )
        finish.assert_called_once_with(
            {"draft": "测试报告"},
            "test-thread",
        )

    def test_resume_command_can_replace_the_plan(self) -> None:
        graph = Mock()
        graph.get_state.return_value = SimpleNamespace(
            values={"topic": "测试主题"},
            next=("plan_approval",),
        )
        graph.invoke.return_value = {"draft": "测试报告"}

        with patch("app.main.finish_or_report_interrupt"):
            resume_research(
                graph,
                "test-thread",
                approve=False,
                revised_plan="任务一；任务二",
            )

        command = graph.invoke.call_args.args[0]
        self.assertEqual(
            command.resume,
            {"action": "edit", "plan": ["任务一", "任务二"]},
        )

    def test_resume_command_retries_a_non_interrupt_node(self) -> None:
        graph = Mock()
        graph.get_state.return_value = SimpleNamespace(
            values={"topic": "测试主题"},
            next=("researcher",),
        )
        graph.invoke.return_value = {"draft": "测试报告"}

        with patch("app.main.finish_or_report_interrupt"):
            resume_research(
                graph,
                "test-thread",
                approve=False,
                revised_plan=None,
            )

        self.assertIsNone(graph.invoke.call_args.args[0])

    def test_status_does_not_invoke_the_graph(self) -> None:
        graph = Mock()
        graph.get_state.return_value = SimpleNamespace(
            values={"topic": "测试主题"},
            next=("plan_approval",),
        )
        console_output = StringIO()

        with redirect_stdout(console_output):
            show_status(graph, "test-thread")

        graph.invoke.assert_not_called()
        self.assertIn("等待人工审批", console_output.getvalue())
        self.assertIn("plan_approval", console_output.getvalue())

    @patch("app.main.save_result", return_value=Path("outputs/result.md"))
    def test_completed_result_is_saved_without_printing_report(
        self,
        _save_result,
    ) -> None:
        result = {"draft": "不应出现在控制台的报告正文"}
        console_output = StringIO()

        with redirect_stdout(console_output):
            finish_or_report_interrupt(result, "test-thread")

        output = console_output.getvalue()
        self.assertIn("执行完成", output)
        self.assertIn("outputs/result.md", output)
        self.assertNotIn("不应出现在控制台的报告正文", output)

    def test_split_plan_supports_both_kinds_of_semicolons(self) -> None:
        self.assertEqual(
            split_plan("任务一；任务二; 任务三"),
            ["任务一", "任务二", "任务三"],
        )


if __name__ == "__main__":
    unittest.main()
