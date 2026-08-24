"""Tests for writing the final result to disk."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.output import build_result_document, save_result


class OutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = {
            "topic": "测试主题",
            "plan": ["研究背景", "总结趋势"],
            "plan_approved": True,
            "research_score": 82,
            "research_comment": "研究资料已足够。",
            "research_iteration": 2,
            "draft": "# 测试报告\n\n这是报告正文。",
            "sources": [
                "https://example.com/one",
                "https://example.com/two",
            ],
            "review_score": 86,
            "review_comment": "报告符合要求。",
            "revision_count": 1,
        }

    def test_build_result_document_contains_report_and_metadata(self) -> None:
        document = build_result_document(self.result)

        self.assertIn("# 测试报告", document)
        self.assertIn("审核分数：86", document)
        self.assertIn("审核意见：报告符合要求。", document)
        self.assertIn("1. 研究背景", document)
        self.assertIn("研究评分：82", document)
        self.assertIn("研究轮数：2", document)
        self.assertIn("https://example.com/one", document)

    def test_save_result_creates_a_markdown_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            output_path = save_result(self.result, output_directory)

            self.assertEqual(output_path.parent, output_directory)
            self.assertEqual(output_path.suffix, ".md")
            self.assertTrue(output_path.exists())
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                build_result_document(self.result),
            )


if __name__ == "__main__":
    unittest.main()
