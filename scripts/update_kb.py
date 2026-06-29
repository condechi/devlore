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
# Split literal: this file is itself materialized by the very rewrite that
# resolves the placeholder — an intact literal here would be rewritten to the
# KB path, corrupting the constant and leaving placeholders unresolved on the
# NEXT update (same in-band-sentinel class as the flush FLUSH_OK bug).
PLACEHOLDER = "__DEVLORE" + "_HOME__"

# Machinery surfaces re-materialized from the dist. scripts/ and hooks/ copy
# every file the DIST ships (the dist contains only machinery), so KB-local
# runtime files (state.json, markers, capture-roots, code-roots, logs) are
# never listed in the dist and therefore never touched.
SURFACES = ["scripts", "hooks", ".claude/commands"]
ROOT_FILES = ["AGENTS.md", "pyproject.toml", "uv.lock", ".gitignore",
              ".claude/settings.json", "VERSION"]


def _rewrite(text: str, src: Path, kb: Path) -> str:
    return text.replace(PLACEHOLDER, str(kb)).replace(str(src), str(kb))


def _rewire_capture_hooks(kb: Path) -> None:
    """Re-register capture hooks in every EXTERNAL captured project's agent config.

    `devlore update` re-materializes the KB's own machinery + its own
    .claude/settings.json, but captured projects OUTSIDE the KB keep their hook
    wiring in their own settings.local.json / .codex/hooks.json — written once at
    opt-in time. A NEW hook event (e.g. the Stop bootstrap hook) would never reach
    them without this. The merge is idempotent: it only adds missing events and
    never clobbers existing settings."""
    cr = kb / "scripts" / "capture-roots"
    if not cr.exists():
        return
    sys.path.insert(0, str(kb / "scripts"))
    try:
        from optin import project_root_of
        from init_kb import merge_codebase_hooks
    except Exception as e:
        print(f"  ⚠ could not load hook-rewire helpers: {e}")
        return
    seen: set[Path] = set()
    for line in cr.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = Path(line.rstrip("/"))
        if d == kb or str(d).startswith(str(kb) + "/"):
            continue  # inside the KB → covered by the KB's own settings.json
        if not d.is_dir():
            continue
        proj = project_root_of(d)
        if proj in seen:
            continue
        seen.add(proj)
        try:
            note = merge_codebase_hooks(proj, kb, dry=False)
            print(f"  ✓ rewired hooks for {proj.name}: {note}")
        except Exception as e:
            print(f"  ⚠ could not rewire {proj}: {e}")


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
            # fetch + hard-reset rather than pull: survives upstream history
            # rewrites, and a failed refresh is reported instead of silently
            # updating from a stale cache.
            f = subprocess.run(["git", "-C", str(src), "fetch", "-q", "origin"],
                               capture_output=True, text=True)
            if f.returncode == 0:
                r = subprocess.run(["git", "-C", str(src), "reset", "-q", "--hard",
                                    "origin/main"], capture_output=True, text=True)
                if r.returncode != 0:
                    sys.exit(f"error: dist cache at {src} is broken — delete it and "
                             f"re-run: {r.stderr.strip()[:200]}")
            else:
                print("  ⚠ could not refresh the dist cache (offline?) — "
                      "updating from the cached copy")
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

    # Re-wire capture hooks into external captured projects so new hook events
    # (e.g. the Stop bootstrap hook) reach existing installs, not just new opt-ins.
    _rewire_capture_hooks(kb)

    # Self-heal: code-root symlinks are machine-specific and belong in the LOCAL,
    # update-safe .git/info/exclude — not the dist-managed .gitignore (which this
    # very step just overwrote). Sync every current code root so a later `git add`
    # never tracks them, regardless of what the template .gitignore carries.
    sys.path.insert(0, str(kb / "scripts"))
    from utils import git_exclude
    cr = kb / "scripts" / "code-roots"
    if cr.exists():
        for line in cr.read_text(encoding="utf-8").splitlines():
            nm = line.strip()
            if nm and not nm.startswith("#"):
                git_exclude(kb, nm, add=True)

    r = subprocess.run(["uv", "sync", "--directory", str(kb)], capture_output=True, text=True)
    print(f"  {'✓' if r.returncode == 0 else '⚠'} uv sync")

    subprocess.run(["git", "-C", str(kb), "add", "-A"], capture_output=True)
    c = subprocess.run(["git", "-C", str(kb), "commit", "-q", "-m",
                        f"update: machinery → devlore v{version}"], capture_output=True)
    print(f"  ✓ committed (devlore v{version})" if c.returncode == 0
          else "  · nothing to commit (already current)")


if __name__ == "__main__":
    main()
