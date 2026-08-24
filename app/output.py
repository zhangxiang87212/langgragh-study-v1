"""Build and save the final research result."""

from datetime import datetime
from pathlib import Path

from app.state import ResearchState


DEFAULT_OUTPUT_DIRECTORY = Path("outputs")


def build_result_document(state: ResearchState) -> str:
    """Convert the final graph state into one Markdown document."""

    plan_list = "\n".join(
        f"{index}. {task}"
        for index, task in enumerate(state["plan"], start=1)
    )
    source_list = "\n".join(f"- {source}" for source in state["sources"])
    run_summary = (
        "## 执行信息\n\n"
        f"- 研究主题：{state['topic']}\n"
        f"- 研究评分：{state['research_score']}\n"
        f"- 研究评估意见：{state['research_comment']}\n"
        f"- 研究轮数：{state['research_iteration']}\n"
        f"- 审核分数：{state['review_score']}\n"
        f"- 审核意见：{state['review_comment']}\n"
        f"- 重写次数：{state['revision_count']}"
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
    """Write the final result to a uniquely named UTF-8 Markdown file."""

    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_path = output_directory / f"research-report-{timestamp}.md"
    output_path.write_text(build_result_document(state), encoding="utf-8")

    return output_path
