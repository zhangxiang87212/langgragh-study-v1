"""Tests for the OpenAI adapter without making network requests."""

import unittest
from types import SimpleNamespace

from app.llm import (
    MAX_WEB_SEARCH_CALLS,
    OpenAIResearchService,
    ReportReview,
    ResearchEvaluation,
    ResearchPlan,
)


class FakeResponses:
    def __init__(self) -> None:
        self.last_request = None

    def parse(self, **request):
        self.last_request = request
        output_type = request["text_format"]

        if output_type is ResearchPlan:
            parsed = ResearchPlan(tasks=["任务一", "任务二", "任务三"])
        elif output_type is ResearchEvaluation:
            parsed = ResearchEvaluation(score=76, comment="缺少近期官方数据。")
        else:
            parsed = ReportReview(score=88, comment="结构清晰。")

        return SimpleNamespace(output_parsed=parsed)

    def create(self, **request):
        self.last_request = request

        if request.get("stream"):
            return iter(
                [
                    SimpleNamespace(
                        type="response.output_text.delta",
                        delta="# 流式报告\n\n",
                    ),
                    SimpleNamespace(
                        type="response.output_text.delta",
                        delta="测试内容。",
                    ),
                    SimpleNamespace(type="response.completed"),
                ]
            )

        if request.get("tools") == [{"type": "web_search"}]:
            source_one = SimpleNamespace(url="https://example.com/one")
            source_two = SimpleNamespace(url="https://example.com/two")
            search_call_one = SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(sources=[source_one, source_two]),
            )
            search_call_two = SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(sources=[source_one]),
            )
            return SimpleNamespace(
                output_text="  测试研究摘要。  ",
                output=[search_call_one, search_call_two],
            )

        return SimpleNamespace(output_text="  # 测试报告\n\n测试内容。  ")


class OpenAIResearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.responses = FakeResponses()
        client = SimpleNamespace(responses=self.responses)
        self.service = OpenAIResearchService(
            client=client,
            model="test-model",
            search_model="test-search-model",
        )

    def test_create_plan_uses_structured_output(self) -> None:
        plan = self.service.create_plan("测试主题")

        self.assertEqual(plan, ["任务一", "任务二", "任务三"])
        self.assertEqual(self.responses.last_request["model"], "test-model")
        self.assertIs(self.responses.last_request["text_format"], ResearchPlan)

    def test_research_requires_web_search_and_collects_unique_sources(self) -> None:
        research = self.service.research(
            topic="测试主题",
            tasks=["任务一", "任务二"],
        )

        request = self.responses.last_request
        self.assertEqual(request["model"], "test-search-model")
        self.assertEqual(request["tools"], [{"type": "web_search"}])
        self.assertEqual(request["tool_choice"], "required")
        self.assertEqual(request["max_tool_calls"], MAX_WEB_SEARCH_CALLS)
        self.assertEqual(
            request["include"],
            ["web_search_call.action.sources"],
        )
        self.assertEqual(research.content, "测试研究摘要。")
        self.assertEqual(
            research.sources,
            ["https://example.com/one", "https://example.com/two"],
        )

    def test_follow_up_research_includes_existing_evidence_and_feedback(self) -> None:
        self.service.research(
            topic="测试主题",
            tasks=["任务一"],
            existing_research="第一轮资料",
            evaluation_comment="缺少官方数据",
        )

        user_prompt = self.responses.last_request["input"][1]["content"]
        self.assertIn("第一轮资料", user_prompt)
        self.assertIn("缺少官方数据", user_prompt)
        self.assertIn("避免重复已有资料", user_prompt)

    def test_evaluate_research_uses_structured_output(self) -> None:
        evaluation = self.service.evaluate_research(
            topic="测试主题",
            tasks=["任务一"],
            research_content="测试资料",
            sources=["https://example.com/research"],
        )

        request = self.responses.last_request
        self.assertEqual(evaluation.score, 76)
        self.assertEqual(evaluation.comment, "缺少近期官方数据。")
        self.assertIs(request["text_format"], ResearchEvaluation)
        self.assertIn("https://example.com/research", request["input"][1]["content"])

    def test_write_report_returns_clean_text_and_includes_feedback(self) -> None:
        draft = self.service.write_report(
            topic="测试主题",
            research_content="测试资料",
            sources=["https://example.com/research"],
            review_comment="请补充结论。",
        )

        user_prompt = self.responses.last_request["input"][1]["content"]
        self.assertEqual(draft, "# 测试报告\n\n测试内容。")
        self.assertIn("请补充结论。", user_prompt)
        self.assertIn("https://example.com/research", user_prompt)

    def test_write_report_streams_and_collects_text(self) -> None:
        tokens = []

        draft = self.service.write_report(
            topic="测试主题",
            research_content="测试资料",
            sources=["https://example.com/research"],
            on_token=tokens.append,
        )

        self.assertTrue(self.responses.last_request["stream"])
        self.assertEqual(tokens, ["# 流式报告\n\n", "测试内容。"])
        self.assertEqual(draft, "# 流式报告\n\n测试内容。")

    def test_review_report_uses_structured_output(self) -> None:
        review = self.service.review_report("测试报告")

        self.assertEqual(review.score, 88)
        self.assertEqual(review.comment, "结构清晰。")
        self.assertIs(self.responses.last_request["text_format"], ReportReview)


if __name__ == "__main__":
    unittest.main()
