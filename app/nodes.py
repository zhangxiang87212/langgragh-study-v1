"""Node functions for the first-stage research workflow.

These nodes deliberately use deterministic Python code instead of a real
language model. That keeps the first stage focused on State, Node, and Edge.
"""

from app.state import ResearchState


def planner_node(state: ResearchState) -> dict[str, list[str]]:
    """Break the topic into a small, fixed research plan."""

    topic = state["topic"]
    print(f"正在规划研究任务：{topic}")

    plan = [
        "分析研究背景",
        "梳理当前应用",
        "总结主要问题",
        "判断未来趋势",
    ]
    return {"plan": plan}


def researcher_node(state: ResearchState) -> dict[str, str]:
    """Create placeholder research notes for every item in the plan."""

    print("正在研究...")

    plan = state["plan"]
    research_notes = [
        f"{index}. {item}：这里是与该任务相关的研究资料。"
        for index, item in enumerate(plan, start=1)
    ]
    research_content = "\n".join(research_notes)

    return {"research_content": research_content}


def writer_node(state: ResearchState) -> dict[str, str]:
    """Turn the collected notes into a simple report draft."""

    print("正在生成报告...")

    topic = state["topic"]
    research_content = state["research_content"]
    draft = (
        f"# {topic}\n\n"
        "## 研究内容\n\n"
        f"{research_content}\n\n"
        "## 初步结论\n\n"
        "综合以上资料，可以发现该主题仍值得继续跟踪和深入研究。"
    )

    return {"draft": draft}


def reviewer_node(state: ResearchState) -> dict[str, int | str]:
    """Perform a small deterministic quality check on the report."""

    print("正在审核报告...")

    draft = state["draft"]
    has_title = draft.startswith("# ")
    has_conclusion = "## 初步结论" in draft

    if has_title and has_conclusion:
        return {
            "review_score": 85,
            "review_comment": "报告结构基本完整。",
        }

    return {
        "review_score": 60,
        "review_comment": "报告缺少标题或结论。",
    }
