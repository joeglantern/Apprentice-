# collector-mac

Opt-in, visible, revocable capture of a designer's exports. See `CLAUDE.md`
§"Non-negotiable: consent over the collector" - every rule there is enforced in
code, and `.claude/skills/consent-gate-review` is the checklist for changes here.

## What it does
- A **menu-bar app** (`ghost_agent/app.py`, `rumps`) that is always visible and
  shows one of three states: `○` off, `●` watching N projects, `||` paused.
- **Add project folder...** opens a native folder picker, then a consent sheet
  that lists exactly what will and won't be captured. Only then is the folder
  watched. Home directory, volumes, Desktop/Documents/Downloads are refused.
- New/changed `.psd .ai .png .jpg` files inside an opted-in folder are parsed
  locally (`parser.py`, `psd-tools`) into the doc 01 §3 schema and sent to the
  ingestion API (`sync.py`) with the export file. Offline -> queued on disk.
- **Pause** stops all watchers client-side and persists before anything else.
  **Stop capturing this project** revokes one folder and drops its unsent items.
- Every event is appended to `~/.ghost_agent/activity.log` (plain language),
  openable from the menu.
- A **UXP panel** for Photoshop (`uxp-plugin/`) with an explicit per-session
  toggle that logs layer-tree snapshots on history/save events to a JSON-lines
  file. Off at every launch.

## Install (2015 MacBook Pro / Monterey, or the M4)
```bash
brew install python@3.11        # system python is too old on Monterey
./install.sh                    # venv + deps + launchd (starts at login)
```
Then click `○ Ghost Agent` -> **Pair with server...** (URL + token from your
collaborator) -> **Add project folder...**.

Run in the foreground instead: `.venv/bin/python agent.py`.

UXP panel: Photoshop -> Plugins -> Development -> Load plugin... -> `uxp-plugin/manifest.json`
(requires the Adobe UXP Developer Tool, and Photoshop 23+ - may not run on the 2015 machine).

## Files
```
ghost_agent/
  paths.py         where state/log/queue live (GHOST_AGENT_HOME overrides, for tests)
  state.py         StateStore: opt-in list, pause flag, blanket-path refusal, pairing token
  watcher.py       WatchManager: watchdog observers for opted-in folders only, debounced
  parser.py        PSD/PNG/JPG/AI -> file/layers/palette
  sync.py          payload builder + SyncClient (consent gate, disk queue, retries)
  activity_log.py  plain-language log
  app.py           rumps menu-bar UI, ties it together
agent.py           launchd entry point
launchd/           plist template (install.sh fills in paths)
uxp-plugin/        Photoshop panel
tests/             pytest (runs on any OS; rumps is not imported)
```

## Tests
```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```
