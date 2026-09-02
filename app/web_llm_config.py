"""Keep browser-supplied LLM credentials in short-lived server memory."""

from dataclasses import dataclass
import secrets
from threading import Lock
from time import monotonic

from app.config import Settings


LLM_SESSION_COOKIE = "research_llm_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_LLM_SESSIONS = 1_000


@dataclass
class StoredLLMSettings:
    """One session's secret settings and last access time."""

    settings: Settings
    last_accessed: float


class WebLLMSettingsStore:
    """A process-local credential store keyed by an opaque browser cookie."""

    def __init__(self) -> None:
        self._sessions: dict[str, StoredLLMSettings] = {}
        self._lock = Lock()

    def save(self, settings: Settings, previous_session_id: str | None = None) -> str:
        """Rotate the session identifier whenever credentials are saved."""

        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._remove_expired_locked()
            if previous_session_id:
                self._sessions.pop(previous_session_id, None)
            if len(self._sessions) >= MAX_LLM_SESSIONS:
                oldest_session_id = min(
                    self._sessions,
                    key=lambda key: self._sessions[key].last_accessed,
                )
                self._sessions.pop(oldest_session_id, None)
            self._sessions[session_id] = StoredLLMSettings(
                settings=settings,
                last_accessed=monotonic(),
            )
        return session_id

    def get(self, session_id: str | None) -> Settings | None:
        """Return one session's settings without exposing them to other users."""

        if not session_id:
            return None
        with self._lock:
            stored = self._sessions.get(session_id)
            if stored is None:
                return None
            if monotonic() - stored.last_accessed > SESSION_TTL_SECONDS:
                self._sessions.pop(session_id, None)
                return None
            stored.last_accessed = monotonic()
            return stored.settings

    def delete(self, session_id: str | None) -> None:
        """Forget credentials for one browser session."""

        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def _remove_expired_locked(self) -> None:
        """Discard expired entries while the caller owns the lock."""

        now = monotonic()
        expired_ids = [
            session_id
            for session_id, stored in self._sessions.items()
            if now - stored.last_accessed > SESSION_TTL_SECONDS
        ]
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)


web_llm_settings = WebLLMSettingsStore()
