"""Unit tests for each node's state update."""

import unittest

from app.nodes import planner_node, researcher_node, reviewer_node, writer_node


class NodeTests(unittest.TestCase):
    def test_planner_returns_a_four_step_plan(self) -> None:
        update = planner_node({"topic": "测试主题"})

        self.assertEqual(list(update), ["plan"])
        self.assertEqual(len(update["plan"]), 4)

    def test_researcher_creates_one_note_per_plan_item(self) -> None:
        update = researcher_node({"plan": ["任务一", "任务二"]})

        self.assertEqual(list(update), ["research_content"])
        self.assertIn("1. 任务一", update["research_content"])
        self.assertIn("2. 任务二", update["research_content"])

    def test_writer_uses_topic_and_research_content(self) -> None:
        update = writer_node(
            {
                "topic": "测试主题",
                "research_content": "测试资料",
            }
        )

        self.assertEqual(list(update), ["draft"])
        self.assertIn("测试主题", update["draft"])
        self.assertIn("测试资料", update["draft"])

    def test_reviewer_accepts_a_complete_draft(self) -> None:
        update = reviewer_node(
            {"draft": "# 测试主题\n\n正文\n\n## 初步结论\n\n结论内容"}
        )

        self.assertEqual(update["review_score"], 85)
        self.assertEqual(update["review_comment"], "报告结构基本完整。")


if __name__ == "__main__":
    unittest.main()
