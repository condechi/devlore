"""devlore init — bootstrap a NET-NEW knowledge base for another project.

Creates a self-sufficient KB directory from THIS repo's machinery (the committed
state is the template), wires Claude Code/Codex capture for the target codebase, and
git-inits with the standard commit strategy. **Obsidian is optional**: the core
install has zero Obsidian artifacts; `--with-obsidian` additionally drops in the
devlore plugin + vault config for users who open the KB directory as a vault.

What it does, in order:
  1. validate target KB dir (new/empty) + codebase path(s)
  2. copy the machinery payload: hooks/, the core scripts/, AGENTS.md,
     .claude/commands + settings.json, pyproject.toml + uv.lock, .gitignore
     — rewriting this KB's absolute path → the target's in every copied file
  3. symlink each codebase into the KB dir; write scripts/capture-roots
     (subtree mode) + scripts/code-roots; fresh capture-config
  4. register the capture hooks in each CODEBASE's .claude/settings.local.json
     and .codex/hooks.json (merge-aware — never clobbers existing settings)
  5. skeleton knowledge/{concepts,connections,qa,mocs}/ + daily/ + generated
     empty index.md + log.md header
  6. `uv sync` the venv; git init + initial commit (local-only strategy)
  7. append the KB to ~/.claude/kb-dirs (shared Claude status-line dispatcher)
  8. [--with-obsidian] copy .obsidian/plugins/devlore + app.json ignore filters

After init: start Claude Code or Codex sessions in the codebase (capture is live),
`/devlore <docs>` to ingest existing documentation, and
`scripts/ingest_all_context.py` to backfill any surviving past conversations.

Usage:
    uv run python scripts/init_kb.py <kb-dir> --code <codebase-path> [--code …]
                                     [--with-obsidian] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent  # the template KB (this repo)

# The machinery payload: everything a new KB needs, nothing specific to the template KB.
# (enrich_frontmatter.py is excluded on purpose — its subsystem taxonomy is this
# KB's backfill tool; new KBs start empty and the compiler fills `subsystem:`.)
PAYLOAD_SCRIPTS = [
    "activity.py", "add_codebase.py", "build_index.py", "capture-config",
    "capture_config.py", "compile.py", "compile.sh", "config.py", "flush.py",
    "ingest_all_context.py", "ingest_doc.py", "init_kb.py", "kb_commit.py",
    "kb_resolve.py", "lint.py", "obsidian_setup.py", "optin.py", "query.py",
    "query.sh", "recheck.py", "recheck.sh", "remove_codebase.py", "staleness.py",
    "stamp_baseline.py", "status.py", "status.sh", "statusline-wrapper.sh",
    "statusline.py", "transcripts.py", "update.sh", "update_kb.py", "utils.py",
    "verify.py", "verify.sh", "devlore", "devlore.sh",
]
PAYLOAD_HOOKS = ["capture_gate.py", "pre-compact.py", "session-end.py",
                 "session-start.py", "stop.py"]
PAYLOAD_ROOT = ["AGENTS.md", "pyproject.toml", "uv.lock", ".gitignore"]
PAYLOAD_CLAUDE = ["settings.json"]  # + commands/ tree
# Claude fires SessionEnd only at session end and PreCompact only on compaction,
# so a long session captures nothing until one of those — Stop (every turn) runs
# the bootstrap/safety-valve flush that establishes the delta marker early.
CLAUDE_HOOK_EVENTS = ("SessionStart", "PreCompact", "SessionEnd", "Stop")
# Codex's Stop already maps to session-end.py (it captures every turn), so Codex
# does not need the separate bootstrap hook.
CODEX_HOOK_EVENTS = ("SessionStart", "PreCompact", "Stop")


_SHELL_SAFE = re.compile(r'^[A-Za-z0-9_\-/.~ ]+$')


def _assert_path_safe(p: Path, label: str = "path") -> None:
    """Reject paths with shell metacharacters before they can be embedded in command strings."""
    if not _SHELL_SAFE.match(str(p)):
        sys.exit(f"error: {label} contains characters not allowed in command strings: {p}\n"
                 "Use a path with only alphanumeric, '-', '_', '/', '.', '~', or space characters.")


def _rewrite(text: str, target: Path) -> str:
    """Point every reference to the template KB at the new KB instead. Also resolves
    the distribution home placeholder written by build_dist.py, so a cloned
    distribution works no matter where it was cloned. The placeholder literal is
    split below because this file is itself materialized through this rewrite —
    an intact literal would be resolved to the KB path, corrupting the installed
    copy's ability to resolve future placeholders."""
    return (text.replace(str(SOURCE_ROOT), str(target))
                .replace("__DEVLORE" + "_HOME__", str(target)))


def _copy(src: Path, dst: Path, target: Path, dry: bool) -> None:
    if dry:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = src.read_text(encoding="utf-8")
        dst.write_text(_rewrite(text, target), encoding="utf-8")
        dst.chmod(src.stat().st_mode)
    except UnicodeDecodeError:  # binary (none expected, but be safe)
        shutil.copy2(src, dst)


def _slug(path: Path) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", path.name.lower()).strip("-") or "code"


# The KB's own structure — a codebase symlink must never shadow these.
RESERVED_NAMES = {"knowledge", "daily", "scripts", "hooks", "quarantine", "reports",
                  ".claude", ".obsidian", ".git", ".venv"}


def link_name(kb: Path, codebase: Path) -> str:
    """Symlink name for a codebase inside the KB. Falls back to a parent-qualified
    slug when the basename collides with a reserved KB directory or an existing
    non-symlink path (e.g. a codebase literally named `daily` → `<parent>-daily`)."""
    name = _slug(codebase)
    if name in RESERVED_NAMES or ((kb / name).exists() and not (kb / name).is_symlink()):
        name = f"{_slug(codebase.parent)}-{name}"
    return name


def _merge_hook_file(
    settings_path: Path,
    kb: Path,
    dry: bool,
    events: tuple[str, ...],
    scripts: dict[str, str],
    timeouts: dict[str, int],
    matchers: dict[str, str | None],
    status_messages: dict[str, str] | None = None,
) -> str:
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return f"⚠ {settings_path} unreadable — hooks NOT registered (register manually)"
    hooks = settings.setdefault("hooks", {})
    added = []
    for ev in events:
        cmd = f"uv run --directory {kb} python hooks/{scripts[ev]}"
        groups = hooks.setdefault(ev, [])
        already = any(h.get("command") == cmd
                      for g in groups for h in g.get("hooks", []))
        if already:
            continue
        handler = {"type": "command", "command": cmd, "timeout": timeouts[ev]}
        if status_messages and ev in status_messages:
            handler["statusMessage"] = status_messages[ev]
        group = {"hooks": [handler]}
        matcher = matchers.get(ev)
        if matcher is not None:
            group["matcher"] = matcher
        groups.append(group)
        added.append(ev)
    if not dry and added:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return f"registered {', '.join(added)}" if added else "already registered"


def merge_claude_hooks(codebase: Path, kb: Path, dry: bool) -> str:
    """Register capture hooks in Claude Code settings.local.json."""
    return _merge_hook_file(
        codebase / ".claude" / "settings.local.json",
        kb,
        dry,
        CLAUDE_HOOK_EVENTS,
        {"SessionStart": "session-start.py", "PreCompact": "pre-compact.py",
         "SessionEnd": "session-end.py", "Stop": "stop.py"},
        {"SessionStart": 15, "PreCompact": 10, "SessionEnd": 10, "Stop": 10},
        {"SessionStart": "", "PreCompact": "", "SessionEnd": "", "Stop": ""},
    )


def merge_codex_hooks(codebase: Path, kb: Path, dry: bool) -> str:
    """Register capture hooks in Codex's project-local hooks.json."""
    return _merge_hook_file(
        codebase / ".codex" / "hooks.json",
        kb,
        dry,
        CODEX_HOOK_EVENTS,
        {"SessionStart": "session-start.py", "PreCompact": "pre-compact.py",
         "Stop": "session-end.py"},
        {"SessionStart": 15, "PreCompact": 10, "Stop": 10},
        {"SessionStart": "startup|resume|clear|compact", "PreCompact": "manual|auto",
         "Stop": None},
        {"SessionStart": "Loading devlore context",
         "PreCompact": "Capturing devlore context",
         "Stop": "Capturing devlore session"},
    )


def merge_codebase_hooks(codebase: Path, kb: Path, dry: bool) -> str:
    """Register capture hooks for supported local coding agents."""
    return (
        f"Claude: {merge_claude_hooks(codebase, kb, dry)}; "
        f"Codex: {merge_codex_hooks(codebase, kb, dry)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Bootstrap a new knowledge base (devlore init).")
    ap.add_argument("kb_dir", help="Target KB directory (created; must not be a non-empty dir).")
    ap.add_argument("--code", action="append", default=[],
                    help="Path to a codebase to document (repeatable; omit to create an "
                         "empty KB and opt codebases in later with `devlore add`).")
    ap.add_argument("--with-obsidian", action="store_true",
                    help="Also install the OPTIONAL Obsidian layer (devlore plugin + vault config).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    kb = Path(args.kb_dir).expanduser().resolve()
    if kb.exists() and any(kb.iterdir()):
        sys.exit(f"error: {kb} exists and is not empty")
    if kb == SOURCE_ROOT or str(kb).startswith(str(SOURCE_ROOT) + "/"):
        sys.exit("error: target must be outside the template KB")
    _assert_path_safe(kb, "kb-dir")
    codebases = []
    for c in args.code:
        p = Path(c).expanduser().resolve()
        if not p.is_dir():
            sys.exit(f"error: codebase not found: {p}")
        if str(p) == "/" or not str(p).startswith(str(Path.home())):
            sys.exit(f"error: codebase must be inside your home directory: {p}")
        _assert_path_safe(p, "codebase")
        codebases.append(p)

    print(f"{'DRY RUN — ' if dry else ''}initializing KB at {kb}")
    print(f"  template: {SOURCE_ROOT}")

    # 2. machinery payload (path-rewritten)
    for name in PAYLOAD_SCRIPTS:
        _copy(SOURCE_ROOT / "scripts" / name, kb / "scripts" / name, kb, dry)
    for name in PAYLOAD_HOOKS:
        _copy(SOURCE_ROOT / "hooks" / name, kb / "hooks" / name, kb, dry)
    for name in PAYLOAD_ROOT:
        _copy(SOURCE_ROOT / name, kb / name, kb, dry)
    for name in PAYLOAD_CLAUDE:
        _copy(SOURCE_ROOT / ".claude" / name, kb / ".claude" / name, kb, dry)
    for cmd in sorted((SOURCE_ROOT / ".claude" / "commands").glob("*.md")):
        _copy(cmd, kb / ".claude" / "commands" / cmd.name, kb, dry)
    print(f"  ✓ machinery copied ({len(PAYLOAD_SCRIPTS)} scripts, {len(PAYLOAD_HOOKS)} hooks, "
          f"commands, AGENTS.md)")

    # 3. symlinks + capture-roots + code-roots + fresh runtime config
    links = []
    for cb in codebases:
        name = link_name(kb, cb)
        if not dry:
            (kb / name).symlink_to(cb)
        links.append((name, cb))
    if not dry:
        (kb / "scripts" / "capture-roots").write_text(
            "# Knowledge-base capture opt-in (one dir per line; trailing '/' = subtree).\n"
            + "".join(f"{cb}/\n" for _, cb in links), encoding="utf-8")
        (kb / "scripts" / "code-roots").write_text(
            "# Code roots: symlinks under the KB root holding the project code.\n"
            + "".join(f"{name}\n" for name, _ in links), encoding="utf-8")
    if links:
        print("  ✓ linked: " + ", ".join(f"{name} → {cb}" for name, cb in links))
    else:
        print("  · no codebase linked yet — opt one in later with `devlore add <path>`")

    # 4. codebase hook registration (merge-aware)
    for name, cb in links:
        note = merge_codebase_hooks(cb, kb, dry)
        print(f"  ✓ capture hooks for {cb.name}: {note}")

    # 5. skeletons
    if not dry:
        for sub in ("concepts", "connections", "qa", "mocs"):
            (kb / "knowledge" / sub).mkdir(parents=True, exist_ok=True)
            (kb / "knowledge" / sub / ".gitkeep").touch()
        (kb / "daily").mkdir(exist_ok=True)
        (kb / "daily" / ".gitkeep").touch()
        (kb / "knowledge" / "log.md").write_text("# Build Log\n\n", encoding="utf-8")
        subprocess.run([sys.executable, str(kb / "scripts" / "build_index.py")],
                       capture_output=True, cwd=str(kb))
    print("  ✓ knowledge/ + daily/ skeletons (+ empty generated index.md)")

    # 6. venv (git commit happens LAST, after the optional Obsidian layer)
    if not dry:
        r = subprocess.run(["uv", "sync", "--directory", str(kb)],
                           capture_output=True, text=True)
        print(f"  {'✓' if r.returncode == 0 else '⚠'} uv sync "
              f"({'ok' if r.returncode == 0 else r.stderr.strip()[:120]})")

    # 7. status-line registry
    reg = Path.home() / ".claude" / "kb-dirs"
    if not dry:
        existing = reg.read_text(encoding="utf-8") if reg.exists() else \
            "# Knowledge-base roots for the shared status-line dispatcher\n"
        if str(kb) not in existing:
            reg.write_text(existing.rstrip("\n") + f"\n{kb}\n", encoding="utf-8")
    print(f"  ✓ registered in {reg}")

    # 8. OPTIONAL Obsidian layer. The install step is shared with `devlore
    #    obsidian` (obsidian_setup.install_obsidian_layer) — one source of truth
    #    for the copy + placeholder rewrite + vault config.
    if args.with_obsidian:
        from obsidian_setup import activation_steps, install_obsidian_layer
        n = install_obsidian_layer(kb, SOURCE_ROOT, dry=dry)
        print(f"  ✓ Obsidian layer (OPTIONAL): devlore plugin + vault config ({n} file(s))")
        if not dry:
            print("    " + activation_steps(kb).replace("\n", "\n    "))
    else:
        print("  · Obsidian layer skipped (core is fully functional without it; "
              f"add it anytime with:  {kb}/scripts/devlore obsidian)")

    # 9. git init + initial commit (after everything, so the commit is complete)
    if not dry:
        subprocess.run(["git", "init", "-q"], cwd=str(kb), capture_output=True)
        # Keep code-root symlinks (machine-specific) out of git via the LOCAL,
        # update-safe exclude — never the dist-managed .gitignore.
        from utils import git_exclude
        for name, _ in links:
            git_exclude(kb, name, add=True)
        subprocess.run(["git", "add", "-A"], cwd=str(kb), capture_output=True)
        what = ", ".join(n for n, _ in links) if links else "(no codebase yet)"
        subprocess.run(["git", "commit", "-q", "-m",
                        f"devlore init: knowledge base for {what}\n\n"
                        f"Bootstrapped from {SOURCE_ROOT} (template). Local-only commit\n"
                        f"strategy; the pipeline auto-commits after each write."],
                       cwd=str(kb), capture_output=True)
        print("  ✓ git init + initial commit")

    first = (f"  1. cd {codebases[0]}  &&  start a Claude Code or Codex session — capture is LIVE"
             if codebases else
             f"  1. opt your first codebase in:  {kb}/scripts/devlore add <codebase-path>")
    print(f"""
Next steps:
{first}
  2. ask the KB:              {kb}/scripts/devlore ask "your question"
  3. anytime:                 {kb}/scripts/devlore help{'''
  4. open ''' + str(kb) + ''' as an Obsidian vault for the rendered experience''' if args.with_obsidian else ''}""")


if __name__ == "__main__":
    main()
