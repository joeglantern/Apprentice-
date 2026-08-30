"""Picks the better of several rendered candidates with a small local vision model.

Docs/06 D17. SDXL's worst outputs are a minority - a stray letter, a mangled hand, a
subject parked exactly where the type goes. Rendering two seeds and letting a VLM
choose costs one extra render and removes most of them. The model is Qwen2.5-VL
through the same Ollama instance the director uses (/api/chat with base64 images);
any failure - unreachable, bad answer - falls back to the first candidate, never to
no image.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

PROMPT = """You are judging {n} candidate background photographs for a poster. The brief:
"{brief}"

Score each candidate 1 to 10 on: (a) it matches the brief, (b) it is a clean, sharp,
believable photograph, (c) it has no lettering, logos, watermarks or gibberish text
anywhere, (d) it leaves calm negative space in the {zone} for type to sit on, (e) no
deformed faces, hands or animals.

Answer with only JSON: {{"scores": [s1, s2, ...], "best": index_from_zero, "why": "one line"}}"""


def pick_best(
    candidates: list[bytes], brief: str, zone: str, settings: Settings, timeout: float = 120.0
) -> tuple[int, str]:
    """Index of the chosen candidate and the model's one-line reason. Index 0 with an
    empty reason whenever judging is off, fails, or there is only one candidate."""
    if len(candidates) < 2 or not settings.critic_model or not settings.local_director_url:
        return 0, ""
    body: dict[str, Any] = {
        "model": settings.critic_model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
        "messages": [
            {
                "role": "user",
                "content": PROMPT.format(n=len(candidates), brief=brief[:600], zone=zone),
                "images": [base64.b64encode(c).decode("ascii") for c in candidates],
            }
        ],
    }
    try:
        r = httpx.post(
            f"{settings.local_director_url.rstrip('/')}/api/chat", json=body, timeout=timeout
        )
        r.raise_for_status()
        content = str(r.json()["message"]["content"])
        data = json.loads(content)
        best = int(data.get("best", 0))
        why = str(data.get("why", ""))[:200]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        log.warning("critic failed (%s); keeping the first candidate", exc)
        return 0, ""
    if not 0 <= best < len(candidates):
        # A model that answers 1-based, or with a score list only.
        scores = data.get("scores") if isinstance(data, dict) else None
        if isinstance(scores, list) and scores:
            best = max(range(len(scores)), key=lambda i: float(scores[i]))
        else:
            m = re.search(r"\d+", str(best))
            best = int(m.group()) - 1 if m else 0
        best = best if 0 <= best < len(candidates) else 0
    return best, why
