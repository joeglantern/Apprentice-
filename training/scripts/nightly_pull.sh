#!/usr/bin/env bash
# Nightly: pull new consented records from the VPS, validate, build curated sets.
# Run from the training/ folder on the Legion with the venv active and
# GHOST_API_URL / GHOST_API_TOKEN / GHOST_DATA_DIR exported (see README).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

: "${GHOST_DATA_DIR:=data}"
LOG="$GHOST_DATA_DIR/logs/pull-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$LOG")"

{
  echo "== pull $(date -Is)"
  python -m ghost_training.pull
  echo "== validate"
  python -m ghost_training.validate "$GHOST_DATA_DIR/raw/records"
  echo "== prepare"
  python -m ghost_training.prepare
  echo "== done $(date -Is)"
} 2>&1 | tee "$LOG"
