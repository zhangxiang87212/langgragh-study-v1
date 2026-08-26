"""Helpers for starting a checkpointed graph run."""

from typing import Any
from uuid import uuid4

from app.state import ResearchState


MAX_RESEARCH_CONCURRENCY = 4


def create_thread_id(thread_id: str | None = None) -> str:
    """Use the supplied thread ID or generate a unique one."""

    if thread_id and thread_id.strip():
        return thread_id.strip()

    return str(uuid4())


def create_run_config(thread_id: str) -> dict[str, Any]:
    """Build the configurable data required by a checkpointer."""

    return {
        "configurable": {"thread_id": thread_id},
        "max_concurrency": MAX_RESEARCH_CONCURRENCY,
    }


def create_initial_state(topic: str) -> ResearchState:
    """Create fresh run state while allowing a thread to keep its history."""

    return {
        "topic": topic,
        "run_id": str(uuid4()),
        "plan_approved": False,
        "research_comment": "",
        "research_iteration": 0,
        "research_results": [],
        "review_comment": "",
        "revision_count": 0,
    }
