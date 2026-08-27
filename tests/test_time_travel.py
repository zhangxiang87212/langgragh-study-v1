"""Tests for checkpoint replay and human-corrected branches."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.checkpoints import CheckpointSettings, open_checkpointer
from app.graph import build_graph
from app.runtime import create_initial_state, create_run_config
from app.time_travel import BranchCorrections, create_corrected_branch
from tests.fakes import FakeResearchLLM


class TimeTravelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_llm = FakeResearchLLM()
        self.llm_patcher = patch("app.nodes.llm", self.fake_llm)
        self.llm_patcher.start()
        self.graph = build_graph(checkpointer=InMemorySaver())

    def tearDown(self) -> None:
        self.llm_patcher.stop()

    def test_changed_plan_skips_planner_and_uses_a_new_thread(self) -> None:
        source_config = create_run_config("source-plan-thread")
        self.graph.invoke(
            create_initial_state("时间旅行计划测试"),
            config=source_config,
        )
        source_snapshot = self.graph.get_state(source_config)
        checkpoint_id = source_snapshot.config["configurable"]["checkpoint_id"]
        original_plan = list(source_snapshot.values["plan"])
        original_run_id = source_snapshot.values["run_id"]

        branch = create_corrected_branch(
            self.graph,
            source_thread_id="source-plan-thread",
            checkpoint_id=checkpoint_id,
            new_thread_id="changed-plan-thread",
            corrections=BranchCorrections(plan=("只研究人工指定任务",)),
        )
        result = self.graph.invoke(None, config=branch.config)

        self.assertEqual(result["plan"], ["只研究人工指定任务"])
        self.assertEqual(self.fake_llm.plan_calls, 1)
        self.assertEqual(self.fake_llm.research_calls, 1)
        self.assertNotEqual(result["run_id"], original_run_id)
        self.assertEqual(result["parent_thread_id"], "source-plan-thread")
        self.assertEqual(result["parent_checkpoint_id"], checkpoint_id)
        self.assertEqual(
            self.graph.get_state(source_config).values["plan"],
            original_plan,
        )

    def test_corrected_evidence_skips_planner_and_research_workers(self) -> None:
        source_config = create_run_config("source-evidence-thread")
        self.graph.invoke(
            create_initial_state("时间旅行资料测试"),
            config=source_config,
        )
        original = self.graph.invoke(
            Command(resume={"action": "approve"}),
            config=source_config,
        )
        source_snapshot = self.graph.get_state(source_config)
        checkpoint_id = source_snapshot.config["configurable"]["checkpoint_id"]

        branch = create_corrected_branch(
            self.graph,
            source_thread_id="source-evidence-thread",
            checkpoint_id=checkpoint_id,
            new_thread_id="corrected-evidence-thread",
            corrections=BranchCorrections(
                remove_sources=("https://example.com/research",),
                evidence=(
                    "人工核验的数据，来源 https://human.example/evidence",
                ),
            ),
        )
        result = self.graph.invoke(None, config=branch.config)

        self.assertEqual(self.fake_llm.plan_calls, 1)
        self.assertEqual(self.fake_llm.research_calls, 4)
        self.assertEqual(self.fake_llm.research_evaluation_calls, 2)
        self.assertNotIn("https://example.com/research", result["sources"])
        self.assertIn("https://human.example/evidence", result["sources"])
        self.assertIn("## 人工补充证据", result["research_content"])
        self.assertEqual(
            original["sources"],
            self.graph.get_state(source_config).values["sources"],
        )

    def test_sqlite_persists_a_branch_created_after_reopening(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = CheckpointSettings(
                backend="sqlite",
                database_path=(
                    Path(temporary_directory) / "time-travel.sqlite"
                ),
            )
            source_config = create_run_config("sqlite-source-thread")

            with open_checkpointer(settings) as checkpointer:
                graph = build_graph(checkpointer=checkpointer)
                graph.invoke(
                    create_initial_state("SQLite 时间旅行测试"),
                    config=source_config,
                )
                graph.invoke(
                    Command(resume={"action": "approve"}),
                    config=source_config,
                )
                source_snapshot = graph.get_state(source_config)
                checkpoint_id = source_snapshot.config["configurable"][
                    "checkpoint_id"
                ]

            with open_checkpointer(settings) as checkpointer:
                graph = build_graph(checkpointer=checkpointer)
                branch = create_corrected_branch(
                    graph,
                    source_thread_id="sqlite-source-thread",
                    checkpoint_id=checkpoint_id,
                    new_thread_id="sqlite-branch-thread",
                    corrections=BranchCorrections(
                        evidence=("人工补充的持久化证据",),
                    ),
                )
                graph.invoke(None, config=branch.config)

            with open_checkpointer(settings) as checkpointer:
                graph = build_graph(checkpointer=checkpointer)
                persisted = graph.get_state(
                    create_run_config("sqlite-branch-thread")
                ).values

            self.assertEqual(
                persisted["parent_thread_id"],
                "sqlite-source-thread",
            )
            self.assertIn(
                "人工补充的持久化证据",
                persisted["research_content"],
            )
            self.assertEqual(self.fake_llm.plan_calls, 1)
            self.assertEqual(self.fake_llm.research_calls, 4)


if __name__ == "__main__":
    unittest.main()
