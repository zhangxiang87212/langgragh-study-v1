"""Tests for the complete graph and its conditional route."""

import unittest
from uuid import uuid4
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph import (
    MAX_RESEARCH_ITERATIONS,
    MAX_REVISIONS,
    RESEARCH_PASS_SCORE,
    build_graph,
    dispatch_research_workers,
    graph,
    research_router,
    review_router,
)
from app.runtime import create_initial_state, create_run_config
from tests.fakes import FakeResearchLLM, ParallelTrackingResearchLLM


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_llm = FakeResearchLLM()
        self.llm_patcher = patch("app.nodes.llm", self.fake_llm)
        self.llm_patcher.start()
        self.config = create_run_config(str(uuid4()))

    def tearDown(self) -> None:
        self.llm_patcher.stop()

    def invoke_with_approval(self, target_graph, topic: str, config):
        """Run until the plan interrupt, approve it, and finish the graph."""

        paused_result = target_graph.invoke(create_initial_state(topic), config=config)
        self.assertIn("__interrupt__", paused_result)
        self.assertEqual(target_graph.get_state(config).next, ("plan_approval",))

        return target_graph.invoke(
            Command(resume={"action": "approve"}),
            config=config,
        )

    def test_review_router_ends_after_a_passing_score(self) -> None:
        next_step = review_router(
            {
                "review_score": 80,
                "revision_count": 0,
            }
        )

        self.assertEqual(next_step, "pass")

    def test_research_router_writes_when_evidence_is_sufficient(self) -> None:
        next_step = research_router(
            {
                "research_score": RESEARCH_PASS_SCORE,
                "research_iteration": 1,
            }
        )

        self.assertEqual(next_step, "sufficient")

    def test_research_router_retries_when_evidence_is_insufficient(self) -> None:
        next_step = research_router(
            {
                "research_score": RESEARCH_PASS_SCORE - 1,
                "research_iteration": MAX_RESEARCH_ITERATIONS - 1,
            }
        )

        self.assertEqual(next_step, "retry")

    def test_research_router_stops_at_the_iteration_limit(self) -> None:
        next_step = research_router(
            {
                "research_score": RESEARCH_PASS_SCORE - 1,
                "research_iteration": MAX_RESEARCH_ITERATIONS,
            }
        )

        self.assertEqual(next_step, "sufficient")

    def test_review_router_rewrites_after_a_failing_score(self) -> None:
        next_step = review_router(
            {
                "review_score": 79,
                "revision_count": MAX_REVISIONS - 1,
            }
        )

        self.assertEqual(next_step, "rewrite")

    def test_review_router_stops_at_the_revision_limit(self) -> None:
        next_step = review_router(
            {
                "review_score": 79,
                "revision_count": MAX_REVISIONS,
            }
        )

        self.assertEqual(next_step, "pass")

    def test_graph_stops_when_reviewer_always_fails(self) -> None:
        def always_fail_reviewer(_state):
            return {
                "review_score": 60,
                "review_comment": "测试中固定返回不通过。",
            }

        failing_graph = build_graph(
            reviewer=always_fail_reviewer,
            checkpointer=InMemorySaver(),
        )
        result = self.invoke_with_approval(
            failing_graph,
            "测试循环退出",
            self.config,
        )

        self.assertEqual(result["review_score"], 60)
        self.assertEqual(result["revision_count"], MAX_REVISIONS)

    def test_graph_fills_the_whole_state(self) -> None:
        result = self.invoke_with_approval(graph, "测试主题", self.config)

        expected_keys = {
            "topic",
            "run_id",
            "plan",
            "plan_approved",
            "research_content",
            "sources",
            "research_score",
            "research_comment",
            "research_iteration",
            "research_results",
            "draft",
            "review_score",
            "review_comment",
            "revision_count",
            "usage_events",
            "max_llm_calls",
            "max_search_rounds",
            "max_total_tokens",
            "max_cost_usd",
            "input_cost_per_million",
            "output_cost_per_million",
            "node_timeout_seconds",
            "budget_exhausted",
            "termination_reason",
        }
        self.assertEqual(set(result), expected_keys)
        self.assertEqual(result["topic"], "测试主题")
        self.assertEqual(result["review_score"], 85)
        self.assertEqual(result["research_score"], 85)
        self.assertEqual(result["research_iteration"], 1)
        self.assertEqual(len(result["research_results"]), 4)
        self.assertEqual(result["revision_count"], 0)
        self.assertEqual(result["sources"], ["https://example.com/research"])
        self.assertEqual(len(result["usage_events"]), 8)

    def test_graph_pauses_before_research(self) -> None:
        paused_result = graph.invoke(
            create_initial_state("等待确认"),
            config=self.config,
        )

        self.assertIn("__interrupt__", paused_result)
        self.assertNotIn("research_content", paused_result)
        self.assertFalse(paused_result["plan_approved"])
        self.assertEqual(graph.get_state(self.config).next, ("plan_approval",))

    def test_research_uses_the_plan_edited_by_a_human(self) -> None:
        graph.invoke(create_initial_state("人工修改计划"), config=self.config)

        result = graph.invoke(
            Command(
                resume={
                    "action": "edit",
                    "plan": ["只研究人工指定的问题"],
                }
            ),
            config=self.config,
        )

        self.assertEqual(result["plan"], ["只研究人工指定的问题"])
        self.assertIn("只研究人工指定的问题", result["research_content"])
        self.assertTrue(result["plan_approved"])

    def test_insufficient_research_is_repeated_with_feedback(self) -> None:
        self.fake_llm.research_scores = [60, 85]

        result = self.invoke_with_approval(
            graph,
            "补充研究测试",
            self.config,
        )

        self.assertEqual(self.fake_llm.research_calls, 8)
        self.assertEqual(result["research_iteration"], 2)
        self.assertEqual(result["research_score"], 85)
        self.assertIn("第 2 轮补充研究", result["research_content"])
        self.assertEqual(
            self.fake_llm.last_research_feedback,
            "请补充更多可验证证据。",
        )

    def test_insufficient_research_stops_at_the_iteration_limit(self) -> None:
        self.fake_llm.research_scores = [60]

        result = self.invoke_with_approval(
            graph,
            "研究轮数上限测试",
            self.config,
        )

        self.assertEqual(
            self.fake_llm.research_calls,
            4 * MAX_RESEARCH_ITERATIONS,
        )
        self.assertEqual(result["research_iteration"], MAX_RESEARCH_ITERATIONS)
        self.assertEqual(result["research_score"], 60)
        self.assertIn("draft", result)

    def test_graph_saves_final_state_and_history(self) -> None:
        self.invoke_with_approval(graph, "Checkpoint 测试", self.config)

        snapshot = graph.get_state(self.config)
        history = list(graph.get_state_history(self.config))

        self.assertEqual(snapshot.values["topic"], "Checkpoint 测试")
        self.assertEqual(snapshot.next, ())
        self.assertGreaterEqual(len(history), 8)

    def test_threads_keep_independent_state(self) -> None:
        first_config = create_run_config(str(uuid4()))
        second_config = create_run_config(str(uuid4()))

        self.invoke_with_approval(graph, "主题一", first_config)
        self.invoke_with_approval(graph, "主题二", second_config)

        self.assertEqual(graph.get_state(first_config).values["topic"], "主题一")
        self.assertEqual(graph.get_state(second_config).values["topic"], "主题二")

    def test_reusing_thread_resets_revision_state(self) -> None:
        first_result = self.invoke_with_approval(graph, "第一份报告", self.config)
        second_result = self.invoke_with_approval(graph, "第二份报告", self.config)

        self.assertEqual(first_result["revision_count"], 0)
        self.assertEqual(second_result["revision_count"], 0)
        self.assertNotEqual(first_result["run_id"], second_result["run_id"])
        self.assertNotIn("第一份报告", second_result["research_content"])
        self.assertTrue(second_result["plan_approved"])
        self.assertEqual(second_result["review_comment"], "测试审核意见。")

    def test_dispatch_creates_one_worker_for_each_plan_task(self) -> None:
        sends = dispatch_research_workers(
            {
                "run_id": "run-001",
                "topic": "测试主题",
                "plan": ["任务一", "任务二", "任务三"],
                "research_iteration": 2,
                "research_content": "第一轮资料",
                "research_comment": "请补充数据。",
            }
        )

        self.assertEqual(len(sends), 3)
        self.assertTrue(all(send.node == "research_worker" for send in sends))
        self.assertEqual(sends[0].arg["task"], "任务一")
        self.assertEqual(sends[1].arg["task_index"], 1)
        self.assertEqual(sends[2].arg["research_iteration"], 2)
        self.assertEqual(sends[0].arg["existing_research"], "第一轮资料")
        self.assertEqual(sends[0].arg["evaluation_comment"], "请补充数据。")

    def test_research_workers_really_run_in_parallel(self) -> None:
        parallel_llm = ParallelTrackingResearchLLM()
        parallel_graph = build_graph(checkpointer=InMemorySaver())
        config = create_run_config(str(uuid4()))

        with patch("app.nodes.llm", parallel_llm):
            self.invoke_with_approval(
                parallel_graph,
                "并行执行测试",
                config,
            )

        self.assertEqual(parallel_llm.research_calls, 4)
        self.assertGreaterEqual(parallel_llm.max_active_research_calls, 2)


if __name__ == "__main__":
    unittest.main()
