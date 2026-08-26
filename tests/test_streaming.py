"""Tests for LangGraph state and custom streaming events."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
import re
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph import build_graph
from app.runtime import create_initial_state, create_run_config
from app.streaming import STREAM_MODES, run_graph_stream
from tests.fakes import FakeResearchLLM


class StreamingTests(unittest.TestCase):
    def test_stream_runner_collects_state_and_prints_events(self) -> None:
        graph = Mock()
        graph.stream.return_value = iter(
            [
                {
                    "type": "custom",
                    "data": {"event": "llm_stream_start", "node": "Writer"},
                },
                {
                    "type": "custom",
                    "data": {"event": "llm_token", "text": "流式正文"},
                },
                {
                    "type": "custom",
                    "data": {"event": "llm_stream_end", "node": "Writer"},
                },
                {
                    "type": "updates",
                    "data": {"writer": {"draft": "流式正文"}},
                },
            ]
        )
        graph.get_state.return_value = SimpleNamespace(
            values={"draft": "流式正文"}
        )
        console_output = StringIO()

        with redirect_stdout(console_output):
            result = run_graph_stream(graph, {"topic": "测试"}, {"config": 1})

        self.assertEqual(result, {"draft": "流式正文"})
        self.assertEqual(
            graph.stream.call_args.kwargs["stream_mode"],
            STREAM_MODES,
        )
        self.assertEqual(graph.stream.call_args.kwargs["version"], "v2")
        output = console_output.getvalue()
        self.assertIn("Writer 流式输出：", output)
        self.assertIn("流式正文", output)
        self.assertIn("节点完成：writer", output)
        self.assertRegex(
            output,
            re.compile(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]"),
        )

    def test_real_graph_streams_writer_tokens_and_finishes(self) -> None:
        fake_llm = FakeResearchLLM()
        config = create_run_config("streaming-thread")
        graph = build_graph(checkpointer=InMemorySaver())
        console_output = StringIO()

        with patch("app.nodes.llm", fake_llm):
            with redirect_stdout(console_output):
                paused_result = run_graph_stream(
                    graph,
                    create_initial_state("流式执行测试"),
                    config,
                )
                result = run_graph_stream(
                    graph,
                    Command(resume={"action": "approve"}),
                    config,
                )

        self.assertIn("__interrupt__", paused_result)
        self.assertEqual(result["review_score"], 85)
        output = console_output.getvalue()
        self.assertIn("节点完成：planner", output)
        self.assertIn("Researcher 1/4 开始", output)
        self.assertIn("Researcher 4/4 输出", output)
        self.assertIn("节点完成：research_reducer", output)
        self.assertIn("Writer 流式输出：", output)
        self.assertIn("# 流式执行测试", output)
        self.assertIn("节点完成：writer", output)


if __name__ == "__main__":
    unittest.main()
