"""Tests for application settings."""

import os
import unittest
from unittest.mock import patch

from app.config import (
    ConfigurationError,
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_LLM_PROVIDER,
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
        self.assertEqual(settings.llm_provider, DEFAULT_LLM_PROVIDER)
        self.assertEqual(settings.openai_model, DEFAULT_OPENAI_MODEL)
        self.assertEqual(settings.openai_search_model, DEFAULT_OPENAI_SEARCH_MODEL)
        self.assertEqual(settings.deepseek_model, DEFAULT_DEEPSEEK_MODEL)
        self.assertEqual(settings.deepseek_base_url, DEFAULT_DEEPSEEK_BASE_URL)

    @patch("app.config.load_dotenv")
    def test_deepseek_provider_requires_its_api_key(self, _load_dotenv) -> None:
        environment = {
            "LLM_PROVIDER": "deepseek",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "DEEPSEEK_API_KEY"):
                Settings.from_env()

    @patch("app.config.load_dotenv")
    def test_deepseek_settings_are_loaded(self, _load_dotenv) -> None:
        environment = {
            "LLM_PROVIDER": "DEEPSEEK",
            "DEEPSEEK_API_KEY": "deepseek-test-key",
            "DEEPSEEK_MODEL": "deepseek-test-model",
            "DEEPSEEK_BASE_URL": "https://deepseek.example.com",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.llm_provider, "deepseek")
        self.assertIsNone(settings.openai_api_key)
        self.assertEqual(settings.deepseek_api_key, "deepseek-test-key")
        self.assertEqual(settings.deepseek_model, "deepseek-test-model")
        self.assertEqual(
            settings.deepseek_base_url,
            "https://deepseek.example.com",
        )

    @patch("app.config.load_dotenv")
    def test_unknown_provider_has_a_clear_error(self, _load_dotenv) -> None:
        environment = {
            "LLM_PROVIDER": "unknown",
            "OPENAI_API_KEY": "openai-test-key",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "LLM_PROVIDER"):
                Settings.from_env()

    def test_page_values_create_openai_settings_without_environment(self) -> None:
        settings = Settings.from_values(
            llm_provider=" OpenAI ",
            api_key=" page-secret ",
            openai_model="gpt-page",
            openai_search_model="gpt-search-page",
        )

        self.assertEqual(settings.llm_provider, "openai")
        self.assertEqual(settings.openai_api_key, "page-secret")
        self.assertEqual(settings.openai_model, "gpt-page")
        self.assertIsNone(settings.deepseek_api_key)
        self.assertNotIn("page-secret", repr(settings))

    def test_page_values_reject_an_empty_api_key(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "API Key"):
            Settings.from_values(
                llm_provider="deepseek",
                api_key="   ",
            )


if __name__ == "__main__":
    unittest.main()
