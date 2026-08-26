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
from app.runtime import MAX_RESEARCH_CONCURRENCY


class MainTests(unittest.TestCase):
    def test_run_command_accepts_a_topic_and_thread_id(self) -> None:
        arguments = parse_arguments(
            ["run", "测试主题", "--thread-id", "test-thread"]
        )

        self.assertEqual(arguments.command, "run")
        self.assertEqual(arguments.topic, "测试主题")
        self.assertEqual(arguments.thread_id, "test-thread")

    def test_resume_command_builds_an_approval_command(self) -> None:
        graph = self.create_paused_graph("plan_approval")

        with patch(
            "app.main.run_graph_stream",
            return_value={"draft": "测试报告"},
        ) as run_stream:
            with patch("app.main.finish_or_report_interrupt") as finish:
                resume_research(
                    graph,
                    "test-thread",
                    approve=True,
                    revised_plan=None,
                )

        invocation = run_stream.call_args
        self.assertIs(invocation.args[0], graph)
        self.assertIsInstance(invocation.args[1], Command)
        self.assertEqual(invocation.args[1].resume, {"action": "approve"})
        self.assertEqual(
            invocation.args[2],
            {
                "configurable": {"thread_id": "test-thread"},
                "max_concurrency": MAX_RESEARCH_CONCURRENCY,
            },
        )
        finish.assert_called_once_with(
            {"draft": "测试报告"},
            "test-thread",
        )

    def test_resume_command_can_replace_the_plan(self) -> None:
        graph = self.create_paused_graph("plan_approval")

        with patch(
            "app.main.run_graph_stream",
            return_value={"draft": "测试报告"},
        ) as run_stream:
            with patch("app.main.finish_or_report_interrupt"):
                resume_research(
                    graph,
                    "test-thread",
                    approve=False,
                    revised_plan="任务一；任务二",
                )

        command = run_stream.call_args.args[1]
        self.assertEqual(
            command.resume,
            {"action": "edit", "plan": ["任务一", "任务二"]},
        )

    def test_resume_command_retries_a_non_interrupt_node(self) -> None:
        graph = self.create_paused_graph("research_worker")

        with patch(
            "app.main.run_graph_stream",
            return_value={"draft": "测试报告"},
        ) as run_stream:
            with patch("app.main.finish_or_report_interrupt"):
                resume_research(
                    graph,
                    "test-thread",
                    approve=False,
                    revised_plan=None,
                )

        self.assertIsNone(run_stream.call_args.args[1])

    def test_status_does_not_run_the_graph(self) -> None:
        graph = self.create_paused_graph("plan_approval")
        console_output = StringIO()

        with redirect_stdout(console_output):
            show_status(graph, "test-thread")

        graph.invoke.assert_not_called()
        graph.stream.assert_not_called()
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

    @staticmethod
    def create_paused_graph(next_node: str) -> Mock:
        graph = Mock()
        graph.get_state.return_value = SimpleNamespace(
            values={"topic": "测试主题"},
            next=(next_node,),
        )
        return graph


if __name__ == "__main__":
    unittest.main()
