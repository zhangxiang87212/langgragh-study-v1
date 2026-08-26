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
