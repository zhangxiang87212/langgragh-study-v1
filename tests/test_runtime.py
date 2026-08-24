"""Tests for checkpoint run helpers."""

import unittest

from app.runtime import create_initial_state, create_run_config, create_thread_id


class RuntimeTests(unittest.TestCase):
    def test_create_thread_id_preserves_an_explicit_value(self) -> None:
        self.assertEqual(create_thread_id("  user-001  "), "user-001")

    def test_create_thread_id_generates_a_value_when_missing(self) -> None:
        self.assertTrue(create_thread_id())

    def test_create_run_config_uses_configurable_thread_id(self) -> None:
        config = create_run_config("user-001")

        self.assertEqual(config, {"configurable": {"thread_id": "user-001"}})

    def test_initial_state_resets_loop_control_fields(self) -> None:
        state = create_initial_state("测试主题")

        self.assertEqual(state["topic"], "测试主题")
        self.assertFalse(state["plan_approved"])
        self.assertEqual(state["research_comment"], "")
        self.assertEqual(state["research_iteration"], 0)
        self.assertEqual(state["review_comment"], "")
        self.assertEqual(state["revision_count"], 0)


if __name__ == "__main__":
    unittest.main()
