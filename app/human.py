"""Console interaction for reviewing a generated research plan."""

from typing import Any


def ask_for_plan_review(interrupt_value: dict[str, Any]) -> dict[str, Any]:
    """Show the proposed plan and return a serializable human decision."""

    print(interrupt_value["question"])
    for index, task in enumerate(interrupt_value["plan"], start=1):
        print(f"{index}. {task}")

    while True:
        answer = input(
            "按 Enter 确认；如需修改，请输入用分号分隔的新任务：\n> "
        ).strip()

        if not answer:
            return {"action": "approve"}

        revised_plan = [
            task.strip()
            for task in answer.replace("；", ";").split(";")
            if task.strip()
        ]
        if revised_plan:
            return {
                "action": "edit",
                "plan": revised_plan,
            }

        print("修改后的计划不能为空，请重新输入。")
