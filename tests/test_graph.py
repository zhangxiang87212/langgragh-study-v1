"""Integration test for the complete first-stage graph."""

import unittest

from app.graph import graph


class GraphTests(unittest.TestCase):
    def test_graph_fills_the_whole_state(self) -> None:
        result = graph.invoke({"topic": "测试主题"})

        expected_keys = {
            "topic",
            "plan",
            "research_content",
            "draft",
            "review_score",
            "review_comment",
        }
        self.assertEqual(set(result), expected_keys)
        self.assertEqual(result["topic"], "测试主题")
        self.assertEqual(result["review_score"], 85)


if __name__ == "__main__":
    unittest.main()
