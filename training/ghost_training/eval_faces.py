"""Face-integrity evaluation across a diverse portrait matrix (docs/06 D20).

Renders a fixed set of portrait briefs spanning skin tones, ages and genders
through the production pipeline, then scores each result with the local VLM
(Ollama, qwen2.5vl:3b) on face integrity - eyes, teeth, hands, artefacts - and
writes a JSON report. Run it before and after a pipeline change; a drop on any
row is a regression, and a consistent gap between rows is bias worth fixing.
FairFace (CC BY 4.0, docs/06 D18) remains the reference for a stricter,
classifier-based version later; this harness needs nothing beyond what the
Legion already runs.

Usage:
    GHOST_API_URL=http://127.0.0.1:18001 GHOST_API_TOKEN=... \
        python -m ghost_training.eval_faces --out report.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from collections.abc import Callable
from typing import Any

# Fixed briefs: same structure, varied person. Editing this list invalidates
# comparisons with older reports - add rows, do not rewrite them.
MATRIX = [
    (
        "dark-skin-woman-elder",
        "Portrait of a dark-skinned Kenyan woman in her seventies, headscarf, soft window light, 85mm",
    ),
    (
        "dark-skin-man-young",
        "Portrait of a dark-skinned young Kenyan man laughing, natural light, 85mm",
    ),
    (
        "medium-skin-woman-adult",
        "Portrait of a brown-skinned Ethiopian woman in her thirties smiling, natural light, 85mm",
    ),
    (
        "medium-skin-man-elder",
        "Portrait of a brown-skinned Somali man in his sixties with a grey beard, natural light, 85mm",
    ),
    (
        "light-skin-woman-young",
        "Portrait of a light-skinned young European woman smiling, natural light, 85mm",
    ),
    (
        "light-skin-man-adult",
        "Portrait of a light-skinned South Asian man in his forties, natural light, 85mm",
    ),
    (
        "group-mixed",
        "Three friends of different ethnicities laughing together at a table, all faces visible, 50mm",
    ),
    (
        "hands-visible",
        "A dark-skinned Kenyan potter shaping clay with both hands clearly visible, natural light, 50mm",
    ),
]

SCORE_PROMPT = (
    "Score this generated portrait 1-10 on face integrity: natural eyes, correct "
    "teeth, no warped features, correct hands if visible, no AI artefacts. Reply "
    "with only JSON having an integer field named score and a list field named "
    "problems that describes, in your own words, each defect you actually see in "
    "this specific image. If you see no defects, problems must be an empty list."
)


def _retrying(fn: Callable[[], Any], attempts: int = 3, wait: float = 5.0) -> Any:
    """Retries transient transport failures (a tunnel hiccup mid-poll killed a real
    run); anything still failing after the attempts propagates."""
    import httpx

    for i in range(attempts):
        try:
            return fn()
        except (httpx.TransportError, httpx.HTTPStatusError):
            if i == attempts - 1:
                raise
            time.sleep(wait)


def render(
    api_url: str, token: str, prompt: str, timeout: int = 1500
) -> tuple[str | None, bytes | None]:
    import httpx

    headers = {"Authorization": f"Bearer {token}"}
    r = _retrying(
        lambda: httpx.post(
            f"{api_url}/generate",
            headers=headers,
            json={"prompt": prompt, "kind": "image", "width": 832, "height": 1024},
            timeout=30,
        )
    )
    r.raise_for_status()
    job_id = r.json()["job_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = _retrying(
            lambda: httpx.get(f"{api_url}/generate/{job_id}", headers=headers, timeout=30)
        ).json()
        if d["status"] in ("done", "error"):
            break
        time.sleep(6)
    layers = (d.get("result") or {}).get("layers") or []
    if not layers or not layers[0].get("raster_key"):
        return job_id, None
    img = _retrying(
        lambda: httpx.get(
            f"{api_url}/generate/{job_id}/raster/{layers[0]['layer_id']}",
            headers=headers,
            timeout=60,
        )
    )
    img.raise_for_status()
    return job_id, img.content


def score(image: bytes, ollama_url: str, model: str = "qwen2.5vl:3b") -> dict[str, Any]:
    import httpx

    r = httpx.post(
        f"{ollama_url}/api/chat",
        timeout=180,
        json={
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
            "messages": [
                {
                    "role": "user",
                    "content": SCORE_PROMPT,
                    "images": [base64.b64encode(image).decode("ascii")],
                }
            ],
        },
    )
    r.raise_for_status()
    try:
        return json.loads(r.json()["message"]["content"])
    except (ValueError, KeyError):
        return {"score": None, "problems": ["unscorable answer"]}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregates a report: mean score, worst row, and the spread between the
    best- and worst-scoring skin-tone groups (the bias signal)."""
    scored = [r for r in rows if isinstance(r.get("score"), (int, float))]
    if not scored:
        return {"mean": None, "worst": None, "tone_spread": None}
    mean = round(sum(r["score"] for r in scored) / len(scored), 2)
    worst = min(scored, key=lambda r: r["score"])
    by_tone: dict[str, list[float]] = {}
    for r in scored:
        tone = r["name"].split("-")[0]
        by_tone.setdefault(tone, []).append(r["score"])
    tone_means = {
        t: sum(v) / len(v) for t, v in by_tone.items() if t in ("dark", "medium", "light")
    }
    spread = round(max(tone_means.values()) - min(tone_means.values()), 2) if tone_means else None
    return {
        "mean": mean,
        "worst": {"name": worst["name"], "score": worst["score"]},
        "tone_spread": spread,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="face_eval.json")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434")
    args = ap.parse_args()
    api_url = os.environ.get("GHOST_API_URL", "").rstrip("/")
    token = os.environ.get("GHOST_API_TOKEN", "")
    if not api_url or not token:
        print("set GHOST_API_URL and GHOST_API_TOKEN")
        return 2
    rows = []
    for name, prompt in MATRIX:
        job_id, image = render(api_url, token, prompt)
        if image is None:
            rows.append(
                {"name": name, "job_id": job_id, "score": None, "problems": ["render failed"]}
            )
            continue
        verdict = score(image, args.ollama)
        rows.append({"name": name, "job_id": job_id, **verdict})
        print(name, verdict.get("score"), verdict.get("problems"))
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rows": rows,
        "summary": summarise(rows),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
