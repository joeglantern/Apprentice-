"""A short name for a finished piece, so a gallery reads as work rather than as a
list of prompts.

Three decisions worth stating, because the obvious implementation is worse than this
one on all three:

- Derived once, at generation, and stored. A title is metadata about a finished
  thing, not a view concern. Computing it per render would spend a model call every
  time a grid scrolled, and would let the same piece be called different things on
  two screens.

- The strongest signal already in hand wins. A poster's plan carries a `headline`
  that the director wrote to be the piece's own words. That is a better name than any
  summary of the brief, and it costs nothing, so no model is asked. Only `image` and
  `logo`, which never see the director (generation.run_generation sends them down
  direct_plan), pay for a call.

- No vision model. Titling from the rendered pixels sounds more intelligent, but the
  brief already says what the picture is, and loading a VLM would put a second model
  on an 8GB card that is busy rendering. The cheapest sufficient signal wins.

Failure is never fatal: an unreachable model, a timeout, or a junk answer falls back
to the trimmed brief, which is what the app displayed before titles existed.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You name design work. Given a brief, reply with a short title for the finished "
    "piece: two to five words, no quotes, no trailing punctuation, no explanation. "
    "Name the subject, not the medium: write 'Rooftop Jazz Night', never 'A poster "
    "for a jazz night'."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}

MAX_WORDS = 7
MAX_CHARS = 60


def _clean(raw: str) -> str:
    """Strip the things small models add back after being told not to."""
    text = " ".join(raw.strip().split())
    text = text.strip("\"'“”‘’ ").rstrip(".!,;:")
    words = text.split()
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS])
    return text[:MAX_CHARS].strip()


def from_prompt(prompt: str) -> str:
    """The fallback, and what a title looked like before this module: the brief,
    trimmed at a word boundary so it does not end mid-word."""
    text = " ".join(prompt.strip().split())
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS].rsplit(" ", 1)[0]


def headline_of(plan: dict[str, Any] | None) -> str | None:
    """The poster's own headline, if the director wrote one worth using."""
    if not plan:
        return None
    for element in plan.get("elements") or []:
        if element.get("role") != "headline":
            continue
        content = str(element.get("content") or "").strip()
        # A headline can be a full sentence of copy; past that length it is body text
        # wearing a headline's role and makes a worse name than the brief.
        if content and len(content) <= MAX_CHARS:
            return _clean(content)
    return None


async def _ask_local(prompt: str, settings: Settings) -> str | None:
    """None, never an exception, on anything unusable."""
    model = settings.chat_model or settings.local_director_model
    if not settings.local_director_url or not model:
        return None
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt.strip()[:600]},
        ],
        "format": SCHEMA,
        "stream": False,
        # Naming is not a creative act here; the same brief should get the same name.
        "options": {"temperature": 0.2},
        # Rides the model chat already keeps resident, so this is a warm call.
        "keep_alive": settings.chat_keep_alive,
    }
    if model.startswith(("qwen3", "deepseek-r1")):
        body["think"] = False
    try:
        async with httpx.AsyncClient(timeout=min(settings.chat_timeout_s, 30.0)) as client:
            r = await client.post(
                f"{settings.local_director_url.rstrip('/')}/api/chat", json=body
            )
            r.raise_for_status()
            content = str(r.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("titles: local model unusable (%s)", exc)
        return None

    match = re.search(r'"title"\s*:\s*"([^"]{1,120})"', content)
    candidate = _clean(match.group(1) if match else content)
    return candidate or None


async def make_title(
    prompt: str, plan: dict[str, Any] | None, kind: str, settings: Settings
) -> str:
    """Name a finished piece. Always returns something usable."""
    if kind == "poster":
        headline = headline_of(plan)
        if headline:
            return headline
    generated = await _ask_local(prompt, settings)
    return generated or from_prompt(prompt)
