"""Build and compile the research graph."""

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.nodes import (
    budget_exhausted_node,
    plan_approval_node,
    planner_node,
    prepare_research_round_node,
    research_evaluator_node,
    research_reducer_node,
    research_worker_node,
    reviewer_node,
    writer_node,
)
from app.resilience import (
    DEFAULT_NODE_TIMEOUT_SECONDS,
    ResilienceSettings,
    budget_exceeded_reason,
)
from app.state import ResearchState


MAX_REVISIONS = 3
MAX_RESEARCH_ITERATIONS = 3
RESEARCH_PASS_SCORE = 80


def dispatch_research_workers(state: ResearchState) -> list[Send] | str:
    """Create one parallel worker for every task in the approved plan."""

    if _budget_reason(state, len(state["plan"])):
        return "budget_exhausted"

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
                "node_timeout_seconds": state.get(
                    "node_timeout_seconds",
                    DEFAULT_NODE_TIMEOUT_SECONDS,
                ),
                "input_cost_per_million": state.get(
                    "input_cost_per_million",
                    0.0,
                ),
                "output_cost_per_million": state.get(
                    "output_cost_per_million",
                    0.0,
                ),
            },
        )
        for task_index, task in enumerate(state["plan"])
    ]


def research_router(
    state: ResearchState,
) -> Literal["sufficient", "retry", "budget_exhausted"]:
    """Choose whether to write the report or collect more evidence."""

    research_score = state["research_score"]
    research_iteration = state["research_iteration"]

    if research_score >= RESEARCH_PASS_SCORE:
        if _budget_reason(state, 1):
            return "budget_exhausted"
        print("研究资料已足够，进入 Writer。")
        return "sufficient"

    max_iterations = state.get("max_search_rounds", MAX_RESEARCH_ITERATIONS)
    if research_iteration >= max_iterations:
        print(
            f"已达到最大研究轮数 {max_iterations}，"
            "停止搜索并进入 Writer。"
        )
        if _budget_reason(state, 1):
            return "budget_exhausted"
        return "sufficient"

    print("研究资料不足，返回 Researcher 补充搜索。")
    return "retry"


def review_router(
    state: ResearchState,
) -> Literal["pass", "rewrite", "budget_exhausted"]:
    """Choose the next step from the score and the revision limit."""

    review_score = state["review_score"]
    revision_count = state["revision_count"]

    if review_score >= 80:
        print("审核通过，结束工作流。")
        return "pass"

    if revision_count >= MAX_REVISIONS:
        print(f"已达到最大重写次数 {MAX_REVISIONS}，结束工作流。")
        return "pass"

    if _budget_reason(state, 1):
        return "budget_exhausted"
    print("审核未通过，返回 Writer 重写。")
    return "rewrite"


def evaluator_budget_router(
    state: ResearchState,
) -> Literal["evaluate", "budget_exhausted"]:
    """Protect the evaluator from starting after a budget is exhausted."""

    return "budget_exhausted" if _budget_reason(state, 1) else "evaluate"


def reviewer_budget_router(
    state: ResearchState,
) -> Literal["review", "budget_exhausted"]:
    """Protect the reviewer from starting after a budget is exhausted."""

    return "budget_exhausted" if _budget_reason(state, 1) else "review"


def _budget_reason(state: ResearchState, required_calls: int) -> str | None:
    """Keep small unit-test states compatible with the budgeted graph."""

    if "max_llm_calls" not in state:
        return None
    reason = budget_exceeded_reason(state, required_calls)
    if reason:
        print(f"预算检查未通过：{reason}")
    return reason


def build_graph(
    reviewer=reviewer_node,
    checkpointer=None,
    resilience: ResilienceSettings | None = None,
):
    """Create the graph, optionally replacing Reviewer for isolated tests."""

    builder = StateGraph(ResearchState)
    resilience = resilience or ResilienceSettings.from_env()
    retry_policy = resilience.retry_policy()

    builder.add_node("planner", planner_node, retry_policy=retry_policy)
    builder.add_node("plan_approval", plan_approval_node)
    builder.add_node("prepare_research", prepare_research_round_node)
    builder.add_node(
        "research_worker",
        research_worker_node,
        retry_policy=retry_policy,
    )
    builder.add_node("research_reducer", research_reducer_node)
    builder.add_node(
        "research_evaluator",
        research_evaluator_node,
        retry_policy=retry_policy,
    )
    builder.add_node("writer", writer_node, retry_policy=retry_policy)
    builder.add_node("reviewer", reviewer, retry_policy=retry_policy)
    builder.add_node("budget_exhausted", budget_exhausted_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "plan_approval")
    builder.add_edge("plan_approval", "prepare_research")
    builder.add_conditional_edges(
        "prepare_research",
        dispatch_research_workers,
        ["research_worker", "budget_exhausted"],
    )
    builder.add_edge("research_worker", "research_reducer")
    builder.add_conditional_edges(
        "research_reducer",
        evaluator_budget_router,
        {
            "evaluate": "research_evaluator",
            "budget_exhausted": "budget_exhausted",
        },
    )
    builder.add_conditional_edges(
        "research_evaluator",
        research_router,
        {
            "sufficient": "writer",
            "retry": "prepare_research",
            "budget_exhausted": "budget_exhausted",
        },
    )
    builder.add_conditional_edges(
        "writer",
        reviewer_budget_router,
        {
            "review": "reviewer",
            "budget_exhausted": "budget_exhausted",
        },
    )
    builder.add_conditional_edges(
        "reviewer",
        review_router,
        {
            "pass": END,
            "rewrite": "writer",
            "budget_exhausted": "budget_exhausted",
        },
    )
    builder.add_edge("budget_exhausted", END)

    return builder.compile(checkpointer=checkpointer)


checkpointer = InMemorySaver()
graph = build_graph(checkpointer=checkpointer)
