"""The shared state used by every node in the research graph."""

from typing import TypedDict


class ResearchState(TypedDict, total=False):
    """Data that is gradually filled in while the graph is running.

    ``total=False`` is important here. The graph starts with only ``topic``;
    the remaining fields are added one node at a time.
    """

    topic: str
    plan: list[str]
    plan_approved: bool
    research_content: str
    sources: list[str]
    research_score: int
    research_comment: str
    research_iteration: int
    draft: str
    review_score: int
    review_comment: str
    revision_count: int
