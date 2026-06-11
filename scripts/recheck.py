"""Staleness re-check loop (PR D) — the self-checking KB.

Deterministic, no LLM. Runs the Tier-2 scan (`staleness.stale_risk()`) and makes its
verdict DURABLE in article frontmatter:

  • flagged article            → `status: needs-reverification` + `reverify_reasons: "…"`
  • previously-marked, now clean → `status: active`, marker removed

The `reverify_reasons` key is the loop's ownership marker: only articles carrying it are
ever auto-cleared, so a HUMAN-set `needs-reverification` (no marker) is never overridden.
The mark clears through any of three paths: (1) the compiler rewrites the article with
current truth (born-stamp gives it a fresh baseline), (2) the offending working-tree edit
is reverted, or (3) a human re-verifies the claims and attests with `--verified <slug>`,
which re-stamps `valid_as_of`/`code_baseline` to today/HEAD.

Runs automatically after every compile (compile.py post-step, between stamp_compiled and
build_index so the regenerated index shows the new statuses). Cron/`/loop` optional.

Usage:
    uv run python scripts/recheck.py              # mark + clear (the loop)
    uv run python scripts/recheck.py --dry-run    # show what would change
    uv run python scripts/recheck.py --verified <slug> [<slug>…]   # human attestation
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stamp_baseline import REPOS, apply_stamp, head, repo_dirty  # noqa: E402
from staleness import stale_risk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"

_STATUS = re.compile(r"^status:\s*(\S+)\s*$", re.M)
_MARKER = re.compile(r"^reverify_reasons:.*\n?", re.M)


def _articles() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for sub in ("concepts", "connections", "qa", "mocs"):
        d = KNOWLEDGE / sub
        if d.exists():
            for p in sorted(d.glob("*.md")):
                out[p.stem] = p
    return out


def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """(start, end) character span of the frontmatter body (between the --- fences)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    return (3, end) if end != -1 else None


def _set_status(text: str, value: str) -> str:
    span = _frontmatter_span(text)
    if not span:
        return text
    fm = text[span[0]:span[1]]
    new_fm = _STATUS.sub(f"status: {value}", fm, count=1) if _STATUS.search(fm) \
        else fm.rstrip("\n") + f"\nstatus: {value}\n"
    return text[:span[0]] + new_fm + text[span[1]:]


def _set_marker(text: str, reasons: list[str]) -> str:
    """Write `reverify_reasons:` (replacing any prior one) right after the status line."""
    text = _drop_marker(text)
    span = _frontmatter_span(text)
    if not span:
        return text
    fm = text[span[0]:span[1]]
    quoted = '"' + "; ".join(sorted(reasons)[:4]).replace('"', "'") + '"'
    m = _STATUS.search(fm)
    if m:
        new_fm = fm[:m.end()] + f"\nreverify_reasons: {quoted}" + fm[m.end():]
    else:
        new_fm = fm.rstrip("\n") + f"\nreverify_reasons: {quoted}\n"
    return text[:span[0]] + new_fm + text[span[1]:]


def _drop_marker(text: str) -> str:
    span = _frontmatter_span(text)
    if not span:
        return text
    fm = _MARKER.sub("", text[span[0]:span[1]])
    return text[:span[0]] + fm + text[span[1]:]


def _status_of(text: str) -> str:
    span = _frontmatter_span(text)
    m = _STATUS.search(text[span[0]:span[1]]) if span else None
    return m.group(1) if m else ""


def _has_marker(text: str) -> bool:
    span = _frontmatter_span(text)
    return bool(span and "reverify_reasons:" in text[span[0]:span[1]])


def recheck(dry_run: bool = False) -> tuple[list[str], list[str]]:
    """The loop. Returns (marked_slugs, cleared_slugs)."""
    flagged = dict(stale_risk())  # {stem: [reasons]}
    marked: list[str] = []
    cleared: list[str] = []
    for stem, path in _articles().items():
        text = path.read_text(encoding="utf-8")
        status = _status_of(text)
        if stem in flagged:
            # Mark (or refresh reasons). Never touch `superseded` — it outranks staleness.
            if status == "superseded":
                continue
            new = _set_marker(_set_status(text, "needs-reverification"), flagged[stem])
            if new != text:
                marked.append(stem)
                if not dry_run:
                    path.write_text(new, encoding="utf-8")
        elif _has_marker(text):
            # Loop-owned mark whose cause is gone → restore. Human-set status (no
            # marker) is never auto-cleared.
            new = _drop_marker(_set_status(text, "active"))
            cleared.append(stem)
            if not dry_run:
                path.write_text(new, encoding="utf-8")
    return marked, cleared


def attest_verified(slugs: list[str], dry_run: bool = False) -> list[str]:
    """Human attestation: the article's code-level claims were re-checked against the
    CURRENT working tree. Re-stamps valid_as_of=today + code_baseline=HEAD (dirty-aware)
    and clears the mark, so the Tier-2 scan stops flagging until the code moves again."""
    today = datetime.now(timezone.utc).astimezone().date().isoformat()
    shas = {name: head(repo) for name, repo in REPOS.items()}
    dirty = any(repo_dirty(repo) for repo in REPOS.values())
    arts = _articles()
    done: list[str] = []
    for slug in slugs:
        path = arts.get(slug)
        if not path:
            print(f"  ⚠ no such article: {slug}")
            continue
        text = path.read_text(encoding="utf-8")
        stamped = apply_stamp(text, today, shas, dirty)
        if stamped is None:
            print(f"  ⚠ {slug}: no frontmatter — skipped")
            continue
        new = _drop_marker(_set_status(stamped, "active"))
        done.append(slug)
        if not dry_run:
            path.write_text(new, encoding="utf-8")
        shastr = " ".join(f"{n}@{s}" for n, s in shas.items() if s)
        print(f"  ✓ {slug}: re-stamped valid_as_of={today} {shastr} "
              f"dirty={str(dirty).lower()}, status → active")
    return done


def main() -> None:
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    if args and args[0] == "--verified":
        slugs = args[1:]
        if not slugs:
            print("usage: recheck.py --verified <slug> [<slug>…]")
            sys.exit(1)
        print(f"{'DRY RUN — ' if dry else ''}attesting {len(slugs)} article(s) as re-verified…")
        done = attest_verified(slugs, dry_run=dry)
        if done and not dry:
            try:
                from build_index import build as build_index
                build_index()
                from kb_commit import kb_commit
                kb_commit(f"verify: attested {len(done)} article(s) as re-verified")
            except Exception:
                pass
        return

    marked, cleared = recheck(dry_run=dry)
    verb = "would " if dry else ""
    if marked:
        print(f"{verb}mark needs-reverification ({len(marked)}):")
        for s in marked:
            print(f"  - {s}")
    if cleared:
        print(f"{verb}clear → active ({len(cleared)}):")
        for s in cleared:
            print(f"  - {s}")
    if not marked and not cleared:
        print("nothing to change — statuses already reflect the Tier-2 scan.")


if __name__ == "__main__":
    main()
