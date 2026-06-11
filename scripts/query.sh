#!/usr/bin/env bash
# query: ask the knowledge base a question (index-guided retrieval, no RAG).
#
# Usable from the terminal OR directly from Obsidian (Shell commands plugin) — no
# Claude Code session required. Uses absolute paths so it works under Obsidian's
# minimal shell environment.
#
#   query.sh "your question" [--project <slug>] [--file-back] [--dev]
#
# Examples:
#   query.sh "What CN types do we emit?"
#   query.sh "What's our OOB amount policy?" --project stripe-ledger --file-back
#   query.sh "Where is the 1¢ OOB amount applied?" --dev   # + live file:line pointers

set -uo pipefail

# Resolve symlinks so ROOT is the real KB root even if query.sh is reached via a
# symlink (mirrors the dispatcher in scripts/devlore).
src="${BASH_SOURCE[0]:-$0}"
while [ -h "$src" ]; do
  dir="$(cd -P "$(dirname "$src")" >/dev/null 2>&1 && pwd)"
  src="$(readlink "$src")"
  case "$src" in /*) ;; *) src="$dir/$src" ;; esac
done
ROOT="$(cd -P "$(dirname "$src")/.." >/dev/null 2>&1 && pwd)"
PY="$ROOT/.venv/bin/python3"

if [ "$#" -eq 0 ]; then
  echo 'usage: query.sh "your question" [--project <slug>] [--file-back] [--dev]' >&2
  exit 1
fi

exec "$PY" "$ROOT/scripts/query.py" "$@"
