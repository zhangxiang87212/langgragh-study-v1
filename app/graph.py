"""Build and compile the research graph."""

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.nodes import (
    plan_approval_node,
    planner_node,
    prepare_research_round_node,
    research_evaluator_node,
    research_reducer_node,
    research_worker_node,
    reviewer_node,
    writer_node,
)
from app.state import ResearchState


MAX_REVISIONS = 3
MAX_RESEARCH_ITERATIONS = 3
RESEARCH_PASS_SCORE = 80


def dispatch_research_workers(state: ResearchState) -> list[Send]:
    """Create one parallel worker for every task in the approved plan."""

    is_first_round = state["research_iteration"] == 1
    existing_research = ""
    evaluation_comment = ""
    if not is_first_round:
        existing_research = state.get("research_content", "")
        evaluation_comment = state.get("research_comment", "")

    return [
        Send(
            "research_worker",
            {
                "run_id": state["run_id"],
                "topic": state["topic"],
                "task": task,
                "task_index": task_index,
                "task_count": len(state["plan"]),
                "research_iteration": state["research_iteration"],
                "existing_research": existing_research,
                "evaluation_comment": evaluation_comment,
            },
        )
        for task_index, task in enumerate(state["plan"])
    ]


def research_router(state: ResearchState) -> Literal["sufficient", "retry"]:
    """Choose whether to write the report or collect more evidence."""

    research_score = state["research_score"]
    research_iteration = state["research_iteration"]

    if research_score >= RESEARCH_PASS_SCORE:
        print("研究资料已足够，进入 Writer。")
        return "sufficient"

    if research_iteration >= MAX_RESEARCH_ITERATIONS:
        print(
            f"已达到最大研究轮数 {MAX_RESEARCH_ITERATIONS}，"
            "停止搜索并进入 Writer。"
        )
        return "sufficient"

    print("研究资料不足，返回 Researcher 补充搜索。")
    return "retry"


def review_router(state: ResearchState) -> Literal["pass", "rewrite"]:
    """Choose the next step from the score and the revision limit."""

    review_score = state["review_score"]
    revision_count = state["revision_count"]

    if review_score >= 80:
        print("审核通过，结束工作流。")
        return "pass"

    if revision_count >= MAX_REVISIONS:
        print(f"已达到最大重写次数 {MAX_REVISIONS}，结束工作流。")
        return "pass"

    print("审核未通过，返回 Writer 重写。")
    return "rewrite"


def build_graph(reviewer=reviewer_node, checkpointer=None):
    """Create the graph, optionally replacing Reviewer for isolated tests."""

    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("plan_approval", plan_approval_node)
    builder.add_node("prepare_research", prepare_research_round_node)
    builder.add_node("research_worker", research_worker_node)
    builder.add_node("research_reducer", research_reducer_node)
    builder.add_node("research_evaluator", research_evaluator_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "plan_approval")
    builder.add_edge("plan_approval", "prepare_research")
    builder.add_conditional_edges(
        "prepare_research",
        dispatch_research_workers,
        ["research_worker"],
    )
    builder.add_edge("research_worker", "research_reducer")
    builder.add_edge("research_reducer", "research_evaluator")
    builder.add_conditional_edges(
        "research_evaluator",
        research_router,
        {
            "sufficient": "writer",
            "retry": "prepare_research",
        },
    )
    builder.add_edge("writer", "reviewer")
    builder.add_conditional_edges(
        "reviewer",
        review_router,
        {
            "pass": END,
            "rewrite": "writer",
        },
    )

    return builder.compile(checkpointer=checkpointer)


checkpointer = InMemorySaver()
graph = build_graph(checkpointer=checkpointer)
