#!/usr/bin/env bash
# KB status line: the existing global ccstatusline bar PLUS the knowledge-base
# "turns since last save" segment of whichever registered KB the session belongs to.
#
# Multi-KB dispatch: KB roots are listed in ~/.claude/kb-dirs (one per line,
# # comments; written by `devlore init`). Each KB's statusline.py is GATED — it
# emits a segment only when the session cwd is inside that KB's working roots —
# so we try each registered KB and take the first non-empty segment. Falls back
# to the KB this wrapper lives in, so a single-KB setup needs no registry.
#
# Claude Code passes the session JSON on stdin; we read it once and feed all.

input=$(cat)

# Existing ccstatusline bar (uses its own global config -> identical look).
base=$(printf '%s' "$input" | npx -y ccstatusline@2.2.19 2>/dev/null)

SELF_KB="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
kbs=()
if [ -f "$HOME/.claude/kb-dirs" ]; then
  while IFS= read -r line; do
    case "$line" in ""|\#*) continue ;; esac
    kbs+=("$line")
  done < "$HOME/.claude/kb-dirs"
fi
kbs+=("$SELF_KB")

seg=""
seen=""
for kb in "${kbs[@]}"; do
  case "$seen" in *"|$kb|"*) continue ;; esac
  seen="$seen|$kb|"
  [ -f "$kb/scripts/statusline.py" ] || continue
  py="$kb/.venv/bin/python3"
  [ -x "$py" ] || py="python3"
  s=$(printf '%s' "$input" | "$py" "$kb/scripts/statusline.py" 2>/dev/null)
  if [ -n "$s" ]; then seg="$s"; break; fi
done

if [ -n "$base" ] && [ -n "$seg" ]; then
  printf '%s  ·  %s' "$base" "$seg"
elif [ -n "$seg" ]; then
  printf '%s' "$seg"
else
  printf '%s' "$base"
fi
