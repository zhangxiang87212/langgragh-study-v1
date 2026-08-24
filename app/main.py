"""Command-line entry point for the Mini Research Agent."""

import argparse
import sys

from langgraph.types import Command
from openai import OpenAIError

from app.config import ConfigurationError
from app.graph import graph
from app.human import ask_for_plan_review
from app.output import save_result
from app.runtime import create_initial_state, create_run_config, create_thread_id


DEFAULT_TOPIC = "AI Agent 在教育领域的发展趋势"


def parse_arguments() -> argparse.Namespace:
    """Read the research topic and optional checkpoint thread ID."""

    parser = argparse.ArgumentParser(description="运行 Mini Research Agent")
    parser.add_argument("topic", nargs="?", default=DEFAULT_TOPIC, help="研究主题")
    parser.add_argument("--thread-id", help="用于关联 Checkpoint 的线程 ID")
    return parser.parse_args()


def main() -> None:
    """Run the graph once and save the final state as a Markdown file."""

    arguments = parse_arguments()
    topic = arguments.topic.strip() or DEFAULT_TOPIC
    thread_id = create_thread_id(arguments.thread_id)
    config = create_run_config(thread_id)

    print(f"线程 ID：{thread_id}")
    try:
        result = graph.invoke(create_initial_state(topic), config=config)
        while "__interrupt__" in result:
            current_interrupt = result["__interrupt__"][0]
            decision = ask_for_plan_review(current_interrupt.value)
            result = graph.invoke(Command(resume=decision), config=config)
    except ConfigurationError as error:
        print(f"配置错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error
    except OpenAIError as error:
        print(f"OpenAI API 调用失败：{error}", file=sys.stderr)
        raise SystemExit(1) from error

    output_path = save_result(result)
    print(f"执行完成，结果已写入：{output_path}")


if __name__ == "__main__":
    main()
