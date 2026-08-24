"""Node functions for the research workflow."""

from typing import Any

from langgraph.types import interrupt

from app.llm import llm
from app.state import ResearchState


def planner_node(state: ResearchState) -> dict[str, list[str]]:
    """Ask the LLM to break the topic into concrete research tasks."""

    topic = state["topic"]
    print(f"正在规划研究任务：{topic}")

    plan = llm.create_plan(topic)
    print("Planner 输出：")
    for index, task in enumerate(plan, start=1):
        print(f"{index}. {task}")

    return {"plan": plan}


def plan_approval_node(state: ResearchState) -> dict[str, Any]:
    """Pause so a person can approve or replace the research plan."""

    decision = interrupt(
        {
            "question": "请确认研究计划后再继续。",
            "plan": state["plan"],
        }
    )

    if not isinstance(decision, dict):
        raise ValueError("人工确认结果必须是一个字典。")

    if decision.get("action") == "approve":
        print("研究计划已确认。")
        return {"plan_approved": True}

    revised_plan = decision.get("plan")
    if decision.get("action") != "edit" or not _is_valid_plan(revised_plan):
        raise ValueError("人工确认结果必须批准计划，或者提供修改后的任务列表。")

    print("研究计划已由用户修改：")
    for index, task in enumerate(revised_plan, start=1):
        print(f"{index}. {task}")

    return {
        "plan": revised_plan,
        "plan_approved": True,
    }


def _is_valid_plan(plan: object) -> bool:
    """Return whether a human supplied a non-empty list of non-empty tasks."""

    return (
        isinstance(plan, list)
        and bool(plan)
        and all(isinstance(task, str) and bool(task.strip()) for task in plan)
    )


def researcher_node(state: ResearchState) -> dict[str, str | list[str] | int]:
    """Use web search to collect research notes and source URLs."""

    completed_iterations = state.get("research_iteration", 0)
    research_iteration = completed_iterations + 1
    print(f"正在进行第 {research_iteration} 轮研究...")

    existing_research = ""
    existing_sources = []
    evaluation_comment = ""
    if completed_iterations > 0:
        existing_research = state.get("research_content", "")
        existing_sources = state.get("sources", [])
        evaluation_comment = state.get("research_comment", "")

    research = llm.research(
        topic=state["topic"],
        tasks=state["plan"],
        existing_research=existing_research,
        evaluation_comment=evaluation_comment,
    )
    print(f"Researcher 输出：\n{research.content}")
    print("Researcher 来源：")
    for source in research.sources:
        print(f"- {source}")

    research_content = _combine_research_content(
        existing_research,
        research.content,
        research_iteration,
    )
    sources = list(dict.fromkeys([*existing_sources, *research.sources]))

    return {
        "research_content": research_content,
        "sources": sources,
        "research_iteration": research_iteration,
    }


def _combine_research_content(
    existing_research: str,
    new_research: str,
    research_iteration: int,
) -> str:
    """Keep earlier evidence and append notes from a follow-up search."""

    if not existing_research:
        return new_research

    return (
        f"{existing_research}\n\n"
        f"## 第 {research_iteration} 轮补充研究\n\n"
        f"{new_research}"
    )


def research_evaluator_node(state: ResearchState) -> dict[str, int | str]:
    """Evaluate whether the collected research can support report writing."""

    print("正在评估研究资料...")
    evaluation = llm.evaluate_research(
        topic=state["topic"],
        tasks=state["plan"],
        research_content=state["research_content"],
        sources=state["sources"],
    )
    print(f"Research Evaluator 输出：评分 {evaluation.score}")
    print(f"Research Evaluator 意见：{evaluation.comment}")

    return {
        "research_score": evaluation.score,
        "research_comment": evaluation.comment,
    }


def writer_node(state: ResearchState) -> dict[str, str | int]:
    """Ask the LLM to write or revise the report draft."""

    review_comment = state.get("review_comment")
    if review_comment:
        print(f"正在根据审核意见重写报告：{review_comment}")
        revision_count = state.get("revision_count", 0) + 1
    else:
        print("正在生成报告...")
        revision_count = 0

    topic = state["topic"]
    research_content = state["research_content"]
    draft = llm.write_report(
        topic=topic,
        research_content=research_content,
        sources=state["sources"],
        review_comment=review_comment,
    )
    print(f"Writer 输出：\n{draft}")

    return {
        "draft": draft,
        "revision_count": revision_count,
    }


def reviewer_node(state: ResearchState) -> dict[str, int | str]:
    """Ask the LLM for a structured score and review comment."""

    print("正在审核报告...")

    review = llm.review_report(state["draft"])
    print(f"Reviewer 输出：评分 {review.score}")
    print(f"Reviewer 意见：{review.comment}")

    return {
        "review_score": review.score,
        "review_comment": review.comment,
    }
