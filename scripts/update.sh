#!/usr/bin/env bash
# update: refresh this KB's MACHINERY (scripts, hooks, and — if installed — the
# Obsidian plugin) from the latest devlore release. NEVER touches knowledge/,
# daily/, quarantine/, or your config.
#
# Usable from the terminal OR directly from Obsidian — uses the KB's own venv
# python (no `uv` needed to launch; update_kb runs `uv sync` itself and degrades
# gracefully if uv is absent). After a plugin refresh, reload Obsidian to load it.
#
#   update.sh [--from <dist-path>]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
exec "$ROOT/.venv/bin/python3" "$ROOT/scripts/update_kb.py" "$@"
