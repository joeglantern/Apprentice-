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

    # Face detail pass (docs/06 D18): after an SDXL render, detect faces with
    # face_yolov8m and re-render each at full resolution via Impact Pack's
    # FaceDetailer. Fixes the few-pixels-per-face mush; needs the Impact Pack
    # loaded on the Legion. Off for Flux renders (scene_text), which are cleaner.
    face_detail: bool = True
    # 0.45 grafted repeating fabric texture onto large already-clean RealVisXL
    # faces (docs/06 D20); 0.25 leaves those alone while still fixing small ones.
    face_detail_denoise: float = 0.25
    # Same mechanism pointed at hands (hand_yolov8s), gentler denoise - hands need
    # correcting geometry, not re-imagining texture.
    hand_detail: bool = True
    hand_detail_denoise: float = 0.35

    # Two-seed judge (docs/06 D17): render render_candidates seeds per image layer and
    # let a small local VLM (through local_director_url) pick one. 1 = off.
    render_candidates: int = 1
    critic_model: str = "qwen2.5vl:3b"

    # Chat (docs/06 D22): the conversational turn on the chat screen. Same backend
    # ladder as the director - Claude if a key is set, else the local model, else
    # deterministic keyword routing - but a different, cheaper effort level, because
    # a turn is one routing decision plus a sentence and it sits on the path of every
    # message someone sends.
    chat_effort: str = "low"
    # Measured, not assumed. On a 15-message routing set (2026-09-02, RTX 5060 8GB)
    # qwen3:8b with thinking off routed 15/15 with no unusable answers and a median
    # 1.5s once resident; the director's qwen2.5:7b-instruct managed 6/15 on the same
    # set and returned five answers that failed schema validation twice over. Keep
    # chat_keep_alive generous - the first turn after an unload costs ~8s instead.
    # Empty falls back to local_director_model.
    chat_model: str = "qwen3:8b"
    # Ollama unloads an idle model; without this every turn pays a cold load.
    chat_keep_alive: str = "10m"
    chat_timeout_s: float = 90.0
    # Turns of thread history sent to the model. Small on purpose: the piece summary
    # already carries the state, and a 7B model's instruction following degrades long
    # before its context window fills.
    chat_history_turns: int = 8
    # Guard against a routing loop turning a chat thread into a render queue.
    chat_max_jobs_per_thread: int = 40

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
