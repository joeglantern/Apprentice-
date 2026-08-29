"""Menu-bar app. The visible indicator required by CLAUDE.md lives here.

Title shows exactly one of three states at all times:
    ○ Ghost Agent          off      (no projects opted in)
    ● Ghost Agent (2)      watching (N named projects)
    || Ghost Agent          paused
There is no fourth, hidden state and no flag that suppresses the indicator.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import rumps

from ghost_agent import AGENT_VERSION, CAPTURE_EXTENSIONS
from ghost_agent.activity_log import log_event
from ghost_agent.parser import parse_design_file
from ghost_agent.paths import log_file
from ghost_agent.state import ConsentError, Project, StateStore
from ghost_agent.sync import SyncClient, build_payload
from ghost_agent.watcher import WatchManager

FLUSH_INTERVAL_S = 60


def _choose_folder() -> str | None:
    """Native folder picker via AppleScript (no extra dependency)."""
    script = 'POSIX path of (choose folder with prompt "Choose ONE project folder to opt in:")'
    try:
        out = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=300
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None  # user cancelled
    return out.stdout.strip() or None


class GhostAgentApp(rumps.App):
    def __init__(self, store: StateStore | None = None) -> None:
        super().__init__("Ghost Agent", quit_button=None)
        self.store = store or StateStore()
        self.watches = WatchManager(self._on_capture)
        self.sync = SyncClient(
            self.store.state.api_base_url,
            self.store.get_token(),
            is_paused=lambda: self.store.state.paused,
            is_opted_in=self.store.is_opted_in,
        )
        self._build_menu()
        self._apply_state()
        log_event(f"agent started (v{AGENT_VERSION}), state={self.store.status()}")
        self._flush_timer = rumps.Timer(self._flush_tick, FLUSH_INTERVAL_S)
        self._flush_timer.start()

    # -- menu -------------------------------------------------------------------

    def _build_menu(self) -> None:
        self.status_item = rumps.MenuItem("status")
        self.status_item.set_callback(None)
        self.pause_item = rumps.MenuItem("Pause capture", callback=self.toggle_pause)
        self.projects_menu = rumps.MenuItem("Opted-in projects")
        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("Add project folder...", callback=self.add_project),
            self.projects_menu,
            self.pause_item,
            None,
            rumps.MenuItem("View activity log", callback=self.view_log),
            rumps.MenuItem("Pair with server...", callback=self.pair),
            None,
            rumps.MenuItem("Quit Ghost Agent", callback=self.quit),
        ]

    def _refresh_projects_menu(self) -> None:
        # rumps only creates the native submenu once an item has been added,
        # so clear() raises on a submenu that is still empty.
        if len(self.projects_menu):
            self.projects_menu.clear()
        projects = self.store.projects()
        if not projects:
            item = rumps.MenuItem("(none - nothing is being captured)")
            item.set_callback(None)
            self.projects_menu.add(item)
            return
        for p in projects:
            sub = rumps.MenuItem(f"{p.name}  -  {p.folder}")
            sub.add(
                rumps.MenuItem("Stop capturing this project", callback=self._make_revoke(p.name))
            )
            self.projects_menu.add(sub)

    def _refresh_title(self) -> None:
        status = self.store.status()
        if status == "paused":
            self.title = "|| Ghost Agent"
            self.status_item.title = "Paused - nothing is being captured"
            self.pause_item.title = "Resume capture"
        elif status == "watching":
            n = len(self.store.projects())
            self.title = f"● Ghost Agent ({n})"
            self.status_item.title = f"Watching {n} opted-in project folder(s)"
            self.pause_item.title = "Pause capture"
        else:
            self.title = "○ Ghost Agent"
            self.status_item.title = "Off - no project folders opted in"
            self.pause_item.title = "Pause capture"

    def _apply_state(self) -> None:
        """Make watchers match persisted state. Pause -> no watchers at all."""
        if self.store.state.paused:
            self.watches.stop_all()
        else:
            wanted = {p.name for p in self.store.projects()}
            for name in self.watches.watching():
                if name not in wanted:
                    self.watches.stop(name)
            for p in self.store.projects():
                self.watches.start(p)
        self._refresh_projects_menu()
        self._refresh_title()

    # -- actions ------------------------------------------------------------------

    def add_project(self, _: rumps.MenuItem) -> None:
        folder = _choose_folder()
        if not folder:
            return
        default_name = Path(folder).name
        win = rumps.Window(
            title="Name this project",
            message=f"Folder: {folder}",
            default_text=default_name,
            ok="Next",
            cancel="Cancel",
        )
        resp = win.run()
        if not resp.clicked:
            return
        name = resp.text.strip() or default_name
        exts = ", ".join(sorted(CAPTURE_EXTENSIONS))
        consent = rumps.alert(
            title="Opt this project in to Ghost Agent capture?",
            message=(
                f"Project: {name}\nFolder: {folder}\n\n"
                "What will be captured:\n"
                f"  • New or changed files in this folder ending in {exts}\n"
                "  • Layer names, positions, sizes, fonts and colours read from those files\n"
                "  • The export file itself, uploaded to your collaborator's server\n\n"
                "What will NOT be captured:\n"
                "  • Anything outside this folder\n"
                "  • Keystrokes, screen contents, or clipboard\n\n"
                "Every capture is written to a log you can open from this menu. "
                "You can pause or stop capturing this project at any time, instantly."
            ),
            ok="Opt in",
            cancel="Cancel",
        )
        if consent != 1:
            return
        try:
            project = self.store.add_project(name, folder)
        except ConsentError as exc:
            rumps.alert("Can't opt in that folder", str(exc))
            return
        log_event(f"opted in project '{project.name}' at {project.folder}")
        self._apply_state()

    def _make_revoke(self, name: str):  # noqa: ANN202 - rumps callback
        def revoke(_: rumps.MenuItem) -> None:
            # Order matters: stop the watcher and persist BEFORE anything else.
            self.watches.stop(name)
            try:
                self.store.remove_project(name)
            except KeyError:
                pass
            self.sync.drop_project(name)
            log_event(f"revoked project '{name}' - capture stopped")
            self._apply_state()

        return revoke

    def toggle_pause(self, _: rumps.MenuItem) -> None:
        paused = not self.store.state.paused
        if paused:
            self.watches.stop_all()  # client-side, before persisting, before any network
        self.store.set_paused(paused)
        log_event("capture paused" if paused else "capture resumed")
        self._apply_state()

    def view_log(self, _: rumps.MenuItem) -> None:
        path = log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        subprocess.run(["open", "-a", "TextEdit", str(path)], check=False)

    def pair(self, _: rumps.MenuItem) -> None:
        url_win = rumps.Window(
            title="Pair with server",
            message="Ingestion API base URL (e.g. https://ghost.example.com)",
            default_text=self.store.state.api_base_url,
            ok="Next",
            cancel="Cancel",
        )
        r1 = url_win.run()
        if not r1.clicked:
            return
        tok_win = rumps.Window(
            title="Pair with server",
            message="Agent token issued by your collaborator",
            default_text="",
            ok="Save",
            cancel="Cancel",
            secure=True,
        )
        r2 = tok_win.run()
        if not r2.clicked:
            return
        self.store.set_api_base_url(r1.text)
        if r2.text.strip():
            self.store.set_token(r2.text)
        self.sync.base_url = self.store.state.api_base_url
        self.sync.token = self.store.get_token()
        ok, message = self.sync.check()
        log_event(("paired with server " if ok else "pairing failed: ") + message)
        rumps.alert("Paired" if ok else "Pairing failed", message)
        if ok:
            threading.Thread(target=self.sync.flush, daemon=True).start()

    def quit(self, _: rumps.MenuItem) -> None:
        log_event("agent quit")
        self.watches.shutdown()
        rumps.quit_application()

    # -- capture pipeline -----------------------------------------------------------

    def _on_capture(self, path: Path, project: Project) -> None:
        # Re-check state at capture time: a pause/revoke may have raced the debounce timer.
        if self.store.state.paused or not self.store.is_opted_in(project.name):
            return
        if self.store.project_for_path(path) is None:
            return  # never capture outside an opted-in folder
        log_event(f"captured: {path} (project={project.name})")
        threading.Thread(target=self._process, args=(path, project), daemon=True).start()

    def _process(self, path: Path, project: Project) -> None:
        try:
            parsed = parse_design_file(path)
        except Exception as exc:  # noqa: BLE001
            log_event(f"could not read {path.name}: {exc.__class__.__name__}: {exc}")
            return
        payload = build_payload(
            project_name=project.name,
            file_path=path,
            parsed=parsed,
            opted_in=self.store.is_opted_in(project.name),
        )
        self.sync.send(payload)

    def _flush_tick(self, _: rumps.Timer) -> None:
        threading.Thread(target=self.sync.flush, daemon=True).start()


def main() -> None:
    if sys.platform != "darwin":
        print("Ghost Agent's menu-bar app runs on macOS only.", file=sys.stderr)
        sys.exit(1)
    GhostAgentApp().run()


if __name__ == "__main__":
    main()
