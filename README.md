# Ghost Agent

A pipeline that learns one designer's visual style and layout habits from their
real design work (captured only with explicit, visible, per-project consent) and
lets a collaborator generate new graphics in that aesthetic through an Expo app.

| Subsystem | Machine | Folder |
|---|---|---|
| Consented collector | Designer's M4 Mac | `collector-mac/` |
| Ingestion + inference gateway | Contabo VPS (no GPU) | `backend/` |
| LoRA + VLM training, inference | Lenovo Legion (RTX 5060, 8GB) | `training/` |
| Prompt / aesthetic / canvas UI | Expo (Web + Expo Go) | `app/` |

Start with `CLAUDE.md`, then `docs/01` -> `docs/05`.
