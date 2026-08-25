"""Create the checkpoint backend used by the command-line application."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver


DEFAULT_CHECKPOINT_BACKEND = "sqlite"
DEFAULT_CHECKPOINT_DB_PATH = Path("checkpoints/research.sqlite")
SUPPORTED_CHECKPOINT_BACKENDS = {"memory", "sqlite"}


class CheckpointConfigurationError(RuntimeError):
    """Raised when the checkpoint settings cannot be used."""


@dataclass(frozen=True)
class CheckpointSettings:
    """Settings that are independent from the selected LLM provider."""

    backend: str
    database_path: Path

    @classmethod
    def from_env(cls) -> "CheckpointSettings":
        """Load checkpoint settings from .env and environment variables."""

        load_dotenv()

        backend = os.getenv(
            "CHECKPOINT_BACKEND",
            DEFAULT_CHECKPOINT_BACKEND,
        ).strip().lower()
        if backend not in SUPPORTED_CHECKPOINT_BACKENDS:
            supported_values = ", ".join(sorted(SUPPORTED_CHECKPOINT_BACKENDS))
            raise CheckpointConfigurationError(
                f"CHECKPOINT_BACKEND 只支持：{supported_values}。"
            )

        configured_path = os.getenv(
            "CHECKPOINT_DB_PATH",
            str(DEFAULT_CHECKPOINT_DB_PATH),
        ).strip()
        database_path = Path(configured_path or DEFAULT_CHECKPOINT_DB_PATH)

        return cls(backend=backend, database_path=database_path)


@contextmanager
def open_checkpointer(
    settings: CheckpointSettings,
) -> Iterator[BaseCheckpointSaver]:
    """Open one checkpointer and close its resources after the command."""

    if settings.backend == "memory":
        yield InMemorySaver()
        return

    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path = str(settings.database_path)
    with SqliteSaver.from_conn_string(database_path) as checkpointer:
        checkpointer.setup()
        yield checkpointer
