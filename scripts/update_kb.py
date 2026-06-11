"""devlore update — refresh this KB's MACHINERY from the distribution.

Closes the drift gap: installed KBs are snapshots of the machinery at install
time; fixes shipped upstream never reached them except by hand-copying. This
re-materializes the machinery from the dist (pulling the latest) while NEVER
touching what makes the KB *yours*:

  preserved: knowledge/, daily/, quarantine/, scripts/state.json,
             scripts/capture-roots, scripts/code-roots, flush markers, logs,
             your git history
  updated:   every machinery file present in the dist — scripts, hooks,
             AGENTS.md, .claude/commands + settings.json, pyproject/uv.lock,
             .gitignore, and (only if this KB has an .obsidian/) the plugin

Usage:
    devlore update                       # pull latest dist, update this KB
    devlore update --from <dist-path>    # update from a local dist/clone
    python3 update_kb.py --kb <kb-path>  # update ANOTHER KB (bootstrap case:
                                         #   the target predates this command)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_CACHE = Path.home() / ".devlore" / "dist"
REPO = "https://github.com/condechi/devlore.git"
PLACEHOLDER = "__DEVLORE_HOME__"

# Machinery surfaces re-materialized from the dist. scripts/ and hooks/ copy
# every file the DIST ships (the dist contains only machinery), so KB-local
# runtime files (state.json, markers, capture-roots, code-roots, logs) are
# never listed in the dist and therefore never touched.
SURFACES = ["scripts", "hooks", ".claude/commands"]
ROOT_FILES = ["AGENTS.md", "pyproject.toml", "uv.lock", ".gitignore",
              ".claude/settings.json", "VERSION"]


def _rewrite(text: str, src: Path, kb: Path) -> str:
    return text.replace(PLACEHOLDER, str(kb)).replace(str(src), str(kb))


def _copy(src_file: Path, dst_file: Path, src: Path, kb: Path) -> None:
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst_file.write_text(_rewrite(src_file.read_text(encoding="utf-8"), src, kb),
                            encoding="utf-8")
        dst_file.chmod(src_file.stat().st_mode)
    except UnicodeDecodeError:
        shutil.copy2(src_file, dst_file)


def main() -> None:
    ap = argparse.ArgumentParser(description="Update this KB's machinery from the devlore dist.")
    ap.add_argument("--from", dest="src", help="Local dist/clone to update from "
                    "(default: ~/.devlore/dist, git-pulled).")
    ap.add_argument("--kb", help="KB to update (default: the KB this script lives in).")
    args = ap.parse_args()

    kb = Path(args.kb).expanduser().resolve() if args.kb \
        else Path(__file__).resolve().parent.parent
    if not (kb / "knowledge").is_dir() or not (kb / "scripts").is_dir():
        sys.exit(f"error: {kb} does not look like a devlore KB (missing knowledge/ or scripts/)")

    if args.src:
        src = Path(args.src).expanduser().resolve()
    else:
        src = DEFAULT_CACHE
        if (src / ".git").exists():
            subprocess.run(["git", "-C", str(src), "pull", "-q"], capture_output=True)
        else:
            src.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(["git", "clone", "-q", "--depth", "1", REPO, str(src)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit(f"error: could not fetch the dist: {r.stderr.strip()[:200]}")
    if not (src / "scripts" / "init_kb.py").exists():
        sys.exit(f"error: {src} is not a devlore distribution")
    version = (src / "VERSION").read_text().strip() if (src / "VERSION").exists() else "?"

    print(f"Updating machinery of {kb}")
    print(f"  from {src} (v{version})")

    n = 0
    for surface in SURFACES:
        sdir = src / surface
        if not sdir.is_dir():
            continue
        for f in sorted(sdir.iterdir()):
            if f.is_file():
                _copy(f, kb / surface / f.name, src, kb)
                n += 1
    for rel in ROOT_FILES:
        f = src / rel
        if f.exists():
            _copy(f, kb / rel, src, kb)
            n += 1
    # Obsidian layer only if this KB opted into it at install time
    if (kb / ".obsidian").is_dir() and (src / ".obsidian" / "plugins").is_dir():
        for plug in (src / ".obsidian" / "plugins").iterdir():
            if plug.is_dir():
                for f in plug.iterdir():
                    if f.is_file():
                        _copy(f, kb / ".obsidian" / "plugins" / plug.name / f.name, src, kb)
                        n += 1
    # The CLI launcher is symlinked onto PATH (install.sh) and must stay executable
    # regardless of the mode the dist recorded for it — guarantee it here.
    cli = kb / "scripts" / "devlore"
    if cli.exists():
        cli.chmod(cli.stat().st_mode | 0o111)
    print(f"  ✓ {n} machinery file(s) refreshed (knowledge/daily/config untouched)")

    r = subprocess.run(["uv", "sync", "--directory", str(kb)], capture_output=True, text=True)
    print(f"  {'✓' if r.returncode == 0 else '⚠'} uv sync")

    subprocess.run(["git", "-C", str(kb), "add", "-A"], capture_output=True)
    c = subprocess.run(["git", "-C", str(kb), "commit", "-q", "-m",
                        f"update: machinery → devlore v{version}"], capture_output=True)
    print(f"  ✓ committed (devlore v{version})" if c.returncode == 0
          else "  · nothing to commit (already current)")


if __name__ == "__main__":
    main()
