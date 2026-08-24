"""Helpers for starting a checkpointed graph run."""

from uuid import uuid4

from app.state import ResearchState


def create_thread_id(thread_id: str | None = None) -> str:
    """Use the supplied thread ID or generate a unique one."""

    if thread_id and thread_id.strip():
        return thread_id.strip()

    return str(uuid4())


def create_run_config(thread_id: str) -> dict[str, dict[str, str]]:
    """Build the configurable data required by a checkpointer."""

    return {"configurable": {"thread_id": thread_id}}


def create_initial_state(topic: str) -> ResearchState:
    """Create fresh run state while allowing a thread to keep its history."""

    return {
        "topic": topic,
        "plan_approved": False,
        "research_comment": "",
        "research_iteration": 0,
        "review_comment": "",
        "revision_count": 0,
    }
