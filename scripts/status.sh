#!/usr/bin/env bash
# status: one-view summary of this knowledge base — articles, dailies, captured
# sessions, capture roots, spend, recent commits, and a Tier-2 staleness preview.
#
# Deterministic (no LLM, no cost). Usable from the terminal OR directly from
# Obsidian — uses the KB's own venv python, since Obsidian's minimal GUI shell
# has no `uv` on PATH.
#
#   status.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec "$ROOT/.venv/bin/python3" "$ROOT/scripts/status.py" "$@"
