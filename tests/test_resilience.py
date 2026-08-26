"""Tests for retry classification, timeouts, accounting, and budgets."""

import time
import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph import build_graph
from app.resilience import (
    NodeCallTimeoutError,
    ResilienceConfigurationError,
    ResilienceSettings,
    budget_exceeded_reason,
    call_with_timeout,
    is_retryable_error,
    summarize_usage,
)
from app.runtime import create_initial_state, create_run_config
from tests.fakes import FakeResearchLLM


def test_settings(**changes) -> ResilienceSettings:
    """Return fast, deterministic limits suitable for unit tests."""

    defaults = ResilienceSettings(
        retry_max_attempts=3,
        retry_initial_interval=0.001,
        retry_backoff_factor=2.0,
        retry_max_interval=0.01,
        node_timeout_seconds=1.0,
        max_llm_calls=30,
        max_search_rounds=3,
        max_total_tokens=0,
        max_cost_usd=0.0,
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    )
    return replace(defaults, **changes)


class FlakyPlannerLLM(FakeResearchLLM):
    """Fail once with a transient network error, then recover."""

    def create_plan(self, topic: str) -> list[str]:
        self.plan_calls += 1
        if self.plan_calls == 1:
            raise ConnectionError("temporary outage")
        return [f"研究 {topic}"]


class ResilienceTests(unittest.TestCase):
    def test_retry_classifier_separates_transient_and_permanent_errors(self) -> None:
        self.assertTrue(is_retryable_error(ConnectionError("temporary")))
        self.assertTrue(is_retryable_error(NodeCallTimeoutError("slow", 1.0)))
        self.assertFalse(is_retryable_error(ValueError("bad request")))

    def test_invalid_environment_limit_is_rejected(self) -> None:
        with patch.dict("os.environ", {"LLM_MAX_CALLS": "0"}):
            with self.assertRaises(ResilienceConfigurationError):
                ResilienceSettings.from_env()

    def test_blocking_call_has_a_deadline(self) -> None:
        def slow_operation() -> None:
            time.sleep(0.03)

        with self.assertRaises(NodeCallTimeoutError):
            call_with_timeout("slow test", 0.001, slow_operation)

    def test_langgraph_retries_a_transient_planner_failure(self) -> None:
        settings = test_settings()
        flaky_llm = FlakyPlannerLLM()
        target_graph = build_graph(
            checkpointer=InMemorySaver(),
            resilience=settings,
        )
        config = create_run_config(str(uuid4()))

        with patch("app.nodes.llm", flaky_llm):
            result = target_graph.invoke(
                create_initial_state("重试测试", settings),
                config=config,
            )

        self.assertIn("__interrupt__", result)
        self.assertEqual(flaky_llm.plan_calls, 2)

    def test_llm_call_budget_stops_before_parallel_research(self) -> None:
        settings = test_settings(max_llm_calls=1)
        fake_llm = FakeResearchLLM()
        target_graph = build_graph(
            checkpointer=InMemorySaver(),
            resilience=settings,
        )
        config = create_run_config(str(uuid4()))

        with patch("app.nodes.llm", fake_llm):
            target_graph.invoke(
                create_initial_state("预算测试", settings),
                config=config,
            )
            result = target_graph.invoke(
                Command(resume={"action": "approve"}),
                config=config,
            )

        self.assertTrue(result["budget_exhausted"])
        self.assertEqual(fake_llm.plan_calls, 1)
        self.assertEqual(fake_llm.research_calls, 0)
        self.assertIn("LLM 调用预算不足", result["termination_reason"])

    def test_token_and_cost_limits_stop_the_next_paid_step(self) -> None:
        state = {
            "run_id": "run-001",
            "usage_events": [
                {
                    "run_id": "run-001",
                    "operation": "Planner",
                    "llm_calls": 1,
                    "search_calls": 0,
                    "input_tokens": 40,
                    "output_tokens": 60,
                    "total_tokens": 100,
                    "cost_usd": 0.002,
                    "estimated": True,
                }
            ],
            "max_llm_calls": 10,
            "max_total_tokens": 100,
            "max_cost_usd": 0.002,
        }

        token_reason = budget_exceeded_reason(state, required_calls=1)
        state["max_total_tokens"] = 0
        cost_reason = budget_exceeded_reason(state, required_calls=1)

        self.assertIn("Token 预算已用尽", token_reason)
        self.assertIn("费用预算已用尽", cost_reason)

    def test_search_round_limit_comes_from_run_settings(self) -> None:
        settings = test_settings(max_search_rounds=1)
        fake_llm = FakeResearchLLM(research_scores=[60])
        target_graph = build_graph(
            checkpointer=InMemorySaver(),
            resilience=settings,
        )
        config = create_run_config(str(uuid4()))

        with patch("app.nodes.llm", fake_llm):
            target_graph.invoke(
                create_initial_state("轮数测试", settings),
                config=config,
            )
            result = target_graph.invoke(
                Command(resume={"action": "approve"}),
                config=config,
            )

        self.assertEqual(result["research_iteration"], 1)
        self.assertEqual(fake_llm.research_calls, 4)
        self.assertFalse(result["budget_exhausted"])

    def test_usage_events_are_persisted_and_priced(self) -> None:
        settings = test_settings(
            input_cost_per_million=1.0,
            output_cost_per_million=2.0,
        )
        fake_llm = FakeResearchLLM()
        target_graph = build_graph(
            checkpointer=InMemorySaver(),
            resilience=settings,
        )
        config = create_run_config(str(uuid4()))

        with patch("app.nodes.llm", fake_llm):
            target_graph.invoke(
                create_initial_state("用量测试", settings),
                config=config,
            )
            result = target_graph.invoke(
                Command(resume={"action": "approve"}),
                config=config,
            )

        usage = summarize_usage(result)
        self.assertEqual(usage["llm_calls"], 8)
        self.assertEqual(usage["search_calls"], 4)
        self.assertGreater(usage["total_tokens"], 0)
        self.assertGreater(usage["cost_usd"], 0)


if __name__ == "__main__":
    unittest.main()
