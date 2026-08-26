"""Command-line entry point for the Mini Research Agent."""

import argparse
import sys
from typing import Any

from langgraph.types import Command
from openai import OpenAIError

from app.checkpoints import (
    CheckpointConfigurationError,
    CheckpointSettings,
    open_checkpointer,
)
from app.config import ConfigurationError
from app.graph import build_graph
from app.output import save_result
from app.resilience import ResilienceConfigurationError, summarize_usage
from app.runtime import create_initial_state, create_run_config, create_thread_id
from app.streaming import run_graph_stream


DEFAULT_TOPIC = "AI Agent 在教育领域的发展趋势"


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Read a checkpoint command and its arguments."""

    parser = argparse.ArgumentParser(description="运行 Mini Research Agent")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="创建一个新的研究任务")
    run_parser.add_argument("topic", nargs="?", default=DEFAULT_TOPIC)
    run_parser.add_argument("--thread-id", help="任务的唯一线程 ID")

    resume_parser = commands.add_parser("resume", help="恢复暂停的研究任务")
    resume_parser.add_argument("--thread-id", required=True)
    decision = resume_parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true", help="批准原研究计划")
    decision.add_argument(
        "--plan",
        help="替换研究计划，多个任务使用分号分隔",
    )

    status_parser = commands.add_parser("status", help="查看任务当前状态")
    status_parser.add_argument("--thread-id", required=True)

    history_parser = commands.add_parser("history", help="查看任务快照历史")
    history_parser.add_argument("--thread-id", required=True)

    return parser.parse_args(arguments)


def main() -> None:
    """Open the configured checkpointer and execute one CLI command."""

    arguments = parse_arguments()
    try:
        checkpoint_settings = CheckpointSettings.from_env()
        with open_checkpointer(checkpoint_settings) as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            execute_command(graph, arguments)
    except (
        ConfigurationError,
        CheckpointConfigurationError,
        ResilienceConfigurationError,
    ) as error:
        print(f"配置错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error
    except OpenAIError as error:
        print(f"OpenAI API 调用失败：{error}", file=sys.stderr)
        raise SystemExit(1) from error


def execute_command(graph, arguments: argparse.Namespace) -> None:
    """Dispatch a parsed command to a small, focused handler."""

    if arguments.command == "run":
        run_new_research(graph, arguments.topic, arguments.thread_id)
    elif arguments.command == "resume":
        resume_research(
            graph,
            arguments.thread_id,
            approve=arguments.approve,
            revised_plan=arguments.plan,
        )
    elif arguments.command == "status":
        show_status(graph, arguments.thread_id)
    elif arguments.command == "history":
        show_history(graph, arguments.thread_id)


def run_new_research(graph, topic: str, supplied_thread_id: str | None) -> None:
    """Start a new thread and stop when human approval is required."""

    thread_id = create_thread_id(supplied_thread_id)
    config = create_run_config(thread_id)

    if graph.get_state(config).values:
        raise SystemExit(
            f"线程 {thread_id} 已存在。请更换 thread_id，或者使用 resume。"
        )

    clean_topic = topic.strip() or DEFAULT_TOPIC
    print(f"线程 ID：{thread_id}")
    result = run_graph_stream(
        graph,
        create_initial_state(clean_topic),
        config,
    )
    finish_or_report_interrupt(result, thread_id)


def resume_research(
    graph,
    thread_id: str,
    approve: bool,
    revised_plan: str | None,
) -> None:
    """Resume an interrupt or retry the next node after a failure."""

    config = create_run_config(create_thread_id(thread_id))
    snapshot = graph.get_state(config)
    require_existing_thread(snapshot, thread_id)

    if not snapshot.next:
        raise SystemExit(f"线程 {thread_id} 已经执行完成，无需恢复。")
    print(f"正在恢复线程：{thread_id}")

    if snapshot.next == ("plan_approval",):
        decision = create_plan_decision(approve, revised_plan)
        graph_input = Command(resume=decision)
    else:
        if approve or revised_plan is not None:
            waiting_nodes = ", ".join(snapshot.next)
            raise SystemExit(
                f"线程 {thread_id} 不在计划审批点，"
                f"待执行节点：{waiting_nodes}"
            )
        graph_input = None

    result = run_graph_stream(graph, graph_input, config)
    finish_or_report_interrupt(result, thread_id)


def create_plan_decision(
    approve: bool,
    revised_plan: str | None,
) -> dict[str, Any]:
    """Convert resume flags into the value returned by interrupt()."""

    if approve:
        return {"action": "approve"}
    if revised_plan is None:
        raise SystemExit("当前任务正在等待审批，请使用 --approve 或 --plan。")

    tasks = split_plan(revised_plan)
    if not tasks:
        raise SystemExit("修改后的研究计划不能为空。")
    return {"action": "edit", "plan": tasks}


def show_status(graph, thread_id: str) -> None:
    """Print the latest persisted state without running any graph node."""

    config = create_run_config(create_thread_id(thread_id))
    snapshot = graph.get_state(config)
    require_existing_thread(snapshot, thread_id)

    print(f"线程 ID：{thread_id}")
    print(f"研究主题：{snapshot.values.get('topic', '未知')}")
    print(f"当前状态：{describe_snapshot(snapshot)}")
    usage = summarize_usage(snapshot.values)
    print(
        f"资源用量：LLM {usage['llm_calls']} 次，"
        f"搜索 {usage['search_calls']} 次，"
        f"约 {usage['total_tokens']} tokens，"
        f"${usage['cost_usd']:.6f}"
    )
    if snapshot.next:
        print(f"下一节点：{', '.join(snapshot.next)}")


def show_history(graph, thread_id: str) -> None:
    """Print persisted checkpoints from the first snapshot to the latest."""

    config = create_run_config(create_thread_id(thread_id))
    snapshots = list(graph.get_state_history(config))
    if not snapshots:
        raise SystemExit(f"没有找到线程：{thread_id}")

    print(f"线程 {thread_id} 的 Checkpoint 历史：")
    for index, snapshot in enumerate(reversed(snapshots), start=1):
        checkpoint_id = snapshot.config["configurable"]["checkpoint_id"]
        step = snapshot.metadata.get("step", "未知")
        print(
            f"{index}. step={step} | {describe_snapshot(snapshot)} | "
            f"checkpoint_id={checkpoint_id}"
        )


def require_existing_thread(snapshot, thread_id: str) -> None:
    """Stop a command when its thread has no persisted state."""

    if not snapshot.values:
        raise SystemExit(f"没有找到线程：{thread_id}")


def describe_snapshot(snapshot) -> str:
    """Turn a StateSnapshot into a short status label."""

    if snapshot.next == ("plan_approval",):
        return "等待人工审批"
    if snapshot.next:
        return "等待继续执行"
    return "已完成"


def split_plan(raw_plan: str) -> list[str]:
    """Split a command-line plan on Chinese or English semicolons."""

    return [
        task.strip()
        for task in raw_plan.replace("；", ";").split(";")
        if task.strip()
    ]


def finish_or_report_interrupt(result: dict[str, Any], thread_id: str) -> None:
    """Save a completed report or explain how to resume an interrupt."""

    if "__interrupt__" in result:
        interrupt_value = result["__interrupt__"][0].value
        print(interrupt_value["question"])
        for index, task in enumerate(interrupt_value["plan"], start=1):
            print(f"{index}. {task}")
        print("任务已持久化，可以退出程序后再恢复。")
        print(
            "批准命令：python -m app.main resume "
            f"--thread-id {thread_id} --approve"
        )
        return

    output_path = save_result(result)
    print(f"执行完成，结果已写入：{output_path}")


if __name__ == "__main__":
    main()
