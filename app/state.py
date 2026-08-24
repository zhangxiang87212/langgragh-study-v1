"""The shared state used by every node in the research graph."""

from typing import TypedDict


class ResearchState(TypedDict, total=False):
    """Data that is gradually filled in while the graph is running.

    ``total=False`` is important here. The graph starts with only ``topic``;
    the remaining fields are added one node at a time.
    """

    topic: str
    plan: list[str]
    research_content: str
    draft: str
    review_score: int
    review_comment: str
