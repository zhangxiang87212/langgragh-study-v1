"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_OPENAI_SEARCH_MODEL = "gpt-5.4-mini"


class ConfigurationError(RuntimeError):
    """Raised when a required application setting is missing."""


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    openai_search_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from a local .env file and the process environment."""

        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError(
                "缺少 OPENAI_API_KEY。请复制 .env.example 为 .env 并填写密钥。"
            )

        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
        if not model:
            model = DEFAULT_OPENAI_MODEL

        search_model = os.getenv(
            "OPENAI_SEARCH_MODEL", DEFAULT_OPENAI_SEARCH_MODEL
        ).strip()
        if not search_model:
            search_model = DEFAULT_OPENAI_SEARCH_MODEL

        return cls(
            openai_api_key=api_key,
            openai_model=model,
            openai_search_model=search_model,
        )
