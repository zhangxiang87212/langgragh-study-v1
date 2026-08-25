"""Tests for persistent checkpoint configuration and recovery."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from langgraph.types import Command

from app.checkpoints import (
    CheckpointConfigurationError,
    CheckpointSettings,
    open_checkpointer,
)
from app.graph import build_graph
from app.runtime import create_initial_state, create_run_config
from tests.fakes import FakeResearchLLM


class CheckpointSettingsTests(unittest.TestCase):
    @patch("app.checkpoints.load_dotenv")
    def test_sqlite_is_the_default_backend(self, _load_dotenv) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = CheckpointSettings.from_env()

        self.assertEqual(settings.backend, "sqlite")
        self.assertEqual(
            settings.database_path,
            Path("checkpoints/research.sqlite"),
        )

    @patch("app.checkpoints.load_dotenv")
    def test_memory_backend_can_be_selected(self, _load_dotenv) -> None:
        environment = {"CHECKPOINT_BACKEND": "memory"}

        with patch.dict(os.environ, environment, clear=True):
            settings = CheckpointSettings.from_env()

        self.assertEqual(settings.backend, "memory")

    @patch("app.checkpoints.load_dotenv")
    def test_unknown_backend_has_a_clear_error(self, _load_dotenv) -> None:
        environment = {"CHECKPOINT_BACKEND": "unknown"}

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(
                CheckpointConfigurationError,
                "CHECKPOINT_BACKEND",
            ):
                CheckpointSettings.from_env()


class SqliteRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_llm = FakeResearchLLM()
        self.llm_patcher = patch("app.nodes.llm", self.fake_llm)
        self.llm_patcher.start()

    def tearDown(self) -> None:
        self.llm_patcher.stop()

    def test_reopening_database_recovers_a_paused_thread(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = CheckpointSettings(
                backend="sqlite",
                database_path=Path(temporary_directory) / "checkpoint.sqlite",
            )
            config = create_run_config("persistent-thread")

            with open_checkpointer(settings) as first_checkpointer:
                first_graph = build_graph(checkpointer=first_checkpointer)
                paused_result = first_graph.invoke(
                    create_initial_state("跨进程恢复测试"),
                    config=config,
                )

                self.assertIn("__interrupt__", paused_result)
                self.assertEqual(self.fake_llm.plan_calls, 1)

            with open_checkpointer(settings) as second_checkpointer:
                second_graph = build_graph(checkpointer=second_checkpointer)
                recovered_snapshot = second_graph.get_state(config)

                self.assertEqual(
                    recovered_snapshot.values["topic"],
                    "跨进程恢复测试",
                )
                self.assertEqual(recovered_snapshot.next, ("plan_approval",))

                result = second_graph.invoke(
                    Command(resume={"action": "approve"}),
                    config=config,
                )

            self.assertEqual(result["review_score"], 85)
            self.assertEqual(self.fake_llm.plan_calls, 1)
            self.assertEqual(self.fake_llm.research_calls, 1)

    def test_sqlite_keeps_threads_independent(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = CheckpointSettings(
                backend="sqlite",
                database_path=Path(temporary_directory) / "checkpoint.sqlite",
            )
            first_config = create_run_config("first-thread")
            second_config = create_run_config("second-thread")

            with open_checkpointer(settings) as checkpointer:
                graph = build_graph(checkpointer=checkpointer)
                graph.invoke(create_initial_state("主题一"), config=first_config)
                graph.invoke(create_initial_state("主题二"), config=second_config)

            with open_checkpointer(settings) as checkpointer:
                graph = build_graph(checkpointer=checkpointer)
                first_topic = graph.get_state(first_config).values["topic"]
                second_topic = graph.get_state(second_config).values["topic"]

            self.assertEqual(first_topic, "主题一")
            self.assertEqual(second_topic, "主题二")

    def test_reopening_database_retries_only_the_failed_node(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = CheckpointSettings(
                backend="sqlite",
                database_path=Path(temporary_directory) / "checkpoint.sqlite",
            )
            config = create_run_config("failed-thread")
            working_research_method = self.fake_llm.research

            with open_checkpointer(settings) as first_checkpointer:
                first_graph = build_graph(checkpointer=first_checkpointer)
                first_graph.invoke(
                    create_initial_state("失败恢复测试"),
                    config=config,
                )
                self.fake_llm.research = Mock(
                    side_effect=RuntimeError("模拟网络错误")
                )

                with self.assertRaisesRegex(RuntimeError, "模拟网络错误"):
                    first_graph.invoke(
                        Command(resume={"action": "approve"}),
                        config=config,
                    )

                self.assertEqual(first_graph.get_state(config).next, ("researcher",))

            self.fake_llm.research = working_research_method
            with open_checkpointer(settings) as second_checkpointer:
                second_graph = build_graph(checkpointer=second_checkpointer)
                result = second_graph.invoke(None, config=config)

            self.assertEqual(result["review_score"], 85)
            self.assertEqual(self.fake_llm.plan_calls, 1)
            self.assertEqual(self.fake_llm.research_calls, 1)


if __name__ == "__main__":
    unittest.main()
