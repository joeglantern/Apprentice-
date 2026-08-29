"""Creative director (docs/06 D1): reasons about a brief and writes a design plan.

Stage 1 of generation. The plan says what should exist and why; the layout stage
(layout.py, later the layout VLM) decides where it goes; the style stage renders it.
Without an API key the director degrades to a heuristic plan so the rest of the
pipeline can still be exercised.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings

log = logging.getLogger(__name__)

Role = Literal["headline", "subhead", "body", "cta", "logo", "image", "shape", "caption"]


class PlanElement(BaseModel):
    role: Role
    content: str = Field(description="Copy for text roles; a short description for others")
    priority: int = Field(ge=1, le=5, description="1 is the most important element")
    image_prompt: str | None = Field(
        default=None, description="For image roles: what the style renderer should paint"
    )
    notes: str = Field(default="", description="Placement or treatment guidance in one line")


class DesignPlan(BaseModel):
    rationale: str = Field(description="Two to four sentences on the thinking behind the plan")
    canvas: dict[str, int] = Field(description="width and height in pixels")
    mood: list[str] = Field(description="Three to six adjectives")
    palette_intent: list[str] = Field(description="Hex colours to lean on, from the profile")
    elements: list[PlanElement]
    source: Literal["director", "heuristic"] = "director"


SYSTEM_PROMPT = """You are the creative director for one specific graphic designer. You plan
new graphics in that designer's voice: you decide what a piece needs to say, which elements
earn a place on the canvas, their hierarchy, the copy, and the mood. You do not place
elements; a layout model trained on the designer's own files does that afterwards.

You are given the designer's style profile, derived only from work he opted in to share.
Treat it as evidence of his taste: favour its palette, its alignment habits, its typical
number of elements, and its margins. Do not invent a different aesthetic.

Write copy that is specific to the brief, never placeholder text. Keep headlines short.
Give every image element a concrete image_prompt the renderer can paint. Prefer fewer,
stronger elements over many weak ones. The rationale should read like a designer
explaining choices to a collaborator, in plain language."""


def _profile_text(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "No style profile is available yet; use restrained, modern defaults."
    return json.dumps(profile, indent=1)


def heuristic_plan(
    brief: str, width: int, height: int, profile: dict[str, Any] | None
) -> DesignPlan:
    """A serviceable plan with no model call, used when the director is unavailable."""
    palette = [c["value"] for c in (profile or {}).get("dominant_colours", [])[:4]] or [
        "#1A1A1A",
        "#F2A623",
        "#FFFFFF",
    ]
    words = brief.strip().split()
    headline = " ".join(words[:6]).rstrip(".,;:") or "Untitled"
    return DesignPlan(
        rationale=(
            "Director unavailable, so this plan follows the profile mechanically: one "
            "headline carrying the brief, a supporting line, an image area and a colour "
            "block in the designer's dominant palette."
        ),
        canvas={"width": width, "height": height},
        mood=["direct", "clean", "confident"],
        palette_intent=palette,
        elements=[
            PlanElement(role="shape", content="background colour block", priority=4),
            PlanElement(
                role="image",
                content="hero visual",
                priority=2,
                image_prompt=f"{brief}, in the designer's signature style",
            ),
            PlanElement(role="headline", content=headline, priority=1),
            PlanElement(role="subhead", content=brief.strip()[:120], priority=3),
        ],
        source="heuristic",
    )


class DirectorRefused(RuntimeError):
    pass


async def plan_design(
    brief: str,
    width: int,
    height: int,
    profile: dict[str, Any] | None,
    settings: Settings,
) -> DesignPlan:
    if not settings.anthropic_api_key:
        log.warning("ANTHROPIC_API_KEY not set; using the heuristic plan")
        return heuristic_plan(brief, width, height, profile)

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_text = (
        f"Brief: {brief.strip()}\n\nCanvas: {width} x {height} px\n\n"
        f"Designer style profile:\n{_profile_text(profile)}\n\n"
        "Produce the design plan."
    )
    try:
        response = await client.messages.parse(
            model=settings.director_model,
            max_tokens=8000,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user_text}],
            output_format=DesignPlan,
            output_config={"effort": settings.director_effort},
        )
    except anthropic.RateLimitError:
        log.warning("director rate limited; using the heuristic plan")
        return heuristic_plan(brief, width, height, profile)
    except anthropic.APIStatusError as exc:
        log.error("director request failed: %s", exc)
        raise
    except anthropic.APIConnectionError:
        log.warning("director unreachable; using the heuristic plan")
        return heuristic_plan(brief, width, height, profile)

    if response.stop_reason == "refusal":
        detail = (
            getattr(response.stop_details, "explanation", None) if response.stop_details else None
        )
        raise DirectorRefused(detail or "The director declined this brief.")
    plan = response.parsed_output
    if plan is None:
        raise RuntimeError("director returned no parsable plan")
    plan.canvas = {"width": width, "height": height}
    plan.source = "director"
    return plan
