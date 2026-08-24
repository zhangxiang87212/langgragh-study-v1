"""Command-line entry point for the Mini Research Agent."""

import sys

from app.graph import graph


DEFAULT_TOPIC = "AI Agent 在教育领域的发展趋势"


def main() -> None:
    """Run the graph once and print the final state in a readable form."""

    topic = " ".join(sys.argv[1:]).strip() or DEFAULT_TOPIC
    result = graph.invoke({"topic": topic})

    print("\n最终报告：\n")
    print(result["draft"])
    print(f"\n审核分数：{result['review_score']}")
    print(f"审核意见：{result['review_comment']}")


if __name__ == "__main__":
    main()
