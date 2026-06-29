"""devlore status — what this knowledge base holds, in one view.

Articles by type, dailies, captured sessions, capture/code roots, spend, recent
commits, and a Tier-2 staleness preview. Deterministic, no LLM, no cost.

Pure-stdlib on purpose: the Obsidian plugin runs this through status.sh under the
KB's own venv python (Obsidian's minimal GUI shell has no `uv` on PATH), while the
terminal reaches the same view via `devlore status`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent.parent
ARTICLE_DIRS = ("concepts", "connections", "qa", "mocs")


def _version() -> str:
    vf = KB / "VERSION"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip() or "dev"
    # Source checkout (no VERSION file): fall back to the build constant.
    bd = KB / "scripts" / "build_dist.py"
    if bd.exists():
        for line in bd.read_text(encoding="utf-8").splitlines():
            if line.startswith("VERSION = "):
                return line.split('"')[1]
    return "dev"


def _roots(name: str) -> list[str]:
    f = KB / "scripts" / name
    if not f.exists():
        return []
    return [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(KB), *args],
                              capture_output=True, text=True, timeout=15).stdout.rstrip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> None:
    print(f"devlore v{_version()} — knowledge base: {KB}")

    total = 0
    parts = []
    for d in ARTICLE_DIRS:
        c = len(list((KB / "knowledge" / d).glob("*.md"))) if (KB / "knowledge" / d).is_dir() else 0
        total += c
        parts.append(f"{c} {d}")
    print(f"  articles:     {total}  ({', '.join(parts)})")
    print("                knowledge/index.md is the catalog")

    dailies = sorted(p.name[:-3] for p in (KB / "daily").glob("2*.md")) if (KB / "daily").is_dir() else []
    if dailies:
        print(f"  dailies:      {len(dailies)} daily log(s), {dailies[0]} → {dailies[-1]}")
    else:
        print("  dailies:      none yet")

    sessions = len(list((KB / "scripts").glob("flush-marker-*.json")))
    print(f"  sessions:     {sessions} conversation(s) captured")

    quarantine = len(list((KB / "quarantine").glob("*.md"))) if (KB / "quarantine").is_dir() else 0
    if quarantine:
        print(f"  quarantine:   {quarantine} conversation(s) awaiting review")

    capture = _roots("capture-roots")
    print("  capture roots (live conversation capture is on for):")
    if capture:
        for r in capture:
            print(f"    {r}")
    else:
        print("    (none — run: devlore add <codebase>)")
    code = _roots("code-roots")
    if code:
        print(f"  code roots:   {' '.join(code)}")

    state = KB / "scripts" / "state.json"
    if state.exists():
        try:
            d = json.loads(state.read_text(encoding="utf-8"))
            print(f"  ledger:       {d.get('total_cost', 0):.2f} USD total compile/query "
                  f"spend, {d.get('query_count', 0)} question(s) answered")
        except (ValueError, OSError):
            pass

    log = _git("log", "--oneline", "-3")
    if log:
        print("  recent commits:")
        for line in log.splitlines():
            print(f"    {line}")

    # Tier-2 staleness preview (deterministic, no cost). Same interpreter we run
    # under, so it works from the venv (status.sh) and from uv (devlore status).
    try:
        out = subprocess.run([sys.executable, str(KB / "scripts" / "staleness.py")],
                             capture_output=True, text=True, timeout=90)
        for line in (out.stdout or "").strip().splitlines()[:3]:
            print(line)
    except (OSError, subprocess.SubprocessError):
        pass


if __name__ == "__main__":
    main()
