"""Manually exercise DeepSeekResearchService.research against the real API.

This test is skipped by default because it sends a real request and may incur
API charges. Run it explicitly with:

    RUN_DEEPSEEK_RESEARCH_MANUAL_TEST=1 \
    python -m unittest -v tests.test_deepseek_research_manual

Optional environment variables:
    DEEPSEEK_RESEARCH_TOPIC       Research topic to send to DeepSeek.
    DEEPSEEK_RESEARCH_TASKS       Tasks separated by ``|``.
"""

import os
import unittest

from app.config import Settings
from app.llm import DeepSeekResearchService


@unittest.skipUnless(
    os.getenv("RUN_DEEPSEEK_RESEARCH_MANUAL_TEST") == "1",
    "Set RUN_DEEPSEEK_RESEARCH_MANUAL_TEST=1 to make a real DeepSeek API call.",
)
class DeepSeekResearchManualTests(unittest.TestCase):
    """Integration test intended for local, on-demand verification only."""

    def test_research_prints_real_response(self) -> None:
        settings = Settings.from_env()
        self.assertEqual(
            settings.llm_provider,
            "deepseek",
            "Set LLM_PROVIDER=deepseek before running this manual test.",
        )

        topic = os.getenv("DEEPSEEK_RESEARCH_TOPIC", "DeepSeek 最新模型能力")
        tasks_value = os.getenv(
            "DEEPSEEK_RESEARCH_TASKS",
            "查找 DeepSeek 官方最新模型发布信息|总结模型的主要能力和适用场景",
        )
        tasks = [task.strip() for task in tasks_value.split("|") if task.strip()]
        self.assertTrue(tasks, "DEEPSEEK_RESEARCH_TASKS 至少要包含一个任务。")

        service = DeepSeekResearchService()
        result = service.research(topic=topic, tasks=tasks)

        print("\n=== DeepSeek research result ===")
        print(f"Topic: {topic}")
        print("\nContent:\n" + result.content)
        print("\nSources:")
        for source in result.sources:
            print(f"- {source}")

        self.assertTrue(result.content)
        self.assertTrue(result.sources)

