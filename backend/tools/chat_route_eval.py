"""Routing accuracy for the chat turn, measured against a live local model.

The unit tests stub the model, because what they check is that every action is carried
out correctly. This checks the other half: whether the model on the far end actually
picks the right action for a real message. It is the only way to answer "is this model
good enough" without guessing, and the only honest basis for changing chat_model.

    cd backend
    DATABASE_URL=sqlite+aiosqlite:///:memory: python tools/chat_route_eval.py qwen3:8b

Needs Ollama reachable at localhost:11434 (the Legion, or through the tunnel). Costs
nothing but GPU seconds. Fifteen cases is small - it catches a model that is unfit, not
a subtle regression - so extend CASES with real messages as they come in, and rerun
before changing the model, the schema, or the system prompt. All three move the number.

Baseline, 2026-09-02, RTX 5060 8GB:
    qwen3:8b             15/15, 0 unusable answers, median 1.1s resident
    qwen2.5:7b-instruct   6/15, 5 unusable answers (validation failed twice over)
"""

from __future__ import annotations

import asyncio
import sys
import time

from app.chat import ChatTurn, interpret
from app.config import Settings
from app.director import heuristic_plan

PLAN = heuristic_plan("Poster for Mama Njeri's Kitchen, nyama choma in Kilimani", 1080, 1350, None)
PLAN_D = PLAN.model_dump()
PLAN_D.update({"composition": "anchor", "typeface": "bebas"})
for e in PLAN_D["elements"]:
    if e["role"] == "headline":
        e["content"] = "Choma Done Right In Kilimani Tonight"
    if e["role"] == "subhead":
        e["content"] = "Slow fire. Fresh goat. No shortcuts."

CASES: list[tuple[str, str]] = [
    ("make it a split layout", "revise"),
    ("try a serif instead", "revise"),
    ("the photo is not working, give me another one", "revise"),
    # The piece is already set in bebas, so the right move is to say so rather than
    # spend a render arriving where it already is.
    ("can you use bebas", "answer"),
    ("shorter headline", "edit_copy"),
    ("the headline should just say Choma Nights", "edit_copy"),
    ("change the subhead to mention the opening date", "edit_copy"),
    ("add a call to action", "edit_copy"),
    ("now do one for a christmas menu at the same place", "new_direction"),
    ("poster for a gym opening in westlands", "new_direction"),
    ("why did you pick bebas", "answer"),
    ("what sizes can you do", "answer"),
    ("looks good", "answer"),
    ("can you move the headline down 20 pixels", "answer"),
    ("export this as a pdf", "answer"),
]


async def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        anthropic_api_key="",
        local_director_url="http://localhost:11434",
        chat_model=model,
    )
    right = 0
    fell_back = 0
    times: list[float] = []
    print(f"model: {model}", file=sys.stderr)
    for message, expected in CASES:
        start = time.perf_counter()
        turn: ChatTurn = await interpret(
            message=message,
            history=[],
            plan=PLAN_D,
            prompt="Poster for Mama Njeri's Kitchen",
            status="done",
            settings=settings,
        )
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        # The deterministic router is the tell that the model failed twice.
        deterministic = turn.reply.startswith("the director model is offline")
        fell_back += deterministic
        ok = turn.action == expected and not deterministic
        right += ok
        mark = "ok " if ok else "MISS"
        extra = ""
        if turn.action == "edit_copy":
            extra = " -> " + "; ".join(f"{e.role}={e.content[:40]!r}" for e in turn.copy_edits)
        elif turn.action == "revise":
            extra = (
                f" -> {turn.composition or ''} {turn.typeface or ''} photo={turn.rerender_photo}"
            )
        print(
            f"{mark} {elapsed:5.1f}s  {message[:44]:<46} want={expected:<13} "
            f"got={turn.action:<13}{extra}",
            file=sys.stderr,
        )
        if not ok:
            print(f"      reply: {turn.reply[:110]}", file=sys.stderr)

    n = len(CASES)
    print(
        f"\n{model}: {right}/{n} routed correctly, {fell_back} hard failures, "
        f"median {sorted(times)[n // 2]:.1f}s, max {max(times):.1f}s",
        file=sys.stderr,
    )


asyncio.run(main())
