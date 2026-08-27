"""Tests for read-only checkpoint evidence inspection."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from app.inspection import (
    InspectionError,
    build_inspection_document,
    load_inspection_snapshot,
    save_inspection_document,
)


class InspectionTests(unittest.TestCase):
    def test_document_maps_each_worker_to_its_sources_and_flags_gaps(self) -> None:
        snapshot = self.create_snapshot()

        document = build_inspection_document(
            snapshot,
            thread_id="inspection-thread",
        )

        self.assertIn("Checkpoint ID：checkpoint-001", document)
        self.assertIn("Research Evaluator 评分为 65", document)
        self.assertIn("任务二", document)
        self.assertIn("以下 Worker 没有返回来源", document)
        self.assertIn("https://official.example/data", document)
        self.assertIn("人工核验清单", document)
        self.assertIn("python -m app.main fork", document)

    def test_latest_snapshot_is_loaded_without_running_the_graph(self) -> None:
        graph = Mock()
        snapshot = self.create_snapshot()
        graph.get_state.return_value = snapshot

        loaded = load_inspection_snapshot(
            graph,
            thread_id="inspection-thread",
            checkpoint_id=None,
        )

        self.assertIs(loaded, snapshot)
        graph.invoke.assert_not_called()
        graph.stream.assert_not_called()

    def test_export_refuses_to_overwrite_an_existing_review(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "review.md"
            save_inspection_document("第一次审查", output_path)

            with self.assertRaisesRegex(InspectionError, "不会覆盖"):
                save_inspection_document("第二次审查", output_path)

            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "第一次审查",
            )

    @staticmethod
    def create_snapshot() -> SimpleNamespace:
        return SimpleNamespace(
            values={
                "topic": "资料审查测试",
                "run_id": "run-001",
                "plan": ["任务一", "任务二"],
                "research_content": "合并后的研究资料",
                "sources": ["https://official.example/data"],
                "research_score": 65,
                "research_comment": "任务二缺少来源。",
                "research_results": [
                    {
                        "run_id": "run-001",
                        "research_iteration": 1,
                        "task_index": 0,
                        "task": "任务一",
                        "content": "有来源的研究资料。",
                        "sources": ["https://official.example/data"],
                    },
                    {
                        "run_id": "run-001",
                        "research_iteration": 1,
                        "task_index": 1,
                        "task": "任务二",
                        "content": "缺少来源的研究资料。",
                        "sources": [],
                    },
                ],
            },
            config={
                "configurable": {
                    "thread_id": "inspection-thread",
                    "checkpoint_id": "checkpoint-001",
                }
            },
            metadata={"step": 7},
            next=("writer",),
        )


if __name__ == "__main__":
    unittest.main()
