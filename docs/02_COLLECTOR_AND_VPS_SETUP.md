# 02 - Collector and VPS setup

These are reference skeletons, not finished production code - Claude Code
should flesh out error handling, retries, and tests as it implements each
piece against your actual repo layout.

## 1. Mac collector - visible menu-bar agent

Built with `rumps` (a thin Python wrapper around `NSStatusItem`) so the
consent UI is a first-class part of the agent, not bolted on after.

```python
# collector-mac/agent.py
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import rumps
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

STATE_FILE = Path.home() / ".ghost_agent" / "state.json"
LOG_FILE = Path.home() / ".ghost_agent" / "activity.log"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"watched_projects": {}, "paused": False}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def log_event(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}  {message}\n")


class ExportHandler(FileSystemEventHandler):
    """Watches one opted-in project folder for new/changed design exports."""

    def __init__(self, project_name: str, on_capture):
        self.project_name = project_name
        self.on_capture = on_capture

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).suffix.lower() not in {".psd", ".ai", ".png", ".jpg"}:
            return
        log_event(f"captured: {event.src_path} (project={self.project_name})")
        self.on_capture(event.src_path, self.project_name)


class GhostAgent(rumps.App):
    """Menu-bar agent. Three states only: off / watching / paused -
    no fourth, invisible state, per CLAUDE.md's consent requirement."""

    def __init__(self):
        super().__init__("Ghost Agent", icon=None, quit_button="Quit")
        self.state = load_state()
        self.observer = Observer()
        self.menu = [
            rumps.MenuItem("Add project...", callback=self.add_project),
            rumps.MenuItem("Pause capture", callback=self.toggle_pause),
            rumps.MenuItem("View activity log", callback=self.view_log),
            None,
        ]
        self._refresh_title()
        self._start_watches()

    def _refresh_title(self):
        if self.state["paused"]:
            self.title = "|| Ghost Agent"
        elif self.state["watched_projects"]:
            self.title = f"● Ghost Agent ({len(self.state['watched_projects'])})"
        else:
            self.title = "○ Ghost Agent"

    def _start_watches(self):
        if self.state["paused"]:
            return
        for name, folder in self.state["watched_projects"].items():
            handler = ExportHandler(name, self._handle_capture)
            self.observer.schedule(handler, folder, recursive=True)
        if not self.observer.is_alive():
            self.observer.start()

    def add_project(self, _):
        # In the real app: an NSOpenPanel folder picker, then a one-time
        # consent sheet naming exactly what will be captured, before the
        # folder is added to self.state["watched_projects"].
        rumps.alert("Add project", "Wire this to an NSOpenPanel folder picker + consent sheet.")

    def toggle_pause(self, sender):
        self.state["paused"] = not self.state["paused"]
        save_state(self.state)
        sender.title = "Resume capture" if self.state["paused"] else "Pause capture"
        if self.state["paused"]:
            self.observer.unschedule_all()
        else:
            self._start_watches()
        self._refresh_title()

    def view_log(self, _):
        import subprocess
        subprocess.run(["open", "-a", "TextEdit", str(LOG_FILE)])

    def _handle_capture(self, path: str, project: str):
        payload = {
            "asset_id": str(uuid.uuid4()),
            "source_project": project,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "consent": {"project_opted_in": True, "captured_by_agent_version": "0.3.0"},
        }
        # Hand off to the sync module (doc 01 §3 data schema) - parse with
        # psd-tools if it's a .psd, then POST to the ingestion API.


if __name__ == "__main__":
    GhostAgent().run()
```

`launchd` still starts this at login - that part of the original plan was
fine. What matters is that what it starts is this visible, toggleable app,
not a headless process:

```xml
<!-- ~/Library/LaunchAgents/com.designer.ghostagent.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.designer.ghostagent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Applications/GhostAgent/agent.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

## 2. Photoshop/Illustrator - UXP plugin, not silent ExtendScript

Adobe's current extensibility platform is UXP, which replaces the old
ExtendScript/CEP approach the original plan called for. The win for this
project specifically: a UXP plugin has a real panel, so the visible-toggle
requirement is native to the platform rather than something you have to fake.

```javascript
// collector-mac/uxp-plugin/index.js
const { entrypoints } = require("uxp");
const photoshop = require("photoshop");

let capturing = false;

entrypoints.setup({
  panels: {
    vanilla: {
      show(node) {
        node.innerHTML = `
          <sp-body>Ghost Agent capture</sp-body>
          <sp-checkbox id="capture-toggle">Log layer changes for this document</sp-checkbox>
        `;
        node.querySelector("#capture-toggle").addEventListener("change", (e) => {
          capturing = e.target.checked;
        });
      },
    },
  },
});

photoshop.action.addNotificationListener(["historyStateChanged"], (event, descriptor) => {
  if (!capturing) return; // no logging unless the panel toggle is on
  const entry = {
    event_type: event,
    document: photoshop.app.activeDocument?.name,
    timestamp: new Date().toISOString(),
  };
  // append to a local JSON log the collector agent (§1) later reads and syncs
});
```

## 3. Contabo ingestion API

```python
# backend/app/models.py
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON


class Asset(SQLModel, table=True):
    asset_id: str = Field(primary_key=True)
    source_project: str = Field(index=True)
    captured_at: datetime
    agent_id: str
    payload: dict = Field(sa_column=Column(JSON))  # the full doc 01 §3 schema
```

```python
# backend/app/routes/ingest.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models import Asset
from app.queue import enqueue_vision_tagging
from app.auth import verify_agent_token

router = APIRouter(prefix="/ingest", tags=["ingest"])


class ConsentBlock(BaseModel):
    project_opted_in: bool
    captured_by_agent_version: str


class AssetPayload(BaseModel):
    asset_id: str
    source_project: str
    captured_at: str
    file: dict
    layers: list[dict]
    palette: list[str]
    consent: ConsentBlock


@router.post("/asset", status_code=202)
async def ingest_asset(
    payload: AssetPayload,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
):
    # Structural enforcement of the consent requirement (CLAUDE.md, doc 01 §4):
    # reject anything not explicitly opted in, regardless of caller.
    if not payload.consent.project_opted_in:
        raise HTTPException(status_code=403, detail="Project is not opted in for capture")

    asset = Asset(
        asset_id=payload.asset_id,
        source_project=payload.source_project,
        captured_at=payload.captured_at,
        agent_id=agent_id,
        payload=payload.model_dump(),
    )
    session.add(asset)
    await session.commit()
    await enqueue_vision_tagging(payload.asset_id)
    return {"status": "queued", "asset_id": payload.asset_id}
```

Auth (`verify_agent_token`) is a simple per-agent bearer token issued when the
designer's Mac is first paired with the VPS - enough for a two-person project;
swap for OAuth/device-cert auth if this ever grows beyond that.

Migrations are Alembic, run explicitly rather than on app boot:

```bash
alembic revision --autogenerate -m "create assets table"
docker compose run --rm api alembic upgrade head
```

## 4. Docker Compose for the VPS stack

Split into a lightweight `api` (ingestion, no model weights loaded) and a
separate `inference` service (loads the checkpoint, needs the GPU) so a
restart or crash in one doesn't take down the other, and so ingestion stays
fast even while a generation job is running:

```yaml
# backend/docker-compose.yml
services:
  api:
    build: .
    env_file: .env
    depends_on: [postgres, redis]
    ports: ["8000:8000"]

  inference:
    build:
      context: .
      dockerfile: Dockerfile.inference
    env_file: .env
    depends_on: [redis]
    # Only relevant if this VPS is the GPU tier from doc 01 §5 - omit this
    # block entirely if inference runs on the Legion or a burst GPU rental
    # instead. Requires nvidia-container-toolkit installed on the host.
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  worker:
    build: .
    command: celery -A app.worker worker --loglevel=info
    env_file: .env
    depends_on: [postgres, redis]

  flower:
    image: mher/flower
    command: celery flower --broker=redis://redis:6379/0
    ports: ["5555:5555"]
    depends_on: [redis]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ghostagent
      POSTGRES_PASSWORD_FILE: /run/secrets/pg_password
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7

  nginx:
    image: nginx:latest
    volumes: ["./nginx.conf:/etc/nginx/nginx.conf:ro"]
    ports: ["443:443", "80:80"]
    depends_on: [api]

volumes:
  pgdata:
```

`flower` is a one-line addition that gives you a web UI over the Celery
queue - worth having from day one given how much of this pipeline is
background jobs (vision tagging, nightly dataset curation, generation
requests). Point Nginx at Let's Encrypt (`certbot`) or swap it for Caddy if
you'd rather not manage certificate renewal by hand - either is a same-day
setup on a fresh Contabo box.

For local development, layer a `docker-compose.dev.yml` on top that swaps
Contabo Object Storage for a local **MinIO** container, so Claude Code (and
you) can iterate on the ingestion pipeline without touching real storage or
incurring cost:

```yaml
# backend/docker-compose.dev.yml
services:
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: devuser
      MINIO_ROOT_PASSWORD: devpassword
    volumes: ["miniodata:/data"]

volumes:
  miniodata:
```

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## 5. Real-time generation progress (Socket.IO)

Mounted onto the same FastAPI ASGI app that serves `/generate`, backed by
the Redis instance already in the stack so the Celery worker running the
actual generation - a separate process from the API - can emit progress
events into the same room:

```python
# backend/app/realtime.py
import socketio

mgr = socketio.AsyncRedisManager("redis://redis:6379/0")
sio = socketio.AsyncServer(async_mode="asgi", client_manager=mgr, cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio)
```

```python
# backend/app/main.py
from fastapi import FastAPI
from app.realtime import socket_app

app = FastAPI()
app.mount("/socket.io", socket_app)
```

```python
# backend/app/worker.py - emitted from inside the Celery task, not the API process
from app.realtime import mgr
import socketio

def emit_progress(job_id: str, step: int, total_steps: int):
    external_sio = socketio.RedisManager("redis://redis:6379/0", write_only=True)
    external_sio.emit("progress", {"step": step, "total": total_steps}, room=job_id)
```

The Expo client's corresponding hook is in doc 04 §5.

## 6. Nginx: TLS and WebSocket upgrade

WebSocket connections need explicit upgrade headers and a longer read
timeout than Nginx's defaults, or long-running generation connections get
silently dropped:

```nginx
# backend/nginx.conf (relevant location block)
location /socket.io/ {
    proxy_pass http://api:8000/socket.io/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
}
```
