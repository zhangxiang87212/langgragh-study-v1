"""Small helpers for timestamped console logs."""

from datetime import datetime


def current_timestamp() -> str:
    """Return local time with millisecond precision."""

    local_time = datetime.now().astimezone()
    return local_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def print_log(message: str, *, timestamp: str | None = None) -> None:
    """Print one timestamped log entry immediately."""

    timestamp = timestamp or current_timestamp()
    print(f"[{timestamp}] {message}", flush=True)
