from __future__ import annotations

from ghost_training.eval_faces import MATRIX, summarise


def test_matrix_covers_tones_ages_and_hands() -> None:
    names = [n for n, _ in MATRIX]
    assert any(n.startswith("dark-") for n in names)
    assert any(n.startswith("medium-") for n in names)
    assert any(n.startswith("light-") for n in names)
    assert "hands-visible" in names and "group-mixed" in names


def test_summarise_reports_mean_worst_and_tone_spread() -> None:
    rows = [
        {"name": "dark-skin-woman-elder", "score": 9},
        {"name": "dark-skin-man-young", "score": 7},
        {"name": "light-skin-woman-young", "score": 6},
        {"name": "group-mixed", "score": None},
    ]
    s = summarise(rows)
    assert s["mean"] == 7.33
    assert s["worst"] == {"name": "light-skin-woman-young", "score": 6}
    assert s["tone_spread"] == 2.0  # dark mean 8.0 vs light 6.0


def test_summarise_survives_no_scores() -> None:
    assert summarise([{"name": "x", "score": None}]) == {
        "mean": None,
        "worst": None,
        "tone_spread": None,
    }
