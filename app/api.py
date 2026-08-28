"""FastAPI router and SSE endpoints for Mini Research Agent."""

import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, AsyncIterator, List, Optional

from fastapi import APIRouter, HTTPException, Query
from langgraph.types import Command
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.checkpoints import (
    CheckpointConfigurationError,
    CheckpointSettings,
    open_checkpointer,
)
from app.config import ConfigurationError, Settings
from app.graph import build_graph
from app.inspection import (
    InspectionError,
    build_inspection_document,
    load_inspection_snapshot,
)
from app.resilience import (
    ResilienceConfigurationError,
    ResilienceSettings,
    summarize_usage,
)
from app.runtime import create_initial_state, create_run_config, create_thread_id
from app.streaming import STREAM_MODES
from app.time_travel import (
    BranchCorrections,
    TimeTravelError,
    create_corrected_branch,
    find_checkpoint,
)

router = APIRouter(prefix="/api")

# 全局单例 checkpointer 和 graph
_checkpoint_settings: Optional[CheckpointSettings] = None
_checkpointer_cm = None
_checkpointer = None
_graph = None


def get_graph():
    """Lazily initialize and return the global compiled LangGraph."""
    global _checkpoint_settings, _checkpointer_cm, _checkpointer, _graph
    if _graph is None:
        _checkpoint_settings = CheckpointSettings.from_env()
        _checkpointer_cm = open_checkpointer(_checkpoint_settings)
        _checkpointer = _checkpointer_cm.__enter__()
        _graph = build_graph(checkpointer=_checkpointer)
    return _graph


def close_graph():
    """Clean up checkpointer resources on application shutdown."""
    global _checkpointer_cm
    if _checkpointer_cm is not None:
        try:
            _checkpointer_cm.__exit__(None, None, None)
        except Exception:
            pass


# ---------------- Models ---------------- #

class RunRequest(BaseModel):
    topic: str = Field(default="AI Agent 在教育领域的发展趋势", description="研究主题")
    thread_id: Optional[str] = Field(default=None, description="任务线程 ID")


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="任务线程 ID")
    approved: bool = Field(default=True, description="是否批准原研究计划")
    plan: Optional[List[str]] = Field(default=None, description="修改后的研究计划列表")


class ForkRequest(BaseModel):
    source_thread_id: str = Field(..., description="原任务线程 ID")
    checkpoint_id: str = Field(..., description="分叉起点的 Checkpoint ID")
    new_thread_id: Optional[str] = Field(default=None, description="新分支线程 ID")
    revised_plan: Optional[List[str]] = Field(default=None, description="替换研究计划")
    remove_sources: Optional[List[str]] = Field(default=None, description="删除的错误来源 URL")
    remove_texts: Optional[List[str]] = Field(default=None, description="删除的资料文字")
    manual_evidence: Optional[List[str]] = Field(default=None, description="补充的人工证据")


# ---------------- API Endpoints ---------------- #

@router.get("/config")
def get_system_config():
    """Return runtime configuration and LLM settings."""
    try:
        settings = Settings.from_env()
        res_settings = ResilienceSettings.from_env()
        cp_settings = CheckpointSettings.from_env()
        model_name = settings.openai_model if settings.llm_provider == "openai" else settings.deepseek_model
        return {
            "provider": settings.llm_provider,
            "model": model_name,
            "search_max_rounds": res_settings.max_search_rounds,
            "llm_max_calls": res_settings.max_llm_calls,
            "max_total_tokens": res_settings.max_total_tokens,
            "max_cost_usd": res_settings.max_cost_usd,
            "node_timeout_seconds": res_settings.node_timeout_seconds,
            "checkpoint_backend": cp_settings.backend,
            "checkpoint_db_path": str(cp_settings.database_path),
        }
    except Exception as e:
        return {
            "error": str(e),
            "checkpoint_backend": "sqlite",
        }


@router.get("/research/threads")
def list_threads():
    """List all research threads recorded in the SQLite checkpointer."""
    try:
        cp_settings = CheckpointSettings.from_env()
        if cp_settings.backend != "sqlite" or not cp_settings.database_path.exists():
            return {"threads": []}

        graph = get_graph()
        # Query distinct threads from SQLite checkpoints table
        conn = sqlite3.connect(str(cp_settings.database_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT thread_id, MAX(checkpoint_id) as last_cp
            FROM checkpoints
            GROUP BY thread_id
            ORDER BY last_cp DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()

        threads = []
        for thread_id, _ in rows:
            try:
                snapshot = graph.get_state(create_run_config(thread_id))
                values = snapshot.values or {}
                if not values:
                    continue
                
                # Check status
                is_interrupted = bool(snapshot.next and "plan_approval" in snapshot.next)
                is_finished = not bool(snapshot.next)
                status = "waiting_approval" if is_interrupted else ("completed" if is_finished else "running")

                usage = summarize_usage(values)

                threads.append({
                    "thread_id": thread_id,
                    "topic": values.get("topic", "未命名研究"),
                    "status": status,
                    "next_nodes": list(snapshot.next),
                    "created_at": snapshot.config["configurable"].get("checkpoint_id"),
                    "plan": values.get("plan", []),
                    "plan_approved": values.get("plan_approved", False),
                    "has_draft": bool(values.get("draft")),
                    "review_score": values.get("review_score"),
                    "usage": usage,
                    "parent_thread_id": values.get("parent_thread_id"),
                })
            except Exception:
                continue

        return {"threads": threads}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"获取线程列表失败: {error}")


@router.post("/research/run")
def start_research(request: RunRequest):
    """Start or initialize a new research task thread."""
    thread_id = request.thread_id or create_thread_id()
    graph = get_graph()
    
    # Check if thread already exists
    existing = graph.get_state(create_run_config(thread_id)).values
    if existing:
        return {"thread_id": thread_id, "status": "exists", "message": "线程已存在"}

    initial_state = create_initial_state(
        topic=request.topic,
    )
    return {
        "thread_id": thread_id,
        "topic": request.topic,
        "status": "ready",
        "initial_state": initial_state,
    }


@router.get("/research/{thread_id}/status")
def get_research_status(thread_id: str):
    """Get current snapshot, state variables, next nodes, and usage for a thread."""
    graph = get_graph()
    config = create_run_config(thread_id)
    snapshot = graph.get_state(config)
    
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"未找到线程 {thread_id}")

    values = dict(snapshot.values)
    current_run_id = values.get("run_id")
    research_results = [
        r for r in values.get("research_results", [])
        if r.get("run_id") == current_run_id
    ]

    is_interrupted = bool(snapshot.next and "plan_approval" in snapshot.next)
    is_finished = not bool(snapshot.next)
    status = "waiting_approval" if is_interrupted else ("completed" if is_finished else "running")

    usage = summarize_usage(values)

    return {
        "thread_id": thread_id,
        "checkpoint_id": snapshot.config["configurable"].get("checkpoint_id"),
        "step": snapshot.metadata.get("step"),
        "status": status,
        "next_nodes": list(snapshot.next),
        "topic": values.get("topic"),
        "plan": values.get("plan", []),
        "plan_approved": values.get("plan_approved", False),
        "research_results": research_results,
        "research_content": values.get("research_content"),
        "sources": values.get("sources", []),
        "research_score": values.get("research_score"),
        "research_comment": values.get("research_comment"),
        "draft": values.get("draft"),
        "review_score": values.get("review_score"),
        "review_comment": values.get("review_comment"),
        "revision_count": values.get("revision_count", 0),
        "budget_exhausted": values.get("budget_exhausted", False),
        "termination_reason": values.get("termination_reason"),
        "usage": usage,
        "parent_thread_id": values.get("parent_thread_id"),
        "parent_checkpoint_id": values.get("parent_checkpoint_id"),
        "manual_evidence": values.get("manual_evidence", []),
    }


@router.get("/research/{thread_id}/history")
def get_research_history(thread_id: str):
    """Retrieve the full checkpoint history list for time travel visualization."""
    graph = get_graph()
    config = create_run_config(thread_id)
    try:
        history_snapshots = list(graph.get_state_history(config))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {e}")

    history = []
    for snapshot in history_snapshots:
        cp_id = snapshot.config["configurable"].get("checkpoint_id")
        parent_cp_id = snapshot.parent_config["configurable"].get("checkpoint_id") if snapshot.parent_config else None
        step = snapshot.metadata.get("step")
        next_nodes = list(snapshot.next)
        values = snapshot.values or {}

        history.append({
            "checkpoint_id": cp_id,
            "parent_checkpoint_id": parent_cp_id,
            "step": step,
            "next_nodes": next_nodes,
            "topic": values.get("topic"),
            "plan_count": len(values.get("plan", [])),
            "research_score": values.get("research_score"),
            "has_draft": bool(values.get("draft")),
            "review_score": values.get("review_score"),
            "created_at": snapshot.metadata.get("created_at") or cp_id,
        })

    return {"thread_id": thread_id, "history": history}


@router.get("/research/{thread_id}/inspect")
def inspect_checkpoint(
    thread_id: str,
    checkpoint_id: Optional[str] = Query(None, description="历史 Checkpoint ID"),
):
    """Inspect research sources, evaluation, and worker outputs at a specific checkpoint."""
    graph = get_graph()
    try:
        snapshot = load_inspection_snapshot(
            graph,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
        )
        document = build_inspection_document(snapshot, thread_id=thread_id)
    except InspectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审查快照失败: {e}")

    values = dict(snapshot.values)
    current_run_id = values.get("run_id")
    research_results = [
        r for r in values.get("research_results", [])
        if r.get("run_id") == current_run_id
    ]

    return {
        "thread_id": thread_id,
        "checkpoint_id": snapshot.config["configurable"].get("checkpoint_id"),
        "step": snapshot.metadata.get("step"),
        "next_nodes": list(snapshot.next),
        "topic": values.get("topic"),
        "plan": values.get("plan", []),
        "research_results": research_results,
        "sources": values.get("sources", []),
        "research_score": values.get("research_score"),
        "research_comment": values.get("research_comment"),
        "document": document,
    }


@router.post("/research/fork")
def fork_research(request: ForkRequest):
    """Create a corrected branch from a historical checkpoint."""
    graph = get_graph()
    new_thread_id = request.new_thread_id or f"{request.source_thread_id}-fork-{create_thread_id()[:6]}"
    
    corrections = BranchCorrections(
        plan=tuple(request.revised_plan or ()),
        remove_sources=tuple(request.remove_sources or ()),
        remove_texts=tuple(request.remove_texts or ()),
        evidence=tuple(request.manual_evidence or ()),
    )

    try:
        created_branch = create_corrected_branch(
            graph,
            source_thread_id=request.source_thread_id,
            checkpoint_id=request.checkpoint_id,
            new_thread_id=new_thread_id,
            corrections=corrections,
        )
    except TimeTravelError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建分支失败: {e}")

    return {
        "source_thread_id": request.source_thread_id,
        "source_checkpoint_id": request.checkpoint_id,
        "new_thread_id": created_branch.thread_id,
        "next_node": created_branch.next_node,
    }


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize data structures, stripping internal keys and serializing non-standard objects."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {
            str(k): sanitize_for_json(v)
            for k, v in obj.items()
            if not str(k).startswith("__")
        }
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, "value"):
        return sanitize_for_json(getattr(obj, "value"))
    if hasattr(obj, "to_dict"):
        return sanitize_for_json(obj.to_dict())
    if hasattr(obj, "__dict__"):
        return sanitize_for_json(obj.__dict__)
    return str(obj)


def safe_json_dumps(obj: Any) -> str:
    """Serialize objects to JSON safely without failing on Interrupts or custom types."""
    cleaned = sanitize_for_json(obj)
    return json.dumps(cleaned, ensure_ascii=False)


@router.get("/research/{thread_id}/stream")
async def stream_research(
    thread_id: str,
    action: str = Query("run", description="Action: run, resume, or replay"),
    topic: Optional[str] = Query(None, description="Topic when action is run"),
    approve: bool = Query(True, description="Approve plan when action is resume"),
    plan: Optional[str] = Query(None, description="Semicolon-separated revised plan tasks"),
):
    """SSE endpoint delivering real-time execution events."""
    graph = get_graph()
    config = create_run_config(thread_id)

    # Determine graph input based on action
    graph_input = None
    if action == "run":
        existing = graph.get_state(config).values
        if not existing:
            graph_input = create_initial_state(
                topic=topic or "AI Agent 在教育领域的发展趋势",
            )
        else:
            graph_input = None
    elif action == "resume":
        if approve:
            graph_input = Command(resume={"approved": True})
        else:
            plan_list = [p.strip() for p in (plan or "").split(";") if p.strip()]
            graph_input = Command(resume={"approved": False, "plan": plan_list})
    elif action == "replay":
        graph_input = None

    async def event_generator() -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def stream_worker():
            try:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"event": "status", "data": {"status": "started", "thread_id": thread_id}}
                )

                for part in graph.stream(
                    graph_input,
                    config=config,
                    stream_mode=STREAM_MODES,
                    version="v2",
                ):
                    part_type = part.get("type")
                    data = part.get("data")
                    
                    if part_type == "custom":
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"event": "custom", "data": data}
                        )
                    elif part_type == "updates":
                        # Filter out internal keys like __interrupt__ or __metadata__
                        clean_updates = {}
                        if isinstance(data, dict):
                            for node_name, node_val in data.items():
                                if node_name.startswith("__"):
                                    continue
                                clean_updates[node_name] = node_val
                        if clean_updates:
                            loop.call_soon_threadsafe(
                                queue.put_nowait,
                                {"event": "updates", "data": clean_updates}
                            )

                snapshot = graph.get_state(config)
                values = dict(snapshot.values or {})
                is_interrupted = bool(snapshot.next and "plan_approval" in snapshot.next)
                is_finished = not bool(snapshot.next)

                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "event": "completed",
                        "data": {
                            "status": "waiting_approval" if is_interrupted else ("completed" if is_finished else "running"),
                            "next_nodes": list(snapshot.next),
                            "plan": values.get("plan", []),
                            "draft": values.get("draft"),
                            "review_score": values.get("review_score"),
                            "review_comment": values.get("review_comment"),
                            "sources": values.get("sources", []),
                            "usage": summarize_usage(values),
                        }
                    }
                )
            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"event": "error", "data": {"error": str(e)}}
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        worker_task = asyncio.create_task(asyncio.to_thread(stream_worker))

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield {
                    "event": item["event"],
                    "data": safe_json_dumps(item["data"]),
                }
        finally:
            await worker_task

    return EventSourceResponse(event_generator())
