"""Plain-language activity log the designer can open with one click from the menu."""

from __future__ import annotations

from datetime import UTC, datetime

from ghost_agent.paths import log_file


def log_event(message: str) -> None:
    """Append one human-readable line. Never raises - logging must not block capture control."""
    try:
        path = log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{stamp}  {message}\n")
    except OSError:
        pass


def tail(n: int = 50) -> list[str]:
    path = log_file()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[-n:]
