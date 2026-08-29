---
name: psd-metadata-extraction
description: Extract layer trees, bounding boxes, typography, and color data from .psd/.ai files into the project's JSON layout schema. Use when working on the collector's parsing code, the ingestion API's payload validation, or the training data pipeline.
---

# PSD metadata extraction

## Target schema
The output of any parser in this repo is the asset record in
`docs/01_ARCHITECTURAL_BLUEPRINT.md` §3. Key fields:

- `file.canvas` - `{width, height, dpi}` from the PSD header.
- `layers[]` - one entry per *leaf* layer, each with `layer_id`, `name`,
  `type` (`text` | `shape` | `image`), `z_index` (0 = bottom, increasing
  toward the top of the stack), `bbox` `{x, y, width, height}` in canvas
  pixels, optional `typography` (text layers only), `color` `{hex, opacity}`.
- `palette[]` - hex strings, dominant colours of the flattened composite
  (dedupe, uppercase `#RRGGBB`, max ~8 entries).
- `consent` - written by the collector, never by the parser. The parser
  must not invent it; the collector attaches it at capture time.

## Where parsing lives
- Collector side: `collector-mac/` (`docs/02` §1) - `psd-tools` runs on the
  Mac so no design file leaves the machine unparsed; the sync module posts
  the JSON record plus the export file.
- Training side: `training/` may re-run the *same* parser for re-extraction
  when the schema evolves. Keep the parser in one importable module and
  share it; do not fork two copies.

## psd-tools conventions
- `PSDImage.open(path)`; iterate with `psd.descendants()` for leaves,
  tracking depth so groups become path-like names (`Group/Child`).
- `layer.bbox` returns `(left, top, right, bottom)` - convert to
  `{x, y, width, height}`.
- Text: `layer.kind == "type"`; font family/size/tracking/leading come from
  `layer.engine_dict` / `layer.text_data` - guard every lookup, these are
  frequently missing or partial.
- Shape: `layer.kind in {"shape", "solidcolorfill"}`; solid-fill colour from
  `layer.tagged_blocks` (`SOLID_COLOR_SHEET_SETTING`).
- Image/pixel layers: `layer.kind == "pixel"`; colour = sampled dominant
  colour of the layer's composite, not a fill.
- `.ai` files: modern `.ai` is PDF-compatible; parse the PDF layer/OCG
  structure if available, otherwise fall back to treating it as an opaque
  image with palette only. Do not shell out to Illustrator.

## Edge cases to handle explicitly
- Nested groups (flatten to leaves, keep group path in `name`).
- Adjustment layers -> skip; they have no geometry.
- Clipping masks -> keep the base layer; the clipped layer's bbox is
  intersected with the base's bbox.
- Hidden layers -> include with `"visible": false` rather than dropping;
  the training curation step decides.
- Smart objects -> `type: image`, bbox from the placed bounds.
- Layers with zero-area bbox -> drop.
- Very large files: never rasterise the whole composite at full resolution
  for palette extraction; downsample to ≤256px first.

Add any new edge case you discover to this list.
