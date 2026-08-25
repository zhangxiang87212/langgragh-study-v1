"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_OPENAI_SEARCH_MODEL = "gpt-5.4-mini"
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
SUPPORTED_LLM_PROVIDERS = {"openai", "deepseek"}


class ConfigurationError(RuntimeError):
    """Raised when a required application setting is missing."""


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    openai_api_key: str | None
    openai_model: str
    openai_search_model: str
    deepseek_api_key: str | None
    deepseek_model: str
    deepseek_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from a local .env file and the process environment."""

        load_dotenv()

        llm_provider = os.getenv(
            "LLM_PROVIDER",
            DEFAULT_LLM_PROVIDER,
        ).strip().lower()
        if llm_provider not in SUPPORTED_LLM_PROVIDERS:
            supported_values = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
            raise ConfigurationError(
                f"LLM_PROVIDER 只支持：{supported_values}。"
            )

        api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        if llm_provider == "openai" and api_key is None:
            raise ConfigurationError(
                "LLM_PROVIDER=openai 时必须设置 OPENAI_API_KEY。"
            )

        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
        if not model:
            model = DEFAULT_OPENAI_MODEL

        search_model = os.getenv(
            "OPENAI_SEARCH_MODEL", DEFAULT_OPENAI_SEARCH_MODEL
        ).strip()
        if not search_model:
            search_model = DEFAULT_OPENAI_SEARCH_MODEL

        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or None
        if llm_provider == "deepseek" and deepseek_api_key is None:
            raise ConfigurationError(
                "LLM_PROVIDER=deepseek 时必须设置 DEEPSEEK_API_KEY。"
            )

        deepseek_model = os.getenv(
            "DEEPSEEK_MODEL",
            DEFAULT_DEEPSEEK_MODEL,
        ).strip()
        if not deepseek_model:
            deepseek_model = DEFAULT_DEEPSEEK_MODEL

        deepseek_base_url = os.getenv(
            "DEEPSEEK_BASE_URL",
            DEFAULT_DEEPSEEK_BASE_URL,
        ).strip()
        if not deepseek_base_url:
            deepseek_base_url = DEFAULT_DEEPSEEK_BASE_URL

        return cls(
            llm_provider=llm_provider,
            openai_api_key=api_key,
            openai_model=model,
            openai_search_model=search_model,
            deepseek_api_key=deepseek_api_key,
            deepseek_model=deepseek_model,
            deepseek_base_url=deepseek_base_url,
        )
