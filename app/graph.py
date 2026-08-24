"""Build and compile the research graph."""

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.nodes import (
    plan_approval_node,
    planner_node,
    research_evaluator_node,
    researcher_node,
    reviewer_node,
    writer_node,
)
from app.state import ResearchState


MAX_REVISIONS = 3
MAX_RESEARCH_ITERATIONS = 3
RESEARCH_PASS_SCORE = 80


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
    builder.add_node("researcher", researcher_node)
    builder.add_node("research_evaluator", research_evaluator_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "plan_approval")
    builder.add_edge("plan_approval", "researcher")
    builder.add_edge("researcher", "research_evaluator")
    builder.add_conditional_edges(
        "research_evaluator",
        research_router,
        {
            "sufficient": "writer",
            "retry": "researcher",
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
