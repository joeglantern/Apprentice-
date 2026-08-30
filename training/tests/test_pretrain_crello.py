"""Fixtures mirror a real downloaded shard row (integer class labels, absolute pixel
boxes, rgba strings, per-character bold), not the dataset card."""

from __future__ import annotations

from ghost_training.pretrain_crello import Labels, crello_row_to_payload
from ghost_training.serialize import parse, serialize

LABELS = Labels(
    {
        "type": [
            "SvgElement",
            "TextElement",
            "ImageElement",
            "ColoredBackground",
            "SvgMaskElement",
        ],
        "font": ["", "Montserrat", "Bebas Neue"],
        "text_align": ["", "left", "center", "right"],
        "category": ["holidaysCelebration", "foodDrinks"],
        "format": [
            "Instagram Story",
            "Instagram",
            "Facebook",
            "Facebook cover",
            "Twitter",
            "Facebook AD",
            "Poster",
        ],
    }
)


def crello_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "canvas_width": 1080,
        "canvas_height": 1350,
        "category": 1,
        "format": 6,
        "type": [3, 1, 2],
        "left": [0.0, 108.0, 540.0],
        "top": [0.0, 135.0, 67.5],
        "width": [1080.0, 432.0, 486.0],
        "height": [1350.0, 135.0, 675.0],
        "opacity": [1.0, 1.0, 1.0],
        "color": [["rgba(26, 26, 26, 1)"], [], ["rgba(0, 0, 0, 1)"]],
        "text": ["", "Grand Opening", ""],
        "font": [0, 2, 0],
        "font_size": [0.0, 48.0, 0.0],
        "font_bold": [
            [],
            [True, True, True, True, True, False, False, False, False, False, False, False, False],
            [],
        ],
        "text_color": [[], ["rgba(242, 166, 35, 1)"], []],
        "text_align": [0, 1, 0],
        "line_height": [1.0, 1.2, 1.0],
        "letter_spacing": [0.0, 2.0, 0.0],
    }
    row.update(overrides)
    return row


def test_maps_a_real_shaped_row_into_the_doc_01_schema() -> None:
    payload = crello_row_to_payload(crello_row(), LABELS)
    assert payload is not None
    assert payload["file"] == {"format": "Poster", "canvas": {"width": 1080, "height": 1350}}
    assert [layer["type"] for layer in payload["layers"]] == ["shape", "text", "image"]
    text = payload["layers"][1]
    assert text["text"] == "Grand Opening"
    assert text["bbox"] == {"x": 108, "y": 135, "width": 432, "height": 135}
    assert text["typography"]["font_family"] == "Bebas Neue"
    assert text["typography"]["font_size"] == 48
    assert text["typography"]["font_weight"] == 400  # 5 of 13 characters bold: not bold
    assert text["typography"]["letter_spacing"] == 2.0
    assert text["align"] == "left"
    assert text["color"]["hex"] == "#F2A623"
    assert payload["layers"][0]["color"]["hex"] == "#1A1A1A"


def test_mostly_bold_text_is_weight_700() -> None:
    payload = crello_row_to_payload(crello_row(font_bold=[[], [True] * 13, []]), LABELS)
    assert payload is not None
    assert payload["layers"][1]["typography"]["font_weight"] == 700


def test_missing_canvas_size_is_rejected() -> None:
    assert crello_row_to_payload(crello_row(canvas_width=0), LABELS) is None
    assert crello_row_to_payload(crello_row(canvas_height=None), LABELS) is None


def test_unknown_type_label_is_dropped_not_guessed_at() -> None:
    payload = crello_row_to_payload(crello_row(type=[3, 1, 99]), LABELS)
    assert payload is not None
    assert len(payload["layers"]) == 2


def test_empty_text_box_is_dropped() -> None:
    payload = crello_row_to_payload(crello_row(type=[3, 1], text=["", "   "]), LABELS)
    assert payload is None  # only the background is left, below the two-layer floor


def test_malformed_colour_is_omitted_not_fatal() -> None:
    payload = crello_row_to_payload(crello_row(color=[["not a colour"], [], []]), LABELS)
    assert payload is not None
    assert "color" not in payload["layers"][0]


def test_mapped_output_serialises_and_round_trips_through_parse() -> None:
    """End-to-end: a Crello row must survive the exact pipeline the layout model
    actually trains and infers through (serialize.py, docs/06 D2)."""
    payload = crello_row_to_payload(crello_row(), LABELS)
    assert payload is not None
    text = serialize(payload)
    assert "<text id=L02" in text and "weight=400" in text
    parsed = parse(text, canvas_width=1080)
    assert len(parsed["layers"]) == len(payload["layers"])
