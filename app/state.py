"""State schemas used by the main graph and parallel research workers."""

import operator
from typing import Annotated, TypedDict


class ResearchTaskResult(TypedDict):
    """One research worker's result for one plan task."""

    run_id: str
    research_iteration: int
    task_index: int
    task: str
    content: str
    sources: list[str]


class ResearchWorkerState(TypedDict):
    """The isolated input sent to one parallel research worker."""

    run_id: str
    topic: str
    task: str
    task_index: int
    task_count: int
    research_iteration: int
    existing_research: str
    evaluation_comment: str
    node_timeout_seconds: float
    input_cost_per_million: float
    output_cost_per_million: float


class UsageEvent(TypedDict):
    """Persisted usage for one successful logical LLM call."""

    run_id: str
    operation: str
    llm_calls: int
    search_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    estimated: bool


class ResearchState(TypedDict, total=False):
    """Data that is gradually filled in while the graph is running.

    ``total=False`` is important because the initial state contains only the
    input and loop-control fields. LLM outputs are added one node at a time.
    """

    topic: str
    run_id: str
    plan: list[str]
    plan_approved: bool
    research_content: str
    sources: list[str]
    research_score: int
    research_comment: str
    research_iteration: int
    research_results: Annotated[list[ResearchTaskResult], operator.add]
    draft: str
    review_score: int
    review_comment: str
    revision_count: int
    usage_events: Annotated[list[UsageEvent], operator.add]
    max_llm_calls: int
    max_search_rounds: int
    max_total_tokens: int
    max_cost_usd: float
    input_cost_per_million: float
    output_cost_per_million: float
    node_timeout_seconds: float
    budget_exhausted: bool
    termination_reason: str
