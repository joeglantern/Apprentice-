"""Settings, read from the environment (.env in development). No defaults for secrets."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str  # required; no default so a password never lives in code
    redis_url: str = "redis://redis:6379/0"

    # Object storage: Contabo S3 in production, MinIO in docker-compose.dev.yml.
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "ghostagent"
    s3_region: str = "us-east-1"

    # Per-agent bearer tokens, "agent_id:token,agent_id2:token2". Issued when a Mac is paired.
    agent_tokens: str = ""

    # Cap on uploaded export files (bytes). PSDs can be large; 512 MB is generous.
    max_upload_bytes: int = 512 * 1024 * 1024

    cors_origins: str = "*"

    def agent_token_map(self) -> dict[str, str]:
        """token -> agent_id"""
        out: dict[str, str] = {}
        for pair in self.agent_tokens.split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            agent_id, token = pair.split(":", 1)
            out[token.strip()] = agent_id.strip()
        return out

    @property
    def sync_database_url(self) -> str:
        """Same database, sync driver, for Celery workers and Alembic."""
        return self.database_url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")

    celery_task_always_eager: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
