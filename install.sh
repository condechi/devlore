#!/usr/bin/env bash
# devlore installer — https://github.com/condechi/devlore
#
#   curl -fsSL https://raw.githubusercontent.com/condechi/devlore/main/install.sh | bash
#   ./install.sh [target-dir] [--yes]
#
# Creates YOUR knowledge base at the target (default ~/devlore) from the devlore
# template, with its own private git history, and puts `devlore` on your PATH.
set -euo pipefail

REPO="https://github.com/condechi/devlore.git"
DIST_CACHE="$HOME/.devlore/dist"
TARGET="${DEVLORE_HOME:-$HOME/devlore}"
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    *) TARGET="$arg" ;;
  esac
done

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
ask() { # ask "prompt" default_yes(1/0)
  local prompt="$1" def="${2:-1}" ans
  [ "$ASSUME_YES" = "1" ] && return $([ "$def" = "1" ] && echo 0 || echo 1)
  if [ -r /dev/tty ]; then
    read -r -p "$prompt $([ "$def" = "1" ] && echo '[Y/n]' || echo '[y/N]') " ans </dev/tty || ans=""
  else
    ans=""
  fi
  case "$ans" in
    [yY]*) return 0 ;; [nN]*) return 1 ;;
    *) [ "$def" = "1" ] && return 0 || return 1 ;;
  esac
}

say "🧠 devlore installer"
echo

# ── dependencies ──────────────────────────────────────────────────────────────
missing=0
command -v git >/dev/null   || { echo "✗ git is required";  missing=1; }
command -v claude >/dev/null || { echo "✗ Claude Code CLI is required → https://claude.com/claude-code"; missing=1; }
command -v uv >/dev/null    || { echo "✗ uv is required → curl -LsSf https://astral.sh/uv/install.sh | sh"; missing=1; }
command -v python3 >/dev/null || { echo "✗ python3 is required"; missing=1; }
[ "$missing" = "1" ] && { echo; echo "Install the missing dependencies and re-run."; exit 1; }
echo "✓ dependencies: git, claude, uv, python3"

# ── get the template ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/scripts/init_kb.py" ]; then
  DIST="$SCRIPT_DIR"                       # running from a clone
  echo "✓ template: local clone ($DIST)"
else
  mkdir -p "$(dirname "$DIST_CACHE")"
  if [ -d "$DIST_CACHE/.git" ]; then
    git -C "$DIST_CACHE" pull -q || true
  else
    git clone -q --depth 1 "$REPO" "$DIST_CACHE"
  fi
  DIST="$DIST_CACHE"
  echo "✓ template: $DIST"
fi

# ── materialize YOUR knowledge base ──────────────────────────────────────────
if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
  echo "✗ $TARGET already exists and is not empty."
  echo "  Pass a different directory:  install.sh ~/my-kb"
  exit 1
fi

OBSIDIAN_FLAG=""
if ask "Add the optional Obsidian layer (vault config + side-panel plugin)?" 1; then
  OBSIDIAN_FLAG="--with-obsidian"
fi

say "→ creating your knowledge base at $TARGET"
python3 "$DIST/scripts/init_kb.py" "$TARGET" $OBSIDIAN_FLAG

# ── CLI on PATH ───────────────────────────────────────────────────────────────
mkdir -p "$HOME/.local/bin"
ln -sf "$TARGET/scripts/devlore" "$HOME/.local/bin/devlore"
chmod +x "$TARGET/scripts/devlore" 2>/dev/null || true
case ":$PATH:" in
  *":$HOME/.local/bin:"*) echo "✓ devlore on PATH (~/.local/bin)";;
  *) echo "⚠ add ~/.local/bin to your PATH to use \`devlore\` directly";;
esac

# ── optional niceties (both prompted, both reversible) ───────────────────────
SETTINGS="$HOME/.claude/settings.json"
if ! python3 - "$SETTINGS" 2>/dev/null <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text()) if p.exists() else {}; sys.exit(0 if "cleanupPeriodDays" in d else 1)
PYEOF
then
  if ask "Raise Claude Code transcript retention to 365 days? (protects future backfills — transcripts older than 30 days are otherwise deleted)" 1; then
    python3 - "$SETTINGS" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True)
d = json.loads(p.read_text()) if p.exists() else {}
d["cleanupPeriodDays"] = 365
p.write_text(json.dumps(d, indent=2) + "\n")
print("✓ cleanupPeriodDays: 365")
PY
  fi
fi
if ! python3 - "$SETTINGS" 2>/dev/null <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text()) if p.exists() else {}; sys.exit(0 if d.get("statusLine") else 1)
PYEOF
then
  if ask "Add the KB status line? (shows 🧠 turns-since-last-capture inside opted-in repos)" 1; then
    python3 - "$SETTINGS" "$TARGET" <<'PY'
import json, sys, pathlib
p, target = pathlib.Path(sys.argv[1]), sys.argv[2]
p.parent.mkdir(parents=True, exist_ok=True)
d = json.loads(p.read_text()) if p.exists() else {}
d["statusLine"] = {"type": "command",
                   "command": f"bash {target}/scripts/statusline-wrapper.sh", "padding": 0}
p.write_text(json.dumps(d, indent=2) + "\n")
print("✓ status line wired")
PY
  fi
else
  echo "· existing statusLine left untouched (wire $TARGET/scripts/statusline-wrapper.sh manually if you want the 🧠 segment)"
fi

echo
say "Done. The magic moment:"
cat <<EOF

    cd ~/code/your-project      # any repo you've used Claude Code or Codex in
    devlore add .

It wires automatic capture, finds your PAST conversations (with a cost
estimate before spending anything), and compiles everything into a wiki
you can query:  devlore ask "what did we decide about X?"
EOF
