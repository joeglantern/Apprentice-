"""Creative director (docs/06 D1/D7): reasons about a brief and writes a design plan.

Stage 1 of generation. The plan says what should exist and why; the layout stage
(layout.py, later the layout VLM) decides where it goes; the style stage renders it.

Three backends, tried in order, each a strict fallback of the last:
  1. Claude API        - best quality, costs money per call, off unless ANTHROPIC_API_KEY
                          is set. Optional upgrade, not required to run this project.
  2. Local LLM          - free after the Legion's GPU is there anyway: a small
                          open-weight instruct model served by Ollama (or anything
                          exposing the same /api/chat + structured-output shape).
                          This is the default "thoughtful" path for a zero-budget setup.
  3. Heuristic          - no model call at all, always available, always the last resort.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.config import Settings

log = logging.getLogger(__name__)

Role = Literal["headline", "subhead", "body", "cta", "logo", "image", "shape", "caption"]
DEFAULT_PALETTE = ["#1A1A1A", "#F2A623", "#FFFFFF"]

# Bundled open (OFL) typefaces, app/assets/fonts. The director picks one pairing per
# piece by mood; layout.py maps it to families and weights.
Typeface = Literal["inter", "bebas", "playfair", "grotesk"]
TYPEFACE_GUIDE = {
    "inter": "neutral, modern, corporate, tech, fintech, real estate",
    "bebas": "loud, condensed, uppercase - concerts, sport, streetwear, sales, nightlife",
    "playfair": "elegant serif - weddings, fine dining, luxury, editorial, church",
    "grotesk": "quirky geometric - creative studios, fashion drops, youth brands",
}


class PlanElement(BaseModel):
    role: Role
    content: str = Field(description="Copy for text roles; a short description for others")
    priority: int = Field(ge=1, le=5, description="1 is the most important element")
    image_prompt: str | None = Field(
        default=None, description="For image roles: what the style renderer should paint"
    )
    scene_text: str | None = Field(
        default=None,
        description=(
            "For image roles only: one to three words that must physically appear inside "
            "the photograph, on a sign, banner, jersey or storefront - only when the brief "
            "asks for it. Everything else is set as real type on top and must stay null."
        ),
    )
    notes: str = Field(default="", description="Placement or treatment guidance in one line")


_HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")


class DesignPlan(BaseModel):
    rationale: str = Field(description="Two to four sentences on the thinking behind the plan")
    canvas: dict[str, int] = Field(description="width and height in pixels")
    mood: list[str] = Field(description="Three to six adjectives")
    palette_intent: list[str] = Field(description="Hex colours to lean on, from the profile")
    typeface: Typeface = Field(
        default="inter",
        description="Type pairing for the piece: "
        + "; ".join(f"{k}: {v}" for k, v in TYPEFACE_GUIDE.items()),
    )
    elements: list[PlanElement]
    source: Literal["director", "heuristic"] = "director"

    @field_validator("palette_intent")
    @classmethod
    def _extract_hex(cls, value: list[str]) -> list[str]:
        """The local model is inconsistent about strict #RRGGBB output - it regularly
        embeds a real hex code inside a colour name ("Dark Navy (#1C1C1C)") or gives a
        mood word instead of a colour ("Vibrant"). Extract whatever real hex code an
        entry contains and drop entries with none, rather than reject an otherwise good
        plan - headline, rationale, elements - over one messy field. layout.py already
        falls back to a sane default palette if this list ends up empty."""
        cleaned: list[str] = []
        for item in value:
            match = _HEX_COLOUR.search(item)
            if match:
                cleaned.append(match.group(0).upper())
        return cleaned

    @model_validator(mode="after")
    def _has_a_visual(self) -> DesignPlan:
        """A smaller local model will sometimes drop the image element entirely, which
        would otherwise silently ship a text-only poster. Reject rather than accept it -
        the caller (plan_design) falls back to the heuristic plan, which always includes
        one, on any validation failure."""
        if not any(e.role == "image" for e in self.elements):
            raise ValueError("plan has no image element")
        return self


SYSTEM_PROMPT = """You are the creative director for one specific graphic designer. You plan
new graphics in that designer's voice: you decide what a piece needs to say, which elements
earn a place on the canvas, their hierarchy, the copy, and the mood. You do not place
elements; a layout model trained on the designer's own files does that afterwards.

You are given the designer's style profile, derived only from work he opted in to share.
Treat it as evidence of his taste: favour its palette, its alignment habits, its typical
number of elements, and its margins. Do not invent a different aesthetic.

Write copy that is specific to the brief, never placeholder text. Structure the piece
the way a printed poster is structured, using these roles:
- caption: one short eyebrow line above the headline (event type, date, or brand line).
- headline: at most five words. This is the biggest thing on the poster.
- subhead: one supporting line.
- body: the concrete details a reader needs - date, time, venue, price, phone, handle -
  as short lines separated by newlines, not paragraphs.
- cta: two or three words, imperative.
- logo: the brand or business name only, as it would appear as a wordmark. Omit this
  element entirely if the brief names no brand; never write a placeholder like "Brand
  Name" or "Church Name" anywhere on the poster.
- image: exactly one. Its image_prompt describes a photographic background for the whole
  poster - the subject, setting, light and mood - with clean negative space. It must not
  ask for any text, lettering, logos or signage; type is added on top afterwards.
Prefer fewer, stronger elements over many weak ones. Pick the typeface pairing that fits
the mood. The rationale should read like a designer explaining choices to a collaborator,
in plain language.

Two examples of the standard expected, for different briefs:

Brief: "Poster for Mama Njeri's Kitchen, a new nyama choma spot in Kilimani, opening 3 October"
{"rationale": "A choma joint sells on smoke, fire and warmth, so the photo carries the appetite and the type stays confident and simple. Bebas gives it the loud, street-level energy of a Nairobi weekend; the amber accent is the glow of the grill.",
 "canvas": {"width": 1080, "height": 1350}, "mood": ["smoky", "warm", "loud", "welcoming"],
 "palette_intent": ["#1B0F08", "#F2A623", "#FFF4E6"], "typeface": "bebas",
 "elements": [
  {"role": "image", "content": "background photograph", "priority": 2, "image_prompt": "close up of goat meat searing on an open charcoal grill at dusk, embers and smoke, Kilimani rooftop, warm amber light, shallow depth of field"},
  {"role": "logo", "content": "Mama Njeri's Kitchen", "priority": 5},
  {"role": "caption", "content": "Now open in Kilimani", "priority": 4},
  {"role": "headline", "content": "Choma Done Right", "priority": 1},
  {"role": "subhead", "content": "Slow fire. Fresh goat. No shortcuts.", "priority": 3},
  {"role": "body", "content": "Opening Saturday 3 October 2026\\nArgwings Kodhek Road, Kilimani\\nPlatters from Kshs 1,200\\n+254 712 345 678", "priority": 4},
  {"role": "cta", "content": "Book a table", "priority": 3}]}

Brief: "Save the date for Amani and Wanjiru's wedding, 14 February, Karen"
{"rationale": "A wedding announcement should feel calm and expensive, so the photo is soft and the type is a serif with room to breathe. Nothing shouts; the date is the second thing you read.",
 "canvas": {"width": 1080, "height": 1350}, "mood": ["serene", "romantic", "elegant"],
 "palette_intent": ["#2B2622", "#D9B99B", "#FBF7F2"], "typeface": "playfair",
 "elements": [
  {"role": "image", "content": "background photograph", "priority": 2, "image_prompt": "a Kenyan couple walking hand in hand under jacaranda trees in soft morning light, Karen, pastel purple blossoms, gentle bokeh, editorial wedding photography"},
  {"role": "caption", "content": "Save the date", "priority": 4},
  {"role": "headline", "content": "Amani & Wanjiru", "priority": 1},
  {"role": "subhead", "content": "are getting married", "priority": 3},
  {"role": "body", "content": "Saturday 14 February 2027\\nKaren, Nairobi\\nFormal invitation to follow", "priority": 4}]}

Respond with only the JSON object described by the schema, no other text."""


def _profile_text(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "No style profile is available yet; use restrained, modern defaults."
    return json.dumps(profile, indent=1)


def heuristic_plan(
    brief: str, width: int, height: int, profile: dict[str, Any] | None
) -> DesignPlan:
    """A serviceable plan with no model call, used when no director backend is available."""
    palette = [c["value"] for c in (profile or {}).get("dominant_colours", [])[:4]] or list(
        DEFAULT_PALETTE
    )
    words = brief.strip().split()
    headline = " ".join(words[:6]).rstrip(".,;:") or "Untitled"
    return DesignPlan(
        rationale=(
            "No director model was available, so this plan follows the profile "
            "mechanically: one headline carrying the brief, a supporting line, an "
            "image area and a colour block in the designer's dominant palette."
        ),
        canvas={"width": width, "height": height},
        mood=["direct", "clean", "confident"],
        palette_intent=palette,
        typeface="inter",
        elements=[
            PlanElement(
                role="image",
                content="background photograph",
                priority=2,
                image_prompt=brief.strip(),
            ),
            PlanElement(role="caption", content="Coming soon", priority=4),
            PlanElement(role="headline", content=headline, priority=1),
            PlanElement(role="subhead", content=brief.strip()[:120], priority=3),
            PlanElement(role="cta", content="Learn more", priority=5),
        ],
        source="heuristic",
    )


class DirectorRefused(RuntimeError):
    pass


def _user_text(brief: str, width: int, height: int, profile: dict[str, Any] | None) -> str:
    today = date.today().isoformat()
    return (
        f"Today's date: {today}\n\n"
        f"Brief: {brief.strip()}\n\nCanvas: {width} x {height} px\n\n"
        f"Designer style profile:\n{_profile_text(profile)}\n\n"
        "If the brief needs a specific date and none is given, invent one at least two "
        "weeks after today's date above - never today, never a past date - and write "
        "dates the way a poster does (12 December 2026), not as ISO strings. The "
        "designer and his clients are in Kenya: phone numbers are +254 7XX XXX XXX, "
        "prices are in Kshs, places are real Kenyan places unless the brief says "
        "otherwise. Every detail must read as real; no placeholder values.\n\n"
        "Produce the design plan."
    )


async def _call_local_director(settings: Settings, user_text: str, schema: dict[str, Any]) -> str:
    """POST to a local Ollama-compatible /api/chat with structured-output format.
    Split out as its own function so tests can monkeypatch it without a real server."""
    body: dict[str, Any] = {
        "model": settings.local_director_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0.7},
    }
    if settings.local_director_model.startswith(("qwen3", "deepseek-r1")):
        # Thinking models otherwise spend the whole budget reasoning and return an
        # empty structured answer; the plan schema is the reasoning here.
        body["think"] = False
    async with httpx.AsyncClient(timeout=240.0) as client:
        r = await client.post(f"{settings.local_director_url.rstrip('/')}/api/chat", json=body)
        r.raise_for_status()
        return str(r.json()["message"]["content"])


async def _local_plan(
    brief: str, width: int, height: int, profile: dict[str, Any] | None, settings: Settings
) -> DesignPlan | None:
    """Returns None (never raises) when the local model is unreachable or answers badly,
    so the caller can fall back to the heuristic plan without the job failing. A smaller
    local model is meaningfully less consistent than a hosted frontier one - one retry on
    a validation failure (not on a connection failure, which is unlikely to change) is
    cheap and, empirically, recovers a real share of otherwise-wasted heuristic fallbacks."""
    schema = DesignPlan.model_json_schema()
    user_text = _user_text(brief, width, height, profile)
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            content = await _call_local_director(settings, user_text, schema)
        except httpx.HTTPError as exc:
            log.warning("local director unreachable (%s); using the heuristic plan", exc)
            return None
        try:
            plan = DesignPlan.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            last_exc = exc
            log.warning("local director answered badly on attempt %d (%s)", attempt + 1, exc)
            continue
        plan.canvas = {"width": width, "height": height}
        plan.source = "director"
        return plan
    log.warning("local director answered badly twice (%s); using the heuristic plan", last_exc)
    return None


async def _anthropic_plan(
    brief: str, width: int, height: int, profile: dict[str, Any] | None, settings: Settings
) -> DesignPlan | None:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await client.messages.parse(
            model=settings.director_model,
            max_tokens=8000,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": _user_text(brief, width, height, profile)}],
            output_format=DesignPlan,
            output_config={"effort": settings.director_effort},
        )
    except anthropic.RateLimitError:
        log.warning("director rate limited; trying the next backend")
        return None
    except anthropic.APIConnectionError:
        log.warning("director unreachable; trying the next backend")
        return None
    except anthropic.APIStatusError as exc:
        log.error("director request failed: %s", exc)
        raise

    if response.stop_reason == "refusal":
        detail = (
            getattr(response.stop_details, "explanation", None) if response.stop_details else None
        )
        raise DirectorRefused(detail or "The director declined this brief.")
    plan = response.parsed_output
    if plan is None:
        return None
    plan.canvas = {"width": width, "height": height}
    plan.source = "director"
    return plan


async def plan_design(
    brief: str,
    width: int,
    height: int,
    profile: dict[str, Any] | None,
    settings: Settings,
) -> DesignPlan:
    """Claude (if configured) -> local LLM (if configured) -> heuristic. Each step is a
    strict fallback: any failure of an earlier step tries the next, never raises past
    DirectorRefused (a real content decision, not an availability problem)."""
    if settings.anthropic_api_key:
        plan = await _anthropic_plan(brief, width, height, profile, settings)
        if plan is not None:
            return plan
    if settings.local_director_url:
        plan = await _local_plan(brief, width, height, profile, settings)
        if plan is not None:
            return plan
    else:
        log.info("no director backend configured; using the heuristic plan")
    return heuristic_plan(brief, width, height, profile)
