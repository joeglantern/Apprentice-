"""Chat turns: routing, the action each one takes, and what it refuses to do.

The model is stubbed everywhere below. What is being tested is not whether a 7B picks
the right action - that is a prompt-quality question, measured against real messages -
but that every action a model can return is carried out correctly, and that every way
a turn can go wrong degrades to talking instead of to a render.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import chat as chat_mod
from app.chat import ChatTurn, apply_copy_edits, deterministic_turn, landed_line, piece_summary
from app.config import Settings
from app.director import heuristic_plan
from tests.conftest import AUTH_A, AUTH_B

PLAN = heuristic_plan("Concert poster for Friday", 1080, 1350, None).model_dump()


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "anthropic_api_key": "",
        "local_director_url": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# --- the schema's own rules ------------------------------------------------------


def test_an_action_must_carry_a_payload() -> None:
    with pytest.raises(ValueError):
        ChatTurn(reply="recomposing.", action="revise")
    with pytest.raises(ValueError):
        ChatTurn(reply="rewriting.", action="edit_copy")
    with pytest.raises(ValueError):
        ChatTurn(reply="on it.", action="new_direction", brief="  ")


def test_talking_and_acting_at_once_is_rejected() -> None:
    """The one failure that would surprise someone: a reply that says nothing is
    changing, next to a job that changed something."""
    with pytest.raises(ValueError):
        ChatTurn(reply="bebas suits the mood.", action="answer", composition="split")


# --- the fallback ladder ---------------------------------------------------------


async def test_interpret_falls_back_to_deterministic_when_nothing_is_configured() -> None:
    turn = await chat_mod.interpret(
        message="make it a split layout",
        history=[],
        plan=PLAN,
        prompt="Concert poster",
        status="done",
        settings=_settings(),
    )
    assert turn.action == "revise" and turn.composition == "split"


async def test_interpret_uses_the_local_model_when_it_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(settings, messages, schema):  # noqa: ANN001, ANN202
        # The piece summary and the message travel together in the last turn.
        assert "They said: shorter headline" in messages[-1]["content"]
        return ChatTurn(
            reply="tightening the headline.",
            action="edit_copy",
            copy_edits=[{"role": "headline", "content": "Friday Night"}],
        ).model_dump_json()

    monkeypatch.setattr(chat_mod, "_call_local", fake)
    turn = await chat_mod.interpret(
        message="shorter headline",
        history=[],
        plan=PLAN,
        prompt="Concert poster",
        status="done",
        settings=_settings(local_director_url="http://legion:11434"),
    )
    assert turn.action == "edit_copy" and turn.copy_edits[0].content == "Friday Night"


async def test_a_local_model_that_is_down_degrades_to_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(settings, messages, schema):  # noqa: ANN001, ANN202
        raise httpx.ConnectError("tunnel is down")

    monkeypatch.setattr(chat_mod, "_call_local", boom)
    turn = await chat_mod.interpret(
        message="what typeface is this",
        history=[],
        plan=PLAN,
        prompt="Concert poster",
        status="done",
        settings=_settings(local_director_url="http://legion:11434"),
    )
    # Not recognised by the keyword router, so it talks. It does not guess a render.
    assert turn.action == "answer"


async def test_a_local_model_that_answers_badly_retries_then_gives_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def junk(settings, messages, schema):  # noqa: ANN001, ANN202
        calls.append(1)
        return '{"reply": "sure", "action": "revise"}'  # fails the payload rule

    monkeypatch.setattr(chat_mod, "_call_local", junk)
    turn = await chat_mod.interpret(
        message="hmm",
        history=[],
        plan=PLAN,
        prompt="Concert poster",
        status="done",
        settings=_settings(local_director_url="http://legion:11434"),
    )
    assert len(calls) == 2
    assert turn.action == "answer"


def test_the_deterministic_router_never_invents_a_render_it_cannot_justify() -> None:
    assert deterministic_turn("try a serif instead", has_piece=True).action == "answer"
    assert deterministic_turn("make it centered", has_piece=True).composition == "centered"
    assert deterministic_turn("a poster for the gym", has_piece=False).action == "new_direction"


# --- context shaping -------------------------------------------------------------


def test_piece_summary_is_short_and_carries_the_copy() -> None:
    text = piece_summary(PLAN, "Concert poster for Friday", "done")
    assert "Concert poster for Friday" in text
    assert "headline:" in text
    # The rationale and per-element notes are the bulk of a plan and are not resent.
    assert "rationale" not in text
    assert len(text) < 1200


def test_copy_edits_patch_only_the_named_roles() -> None:
    patched = apply_copy_edits(PLAN, [chat_mod.CopyEdit(role="headline", content="Friday Night")])
    roles = {e["role"]: e for e in patched["elements"]}
    assert roles["headline"]["content"] == "Friday Night"
    assert roles["image"] == {e["role"]: e for e in PLAN["elements"]}["image"]
    # The original is untouched, so a failed job cannot corrupt the source plan.
    assert {e["role"]: e for e in PLAN["elements"]}["headline"]["content"] != "Friday Night"


def test_a_copy_edit_for_a_missing_role_adds_it() -> None:
    plan = {"elements": [{"role": "headline", "content": "x", "priority": 1}]}
    patched = apply_copy_edits(plan, [chat_mod.CopyEdit(role="cta", content="Book now")])
    assert [e["role"] for e in patched["elements"]] == ["headline", "cta"]


def test_landed_line_reports_the_change_or_the_failure() -> None:
    turn = ChatTurn(reply="recomposing.", action="revise", composition="split")
    assert landed_line(turn, ok=True) == "recomposed to split."
    assert "did not render" in landed_line(turn, ok=False, error="comfy timed out")


# --- the endpoint ----------------------------------------------------------------


async def _thread(client: AsyncClient, job_id: str | None = None) -> str:
    r = await client.post("/chat", json={"job_id": job_id} if job_id else {}, headers=AUTH_A)
    assert r.status_code == 201
    return str(r.json()["thread_id"])


async def _finished_job(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> str:
    r = await client.post("/generate", json={"prompt": "Concert poster"}, headers=AUTH_A)
    job_id = r.json()["job_id"]
    async with session_maker() as session:
        from app.models import Job

        job = await session.get(Job, job_id)
        job.status = "done"
        job.plan = PLAN
        job.result = {"layers": [{"type": "image", "raster_key": "renders/x/L01.png"}]}
        session.add(job)
        await session.commit()
    return str(job_id)


@pytest.fixture
def no_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.routes.chat as chat_route
    import app.routes.generate as gen_mod

    monkeypatch.setattr(gen_mod, "enqueue_generation", lambda job_id: None)
    monkeypatch.setattr(chat_route, "enqueue_generation", lambda job_id: None)


def _stub(monkeypatch: pytest.MonkeyPatch, turn: ChatTurn) -> None:
    async def fake(**kwargs: object) -> ChatTurn:
        return turn

    monkeypatch.setattr("app.routes.chat.interpret", fake)


async def test_a_copy_edit_revises_the_open_piece_rather_than_replacing_it(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)
    _stub(
        monkeypatch,
        ChatTurn(
            reply="tightening the headline.",
            action="edit_copy",
            copy_edits=[{"role": "headline", "content": "Friday Night"}],
        ),
    )

    r = await client.post(
        f"/chat/{thread_id}/turn", json={"message": "shorter headline"}, headers=AUTH_A
    )
    assert r.status_code == 200
    body = r.json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assistant = body["messages"][1]
    assert assistant["text"] == "tightening the headline."
    assert assistant["action"] == "edit_copy"
    new_id = assistant["job_id"]
    assert new_id and new_id != job_id
    assert body["active_job_id"] == new_id

    async with session_maker() as session:
        from app.models import Job

        new = await session.get(Job, new_id)
        # A revision of the same piece: same brief, same photo, patched copy.
        assert new.prompt == "Concert poster"
        assert new.revise["source_job_id"] == job_id
        assert new.revise["rerender_photo"] is False
        assert new.revise["copy_roles"] == ["headline"]
        headline = next(e for e in new.plan["elements"] if e["role"] == "headline")
        assert headline["content"] == "Friday Night"


async def test_an_answer_turn_starts_no_job(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)
    _stub(monkeypatch, ChatTurn(reply="bebas suits a concert.", action="answer"))

    r = await client.post(f"/chat/{thread_id}/turn", json={"message": "why bebas"}, headers=AUTH_A)
    assistant = r.json()["messages"][1]
    assert assistant["job_id"] is None and assistant["action"] is None
    assert r.json()["active_job_id"] == job_id  # unchanged


async def test_a_revision_of_an_unfinished_piece_is_explained_not_queued(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    r = await client.post("/generate", json={"prompt": "Concert poster"}, headers=AUTH_A)
    job_id = r.json()["job_id"]  # still queued, no plan
    thread_id = await _thread(client, job_id)
    _stub(monkeypatch, ChatTurn(reply="recomposing.", action="revise", composition="split"))

    r = await client.post(
        f"/chat/{thread_id}/turn", json={"message": "make it split"}, headers=AUTH_A
    )
    assistant = r.json()["messages"][1]
    assert assistant["job_id"] is None
    assert "still rendering" in assistant["text"]


async def test_a_new_direction_with_no_open_piece_starts_one(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, no_queue: None
) -> None:
    thread_id = await _thread(client)
    _stub(
        monkeypatch,
        ChatTurn(reply="making that.", action="new_direction", brief="poster for a gym opening"),
    )
    r = await client.post(
        f"/chat/{thread_id}/turn", json={"message": "poster for a gym opening"}, headers=AUTH_A
    )
    assistant = r.json()["messages"][1]
    assert assistant["action"] == "new_direction" and assistant["job_id"]


async def test_the_landed_line_appears_only_once_the_job_finishes(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)
    _stub(
        monkeypatch,
        ChatTurn(reply="recomposing to split.", action="revise", composition="split"),
    )
    r = await client.post(f"/chat/{thread_id}/turn", json={"message": "split it"}, headers=AUTH_A)
    new_id = r.json()["messages"][1]["job_id"]
    # Mid-render: the reply stands alone and claims nothing about a result.
    r = await client.get(f"/chat/{thread_id}", headers=AUTH_A)
    assert r.json()["messages"][1]["landed"] is None

    async with session_maker() as session:
        from app.models import Job

        job = await session.get(Job, new_id)
        job.status = "done"
        session.add(job)
        await session.commit()

    r = await client.get(f"/chat/{thread_id}", headers=AUTH_A)
    assert r.json()["messages"][1]["landed"] == "recomposed to split."


async def test_a_failed_job_says_so_in_the_thread(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)
    _stub(
        monkeypatch, ChatTurn(reply="repainting the photo.", action="revise", rerender_photo=True)
    )
    r = await client.post(f"/chat/{thread_id}/turn", json={"message": "new photo"}, headers=AUTH_A)
    new_id = r.json()["messages"][1]["job_id"]

    async with session_maker() as session:
        from app.models import Job

        job = await session.get(Job, new_id)
        job.status = "error"
        job.error = "comfyui unreachable"
        session.add(job)
        await session.commit()

    r = await client.get(f"/chat/{thread_id}", headers=AUTH_A)
    assert "comfyui unreachable" in r.json()["messages"][1]["landed"]


async def test_the_job_cap_stops_a_thread_becoming_a_render_queue(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    from app.config import get_settings

    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)
    # Through the environment rather than the dependency: Depends(get_settings) holds
    # the function object captured when the route was defined, so patching the name in
    # the module has no effect on a live request.
    monkeypatch.setenv("CHAT_MAX_JOBS_PER_THREAD", "1")
    get_settings.cache_clear()
    _stub(monkeypatch, ChatTurn(reply="repainting.", action="revise", rerender_photo=True))

    first = await client.post(f"/chat/{thread_id}/turn", json={"message": "a"}, headers=AUTH_A)
    assert first.json()["messages"][1]["job_id"]
    second = await client.post(f"/chat/{thread_id}/turn", json={"message": "b"}, headers=AUTH_A)
    assistant = second.json()["messages"][3]
    assert assistant["job_id"] is None and "render limit" in assistant["text"]
    get_settings.cache_clear()


async def test_a_thread_belongs_to_one_agent(client: AsyncClient, no_queue: None) -> None:
    thread_id = await _thread(client)
    assert (await client.get(f"/chat/{thread_id}", headers=AUTH_B)).status_code == 404
    r = await client.post(f"/chat/{thread_id}/turn", json={"message": "hi"}, headers=AUTH_B)
    assert r.status_code == 404
    assert (await client.get(f"/chat/{thread_id}")).status_code == 401


async def test_a_quick_action_skips_the_model_and_still_lands_in_the_thread(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)

    async def never(**kwargs: object) -> ChatTurn:
        raise AssertionError("a chip must not cost a model call")

    monkeypatch.setattr("app.routes.chat.interpret", never)

    r = await client.post(
        f"/chat/{thread_id}/turn",
        json={"message": "swap photo", "quick": "swap_photo"},
        headers=AUTH_A,
    )
    assistant = r.json()["messages"][1]
    assert assistant["action"] == "revise" and assistant["job_id"]
    async with session_maker() as session:
        from app.models import Job

        assert (await session.get(Job, assistant["job_id"])).revise["rerender_photo"] is True


async def test_recompose_cycles_through_the_three_compositions(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    no_queue: None,
) -> None:
    job_id = await _finished_job(client, session_maker)
    thread_id = await _thread(client, job_id)
    async with session_maker() as session:
        from app.models import Job

        job = await session.get(Job, job_id)
        job.plan = {**PLAN, "composition": "centered"}
        session.add(job)
        await session.commit()

    r = await client.post(
        f"/chat/{thread_id}/turn",
        json={"message": "recompose", "quick": "recompose"},
        headers=AUTH_A,
    )
    assistant = r.json()["messages"][1]
    assert assistant["text"] == "recomposing to split."
    async with session_maker() as session:
        from app.models import Job

        assert (await session.get(Job, assistant["job_id"])).plan["composition"] == "split"


# --- sessions: naming, listing, removing ------------------------------------------


async def test_a_session_is_named_after_its_piece(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession], no_queue: None
) -> None:
    """A sidebar of raw prompts reads as instructions; titles.py already wrote a name."""
    job_id = await _finished_job(client, session_maker)
    async with session_maker() as session:
        from app.models import Job

        job = await session.get(Job, job_id)
        job.title = "Rooftop Vibes"
        session.add(job)
        await session.commit()

    # Adopt the titled piece and leave it as the open one; generating here would
    # replace active_job_id with a fresh, still untitled job.
    thread_id = await _thread(client, job_id)

    rows = (await client.get("/chat", headers=AUTH_A)).json()
    mine = next(r for r in rows if r["thread_id"] == thread_id)
    assert mine["title"] == "Rooftop Vibes"


async def test_a_session_with_no_title_falls_back_to_its_opening_message(
    client: AsyncClient, no_queue: None
) -> None:
    thread_id = await _thread(client)
    await client.post(
        f"/chat/{thread_id}/generate", json={"prompt": "poster for a gym opening"}, headers=AUTH_A
    )
    rows = (await client.get("/chat", headers=AUTH_A)).json()
    assert next(r for r in rows if r["thread_id"] == thread_id)["title"] == "poster for a gym opening"


async def test_a_session_that_has_said_nothing_still_has_a_name(client: AsyncClient) -> None:
    thread_id = await _thread(client)
    rows = (await client.get("/chat", headers=AUTH_A)).json()
    assert next(r for r in rows if r["thread_id"] == thread_id)["title"] == "new session"


async def test_sessions_are_listed_newest_first(client: AsyncClient, no_queue: None) -> None:
    first = await _thread(client)
    second = await _thread(client)
    await client.post(f"/chat/{first}/generate", json={"prompt": "the older one"}, headers=AUTH_A)
    await client.post(f"/chat/{second}/generate", json={"prompt": "the newer one"}, headers=AUTH_A)
    ids = [r["thread_id"] for r in (await client.get("/chat", headers=AUTH_A)).json()]
    assert ids.index(second) < ids.index(first)


async def test_sessions_are_scoped_to_their_owner(client: AsyncClient) -> None:
    thread_id = await _thread(client)
    assert all(r["thread_id"] != thread_id for r in (await client.get("/chat", headers=AUTH_B)).json())


async def test_deleting_a_session_keeps_the_work_it_made(
    client: AsyncClient, no_queue: None
) -> None:
    """Forgetting the conversation is not forgetting the piece: a generation lives in
    explore, may already be exported, and has its own delete."""
    thread_id = await _thread(client)
    r = await client.post(
        f"/chat/{thread_id}/generate", json={"prompt": "a poster"}, headers=AUTH_A
    )
    job_id = r.json()["active_job_id"]

    assert (await client.delete(f"/chat/{thread_id}", headers=AUTH_A)).status_code == 204
    assert (await client.get(f"/chat/{thread_id}", headers=AUTH_A)).status_code == 404
    assert (await client.get(f"/generate/{job_id}", headers=AUTH_A)).status_code == 200


async def test_deleting_someone_elses_session_is_a_404(client: AsyncClient) -> None:
    thread_id = await _thread(client)
    assert (await client.delete(f"/chat/{thread_id}", headers=AUTH_B)).status_code == 404
    assert (await client.get(f"/chat/{thread_id}", headers=AUTH_A)).status_code == 200


# --- generating inside a session --------------------------------------------------


async def test_generate_in_thread_never_asks_the_model(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, no_queue: None
) -> None:
    """The whole point of the endpoint. Pressing generate must always generate, never
    come back with a sentence because a router decided the message was a question."""

    async def explode(**kwargs: object) -> ChatTurn:
        raise AssertionError("generate must not call interpret")

    monkeypatch.setattr("app.routes.chat.interpret", explode)

    thread_id = await _thread(client)
    r = await client.post(
        f"/chat/{thread_id}/generate", json={"prompt": "poster for a jazz night"}, headers=AUTH_A
    )
    assert r.status_code == 200
    body = r.json()
    assert body["active_job_id"]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["text"] == "poster for a jazz night"
    assert body["messages"][1]["action"] == "new_direction"
    assert body["messages"][1]["job_id"] == body["active_job_id"]


async def test_generate_in_thread_keeps_the_decks_own_choices(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession], no_queue: None
) -> None:
    """A turn inherits kind and size from the open piece, which is right for a
    revision and wrong for the deck: the deck is explicit, and it also carries a brand
    kit that TurnRequest has nowhere to put."""
    poster = await _finished_job(client, session_maker)
    thread_id = await _thread(client, poster)

    r = await client.post(
        f"/chat/{thread_id}/generate",
        json={
            "prompt": "a square mark",
            "kind": "logo",
            "width": 1024,
            "height": 1024,
            "brand": {"name": "tide & salt", "palette": ["#0E3A3A"], "typeface": "grotesk"},
        },
        headers=AUTH_A,
    )
    assert r.status_code == 200

    async with session_maker() as session:
        from app.models import Job

        job = await session.get(Job, r.json()["active_job_id"])
        assert job.kind == "logo"
        assert (job.width, job.height) == (1024, 1024)
        assert job.brand["name"] == "tide & salt"


async def test_generate_in_thread_respects_the_render_cap(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, no_queue: None
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("CHAT_MAX_JOBS_PER_THREAD", "1")
    get_settings.cache_clear()
    thread_id = await _thread(client)
    first = await client.post(f"/chat/{thread_id}/generate", json={"prompt": "one"}, headers=AUTH_A)
    assert first.status_code == 200
    second = await client.post(f"/chat/{thread_id}/generate", json={"prompt": "two"}, headers=AUTH_A)
    assert second.status_code == 409
    get_settings.cache_clear()


async def test_generate_in_thread_rejects_an_unknown_aesthetic(
    client: AsyncClient, no_queue: None
) -> None:
    thread_id = await _thread(client)
    r = await client.post(
        f"/chat/{thread_id}/generate",
        json={"prompt": "a poster", "aesthetic_version": "eidolon-nope-1"},
        headers=AUTH_A,
    )
    assert r.status_code == 404
