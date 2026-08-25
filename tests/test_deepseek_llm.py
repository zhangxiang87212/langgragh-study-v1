"""Tests for the DeepSeek provider without making network requests."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.llm import (
    DeepSeekResearchService,
    OpenAIResearchService,
    create_research_service,
)


class FakeDeepSeekCompletions:
    def __init__(self) -> None:
        self.last_request = None

    def create(self, **request):
        self.last_request = request
        system_prompt = request["messages"][0]["content"]

        if "研究规划专家" in system_prompt:
            content = '{"tasks":["任务一","任务二","任务三"]}'
        elif "研究资料评估专家" in system_prompt:
            content = '{"score":82,"comment":"资料已足够。"}'
        elif "研究报告审核专家" in system_prompt:
            content = '{"score":88,"comment":"报告结构清晰。"}'
        else:
            content = "# DeepSeek 测试报告\n\n正文。"

        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeDeepSeekResponses:
    def __init__(self) -> None:
        self.last_request = None

    def create(self, **request):
        self.last_request = request
        citation = SimpleNamespace(url="https://example.com/deepseek-source")
        content_part = SimpleNamespace(annotations=[citation])
        message = SimpleNamespace(type="message", content=[content_part])
        search_call = SimpleNamespace(type="web_search_call")
        return SimpleNamespace(
            output_text="DeepSeek 网页研究资料。",
            output=[search_call, message],
        )


class DeepSeekResearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.completions = FakeDeepSeekCompletions()
        self.responses = FakeDeepSeekResponses()
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=self.completions),
            responses=self.responses,
        )
        self.service = DeepSeekResearchService(
            client=client,
            model="deepseek-test-model",
        )

    def test_create_plan_uses_json_output(self) -> None:
        plan = self.service.create_plan("测试主题")

        request = self.completions.last_request
        self.assertEqual(plan, ["任务一", "任务二", "任务三"])
        self.assertEqual(request["model"], "deepseek-test-model")
        self.assertEqual(request["response_format"], {"type": "json_object"})

    def test_evaluate_research_parses_json(self) -> None:
        evaluation = self.service.evaluate_research(
            topic="测试主题",
            tasks=["任务一"],
            research_content="测试资料",
            sources=["https://example.com/research"],
        )

        self.assertEqual(evaluation.score, 82)
        self.assertEqual(evaluation.comment, "资料已足够。")

    def test_write_report_returns_text(self) -> None:
        draft = self.service.write_report(
            topic="测试主题",
            research_content="测试资料",
            sources=["https://example.com/research"],
            review_comment="请补充结论。",
        )

        request = self.completions.last_request
        self.assertEqual(draft, "# DeepSeek 测试报告\n\n正文。")
        self.assertNotIn("response_format", request)
        self.assertIn("请补充结论。", request["messages"][1]["content"])

    def test_review_report_parses_json(self) -> None:
        review = self.service.review_report("测试报告")

        self.assertEqual(review.score, 88)
        self.assertEqual(review.comment, "报告结构清晰。")

    def test_research_uses_deepseek_responses_web_search(self) -> None:
        result = self.service.research(
            topic="测试主题",
            tasks=["任务一"],
            existing_research="已有资料",
            evaluation_comment="请补充数据",
        )

        request = self.responses.last_request
        self.assertEqual(result.content, "DeepSeek 网页研究资料。")
        self.assertEqual(
            result.sources,
            ["https://example.com/deepseek-source"],
        )
        self.assertEqual(request["tools"], [{"type": "web_search"}])
        self.assertEqual(request["tool_choice"], "required")
        self.assertNotIn("max_tool_calls", request)
        self.assertNotIn("include", request)
        self.assertIn("已有资料", request["input"][1]["content"])
        self.assertIn("请补充数据", request["input"][1]["content"])


class ResearchServiceFactoryTests(unittest.TestCase):
    def create_settings(self, provider: str) -> Settings:
        return Settings(
            llm_provider=provider,
            openai_api_key="openai-test-key",
            openai_model="openai-test-model",
            openai_search_model="openai-search-test-model",
            deepseek_api_key="deepseek-test-key",
            deepseek_model="deepseek-test-model",
            deepseek_base_url="https://api.deepseek.example.com",
        )

    @patch("app.llm.OpenAI")
    def test_factory_creates_openai_service(self, _openai) -> None:
        service = create_research_service(self.create_settings("openai"))

        self.assertIsInstance(service, OpenAIResearchService)

    @patch("app.llm.OpenAI")
    def test_factory_creates_deepseek_service(self, openai) -> None:
        service = create_research_service(self.create_settings("deepseek"))

        self.assertIsInstance(service, DeepSeekResearchService)
        self.assertEqual(openai.call_count, 1)
        self.assertEqual(
            openai.call_args.kwargs["base_url"],
            "https://api.deepseek.example.com",
        )


if __name__ == "__main__":
    unittest.main()
