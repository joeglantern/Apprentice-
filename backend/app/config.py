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
    # LoRA weights are tens to a few hundred MB.
    max_checkpoint_bytes: int = 2 * 1024 * 1024 * 1024

    cors_origins: str = "*"

    # Creative director (docs/06 D1). Without a key the pipeline uses a heuristic plan.
    anthropic_api_key: str = ""
    director_model: str = "claude-opus-5"
    director_effort: str = "high"

    # Free path: a small open-weight instruct model served by Ollama (or anything
    # exposing the same /api/chat + structured-output shape) on the Legion. Tried
    # after Claude, before the heuristic plan. Leave empty to skip straight to the
    # heuristic planner.
    local_director_url: str = ""
    local_director_model: str = "qwen2.5:7b-instruct"

    # Render endpoints: ComfyUI on the Legion (through the tunnel) and a burst GPU box.
    legion_inference_url: str = ""
    burst_inference_url: str = ""
    inference_timeout_s: float = 240.0

    # SDXL render quality (docs/06 D8) - free wins, no extra data needed. Base+refiner is
    # the official two-stage SDXL 1.0 pipeline; leave sdxl_refiner_checkpoint empty to
    # fall back to a single-stage render if the refiner isn't downloaded yet.
    sdxl_steps: int = 30
    sdxl_base_checkpoint: str = "sd_xl_base_1.0.safetensors"
    sdxl_refiner_checkpoint: str = ""
    sdxl_refiner_switch: float = 0.8

    # Optional hires-fix pass (docs/06 D11): upscale the finished latent, then a short
    # low-denoise re-sample for extra detail. 1.0 = disabled, the default, until it's
    # been verified not to strain the 8GB card - a strict addition on top of D8.
    sdxl_hires_scale: float = 1.0
    sdxl_hires_denoise: float = 0.4
    sdxl_hires_steps: int = 12

    # FLUX.1-schnell (Apache 2.0) as GGUF through ComfyUI-GGUF, docs/06 D15. SDXL cannot
    # spell, so when the director asks for words inside the photograph (a shop sign, a
    # banner) that one layer renders with Flux instead. Leave flux_unet empty to disable.
    flux_unet: str = ""
    flux_t5: str = "t5-v1_1-xxl-encoder-Q4_K_S.gguf"
    flux_clip_l: str = "clip_l.safetensors"
    flux_vae: str = "ae.safetensors"
    flux_steps: int = 4

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
