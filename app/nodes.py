"""Node functions for the research workflow."""

from typing import Any

from langgraph.config import get_stream_writer
from langgraph.types import interrupt

from app.llm import llm
from app.state import ResearchState, ResearchTaskResult, ResearchWorkerState


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


def prepare_research_round_node(state: ResearchState) -> dict[str, int]:
    """Advance the round once before its research workers fan out."""

    research_iteration = state.get("research_iteration", 0) + 1
    task_count = len(state["plan"])
    print(
        f"准备第 {research_iteration} 轮并行研究，"
        f"共 {task_count} 个任务。"
    )
    return {"research_iteration": research_iteration}


def research_worker_node(
    state: ResearchWorkerState,
) -> dict[str, list[ResearchTaskResult]]:
    """Research one plan task in an isolated parallel worker."""

    task_number = state["task_index"] + 1
    stream_writer = _get_stream_writer_or_none()
    if stream_writer is not None:
        stream_writer({
            "event": "research_task_start",
            "task_number": task_number,
            "task_count": state["task_count"],
            "task": state["task"],
        })
    else:
        print(
            f"Researcher {task_number}/{state['task_count']} 开始："
            f"{state['task']}"
        )

    research = llm.research(
        topic=state["topic"],
        tasks=[state["task"]],
        existing_research=state["existing_research"],
        evaluation_comment=state["evaluation_comment"],
    )

    if stream_writer is not None:
        stream_writer({
            "event": "research_task_result",
            "task_number": task_number,
            "task_count": state["task_count"],
            "task": state["task"],
            "content": research.content,
            "sources": research.sources,
        })
    else:
        _print_research_result(
            task_number,
            state["task_count"],
            state["task"],
            research.content,
            research.sources,
        )

    result: ResearchTaskResult = {
        "run_id": state["run_id"],
        "research_iteration": state["research_iteration"],
        "task_index": state["task_index"],
        "task": state["task"],
        "content": research.content,
        "sources": research.sources,
    }
    return {"research_results": [result]}


def research_reducer_node(
    state: ResearchState,
) -> dict[str, str | list[str]]:
    """Merge the current round's parallel results in plan order."""

    current_results = [
        result
        for result in state["research_results"]
        if result["run_id"] == state["run_id"]
        and result["research_iteration"] == state["research_iteration"]
    ]
    current_results.sort(key=lambda result: result["task_index"])

    if len(current_results) != len(state["plan"]):
        raise RuntimeError("并行研究结果数量与研究计划不一致。")

    round_content = "\n\n".join(
        f"### 任务 {result['task_index'] + 1}：{result['task']}\n\n"
        f"{result['content']}"
        for result in current_results
    )
    existing_research = ""
    existing_sources = []
    if state["research_iteration"] > 1:
        existing_research = state.get("research_content", "")
        existing_sources = state.get("sources", [])

    research_content = _combine_research_content(
        existing_research,
        round_content,
        state["research_iteration"],
    )

    new_sources = [
        source
        for result in current_results
        for source in result["sources"]
    ]
    sources = list(dict.fromkeys([*existing_sources, *new_sources]))

    print(
        f"第 {state['research_iteration']} 轮研究汇总完成："
        f"{len(current_results)} 个任务，{len(sources)} 个去重来源。"
    )
    return {
        "research_content": research_content,
        "sources": sources,
    }


def _print_research_result(
    task_number: int,
    task_count: int,
    task: str,
    content: str,
    sources: list[str],
) -> None:
    """Print one complete worker result without interleaving token output."""

    print(f"Researcher {task_number}/{task_count} 输出：{task}\n{content}")
    print(f"Researcher {task_number}/{task_count} 来源：")
    for source in sources:
        print(f"- {source}")


def _combine_research_content(
    existing_research: str,
    new_research: str,
    research_iteration: int,
) -> str:
    """Keep earlier evidence and append notes from a follow-up search."""

    if not existing_research:
        return f"## 第 1 轮并行研究\n\n{new_research}"

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
    stream_writer = _get_stream_writer_or_none()
    token_callback = None
    if stream_writer is not None:
        stream_writer({"event": "llm_stream_start", "node": "Writer"})

        def send_token(token: str) -> None:
            stream_writer({
                "event": "llm_token",
                "node": "Writer",
                "text": token,
            })

        token_callback = send_token

    try:
        draft = llm.write_report(
            topic=topic,
            research_content=research_content,
            sources=state["sources"],
            review_comment=review_comment,
            on_token=token_callback,
        )
    finally:
        if stream_writer is not None:
            stream_writer({"event": "llm_stream_end", "node": "Writer"})

    if stream_writer is None:
        print(f"Writer 输出：\n{draft}")

    return {
        "draft": draft,
        "revision_count": revision_count,
    }


def _get_stream_writer_or_none():
    """Return LangGraph's custom writer only during a streamed run."""

    try:
        return get_stream_writer()
    except RuntimeError:
        return None


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
