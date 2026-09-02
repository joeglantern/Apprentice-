"""Conversational turn for the chat screen: decide what the message means, act, reply.

The chat screen used to fabricate its own assistant lines and treat every free-text
message as a brand new brief. That was honest about being a stub but it made the
thread useless for the thing people actually do - say "make the headline shorter"
and expect the piece to change, not be replaced.

One model call per turn produces both halves at once: the routing decision and the
sentence the user reads. Doing it in one call (rather than classify-then-write) keeps
the reply grounded in the action that was actually chosen - the model cannot promise
one thing while the router does another - and costs one round trip instead of two,
which matters when the model is a 7B on the far end of an ssh tunnel.

Same three-tier ladder as director.py, and for the same reason:
  1. Claude API    - if ANTHROPIC_API_KEY is set. Best intent reading, costs money.
  2. Local LLM     - Ollama on the Legion with a JSON-schema `format`. The default.
  3. Deterministic - keyword routing, no model call. Chat still works with the
                     tunnel down; it just stops being clever.

Failure is closed, never open: an unusable model answer degrades to `answer` (talk),
never to `new_direction` (spend GPU minutes on a poster nobody asked for).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import Settings
from app.director import Composition, Role, Typeface

log = logging.getLogger(__name__)

# What a turn can do. Closed set: the model picks one of these or it talks.
Action = Literal["revise", "edit_copy", "new_direction", "answer", "clarify"]

# Text roles the chat turn is allowed to rewrite. `image` is deliberately absent -
# changing the picture is `revise` with rerender_photo, not a copy edit.
EDITABLE_ROLES: tuple[Role, ...] = ("headline", "subhead", "body", "cta", "caption", "logo")


class CopyEdit(BaseModel):
    role: Literal["headline", "subhead", "body", "cta", "caption", "logo"]
    content: str = Field(min_length=1, max_length=600)


class ChatTurn(BaseModel):
    """One assistant turn: what to say, and what to do about it.

    Flat on purpose. A discriminated union with per-action payloads reads better in
    Python but small local models fill nested optional objects far less reliably than
    flat optional fields, and this schema is handed to Ollama as the response format.
    The model_validator below does the work the union type would have done.

    Field order is load-bearing, not cosmetic. Under a sampling grammar the model emits
    the keys in schema order, so whatever comes first is decided with the least
    information. `reply` used to lead, which meant writing the sentence before choosing
    the route - and a 7B would then write "edit_copy" into the reply, or narrate one
    action and pick another. Deciding first and speaking last measurably fixes both.
    """

    action: Action

    # revise
    composition: Composition | None = None
    typeface: Typeface | None = None
    rerender_photo: bool = False
    # edit_copy
    copy_edits: list[CopyEdit] = Field(default_factory=list, max_length=6)
    # new_direction
    brief: str | None = Field(default=None, max_length=2000)

    # Last: written knowing the action and its payload, so it describes what was
    # actually chosen rather than predicting it.
    reply: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "One or two sentences to the user about the action above, lowercase, "
            "plain, no emoji. For an action, say what you are about to change - never "
            "claim it is finished. For answer or clarify, this is the whole response. "
            "Never write the action name here."
        ),
    )

    @model_validator(mode="after")
    def _payload_matches_action(self) -> ChatTurn:
        if self.action == "revise" and not (
            self.composition or self.typeface or self.rerender_photo
        ):
            raise ValueError("revise with nothing to revise")
        if self.action == "edit_copy" and not self.copy_edits:
            raise ValueError("edit_copy with no edits")
        if self.action == "new_direction" and not (self.brief or "").strip():
            raise ValueError("new_direction with no brief")
        if self.action in ("answer", "clarify") and (
            self.composition or self.typeface or self.rerender_photo or self.copy_edits
        ):
            # Talking and acting at once is the one thing that must not happen: the
            # user reads a sentence and a job appears they did not ask for.
            raise ValueError("answer and clarify do not carry an action payload")
        return self

    def is_action(self) -> bool:
        return self.action in ("revise", "edit_copy", "new_direction")


SYSTEM_PROMPT = """You are Eidolon, the design assistant in a graphics app. Someone has
a poster open and is talking to you about it. Read what they want, pick exactly one
action, and write one or two sentences back.

The actions, and when each one is right:

- revise: they want the same piece arranged differently, or the same layout with a
  different photograph. Set composition (anchor, centered, split), typeface (inter,
  bebas, playfair, grotesk), rerender_photo, or several. "make it a split layout",
  "try a serif", "different photo", "the image is not working".
  Any complaint about the photograph is this action with rerender_photo true. Nobody
  can upload a picture and you cannot edit one, so repainting it is the only thing
  that can change it - never answer a complaint about the photo with advice.
  If they ask for a setting the piece already has, use answer and say so rather than
  spending a render arriving where it already is.
- edit_copy: they want different words on the piece. Give one copy_edits entry per
  role you are changing (headline, subhead, body, cta, caption, logo) with the full
  new text for that role, not a diff. "shorter headline", "call it Friday not
  Saturday", "drop the price line" (send the body without that line).
  This text is set on a printed poster, so capitalise it the way a poster does -
  "Choma Nights", not "choma nights". Use the words they gave you; the lowercase
  house voice below is for your reply to them, never for the copy itself.
- new_direction: they are describing a different piece, not a change to this one.
  Put the whole brief in brief. "now do one for the christmas menu".
- answer: they asked you something, or said something that needs no change to the
  piece. Answer it in reply and change nothing. "why bebas?", "what sizes can you
  do", "looks good".
- clarify: you genuinely cannot tell which piece or which element they mean, and
  guessing would waste a render. Ask one short question. Use this sparingly - a
  reasonable guess and a fast redo beats an interrogation.

What you can actually do, so you never promise more: change composition, typeface,
copy, and the photograph; start a new piece. You cannot move a single element by
hand, change colours outside the brand kit, edit the image itself, or export - the
canvas screen does those. If someone asks for one of those, use answer and say which
screen does it.

Prefer edit_copy or revise over new_direction. A new direction throws away the
current piece and costs a full render; only choose it when the subject genuinely
changed. When in doubt between revise and edit_copy, look at whether the words or
the arrangement is what they are unhappy with.

Voice: lowercase, short, plain. No emoji, no exclamation marks, no em dashes. Say
what you are changing, not that it is done - the render has not run yet when you
write this. Never describe a result you have not seen.

Respond with only the JSON object described by the schema, no other text."""


def piece_summary(plan: dict[str, Any] | None, prompt: str, status: str) -> str:
    """The current piece, compressed.

    The full plan is a large JSON blob with rationale, notes and image prompts. A 7B
    model reads a short list far better than it reads that, and every token here is
    resent on every turn - this is the part of the context that has to stay small.
    """
    if not plan:
        return f"No piece is open yet. The last brief was: {prompt or 'none'}."
    lines = [
        f"Open piece (status: {status}). Brief: {prompt}",
        f"Composition: {plan.get('composition', 'anchor')}. "
        f"Typeface: {plan.get('typeface', 'inter')}. "
        f"Palette: {', '.join(plan.get('palette_intent') or []) or 'default'}.",
        "Current copy:",
    ]
    for element in plan.get("elements", []):
        role = element.get("role")
        if role == "image":
            lines.append(f"- image: {str(element.get('image_prompt') or '')[:120]}")
        elif role in EDITABLE_ROLES:
            content = str(element.get("content") or "").replace("\n", " / ")
            lines.append(f"- {role}: {content[:160]}")
    return "\n".join(lines)


def build_messages(history: list[dict[str, str]], piece: str, message: str) -> list[dict[str, str]]:
    """History, then the piece, then the new message.

    Order is deliberate for caching: the system prompt carries the cache breakpoint and
    is byte-identical every turn. The piece summary sits next to the message it is
    about rather than in the system prompt, because it changes every time a job lands
    and would otherwise invalidate the cached prefix on every single turn.
    """
    out: list[dict[str, str]] = list(history)
    out.append({"role": "user", "content": f"{piece}\n\nThey said: {message.strip()}"})
    return out


def deterministic_turn(message: str, has_piece: bool) -> ChatTurn:
    """No model call. Keyword routing, deliberately timid.

    This runs when both model backends are unreachable. It only recognises the
    unambiguous cases and answers everything else, because a wrong guess here spends
    a render on the Legion and the user has no way to tell a fallback from a decision.
    """
    text = message.lower().strip()
    if not has_piece:
        return ChatTurn(
            reply="starting a fresh piece from that.", action="new_direction", brief=message
        )
    for word, composition in (("split", "split"), ("centre", "centered"), ("center", "centered")):
        if word in text:
            return ChatTurn(
                reply=f"recomposing to {composition}.",
                action="revise",
                composition=composition,  # type: ignore[arg-type]
            )
    if any(w in text for w in ("photo", "picture", "image", "background")):
        return ChatTurn(
            reply="repainting the photo, same layout.", action="revise", rerender_photo=True
        )
    return ChatTurn(
        reply=(
            "the director model is offline right now, so i can only do the quick "
            "actions below until it is back."
        ),
        action="answer",
    )


# Validation keywords Ollama cannot compile into a sampling grammar. Sending a schema
# containing minLength/maxLength makes /api/chat answer 400 "failed to parse grammar",
# which the ladder below would swallow as "model unreachable" - the whole local path
# would sit in the deterministic fallback and only ever log a warning about it. The
# grammar's job is the shape; Pydantic still checks the values on the way back, so
# nothing is lost by dropping these.
_UNGRAMMATICAL = frozenset({"minLength", "maxLength", "minItems", "maxItems", "pattern"})


def grammar_schema(node: Any) -> Any:
    """The response schema with the keywords Ollama's grammar compiler rejects removed."""
    if isinstance(node, dict):
        return {k: grammar_schema(v) for k, v in node.items() if k not in _UNGRAMMATICAL}
    if isinstance(node, list):
        return [grammar_schema(v) for v in node]
    return node


async def _call_local(
    settings: Settings, messages: list[dict[str, str]], schema: dict[str, Any]
) -> str:
    """POST to a local Ollama-compatible /api/chat. Split out so tests can patch it."""
    model = settings.chat_model or settings.local_director_model
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "format": schema,
        "stream": False,
        # Lower than the director's 0.7: this is a routing decision with a sentence
        # attached, not a creative one, and consistency is worth more than variety.
        "options": {"temperature": 0.3},
        # Without this Ollama unloads the model between turns and every message pays a
        # cold load off disk, which on a machine also running ComfyUI is tens of
        # seconds. It is the single biggest latency lever on the local path.
        "keep_alive": settings.chat_keep_alive,
    }
    if model.startswith(("qwen3", "deepseek-r1")):
        # Thinking models otherwise spend the whole budget reasoning and return an
        # empty structured answer; same reason director.py sets this.
        body["think"] = False
    async with httpx.AsyncClient(timeout=settings.chat_timeout_s) as client:
        r = await client.post(f"{settings.local_director_url.rstrip('/')}/api/chat", json=body)
        r.raise_for_status()
        return str(r.json()["message"]["content"])


async def _local_turn(
    settings: Settings, messages: list[dict[str, str]], schema: dict[str, Any]
) -> ChatTurn | None:
    """None (never raises) on an unreachable or unusable local model.

    The retry is not a plain repeat. A grammar guarantees the shape but not the sense,
    and the characteristic 7B failure here is committing to an action with an empty
    payload - `action: "revise"` and nothing to revise. Handing the validation error
    back as the next user turn fixes most of those, where asking the same question
    again just gets the same answer.
    """
    attempt_messages = list(messages)
    for attempt in range(2):
        try:
            content = await _call_local(settings, attempt_messages, schema)
        except httpx.HTTPError as exc:
            log.warning("chat: local model unreachable (%s)", exc)
            return None
        try:
            return ChatTurn.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            attempt_messages = [
                *messages,
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        f"That was rejected: {exc}. Answer again for the same message. "
                        "If you chose an action, fill in the fields it needs; if you "
                        "cannot, use answer instead."
                    ),
                },
            ]
            log.warning("chat: local model answered badly on attempt %d (%s)", attempt + 1, exc)
    return None


async def _anthropic_turn(settings: Settings, messages: list[dict[str, str]]) -> ChatTurn | None:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await client.messages.parse(
            model=settings.director_model,
            max_tokens=2000,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=messages,  # type: ignore[arg-type]
            output_format=ChatTurn,
            # Deliberately below director_effort. Reading one sentence and picking one
            # of five actions is not the hard part of this project, and this call sits
            # on the path of every send, where latency is what people feel.
            output_config={"effort": settings.chat_effort},
        )
    except anthropic.RateLimitError:
        log.warning("chat: rate limited; trying the next backend")
        return None
    except anthropic.APIConnectionError:
        log.warning("chat: unreachable; trying the next backend")
        return None
    except anthropic.APIStatusError as exc:
        log.error("chat: request failed: %s", exc)
        return None

    if response.stop_reason == "refusal":
        detail = (
            getattr(response.stop_details, "explanation", None) if response.stop_details else None
        )
        return ChatTurn(reply=(detail or "i would rather not take that one."), action="answer")
    return response.parsed_output


async def interpret(
    *,
    message: str,
    history: list[dict[str, str]],
    plan: dict[str, Any] | None,
    prompt: str,
    status: str,
    settings: Settings,
) -> ChatTurn:
    """Claude -> local -> deterministic, each a strict fallback of the last.

    Returns a validated turn whatever happens; the caller never has to handle a model
    being down.
    """
    messages = build_messages(history, piece_summary(plan, prompt, status), message)
    if settings.anthropic_api_key:
        turn = await _anthropic_turn(settings, messages)
        if turn is not None:
            return turn
    if settings.local_director_url:
        schema = grammar_schema(ChatTurn.model_json_schema())
        turn = await _local_turn(settings, messages, schema)
        if turn is not None:
            return turn
    return deterministic_turn(message, has_piece=plan is not None)


def apply_copy_edits(plan: dict[str, Any], edits: list[CopyEdit]) -> dict[str, Any]:
    """A copy of the plan with the named roles rewritten.

    An edit to a role the plan does not have adds it, so "add a call to action" works
    on a piece that has none. Everything else - image prompt, palette, notes - is left
    exactly as it was, which is what makes this cheap: the photo is reused and only
    the type is re-set.
    """
    patched = {**plan, "elements": [dict(e) for e in plan.get("elements", [])]}
    for edit in edits:
        for element in patched["elements"]:
            if element.get("role") == edit.role:
                element["content"] = edit.content
                break
        else:
            patched["elements"].append(
                {"role": edit.role, "content": edit.content, "priority": 3, "notes": ""}
            )
    return patched


def landed_line(turn: ChatTurn, ok: bool, error: str | None = None) -> str:
    """The second, deterministic line, written when the job finishes.

    Not a model call. The turn's own reply was written before the render ran and only
    ever promises an intent; this is the only sentence allowed to speak about a
    result, and it is generated from what actually happened rather than guessed.
    """
    if not ok:
        return f"that one did not render: {error or 'unknown error'}. want me to try again?"
    if turn.action == "edit_copy":
        roles = ", ".join(dict.fromkeys(e.role for e in turn.copy_edits))
        return f"updated the {roles}."
    if turn.action == "revise":
        bits = []
        if turn.composition:
            bits.append(f"recomposed to {turn.composition}")
        if turn.typeface:
            bits.append(f"set in {turn.typeface}")
        if turn.rerender_photo:
            bits.append("repainted the photo")
        return f"{' and '.join(bits)}."
    return "rendered."
