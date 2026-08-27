"""Create corrected research branches from historical checkpoints."""

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.runtime import create_run_config
from app.state import ResearchState


URL_PATTERN = re.compile(r"https?://[^\s)\]>，。；;]+")


class TimeTravelError(ValueError):
    """Raised when a checkpoint cannot be replayed safely."""


@dataclass(frozen=True)
class BranchCorrections:
    """Human changes applied before a historical state is replayed."""

    plan: tuple[str, ...] = ()
    remove_sources: tuple[str, ...] = ()
    remove_texts: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    @property
    def changes_plan(self) -> bool:
        return bool(self.plan)

    @property
    def changes_evidence(self) -> bool:
        return bool(self.remove_sources or self.remove_texts or self.evidence)


@dataclass(frozen=True)
class CreatedBranch:
    """The identifiers and resume point of a newly created branch."""

    thread_id: str
    run_id: str
    config: dict[str, Any]
    next_node: str


def create_corrected_branch(
    graph,
    *,
    source_thread_id: str,
    checkpoint_id: str,
    new_thread_id: str,
    corrections: BranchCorrections,
) -> CreatedBranch:
    """Copy one checkpoint into a new thread and schedule its downstream node."""

    source_snapshot = find_checkpoint(
        graph,
        source_thread_id=source_thread_id,
        checkpoint_id=checkpoint_id,
    )
    branch_config = create_run_config(new_thread_id)
    if graph.get_state(branch_config).values:
        raise TimeTravelError(f"新分支线程 {new_thread_id} 已存在。")

    branch_state, next_node = prepare_branch_state(
        source_snapshot,
        source_thread_id=source_thread_id,
        checkpoint_id=checkpoint_id,
        corrections=corrections,
    )
    predecessor = predecessor_for(next_node)
    saved_config = graph.update_state(
        branch_config,
        branch_state,
        as_node=predecessor,
    )

    # update_state 返回 Checkpointer 所需的 checkpoint_id。
    # create_run_config 中的顶层并发配置需要补回。
    resume_config = {
        **branch_config,
        "configurable": saved_config["configurable"],
    }
    return CreatedBranch(
        thread_id=new_thread_id,
        run_id=branch_state["run_id"],
        config=resume_config,
        next_node=next_node,
    )


def find_checkpoint(graph, *, source_thread_id: str, checkpoint_id: str):
    """Find an exact checkpoint instead of silently using the latest state."""

    history_config = create_run_config(source_thread_id)
    for snapshot in graph.get_state_history(history_config):
        saved_id = snapshot.config["configurable"].get("checkpoint_id")
        if saved_id == checkpoint_id:
            return snapshot
    raise TimeTravelError(
        f"线程 {source_thread_id} 中没有 Checkpoint：{checkpoint_id}"
    )


def prepare_branch_state(
    snapshot,
    *,
    source_thread_id: str,
    checkpoint_id: str,
    corrections: BranchCorrections,
) -> tuple[ResearchState, str]:
    """Build an independent state and choose the first node to rerun."""

    state: ResearchState = deepcopy(dict(snapshot.values))
    if not state:
        raise TimeTravelError("所选 Checkpoint 不包含可恢复的 State。")

    old_run_id = state.get("run_id", "")
    new_run_id = str(uuid4())
    state["run_id"] = new_run_id
    state["parent_thread_id"] = source_thread_id
    state["parent_checkpoint_id"] = checkpoint_id
    _inherit_accumulated_values(state, old_run_id, new_run_id)

    if corrections.changes_plan and corrections.changes_evidence:
        raise TimeTravelError("修改计划和修正资料需要分别创建分支。")
    if corrections.changes_plan:
        _apply_plan_change(state, corrections.plan)
        return state, "prepare_research"
    if corrections.changes_evidence:
        _apply_evidence_changes(state, corrections)
        return state, "research_evaluator"

    if not snapshot.next:
        raise TimeTravelError(
            "所选 Checkpoint 已执行完成；"
            "请提供计划或资料修正后再创建分支。"
        )
    if len(snapshot.next) != 1:
        raise TimeTravelError(
            "所选 Checkpoint 包含多个待执行节点，无法安全推断重放点。"
        )
    next_node = snapshot.next[0]
    predecessor_for(next_node)
    return state, next_node


def predecessor_for(next_node: str) -> str:
    """Return the node whose completion schedules ``next_node``."""

    predecessors = {
        "plan_approval": "planner",
        "prepare_research": "plan_approval",
        "research_worker": "prepare_research",
        "research_reducer": "research_worker",
        "research_evaluator": "research_reducer",
        "writer": "research_evaluator",
        "reviewer": "writer",
        "budget_exhausted": "research_evaluator",
    }
    predecessor = predecessors.get(next_node)
    if predecessor is None:
        raise TimeTravelError(f"暂不支持从节点 {next_node} 创建分支。")
    return predecessor


def _inherit_accumulated_values(
    state: ResearchState,
    old_run_id: str,
    new_run_id: str,
) -> None:
    """Move reused results and usage into the branch's independent run."""

    inherited_results = []
    for result in state.get("research_results", []):
        copied_result = deepcopy(result)
        if copied_result.get("run_id") == old_run_id:
            copied_result["run_id"] = new_run_id
        inherited_results.append(copied_result)
    state["research_results"] = inherited_results

    inherited_usage = []
    for event in state.get("usage_events", []):
        copied_event = deepcopy(event)
        if copied_event.get("run_id") == old_run_id:
            copied_event["run_id"] = new_run_id
            copied_event["inherited"] = True
        inherited_usage.append(copied_event)
    state["usage_events"] = inherited_usage


def _apply_plan_change(state: ResearchState, plan: tuple[str, ...]) -> None:
    """Keep Planner work but discard everything produced from the old plan."""

    clean_plan = [task.strip() for task in plan if task.strip()]
    if not clean_plan:
        raise TimeTravelError("修改后的研究计划不能为空。")
    if "plan" not in state:
        raise TimeTravelError("所选 Checkpoint 尚未产生研究计划。")

    state["plan"] = clean_plan
    state["plan_approved"] = True
    state["research_iteration"] = 0
    state["research_results"] = []
    state["usage_events"] = [
        event
        for event in state.get("usage_events", [])
        if event.get("run_id") == state["run_id"]
        and event.get("operation") == "Planner"
    ]
    state["manual_evidence"] = []
    _clear_fields(
        state,
        "research_content",
        "sources",
        "research_score",
        "research_comment",
        "draft",
        "review_score",
        "review_comment",
        "revision_count",
        "budget_exhausted",
        "termination_reason",
    )
    state["research_comment"] = ""
    state["review_comment"] = ""
    state["revision_count"] = 0
    state["budget_exhausted"] = False
    state["termination_reason"] = ""


def _apply_evidence_changes(
    state: ResearchState,
    corrections: BranchCorrections,
) -> None:
    """Correct collected evidence and discard only its downstream products."""

    if not state.get("research_content"):
        raise TimeTravelError("所选 Checkpoint 尚未产生研究资料。")

    content = state["research_content"]
    sources = list(state.get("sources", []))
    for source in corrections.remove_sources:
        clean_source = source.strip()
        if not clean_source:
            continue
        sources = [item for item in sources if item != clean_source]
        content = "\n".join(
            line for line in content.splitlines() if clean_source not in line
        )
    for text in corrections.remove_texts:
        content = content.replace(text, "")

    manual_evidence = list(state.get("manual_evidence", []))
    additions = [item.strip() for item in corrections.evidence if item.strip()]
    if additions:
        content = (
            f"{content.rstrip()}\n\n## 人工补充证据\n\n"
            + "\n\n".join(additions)
        )
        manual_evidence.extend(additions)
        for item in additions:
            sources.extend(URL_PATTERN.findall(item))

    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    if not content:
        raise TimeTravelError(
            "修正后没有剩余研究资料，无法进入评估节点。"
        )

    state["research_content"] = content
    state["sources"] = list(dict.fromkeys(sources))
    state["manual_evidence"] = manual_evidence
    state["usage_events"] = [
        event
        for event in state.get("usage_events", [])
        if event.get("run_id") == state["run_id"]
        and (
            event.get("operation") == "Planner"
            or str(event.get("operation", "")).startswith("Researcher ")
        )
    ]
    _correct_raw_research_results(state, corrections)
    _clear_fields(
        state,
        "research_score",
        "draft",
        "review_score",
    )
    state["research_comment"] = ""
    state["review_comment"] = ""
    state["revision_count"] = 0
    state["budget_exhausted"] = False
    state["termination_reason"] = ""


def _correct_raw_research_results(
    state: ResearchState,
    corrections: BranchCorrections,
) -> None:
    """Keep raw worker data consistent with the corrected merged evidence."""

    removed_sources = {
        source.strip()
        for source in corrections.remove_sources
        if source.strip()
    }
    for result in state.get("research_results", []):
        if result.get("run_id") != state["run_id"]:
            continue
        result["sources"] = [
            source
            for source in result.get("sources", [])
            if source not in removed_sources
        ]
        content = result.get("content", "")
        for source in removed_sources:
            content = "\n".join(
                line for line in content.splitlines() if source not in line
            )
        for text in corrections.remove_texts:
            content = content.replace(text, "")
        result["content"] = content.strip()


def _clear_fields(state: ResearchState, *field_names: str) -> None:
    """Remove stale downstream values from the copied state."""

    for field_name in field_names:
        state.pop(field_name, None)
