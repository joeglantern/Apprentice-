#!/usr/bin/env bash
# Install the Ghost Agent collector on a Mac (tested target: 2015 MacBook Pro on
# Monterey, and the designer's M4). Creates a venv, installs deps, and registers the
# launchd agent that starts the VISIBLE menu-bar app at login.
set -euo pipefail

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$AGENT_DIR/launchd/com.designer.ghostagent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.designer.ghostagent.plist"

# Prefer Homebrew python 3.11+ (system python on Monterey is too old).
PY=""
for candidate in python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
      PY="$(command -v "$candidate")"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "Need Python 3.11+. Install with: brew install python@3.11" >&2
  exit 1
fi
echo "Using $PY"

cd "$AGENT_DIR"
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -e ".[mac]"

VENV_PY="$AGENT_DIR/.venv/bin/python"
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PYTHON__|$VENV_PY|g" -e "s|__AGENT_DIR__|$AGENT_DIR|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo
echo "Installed. Look for '○ Ghost Agent' in the menu bar."
echo "Nothing is captured until you choose 'Add project folder...' and opt a folder in."
echo "To remove: launchctl unload \"$PLIST_DST\" && rm \"$PLIST_DST\""
