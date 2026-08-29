---
name: fastapi-ingestion-conventions
description: Coding conventions for the backend's FastAPI routes, Pydantic models, and Celery tasks. Use when writing or editing anything under backend/.
---

# Backend conventions (`backend/`)

Spec: `docs/02_COLLECTOR_AND_VPS_SETUP.md` §3-§6 and `docs/01` §3, §6.
Language rules: `CLAUDE.md` -> Python 3.11+, type hints everywhere,
`ruff` + `black`, `pytest`.

## Layout
```
backend/
├── app/
│   ├── main.py          # FastAPI app factory; mounts /socket.io
│   ├── config.py        # pydantic-settings, reads .env
│   ├── db.py            # async engine + get_session dependency
│   ├── models.py        # SQLModel tables (Asset, ...)
│   ├── schemas.py       # Pydantic v2 request/response bodies
│   ├── auth.py          # verify_agent_token bearer dependency
│   ├── storage.py       # aioboto3 client (Contabo S3 / MinIO in dev)
│   ├── queue.py         # thin helpers that .delay() Celery tasks
│   ├── worker.py        # Celery app + tasks (vision tagging, generation)
│   ├── realtime.py      # python-socketio server + Redis manager
│   └── routes/          # one APIRouter per resource: ingest.py, generate.py, ...
├── alembic/             # migrations - explicit `alembic upgrade head`, never on boot
├── tests/
├── docker-compose.yml + docker-compose.dev.yml (adds MinIO)
├── Dockerfile
└── nginx.conf
```

## Route pattern (doc 02 §3)
- `APIRouter(prefix="/<resource>", tags=[...])`, **async** endpoints.
- Request/response bodies are Pydantic v2 `BaseModel`s in `schemas.py`;
  DB rows are `SQLModel(table=True)` in `models.py`. Don't reuse a table
  model as a request body.
- DB access via `session: AsyncSession = Depends(get_session)`.
- Auth via `agent_id: str = Depends(verify_agent_token)` on every write.
- Return `202` + `{"status": "queued", ...}` when the work continues in
  Celery; return `201`/`200` only for synchronous completion.
- Raise `HTTPException` with a plain-language `detail`; never swallow.

## Consent enforcement (structural, not optional)
`POST /ingest/asset` rejects with **403** if `consent` is missing or
`consent.project_opted_in` is false - before any DB write or storage
upload. Cover this with a test. Run the `consent-gate-review` skill on any
change to this route.

## Celery
- Tasks live in `worker.py`, named `app.worker.<verb>_<noun>`, take only
  JSON-serialisable IDs (never ORM objects), and re-load from the DB.
- Progress for long jobs is emitted through `socketio.RedisManager(...,
  write_only=True)` into room `job_id` (doc 02 §5).
- Idempotent: re-running a task on the same `asset_id` must be safe.

## Inference gateway
`/generate` does **not** load a checkpoint on the VPS (no GPU). It enqueues
a job whose worker makes an outbound tunneled call to the Legion, falling
back to the burst GPU endpoint if the tunnel is unreachable (doc 01 §5).
Both endpoints come from settings, never hard-coded.

## Config & secrets
`pydantic-settings` `Settings` class; everything from env; `.env` is
gitignored; `.env.example` lists every key with no values.

## Tests
`pytest` + `httpx.AsyncClient` against the app with an SQLite/aiosqlite or
throwaway Postgres session, Celery in eager mode. Minimum per route: happy
path, auth failure, and (for ingest) consent rejection.
