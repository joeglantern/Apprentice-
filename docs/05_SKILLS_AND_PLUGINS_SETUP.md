# 05 - Skills, plugins, and MCP servers for Claude Code

This doc tells Claude Code what to set up in Phase 0 before writing feature
code. Two different mechanisms are in play, worth keeping straight:

- **Custom skills** - folders with a `SKILL.md` file, either authored by
  Claude Code for this specific project (§1) or installed from a public
  marketplace (§2). No package manager involved: Claude Code discovers
  `.claude/skills/<name>/SKILL.md` automatically and loads the body when a
  task matches the skill's description.
- **Plugins** - bundles that can include skills, subagents, hooks, and MCP
  servers together, distributed through marketplaces and installed with the
  `/plugin` command (§3).
- **MCP servers** - external tool connections, addable directly with
  `claude mcp add`, with or without a plugin (§4).

## 1. Custom skills to author for this project

Have Claude Code create each of these as `.claude/skills/<name>/SKILL.md`
with the YAML frontmatter shown, then fill in the body from the
corresponding doc. Keep the `description` field detailed - it's the only
part loaded at startup, and it's what Claude Code uses to decide whether the
skill is relevant to what you just asked for.

**`.claude/skills/psd-metadata-extraction/SKILL.md`**
```yaml
---
name: psd-metadata-extraction
description: Extract layer trees, bounding boxes, typography, and color data from .psd/.ai files into the project's JSON layout schema. Use when working on the collector's parsing code, the ingestion API's payload validation, or the training data pipeline.
---
```
Body: point to doc 01 §3 (the schema) and doc 02 §1 (where `psd-tools`
parsing happens today), plus any edge cases Claude Code discovers while
implementing (nested groups, adjustment layers, clipping masks).

**`.claude/skills/consent-gate-review/SKILL.md`** - a guardrail skill, not a
capability one:
```yaml
---
name: consent-gate-review
description: Check any change touching collector-mac/ or the ingestion API's consent handling against the project's consent requirements before it's considered done. Use whenever code in this repo captures, syncs, or stores the designer's files or activity.
---
```
Body: restate the consent rules from `CLAUDE.md` §"Non-negotiable: consent
over the collector" verbatim, plus a short checklist (visible indicator
present? opt-in per project, not blanket? pause takes effect client-side
before any network call? ingestion rejects unconsented payloads?). This
skill's job is to make the guardrail something Claude Code actively
re-checks, not just something it read once in `CLAUDE.md`.

**`.claude/skills/lora-training-ops/SKILL.md`**
```yaml
---
name: lora-training-ops
description: Conventions for kicking off, monitoring, and checkpointing LoRA and VLM fine-tuning runs on the Lenovo Legion. Use when writing or running anything under training/.
---
```
Body: point to doc 03 - VRAM confirmation step, the two training commands,
the checkpoint push-back convention.

**`.claude/skills/fastapi-ingestion-conventions/SKILL.md`**
```yaml
---
name: fastapi-ingestion-conventions
description: Coding conventions for the backend's FastAPI routes, Pydantic models, and Celery tasks. Use when writing or editing anything under backend/.
---
```
Body: point to doc 02 §3 for the route pattern, and to `CLAUDE.md`'s
Python conventions.

**`.claude/skills/expo-canvas-conventions/SKILL.md`**
```yaml
---
name: expo-canvas-conventions
description: Conventions for the Expo Router app's screens, hooks, and SVG canvas rendering. Use when writing or editing anything under app/.
---
```
Body: point to doc 04, especially the vector/raster compositing pattern in
`CanvasPreview.tsx`.

Claude Code ships several bundled skills already available without setup -
`/code-review`, `/debug`, `/doctor`, `/verify`, `/run`, `/batch`, `/loop` -
worth reaching for throughout rather than reinventing (e.g. run `/code-review`
before marking any phase in the kickoff prompt done, and `/doctor` if the
environment itself seems misconfigured).

## 2. If you'd rather generate the skills interactively

Claude Code also ships a `skill-creator`-style guided flow in some
marketplace distributions that asks a short Q&A and generates the `SKILL.md`
scaffold for you. If you want that instead of hand-writing the five skills
above, ask Claude Code to "help me build a skill for X" and follow the
prompts - the frontmatter and body it produces should match the shape shown
in §1.

## 3. Marketplace plugins worth installing

Run these once, in Phase 0:

```
/plugin marketplace add anthropics/claude-code
/plugin
```

The second command opens the interactive plugin manager - browse the
**Discover** tab, and for each candidate plugin it shows a "Will install"
list (commands, agents, skills, hooks, MCP/LSP servers) before you confirm.
Review that list rather than installing blind, the same way you'd review a
new npm dependency. Useful candidates for this project, if present in the
marketplace you add:

- A **commit-message** plugin, so commits in this repo stay conventional
  without hand-writing every message.
- A **code-review** plugin, complementing (not replacing) the bundled
  `/code-review` skill.

Install syntax once you've picked one from Discover:

```
/plugin install <plugin-name>@<marketplace-name>
```

Manage installed plugins the same way:

```
/plugin disable <plugin-name>@<marketplace-name>   # turn off without uninstalling
/plugin uninstall <plugin-name>@<marketplace-name>
/plugin marketplace update anthropics-claude-code   # refresh the catalog
```

Plugins can run arbitrary code with your privileges - treat a new
marketplace the way you'd treat a new dependency source, and stick to ones
you recognize.

## 4. MCP servers worth adding directly

Not everything needs to come through a plugin. A few MCP servers are worth
adding directly with `claude mcp add`, since this project touches GitHub, a
Postgres database, and (per doc 02) a Docker Compose stack:

```bash
# GitHub - repo, issue, and PR access for this project
claude mcp add github -e GITHUB_PERSONAL_ACCESS_TOKEN=<token> \
  -- docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server

# Postgres - query the backend's schema directly while developing the ingestion API
claude mcp add --transport stdio backend-db \
  -- npx -y @modelcontextprotocol/server-postgres postgresql://localhost:5432/ghostagent

# Project-shared scope, so both of you get the same servers if you ever
# collaborate on this repo directly:
claude mcp add --scope project <name> -- <command>
```

Use `--scope project` for anything you want committed to `.mcp.json` and
shared if the repo is ever cloned elsewhere; leave it at the default
(`local`) scope for anything credentialed and personal, like your own
GitHub token. Check what's connected at any point with `/mcp` inside a
session, and keep the server count small - each one adds its tool
definitions to every session's context whether or not that session uses it.
