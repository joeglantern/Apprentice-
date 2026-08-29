# 00 - Master kickoff prompt

Everything below the line is what you paste as your **first message** to Claude
Code, in an empty repo that already contains `CLAUDE.md` and the `docs/`
folder from this package. Claude Code reads `CLAUDE.md` automatically; the
prompt just tells it what order to do things in.

---

You're starting a new project in this repo. `CLAUDE.md` is already in place -
read it now, along with everything in `docs/01_ARCHITECTURAL_BLUEPRINT.md`
through `docs/05_SKILLS_AND_PLUGINS_SETUP.md`. Those five files are your spec.
Don't start writing feature code until you've read all of them.

Do the following in order, checking in with me between phases:

**Phase 0 - Setup**
1. Set up the repo skeleton from the layout in `CLAUDE.md`.
2. Author the custom project skills listed in `docs/05_SKILLS_AND_PLUGINS_SETUP.md`
   under `.claude/skills/`. Then install the marketplace plugins listed in that
   same doc using the `/plugin` commands it gives you.
3. Ask me for the two hardware facts flagged in `CLAUDE.md` as "confirm, not
   guess": the Lenovo's discrete GPU/VRAM, and the Contabo plan tier. Don't
   proceed to Phase 3 (training) or the inference half of Phase 2 until you
   have real answers, not assumptions.
4. Propose a milestone plan (a short numbered list is fine) covering Phases
   1-4 below, and confirm it with me before writing code.

**Phase 1 - Collector (`collector-mac`)**
Build the opt-in menu-bar sync agent and the UXP plugin panel described in
`docs/02_COLLECTOR_AND_VPS_SETUP.md`. The consent behavior in `CLAUDE.md` is
not optional - if anything here seems to call for a silent/headless mode,
stop and ask rather than building it.

**Phase 2 - Backend (`backend`)**
Build the FastAPI ingestion API, Celery/Redis queue, and Postgres schema from
`docs/02_COLLECTOR_AND_VPS_SETUP.md` and the data schema in
`docs/01_ARCHITECTURAL_BLUEPRINT.md`. Get ingestion working end-to-end
(collector -> API -> DB -> object storage) before touching the inference API,
which depends on Phase 3 producing a checkpoint.

**Phase 3 - Training (`training`)**
Build the nightly pull job and the LoRA + VLM fine-tuning scripts from
`docs/03_ML_TRAINING_AND_DATASETS.md`, sized to whatever GPU/VRAM you
confirmed in Phase 0. Get one full training run producing a usable checkpoint
before optimizing anything.

**Phase 4 - App (`app`)**
Build the Expo Router app from `docs/04_EXPO_APP_IMPLEMENTATION.md`. Wire it
to the backend's inference API. Verify it runs on both web and Expo Go before
calling this phase done.

**Throughout:**
- Small commits, conventional commit messages.
- Run tests/linters and the bundled `/code-review` skill before marking any
  phase complete.
- If you hit a decision point the docs flagged as open (vector vs. raster,
  where inference actually runs, which VLM to fine-tune first), bring it to
  me with a recommendation rather than picking silently.

Start with Phase 0, step 1.
