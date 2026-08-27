"""Build a human-readable review of one persisted research checkpoint."""

from pathlib import Path
import shlex
from typing import Any

from app.runtime import create_run_config
from app.time_travel import TimeTravelError, find_checkpoint


class InspectionError(ValueError):
    """Raised when a checkpoint cannot be inspected or exported."""


def load_inspection_snapshot(
    graph,
    *,
    thread_id: str,
    checkpoint_id: str | None,
):
    """Load an exact historical checkpoint, or the thread's latest one."""

    if checkpoint_id:
        try:
            return find_checkpoint(
                graph,
                source_thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            )
        except TimeTravelError as error:
            raise InspectionError(str(error)) from error

    snapshot = graph.get_state(create_run_config(thread_id))
    if not snapshot.values:
        raise InspectionError(f"没有找到线程：{thread_id}")
    return snapshot


def build_inspection_document(snapshot, *, thread_id: str) -> str:
    """Render State evidence, source mapping, and deterministic review hints."""

    state = snapshot.values
    checkpoint_id = snapshot.config["configurable"].get(
        "checkpoint_id",
        "未知",
    )
    step = snapshot.metadata.get("step", "未知")
    next_nodes = ", ".join(snapshot.next) or "END"
    plan = state.get("plan", [])
    current_run_id = state.get("run_id")
    research_results = [
        result
        for result in state.get("research_results", [])
        if result.get("run_id") == current_run_id
    ]
    research_results.sort(
        key=lambda result: (
            result.get("research_iteration", 0),
            result.get("task_index", 0),
        )
    )

    sections = [
        "# Checkpoint 资料审查",
        _build_checkpoint_summary(
            state,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            step=step,
            next_nodes=next_nodes,
        ),
        _build_review_hints(state, research_results),
        _build_plan_section(plan),
        _build_evaluation_section(state),
        _build_worker_sections(research_results),
        _build_sources_section(state.get("sources", [])),
        _build_manual_checklist(),
        _build_correction_examples(thread_id, checkpoint_id),
    ]
    return "\n\n".join(section for section in sections if section).rstrip() + "\n"


def save_inspection_document(document: str, output_path: Path) -> Path:
    """Write an inspection document without overwriting an existing review."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("x", encoding="utf-8") as output_file:
            output_file.write(document)
    except FileExistsError as error:
        raise InspectionError(
            f"审查文件已存在，不会覆盖：{output_path}"
        ) from error
    return output_path


def _build_checkpoint_summary(
    state: dict[str, Any],
    *,
    thread_id: str,
    checkpoint_id: str,
    step: Any,
    next_nodes: str,
) -> str:
    """Show enough identity data to create a correction branch later."""

    return (
        "## Checkpoint 信息\n\n"
        f"- 线程 ID：{thread_id}\n"
        f"- Checkpoint ID：{checkpoint_id}\n"
        f"- Step：{step}\n"
        f"- 下一节点：{next_nodes}\n"
        f"- 研究主题：{state.get('topic', '未知')}\n"
        f"- Run ID：{state.get('run_id', '未知')}"
    )


def _build_review_hints(state: dict, research_results: list[dict]) -> str:
    """Point out structural problems without pretending to fact-check URLs."""

    hints = []
    if not state.get("research_content"):
        hints.append("这个 Checkpoint 尚未产生合并后的研究资料。")
    if not state.get("sources"):
        hints.append("汇总来源为空，当前资料缺少可追溯 URL。")

    score = state.get("research_score")
    if score is not None and score < 80:
        hints.append(f"Research Evaluator 评分为 {score}，低于通过线 80。")

    source_less_tasks = [
        result.get("task", "未命名任务")
        for result in research_results
        if not result.get("sources")
    ]
    if source_less_tasks:
        hints.append(
            "以下 Worker 没有返回来源：" + "；".join(source_less_tasks)
        )

    if not hints:
        hints.append(
            "未发现来源为空或评分不足等结构性问题；"
            "仍需人工核验来源权威性、时效性及其是否支持正文结论。"
        )

    hint_list = "\n".join(f"- {hint}" for hint in hints)
    return f"## 自动审查提示\n\n{hint_list}"


def _build_plan_section(plan: list[str]) -> str:
    """Render the plan used to judge whether every task has evidence."""

    if not plan:
        return "## 研究计划\n\n这个 Checkpoint 尚未产生研究计划。"
    items = "\n".join(
        f"{index}. {task}" for index, task in enumerate(plan, start=1)
    )
    return f"## 研究计划\n\n{items}"


def _build_evaluation_section(state: dict) -> str:
    """Render the existing evaluator judgment without making a new LLM call."""

    if "research_score" not in state:
        return "## Research Evaluator\n\n这个 Checkpoint 尚未执行资料评估。"
    return (
        "## Research Evaluator\n\n"
        f"- 评分：{state['research_score']}\n"
        f"- 意见：{state.get('research_comment') or '无'}"
    )


def _build_worker_sections(research_results: list[dict]) -> str:
    """Keep every source next to the Worker content that produced it."""

    if not research_results:
        return "## Worker 原始资料与来源\n\n这个 Checkpoint 尚无 Worker 结果。"

    worker_documents = []
    for result in research_results:
        iteration = result.get("research_iteration", "未知")
        task_number = result.get("task_index", 0) + 1
        task = result.get("task", "未命名任务")
        content = result.get("content") or "无研究内容。"
        sources = result.get("sources", [])
        source_list = "\n".join(f"- {source}" for source in sources)
        if not source_list:
            source_list = "- 无来源"

        worker_documents.append(
            f"### 第 {iteration} 轮 · Worker {task_number}：{task}\n\n"
            f"{content}\n\n"
            f"来源：\n\n{source_list}"
        )
    return "## Worker 原始资料与来源\n\n" + "\n\n".join(worker_documents)


def _build_sources_section(sources: list[str]) -> str:
    """Render the Reducer's deduplicated source list."""

    if not sources:
        return "## 汇总来源\n\n- 无来源"
    source_list = "\n".join(f"- {source}" for source in sources)
    return f"## 汇总来源\n\n{source_list}"


def _build_manual_checklist() -> str:
    """Explain judgments that cannot be derived safely from State alone."""

    return (
        "## 人工核验清单\n\n"
        "- 来源是否能正常访问，而不是 404、登录页或已删除页面？\n"
        "- 来源是否来自政府、监管机构、原始研究或可信行业机构？\n"
        "- 来源发布时间是否适合当前研究主题？\n"
        "- 来源原文是否真正支持 Worker 写出的数字和结论？\n"
        "- 不同来源之间是否存在数据口径或结论冲突？\n"
        "- 研究计划中的每一项任务是否都有可验证证据？"
    )


def _build_correction_examples(thread_id: str, checkpoint_id: str) -> str:
    """Provide copyable commands while leaving correction values explicit."""

    safe_thread_id = shlex.quote(thread_id)
    safe_checkpoint_id = shlex.quote(checkpoint_id)
    return (
        "## 修正命令模板\n\n"
        "```bash\n"
        "python -m app.main fork \\\n"
        f"  --thread-id {safe_thread_id} \\\n"
        f"  --checkpoint-id {safe_checkpoint_id} \\\n"
        "  --remove-source \"错误来源 URL\" \\\n"
        "  --remove-text \"错误结论原文\" \\\n"
        "  --evidence \"人工证据及其来源 URL\"\n"
        "```"
    )
