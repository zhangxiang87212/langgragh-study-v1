"""Retry, timeout, usage, and budget helpers for LLM-backed nodes."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextvars import copy_context
from dataclasses import dataclass
import math
import os
from typing import Callable, TypeVar

from langgraph.errors import NodeTimeoutError
from langgraph.types import RetryPolicy
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError


DEFAULT_LLM_MAX_CALLS = 30
DEFAULT_SEARCH_MAX_ROUNDS = 3
DEFAULT_NODE_TIMEOUT_SECONDS = 120.0
DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_INITIAL_INTERVAL = 1.0
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0
DEFAULT_RETRY_MAX_INTERVAL = 30.0

ResultT = TypeVar("ResultT")


class ResilienceConfigurationError(RuntimeError):
    """Raised when a resilience or budget setting is invalid."""


class NodeCallTimeoutError(NodeTimeoutError):
    """Raised when one synchronous provider call exceeds its node deadline."""

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(
            operation,
            timeout_seconds,
            kind="run",
            run_timeout=timeout_seconds,
        )


@dataclass(frozen=True)
class ResilienceSettings:
    """Limits that are fixed for one graph run."""

    retry_max_attempts: int
    retry_initial_interval: float
    retry_backoff_factor: float
    retry_max_interval: float
    node_timeout_seconds: float
    max_llm_calls: int
    max_search_rounds: int
    max_total_tokens: int
    max_cost_usd: float
    input_cost_per_million: float
    output_cost_per_million: float

    @classmethod
    def from_env(cls) -> "ResilienceSettings":
        """Load limits without requiring an LLM API key."""

        return cls(
            retry_max_attempts=_read_positive_int(
                "LLM_RETRY_MAX_ATTEMPTS",
                DEFAULT_RETRY_MAX_ATTEMPTS,
            ),
            retry_initial_interval=_read_positive_float(
                "LLM_RETRY_INITIAL_INTERVAL",
                DEFAULT_RETRY_INITIAL_INTERVAL,
            ),
            retry_backoff_factor=_read_positive_float(
                "LLM_RETRY_BACKOFF_FACTOR",
                DEFAULT_RETRY_BACKOFF_FACTOR,
            ),
            retry_max_interval=_read_positive_float(
                "LLM_RETRY_MAX_INTERVAL",
                DEFAULT_RETRY_MAX_INTERVAL,
            ),
            node_timeout_seconds=_read_positive_float(
                "LLM_NODE_TIMEOUT_SECONDS",
                DEFAULT_NODE_TIMEOUT_SECONDS,
            ),
            max_llm_calls=_read_positive_int(
                "LLM_MAX_CALLS",
                DEFAULT_LLM_MAX_CALLS,
            ),
            max_search_rounds=_read_positive_int(
                "SEARCH_MAX_ROUNDS",
                DEFAULT_SEARCH_MAX_ROUNDS,
            ),
            max_total_tokens=_read_non_negative_int("LLM_MAX_TOTAL_TOKENS", 0),
            max_cost_usd=_read_non_negative_float("LLM_MAX_COST_USD", 0.0),
            input_cost_per_million=_read_non_negative_float(
                "LLM_INPUT_COST_PER_MILLION",
                0.0,
            ),
            output_cost_per_million=_read_non_negative_float(
                "LLM_OUTPUT_COST_PER_MILLION",
                0.0,
            ),
        )

    def retry_policy(self) -> RetryPolicy:
        """Build LangGraph's node-level exponential retry policy."""

        return RetryPolicy(
            max_attempts=self.retry_max_attempts,
            initial_interval=self.retry_initial_interval,
            backoff_factor=self.retry_backoff_factor,
            max_interval=self.retry_max_interval,
            jitter=True,
            retry_on=is_retryable_error,
        )


def is_retryable_error(error: Exception) -> bool:
    """Return whether another attempt could reasonably succeed."""

    if isinstance(
        error,
        (NodeTimeoutError, APITimeoutError, APIConnectionError, RateLimitError),
    ):
        return True

    if isinstance(error, APIStatusError):
        return error.status_code in {408, 409, 429} or error.status_code >= 500

    if isinstance(error, (ConnectionError, TimeoutError)):
        return True

    return False


def call_with_timeout(
    operation: str,
    timeout_seconds: float,
    function: Callable[[], ResultT],
) -> ResultT:
    """Run one blocking provider call with a hard caller-side deadline."""

    executor = ThreadPoolExecutor(max_workers=1)
    # LangGraph stores stream writers and run configuration in context variables.
    # A new thread starts with an empty context unless we copy it explicitly.
    context = copy_context()
    future = executor.submit(context.run, function)
    try:
        result = future.result(timeout=timeout_seconds)
    except FutureTimeout as error:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise NodeCallTimeoutError(operation, timeout_seconds) from error
    except BaseException:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)
        return result


def create_usage_event(
    operation: str,
    input_text: str,
    output_text: str,
    state: dict,
    *,
    search_call: bool = False,
) -> dict[str, object]:
    """Estimate tokens consistently when providers expose different metadata."""

    input_tokens = _estimate_tokens(input_text)
    output_tokens = _estimate_tokens(output_text)
    cost_usd = (
        input_tokens * state.get("input_cost_per_million", 0.0)
        + output_tokens * state.get("output_cost_per_million", 0.0)
    ) / 1_000_000
    return {
        "operation": operation,
        "llm_calls": 1,
        "search_calls": 1 if search_call else 0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost_usd,
        "estimated": True,
    }


def summarize_usage(state: dict) -> dict[str, int | float]:
    """Sum persisted usage events from the current run."""

    events = [
        event
        for event in state.get("usage_events", [])
        if event.get("run_id") == state.get("run_id")
    ]
    return {
        "llm_calls": sum(int(event["llm_calls"]) for event in events),
        "search_calls": sum(int(event["search_calls"]) for event in events),
        "input_tokens": sum(int(event["input_tokens"]) for event in events),
        "output_tokens": sum(int(event["output_tokens"]) for event in events),
        "total_tokens": sum(int(event["total_tokens"]) for event in events),
        "cost_usd": sum(float(event["cost_usd"]) for event in events),
    }


def budget_exceeded_reason(state: dict, required_calls: int = 0) -> str | None:
    """Explain which persisted budget would be exceeded by the next step."""

    usage = summarize_usage(state)
    if usage["llm_calls"] + required_calls > state["max_llm_calls"]:
        return (
            f"LLM 调用预算不足：已调用 {usage['llm_calls']} 次，"
            f"下一步需要 {required_calls} 次，上限 {state['max_llm_calls']} 次。"
        )

    max_tokens = state["max_total_tokens"]
    if max_tokens and usage["total_tokens"] >= max_tokens:
        return f"Token 预算已用尽：{usage['total_tokens']}/{max_tokens}。"

    max_cost = state["max_cost_usd"]
    if max_cost and usage["cost_usd"] >= max_cost:
        return (
            f"费用预算已用尽：${usage['cost_usd']:.6f}/"
            f"${max_cost:.6f}。"
        )

    return None


def _estimate_tokens(text: str) -> int:
    """Use a transparent fallback estimate without adding a tokenizer dependency."""

    if not text:
        return 0
    return max(1, math.ceil(len(text) / 3))


def _read_positive_int(name: str, default: int) -> int:
    value = _read_int(name, default)
    if value <= 0:
        raise ResilienceConfigurationError(f"{name} 必须是正整数。")
    return value


def _read_non_negative_int(name: str, default: int) -> int:
    value = _read_int(name, default)
    if value < 0:
        raise ResilienceConfigurationError(f"{name} 不能是负数。")
    return value


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError as error:
        raise ResilienceConfigurationError(f"{name} 必须是整数。") from error


def _read_positive_float(name: str, default: float) -> float:
    value = _read_float(name, default)
    if value <= 0:
        raise ResilienceConfigurationError(f"{name} 必须大于 0。")
    return value


def _read_non_negative_float(name: str, default: float) -> float:
    value = _read_float(name, default)
    if value < 0:
        raise ResilienceConfigurationError(f"{name} 不能是负数。")
    return value


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return float(raw_value)
    except ValueError as error:
        raise ResilienceConfigurationError(f"{name} 必须是数字。") from error
