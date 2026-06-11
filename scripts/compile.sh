#!/usr/bin/env bash
# Manual compile of any pending daily logs into the wiki.
# Pass --all to force-recompile everything. Usable from the terminal or Obsidian.
# compile.py holds a global lock, so if a compile is already running this no-ops.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec "$ROOT/.venv/bin/python3" "$ROOT/scripts/compile.py" "$@"
