"""Ghost Agent collector - opt-in, visible, revocable capture of a designer's exports.

Consent rules (CLAUDE.md) are enforced in code, not just documented:
- `state.py`      : projects are opted in one folder at a time; blanket paths are refused.
- `watcher.py`    : only folders in the opted-in list are ever watched.
- `sync.py`       : refuses to send anything not opted in or while paused.
- `app.py`        : the menu-bar indicator is always visible and shows one of three states.
"""

AGENT_VERSION = "0.3.0"

CAPTURE_EXTENSIONS: frozenset[str] = frozenset({".psd", ".ai", ".png", ".jpg", ".jpeg"})
