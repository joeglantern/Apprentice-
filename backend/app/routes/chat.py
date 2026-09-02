"""Chat API: a thread about one evolving piece, where every turn is understood.

The screen this serves used to write its own assistant lines and send every free-text
message to /generate, so "make the headline shorter" produced a different poster. Here
the message goes to a model that picks one of five actions (chat.py), the action is
carried out against the existing revision machinery, and the reply the user reads is
the one the model wrote when it chose that action.

Two rules hold everywhere below:

- Fail closed. Anything unusable - model down, job not finished, thread at its job
  cap - degrades to talking, never to starting a render nobody asked for.
- The reply never claims a result. It is written before the render runs, so it states
  an intent; the `landed` line, filled in when the job reaches a terminal state, is
  the only sentence allowed to describe what actually happened.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import verify_agent_token
from app.chat import ChatTurn, apply_copy_edits, interpret, landed_line
from app.config import Settings, get_settings
from app.db import get_session
from app.models import JOB_TERMINAL, ChatMessage, ChatThread, Checkpoint, Job
from app.queue import enqueue_generation
from app.routes.generate import BASELINE, GenerateRequest
from app.schemas import UUID_PATTERN

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

ThreadId = Annotated[str, Path(pattern=UUID_PATTERN)]


COMPOSITIONS = ("anchor", "centered", "split")


class TurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # A quick-action chip. Its intent is already known from which button was pressed,
    # so it skips the model entirely: instant, free, and impossible to misroute. It
    # still goes through this endpoint rather than straight to /revise so the thread
    # stays the one record of what happened to the piece.
    quick: Literal["swap_photo", "recompose"] | None = None
    # Only consulted when a turn starts a fresh piece; a revision inherits everything
    # from the job it revises.
    aesthetic_version: str = Field(default="baseline", pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    kind: Literal["poster", "image", "logo"] = "poster"
    width: int = Field(default=1080, ge=256, le=4096)
    height: int = Field(default=1350, ge=256, le=4096)


class MessageRead(BaseModel):
    message_id: str
    role: str
    text: str
    action: str | None = None
    job_id: str | None = None
    landed: str | None = None
    created_at: Any


class ThreadRead(BaseModel):
    thread_id: str
    active_job_id: str | None
    messages: list[MessageRead]
    created_at: Any
    updated_at: Any


class ThreadSummary(BaseModel):
    thread_id: str
    active_job_id: str | None
    title: str
    created_at: Any
    updated_at: Any


class NewThread(BaseModel):
    """Optionally adopt a piece that already exists - the path from the create screen
    into chat, where someone generates something and then wants to talk about it."""

    job_id: str | None = Field(default=None, pattern=UUID_PATTERN)


async def _owned_thread(thread_id: str, owner: str, session: AsyncSession) -> ChatThread:
    thread = await session.get(ChatThread, thread_id.lower())
    if thread is None or thread.owner != owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return thread


async def _messages(thread_id: str, session: AsyncSession) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at)  # type: ignore[arg-type]
    )
    return list((await session.exec(stmt)).all())


async def _settle(messages: list[ChatMessage], session: AsyncSession) -> bool:
    """Fill in the `landed` line for any turn whose job has since finished.

    Done on read rather than by the worker on purpose: the worker knows nothing about
    chat and should not, and a thread nobody opens does not need settling. It is also
    self-healing - a landed line missed because the process restarted mid-job appears
    the next time the thread is read.
    """
    pending = [m for m in messages if m.job_id and m.landed is None and m.action]
    if not pending:
        return False
    changed = False
    for message in pending:
        job = await session.get(Job, message.job_id)
        if job is None or job.status not in JOB_TERMINAL:
            continue
        # The stored action is enough to regenerate the sentence; the payload that
        # produced it is on the job itself.
        turn = _turn_for_landing(message, job)
        message.landed = landed_line(turn, ok=job.status == "done", error=job.error)
        session.add(message)
        changed = True
    if changed:
        await session.commit()
    return changed


def _turn_for_landing(message: ChatMessage, job: Job) -> ChatTurn:
    """Reconstruct just enough of the turn for landed_line to describe it.

    Only the fields that sentence reads are recovered, from the job rather than from
    anything the model said - so the line reports the change that was actually made.
    """
    action = message.action or "answer"
    if action == "revise":
        # Only what this revision actually changed, from the list the turn recorded.
        # Reading the plan instead would name every field it has - a revision that
        # only recomposed would report "recomposed to split and set in inter", which
        # is not what happened.
        plan = job.plan or {}
        changed = set((job.revise or {}).get("changed") or [])
        return ChatTurn(
            reply=message.text,
            action="revise",
            composition=plan.get("composition") if "composition" in changed else None,
            typeface=plan.get("typeface") if "typeface" in changed else None,
            rerender_photo="rerender_photo" in changed,
        )
    if action == "edit_copy":
        roles = (job.revise or {}).get("copy_roles") or ["headline"]
        return ChatTurn(
            reply=message.text,
            action="edit_copy",
            copy_edits=[{"role": r, "content": "x"} for r in roles],  # type: ignore[list-item]
        )
    return ChatTurn(reply=message.text, action="new_direction", brief=job.prompt)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ThreadRead)
async def create_thread(
    body: NewThread,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> ThreadRead:
    if body.job_id:
        job = await session.get(Job, body.job_id.lower())
        if job is None or job.requested_by != agent_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    thread = ChatThread(
        thread_id=str(uuid.uuid4()),
        owner=agent_id,
        active_job_id=body.job_id.lower() if body.job_id else None,
    )
    session.add(thread)
    await session.commit()
    return ThreadRead(
        thread_id=thread.thread_id,
        active_job_id=thread.active_job_id,
        messages=[],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.get("", response_model=list[ThreadSummary])
async def list_threads(
    limit: int = 30,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> list[ThreadSummary]:
    """Sessions, newest first.

    A session is named after the piece it is about, not after the sentence that
    started it: `app/titles.py` already writes a real name on every landed job, and a
    sidebar of raw prompts reads as a list of instructions rather than a body of work.
    Falls back to the opening message, then to a placeholder, so a session that has
    not produced anything yet still has something to show.

    The name is derived rather than stored. A thread's piece keeps changing as
    revisions land, and a column would go stale the first time one did.
    """
    stmt = (
        select(ChatThread)
        .where(ChatThread.owner == agent_id)
        .order_by(ChatThread.updated_at.desc())  # type: ignore[attr-defined]
        .limit(min(max(limit, 1), 100))
    )
    threads = list((await session.exec(stmt)).all())
    if not threads:
        return []

    # Two queries for the whole page, rather than two per thread.
    job_ids = [t.active_job_id for t in threads if t.active_job_id]
    titles: dict[str, str] = {}
    if job_ids:
        rows = await session.exec(
            select(Job.job_id, Job.title).where(Job.job_id.in_(job_ids))  # type: ignore[attr-defined]
        )
        titles = {jid: title for jid, title in rows if title}

    openers: dict[str, str] = {}
    messages = await session.exec(
        select(ChatMessage.thread_id, ChatMessage.text)
        .where(
            ChatMessage.thread_id.in_([t.thread_id for t in threads]),  # type: ignore[attr-defined]
            ChatMessage.role == "user",
        )
        .order_by(ChatMessage.created_at)  # type: ignore[arg-type]
    )
    for thread_id, text in messages:
        openers.setdefault(thread_id, text)

    return [
        ThreadSummary(
            thread_id=t.thread_id,
            active_job_id=t.active_job_id,
            title=(
                titles.get(t.active_job_id or "")
                or openers.get(t.thread_id)
                or "new session"
            )[:80],
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in threads
    ]


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: ThreadId,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> Response:
    """Remove a session and its messages. The pieces it made are left alone.

    A generation outlives the conversation that produced it: it is in explore, it may
    be exported, and it has its own delete that reference-counts the rasters shared
    with revisions. Removing a session is forgetting the discussion, not the work.

    The messages go explicitly rather than by cascade. 0007 declares ON DELETE CASCADE
    and Postgres honours it, but the test suite runs SQLite, where foreign keys are
    off unless a pragma turns them on; deleting here behaves the same on both.
    """
    thread = await _owned_thread(thread_id, agent_id, session)
    for message in await _messages(thread.thread_id, session):
        await session.delete(message)
    await session.delete(thread)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{thread_id}/generate", response_model=ThreadRead)
async def generate_in_thread(
    thread_id: ThreadId,
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
    settings: Settings = Depends(get_settings),
) -> ThreadRead:
    """Start a piece from the create deck, recorded as a turn in this session.

    Deliberately not routed through /turn, even though a turn can already start a
    new piece. Four reasons, each of which would be a bug:

    - /turn asks the model what the message means and fails closed to `answer`.
      Pressing generate would sometimes return a sentence and no render. Generate
      must always generate.
    - TurnRequest carries no brand, so the deck's kit would be silently dropped.
    - _act inherits kind, width and height from the open job, so changing size or
      kind in the deck mid-session would be ignored.
    - It would put a model call, up to chat_timeout_s of it, on the app's fastest path.

    So this is deterministic: the same two rows a turn writes, no interpretation. The
    reply states intent only, like every other reply here; the landed line added when
    the job finishes is the one that describes what happened.
    """
    thread = await _owned_thread(thread_id, agent_id, session)

    if body.aesthetic_version != BASELINE:
        ckpt = await session.get(Checkpoint, body.aesthetic_version)
        if ckpt is None or ckpt.kind != "style-lora":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown aesthetic version")

    started = (
        await session.exec(
            select(ChatMessage.message_id).where(
                ChatMessage.thread_id == thread.thread_id, ChatMessage.job_id.is_not(None)  # type: ignore[union-attr]
            )
        )
    ).all()
    if len(started) >= settings.chat_max_jobs_per_thread:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This session has hit its render limit; start a new one",
        )

    user_message = ChatMessage(
        message_id=str(uuid.uuid4()),
        thread_id=thread.thread_id,
        role="user",
        text=body.prompt.strip(),
    )
    session.add(user_message)

    job = Job(
        job_id=str(uuid.uuid4()),
        prompt=body.prompt.strip(),
        aesthetic_version=body.aesthetic_version,
        kind=body.kind,
        brand=body.brand.model_dump() if body.brand else None,
        width=body.width,
        height=body.height,
        requested_by=agent_id,
    )
    turn, job_id = await _enqueue(
        ChatTurn(reply="making that now.", action="new_direction", brief=body.prompt.strip()),
        job,
        session,
    )

    session.add(
        ChatMessage(
            message_id=str(uuid.uuid4()),
            thread_id=thread.thread_id,
            role="assistant",
            text=turn.reply,
            action=turn.action if turn.is_action() else None,
            job_id=job_id,
        )
    )
    if job_id:
        thread.active_job_id = job_id
    thread.updated_at = user_message.created_at
    session.add(thread)
    await session.commit()

    messages = await _messages(thread.thread_id, session)
    return ThreadRead(
        thread_id=thread.thread_id,
        active_job_id=thread.active_job_id,
        messages=[MessageRead(**m.model_dump()) for m in messages],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.get("/{thread_id}", response_model=ThreadRead)
async def read_thread(
    thread_id: ThreadId,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
) -> ThreadRead:
    thread = await _owned_thread(thread_id, agent_id, session)
    messages = await _messages(thread.thread_id, session)
    await _settle(messages, session)
    return ThreadRead(
        thread_id=thread.thread_id,
        active_job_id=thread.active_job_id,
        messages=[MessageRead(**m.model_dump()) for m in messages],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.post("/{thread_id}/turn", response_model=ThreadRead)
async def take_turn(
    thread_id: ThreadId,
    body: TurnRequest,
    session: AsyncSession = Depends(get_session),
    agent_id: str = Depends(verify_agent_token),
    settings: Settings = Depends(get_settings),
) -> ThreadRead:
    thread = await _owned_thread(thread_id, agent_id, session)
    history_rows = await _messages(thread.thread_id, session)
    await _settle(history_rows, session)

    active = await session.get(Job, thread.active_job_id) if thread.active_job_id else None
    if active is not None and active.requested_by != agent_id:
        active = None

    user_message = ChatMessage(
        message_id=str(uuid.uuid4()),
        thread_id=thread.thread_id,
        role="user",
        text=body.message.strip(),
    )
    session.add(user_message)
    await session.commit()

    turn = (
        _quick_turn(body.quick, active)
        if body.quick
        else await interpret(
            message=body.message,
            history=_history(history_rows, settings.chat_history_turns),
            plan=active.plan if active else None,
            prompt=active.prompt if active else "",
            status=active.status if active else "none",
            settings=settings,
        )
    )

    job_id: str | None = None
    if turn.is_action():
        turn, job_id = await _act(turn, thread, active, body, agent_id, session, settings)

    assistant = ChatMessage(
        message_id=str(uuid.uuid4()),
        thread_id=thread.thread_id,
        role="assistant",
        text=turn.reply,
        action=turn.action if turn.is_action() else None,
        job_id=job_id,
    )
    session.add(assistant)
    if job_id:
        thread.active_job_id = job_id
    thread.updated_at = user_message.created_at
    session.add(thread)
    await session.commit()

    messages = await _messages(thread.thread_id, session)
    return ThreadRead(
        thread_id=thread.thread_id,
        active_job_id=thread.active_job_id,
        messages=[MessageRead(**m.model_dump()) for m in messages],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _history(rows: list[ChatMessage], limit: int) -> list[dict[str, str]]:
    """The last `limit` turns as plain messages.

    Bounded on purpose: the piece summary already carries the state older turns would
    be needed for, and a 7B model's instruction following falls off well before its
    context window does.
    """
    recent = rows[-limit:] if limit > 0 else []
    return [{"role": r.role, "content": r.text} for r in recent if r.text]


def _quick_turn(quick: str, active: Job | None) -> ChatTurn:
    """A chip's intent, without a model call.

    Recompose cycles rather than asks, which is what the chip meant when it was a
    client-side button - pressing it repeatedly walks the three compositions.
    """
    if quick == "swap_photo":
        return ChatTurn(
            reply="repainting the photo. same layout, same palette.",
            action="revise",
            rerender_photo=True,
        )
    current = (active.plan or {}).get("composition", "anchor") if active else "anchor"
    index = COMPOSITIONS.index(current) if current in COMPOSITIONS else 0
    following = COMPOSITIONS[(index + 1) % len(COMPOSITIONS)]
    return ChatTurn(
        reply=f"recomposing to {following}.",
        action="revise",
        composition=following,  # type: ignore[arg-type]
    )


def _cannot(reply: str) -> ChatTurn:
    """Degrade an action to a plain answer. The user gets a reason, not a 409."""
    return ChatTurn(reply=reply, action="answer")


async def _act(
    turn: ChatTurn,
    thread: ChatThread,
    active: Job | None,
    body: TurnRequest,
    agent_id: str,
    session: AsyncSession,
    settings: Settings,
) -> tuple[ChatTurn, str | None]:
    """Carry out the turn's action, or explain why it cannot happen.

    Returns the turn to record (possibly downgraded to `answer`) and the job it
    started, if any.
    """
    started = (
        await session.exec(
            select(ChatMessage.message_id).where(
                ChatMessage.thread_id == thread.thread_id, ChatMessage.job_id.is_not(None)  # type: ignore[union-attr]
            )
        )
    ).all()
    if len(started) >= settings.chat_max_jobs_per_thread:
        return (
            _cannot(
                "this thread has hit its render limit. start a new one and i will pick "
                "up from the current piece."
            ),
            None,
        )

    if turn.action == "new_direction":
        job = Job(
            job_id=str(uuid.uuid4()),
            prompt=(turn.brief or body.message).strip(),
            aesthetic_version=active.aesthetic_version if active else body.aesthetic_version,
            kind=active.kind if active else body.kind,
            brand=active.brand if active else None,
            width=active.width if active else body.width,
            height=active.height if active else body.height,
            requested_by=agent_id,
        )
        return await _enqueue(turn, job, session)

    # revise and edit_copy both need a finished poster with a plan to work from.
    if active is None:
        return _cannot("there is no piece open yet. describe one and i will make it."), None
    # Status first: an unfinished poster also has no plan yet, and "still rendering"
    # is the true reason - "no layout to change" would send someone looking for a bug.
    if active.status != "done":
        return _cannot("still rendering that one. give it a moment and say it again."), None
    if active.kind != "poster" or not active.plan:
        return _cannot(f"a {active.kind} has no layout to change. i can make a new one."), None

    plan = dict(active.plan)
    revise: dict[str, Any] = {"source_job_id": active.job_id, "rerender_photo": False}
    if turn.action == "revise":
        if turn.composition:
            plan["composition"] = turn.composition
        if turn.typeface:
            plan["typeface"] = turn.typeface
        revise["rerender_photo"] = turn.rerender_photo
        # What this revision touched, so the landed line can name it later without
        # re-reading the plan (where a changed and an unchanged field look alike).
        revise["changed"] = [
            name
            for name, value in (
                ("composition", turn.composition),
                ("typeface", turn.typeface),
                ("rerender_photo", turn.rerender_photo),
            )
            if value
        ]
    else:
        plan = apply_copy_edits(plan, turn.copy_edits)
        # Recorded so the landed line can name the roles that changed without
        # trusting anything the model said about them.
        revise["copy_roles"] = list(dict.fromkeys(e.role for e in turn.copy_edits))

    job = Job(
        job_id=str(uuid.uuid4()),
        prompt=active.prompt,
        aesthetic_version=active.aesthetic_version,
        kind="poster",
        brand=active.brand,
        plan=plan,
        revise=revise,
        width=active.width,
        height=active.height,
        requested_by=agent_id,
    )
    return await _enqueue(turn, job, session)


async def _enqueue(turn: ChatTurn, job: Job, session: AsyncSession) -> tuple[ChatTurn, str | None]:
    session.add(job)
    await session.commit()
    try:
        await run_in_threadpool(enqueue_generation, job.job_id)
    except Exception:  # noqa: BLE001
        log.exception("chat: could not enqueue %s", job.job_id)
        job.status = "error"
        job.error = "Could not queue the job; try again"
        session.add(job)
        await session.commit()
        # A queue outage is not something to say nothing about, but it is also not a
        # reason to lose the turn: the thread keeps the exchange and says what broke.
        return _cannot("could not queue that render. the worker looks down."), None
    return turn, job.job_id
