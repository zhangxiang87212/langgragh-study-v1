"""Build and save the final research result."""

from pathlib import Path

from app.resilience import summarize_usage
from app.state import ResearchState


DEFAULT_OUTPUT_DIRECTORY = Path("outputs")


def build_result_document(state: ResearchState) -> str:
    """Convert the final graph state into one Markdown document."""

    plan_list = "\n".join(
        f"{index}. {task}"
        for index, task in enumerate(state["plan"], start=1)
    )
    source_list = "\n".join(f"- {source}" for source in state["sources"])
    usage = summarize_usage(state)
    branch_summary = ""
    if state.get("parent_thread_id"):
        branch_summary = (
            f"\n- 来源线程：{state['parent_thread_id']}"
            f"\n- 来源 Checkpoint：{state['parent_checkpoint_id']}"
        )
    run_summary = (
        "## 执行信息\n\n"
        f"- 研究主题：{state['topic']}\n"
        f"- 研究评分：{state['research_score']}\n"
        f"- 研究评估意见：{state['research_comment']}\n"
        f"- 研究轮数：{state['research_iteration']}\n"
        f"- 审核分数：{state['review_score']}\n"
        f"- 审核意见：{state['review_comment']}\n"
        f"- 重写次数：{state['revision_count']}\n"
        f"- LLM 调用：{usage['llm_calls']} 次\n"
        f"- 搜索调用：{usage['search_calls']} 次\n"
        f"- 估算 Token：{usage['total_tokens']}\n"
        f"- 估算费用：${usage['cost_usd']:.6f}\n"
        f"- 预算提前结束：{'是' if state.get('budget_exhausted') else '否'}\n"
        f"- 结束原因：{state.get('termination_reason') or '正常完成'}"
        f"{branch_summary}"
    )

    return (
        f"{state['draft'].strip()}\n\n"
        "---\n\n"
        f"{run_summary}\n\n"
        "## 经确认的研究计划\n\n"
        f"{plan_list}\n\n"
        "## 研究来源\n\n"
        f"{source_list}\n"
    )


def save_result(
    state: ResearchState,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> Path:
    """Atomically write one deterministic result file for each run."""

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"research-report-{state['run_id']}.md"
    if output_path.exists():
        return output_path

    temporary_path = output_path.with_suffix(".md.tmp")
    temporary_path.write_text(build_result_document(state), encoding="utf-8")
    temporary_path.replace(output_path)

    return output_path
