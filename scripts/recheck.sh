#!/usr/bin/env bash
# recheck: refresh needs-reverification marks after working-tree edits — flag
# articles whose cited code changed since their knowledge vintage, and clear
# marks the compiler/edits have since resolved.
#
# Deterministic (no LLM, no cost). Usable from the terminal OR directly from
# Obsidian — uses the KB's own venv python (no `uv` needed).
#
#   recheck.sh [--dry-run] [--verified <slug> …]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec "$ROOT/.venv/bin/python3" "$ROOT/scripts/recheck.py" "$@"
