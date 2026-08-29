# backend

FastAPI ingestion API, Celery worker, Postgres, Redis, object storage, and (in M4) the
inference gateway. Runs on the Contabo VPS as one Docker Compose stack.

## Endpoints (M2)
| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest/asset` | Collector posts the JSON record. 403 if consent is missing or not opted in, checked before any write. 202 when queued. |
| PUT | `/ingest/asset/{id}/file` | Collector uploads the export file (multipart `file`). Stored under `assets/<project>/<id>/<name>`. |
| GET | `/ingest/asset/{id}` | Read one record (own agent only). |
| GET | `/ingest/assets?project=&limit=` | List own records. |
| GET | `/health` | Liveness. |
| WS | `/socket.io` | Generation progress (used from M4). |

All `/ingest` routes need `Authorization: Bearer <agent token>`; tokens are configured
in `AGENT_TOKENS` as `agent_id:token` pairs.

## Local development
```bash
cp .env.example .env            # fill AGENT_TOKENS at minimum
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
docker compose run --rm api alembic upgrade head
curl localhost:8000/health
```
MinIO console: http://localhost:9001 (devuser / devpassword). Flower: http://localhost:5555.

Point the collector at it: Pair with server, URL `http://<this machine>:8000`, token from
`AGENT_TOKENS`.

## Tests
```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```
Tests use in-memory SQLite, a fake storage backend, and run the tagging task inline;
no Docker needed.

## Production (Contabo)
1. `cp .env.example .env`, set a real `POSTGRES_PASSWORD`, Contabo S3 credentials, and
   `AGENT_TOKENS`.
2. Put the real hostname in `nginx.conf`, obtain certificates with certbot, add the 443
   server block.
3. `docker compose up -d --build` then `docker compose run --rm api alembic upgrade head`.

Migrations are never run automatically on boot.
