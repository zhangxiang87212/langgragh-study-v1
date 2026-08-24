"""Unit tests for each node's state update."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from app.nodes import (
    plan_approval_node,
    planner_node,
    research_evaluator_node,
    researcher_node,
    reviewer_node,
    writer_node,
)
from tests.fakes import FakeResearchLLM


class NodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_llm = FakeResearchLLM()
        self.llm_patcher = patch("app.nodes.llm", self.fake_llm)
        self.llm_patcher.start()

    def tearDown(self) -> None:
        self.llm_patcher.stop()

    def test_planner_returns_a_four_step_plan(self) -> None:
        update = planner_node({"topic": "测试主题"})

        self.assertEqual(list(update), ["plan"])
        self.assertEqual(len(update["plan"]), 4)

    def test_researcher_returns_content_and_sources(self) -> None:
        update = researcher_node(
            {
                "topic": "测试主题",
                "plan": ["任务一", "任务二"],
            }
        )

        self.assertEqual(
            list(update),
            ["research_content", "sources", "research_iteration"],
        )
        self.assertIn("任务一、任务二", update["research_content"])
        self.assertEqual(update["sources"], ["https://example.com/research"])
        self.assertEqual(update["research_iteration"], 1)

    def test_researcher_uses_evaluator_feedback_on_the_next_iteration(self) -> None:
        update = researcher_node(
            {
                "topic": "测试主题",
                "plan": ["任务一"],
                "research_content": "第一轮资料",
                "sources": ["https://example.com/research"],
                "research_score": 60,
                "research_comment": "需要补充官方数据。",
                "research_iteration": 1,
            }
        )

        self.assertEqual(update["research_iteration"], 2)
        self.assertIn("第 2 轮补充研究", update["research_content"])
        self.assertEqual(
            self.fake_llm.last_research_feedback,
            "需要补充官方数据。",
        )

    def test_research_evaluator_returns_score_and_comment(self) -> None:
        update = research_evaluator_node(
            {
                "topic": "测试主题",
                "plan": ["任务一"],
                "research_content": "测试资料",
                "sources": ["https://example.com/research"],
            }
        )

        self.assertEqual(update["research_score"], 85)
        self.assertEqual(update["research_comment"], "研究资料已足够。")

    @patch("app.nodes.interrupt", return_value={"action": "approve"})
    def test_human_can_approve_the_generated_plan(self, _interrupt) -> None:
        update = plan_approval_node({"plan": ["任务一", "任务二"]})

        self.assertEqual(update, {"plan_approved": True})

    @patch(
        "app.nodes.interrupt",
        return_value={"action": "edit", "plan": ["修改后的任务"]},
    )
    def test_human_can_replace_the_generated_plan(self, _interrupt) -> None:
        update = plan_approval_node({"plan": ["原任务"]})

        self.assertEqual(update["plan"], ["修改后的任务"])
        self.assertTrue(update["plan_approved"])

    def test_writer_uses_topic_and_research_content(self) -> None:
        update = writer_node(
            {
                "topic": "测试主题",
                "research_content": "测试资料",
                "sources": ["https://example.com/research"],
            }
        )

        self.assertEqual(list(update), ["draft", "revision_count"])
        self.assertIn("测试主题", update["draft"])
        self.assertIn("测试资料", update["draft"])
        self.assertEqual(update["revision_count"], 0)

    def test_writer_increments_revision_count_when_rewriting(self) -> None:
        update = writer_node(
            {
                "topic": "测试主题",
                "research_content": "测试资料",
                "sources": ["https://example.com/research"],
                "review_comment": "内容需要补充。",
                "revision_count": 1,
            }
        )

        self.assertEqual(update["revision_count"], 2)
        self.assertEqual(self.fake_llm.last_review_comment, "内容需要补充。")
        self.assertEqual(
            self.fake_llm.last_sources,
            ["https://example.com/research"],
        )

    def test_reviewer_returns_the_llm_review(self) -> None:
        update = reviewer_node({"draft": "测试报告"})

        self.assertEqual(update["review_score"], 85)
        self.assertEqual(update["review_comment"], "测试审核意见。")

    def test_reviewer_can_return_a_failing_score(self) -> None:
        self.fake_llm.review_score = 60
        self.fake_llm.review_comment = "内容深度不足。"

        update = reviewer_node({"draft": "测试报告"})

        self.assertEqual(update["review_score"], 60)
        self.assertEqual(update["review_comment"], "内容深度不足。")

    def test_llm_nodes_log_their_outputs(self) -> None:
        console_output = StringIO()

        with redirect_stdout(console_output):
            planner_node({"topic": "测试主题"})
            researcher_node(
                {
                    "topic": "测试主题",
                    "plan": ["测试任务"],
                }
            )
            research_evaluator_node(
                {
                    "topic": "测试主题",
                    "plan": ["测试任务"],
                    "research_content": "测试资料",
                    "sources": ["https://example.com/research"],
                }
            )
            writer_node(
                {
                    "topic": "测试主题",
                    "research_content": "测试资料",
                    "sources": ["https://example.com/research"],
                }
            )
            reviewer_node({"draft": "测试报告"})

        output = console_output.getvalue()
        self.assertIn("Planner 输出", output)
        self.assertIn("Researcher 输出", output)
        self.assertIn("Research Evaluator 输出：评分 85", output)
        self.assertIn("https://example.com/research", output)
        self.assertIn("Writer 输出", output)
        self.assertIn("Reviewer 输出：评分 85", output)
        self.assertIn("Reviewer 意见：测试审核意见。", output)


if __name__ == "__main__":
    unittest.main()
