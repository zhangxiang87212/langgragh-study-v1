"""Tests for browser-session LLM settings and graph injection."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.config import Settings
from app.graph import build_graph
from app.llm import use_research_service
from app.runtime import create_initial_state, create_run_config
from app.server import app
from tests.fakes import FakeResearchLLM


class WebLLMConfigAPITests(unittest.TestCase):
    def test_api_key_is_kept_out_of_responses_and_isolated_by_cookie(self) -> None:
        first_browser = TestClient(app)
        second_browser = TestClient(app)

        self.assertFalse(first_browser.get("/api/config").json()["configured"])

        response = first_browser.put(
            "/api/config",
            json={
                "provider": "openai",
                "api_key": "browser-only-secret",
                "openai_model": "gpt-page",
                "openai_search_model": "gpt-search-page",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["configured"])
        self.assertNotIn("browser-only-secret", response.text)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertTrue(first_browser.get("/api/config").json()["configured"])
        self.assertFalse(second_browser.get("/api/config").json()["configured"])

        first_browser.delete("/api/config")
        self.assertFalse(first_browser.get("/api/config").json()["configured"])

    def test_stream_rejects_a_browser_without_model_settings(self) -> None:
        browser = TestClient(app)

        response = browser.get("/api/research/not-started/stream")

        self.assertEqual(response.status_code, 428)
        self.assertIn("模型设置", response.json()["detail"])


class RequestScopedResearchServiceTests(unittest.TestCase):
    def test_page_service_reaches_parallel_workers_without_using_env(self) -> None:
        fake_llm = FakeResearchLLM()
        settings = Settings.from_values(
            llm_provider="openai",
            api_key="browser-secret",
        )
        graph = build_graph(checkpointer=InMemorySaver())
        config = create_run_config("request-scoped-service")

        with patch("app.llm.create_research_service", return_value=fake_llm):
            with patch(
                "app.llm.Settings.from_env",
                side_effect=AssertionError("不应读取 .env"),
            ):
                with use_research_service(settings):
                    graph.invoke(
                        create_initial_state("页面模型配置测试"),
                        config=config,
                    )
                    result = graph.invoke(
                        Command(resume={"action": "approve"}),
                        config=config,
                    )

        self.assertEqual(result["review_score"], 85)
        self.assertEqual(fake_llm.plan_calls, 1)
        self.assertEqual(fake_llm.research_calls, 4)


if __name__ == "__main__":
    unittest.main()
