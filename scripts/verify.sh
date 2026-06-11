#!/usr/bin/env bash
# verify: run the KB verification ladder (Tier-1 symbol gate + Tier-2 staleness).
#
# Usable from the terminal OR directly from Obsidian (Shell commands plugin) — no
# Claude Code session required. Uses absolute paths so it works under Obsidian's
# minimal shell environment. Tier-1/Tier-2 are deterministic (no LLM, no cost);
# pass --tier3 to add the adversarial Sonnet refute pass on true-misses.
#
#   verify.sh [--article <slug>] [--tier3] [--no-tier2] [--json]
#
# Examples:
#   verify.sh
#   verify.sh --article crm-stripe-preview-finalize-pipeline
#   verify.sh --tier3

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
PY="$ROOT/.venv/bin/python3"

exec "$PY" "$ROOT/scripts/verify.py" "$@"
