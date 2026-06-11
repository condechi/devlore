#!/usr/bin/env bash
# devlore: ingest doc file(s)/dir(s) into the knowledge base, then compile to the wiki.
#
# Usable from the terminal OR directly from Obsidian (Shell commands plugin) — no
# Claude Code session required. Uses absolute paths so it works under Obsidian's
# minimal shell environment.
#
#   devlore.sh <file-or-dir> [more ...]
#
# Obsidian (Shell commands plugin) examples:
#   devlore.sh "{{file_path:absolute}}"      # right-click a note / command palette
#   devlore.sh "{{folder_path:absolute}}"    # right-click a folder -> all its *.md

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
PY="$ROOT/.venv/bin/python3"

if [ "$#" -eq 0 ]; then
  echo "usage: devlore.sh <file-or-dir> [more ...]" >&2
  exit 1
fi

# 1) Append the doc(s) to today's daily log. Abort the compile if nothing landed.
if ! "$PY" "$ROOT/scripts/ingest_doc.py" "$@"; then
  echo "devlore: nothing ingested; skipping compile." >&2
  exit 1
fi

# 2) Compile into the wiki. The compile holds a global lock; if another compile is
#    already running it exits cleanly and the doc is picked up by that run.
"$PY" "$ROOT/scripts/compile.py"
