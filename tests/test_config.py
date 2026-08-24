"""Tests for application settings."""

import os
import unittest
from unittest.mock import patch

from app.config import (
    ConfigurationError,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_SEARCH_MODEL,
    Settings,
)


class SettingsTests(unittest.TestCase):
    @patch("app.config.load_dotenv")
    def test_missing_api_key_has_a_clear_error(self, _load_dotenv) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "OPENAI_API_KEY"):
                Settings.from_env()

    @patch("app.config.load_dotenv")
    def test_blank_model_uses_the_default(self, _load_dotenv) -> None:
        environment = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.openai_api_key, "test-key")
        self.assertEqual(settings.openai_model, DEFAULT_OPENAI_MODEL)
        self.assertEqual(settings.openai_search_model, DEFAULT_OPENAI_SEARCH_MODEL)


if __name__ == "__main__":
    unittest.main()
