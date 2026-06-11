"""Shared utilities for the personal knowledge base."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from config import (
    CONCEPTS_DIR,
    CONNECTIONS_DIR,
    DAILY_DIR,
    INDEX_FILE,
    KNOWLEDGE_DIR,
    LOG_FILE,
    MOCS_DIR,
    QA_DIR,
    STATE_FILE,
)


# ── State management ──────────────────────────────────────────────────

def load_state() -> dict:
    """Load persistent state from state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"ingested": {}, "query_count": 0, "last_lint": None, "total_cost": 0.0}


def save_state(state: dict) -> None:
    """Save state to state.json."""
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── File hashing ──────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """SHA-256 hash of a file (first 16 hex chars)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── Slug / naming ─────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ── Frontmatter YAML safety ───────────────────────────────────────────

# A top-level frontmatter scalar whose UNQUOTED value contains ": " — invalid YAML
# (breaks Obsidian's parser even though our regex readers shrug it off). Matches only
# unquoted plain scalars: value must not start with a quote, [, {, |, >, or #.
FM_UNSAFE_SCALAR = re.compile(r"""^([A-Za-z_][\w-]*):[ \t]+([^"'\[{|>#\n][^\n]*: [^\n]*)$""")


def quote_unsafe_frontmatter(article_paths) -> int:
    """Deterministically double-quote frontmatter scalars whose unquoted value
    contains ': ' (the LLM compiler writes prose summaries that legitimately contain
    colons). Idempotent; inner double quotes become single quotes. Returns the number
    of files fixed."""
    fixed = 0
    for p in article_paths:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        lines = text[3:end].split("\n")
        changed = False
        for i, ln in enumerate(lines):
            m = FM_UNSAFE_SCALAR.match(ln)
            if m:
                val = m.group(2).rstrip().replace('"', "'")
                lines[i] = f'{m.group(1)}: "{val}"'
                changed = True
        if changed:
            p.write_text(text[:3] + "\n".join(lines) + text[end:], encoding="utf-8")
            fixed += 1
    return fixed


# ── Markdown doc collection (devlore add / devlore docs) ─────────────

# Path segments that mark vendored or generated trees — excluded at ANY depth,
# even when tracked by git (Go's vendor/ is idiomatically committed; legacy
# repos commit node_modules; pip ships _vendor). Directories only — the
# filename itself is never tested against this list.
DOC_DENY_SEGMENTS = frozenset({
    "node_modules", "bower_components", "vendor", "vendors", "third_party",
    "thirdparty", "dist", "build", "out", "target", "site-packages",
    "venv", "env", "coverage", "__pycache__",
})

DOC_MIN_BYTES = 200   # at or below this a .md is noise (badge stubs, empty templates)
DOC_TRIPWIRE = 50     # a first-level dir contributing ≥ this many docs smells vendored


def collect_markdown_docs(root: Path, recursive: bool = False) -> tuple[list[Path], dict[str, int]]:
    """Find human-written markdown docs under `root` for ingestion.

    Candidate set: `git ls-files` (tracked + untracked-but-not-ignored) when
    `root` is a git repo — the repo's own intent signal, so gitignored vendor
    trees and build output vanish for free — falling back to a filesystem walk
    otherwise. Candidates then pass four gates:

      deny-list  drop any path with a vendored/hidden DIRECTORY segment at any
                 depth (catches tracked vendor trees git intent can't)
      depth      default keeps root-level files + first-level subdirs only;
                 recursive=True keeps the whole tree
      size       drop files ≤ DOC_MIN_BYTES
      tripwire   a first-level dir contributing ≥ DOC_TRIPWIRE surviving docs
                 is excluded wholesale — ingest it by passing that dir
                 explicitly (it then becomes the root and is not tripwired)

    Returns (kept, excluded): kept is sorted; excluded maps each tripwired
    first-level dir name to the number of docs it would have contributed.
    """
    root = root.resolve()
    git = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others",
         "--exclude-standard", "-z", "--", "*.md"],
        capture_output=True, text=True)
    if git.returncode == 0:
        rels = [Path(r) for r in git.stdout.split("\0") if r]
    else:
        rels = [p.relative_to(root) for p in root.rglob("*.md")]

    by_top: dict[str, list[Path]] = {}
    for rel in rels:
        parts = rel.parts
        dirs = parts[:-1]
        if any(seg in DOC_DENY_SEGMENTS or seg.startswith(".") for seg in dirs):
            continue
        if not recursive and len(parts) > 2:  # root file = 1 part, first-level = 2
            continue
        p = root / rel
        try:
            if not p.is_file() or p.stat().st_size <= DOC_MIN_BYTES:
                continue
        except OSError:
            continue
        by_top.setdefault(parts[0] if len(parts) > 1 else ".", []).append(p)

    kept: list[Path] = []
    excluded: dict[str, int] = {}
    for top, paths in sorted(by_top.items()):
        if top != "." and len(paths) >= DOC_TRIPWIRE:
            excluded[top] = len(paths)
        else:
            kept.extend(paths)
    return sorted(kept), excluded


# ── Wikilink helpers ──────────────────────────────────────────────────

def extract_wikilinks(content: str) -> list[str]:
    """Extract all [[wikilinks]] from markdown content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def wiki_article_exists(link: str) -> bool:
    """Check if a wikilinked article exists on disk."""
    path = KNOWLEDGE_DIR / f"{link}.md"
    return path.exists()


# ── Wiki content helpers ──────────────────────────────────────────────

def read_wiki_index() -> str:
    """Read the knowledge base index file."""
    if INDEX_FILE.exists():
        return INDEX_FILE.read_text(encoding="utf-8")
    return "# Knowledge Base Index\n\n| Article | Summary | Compiled From | Updated |\n|---------|---------|---------------|---------|"


def read_all_wiki_content() -> str:
    """Read index + all wiki articles into a single string for context."""
    parts = [f"## INDEX\n\n{read_wiki_index()}"]

    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR, MOCS_DIR]:
        if not subdir.exists():
            continue
        for md_file in sorted(subdir.glob("*.md")):
            rel = md_file.relative_to(KNOWLEDGE_DIR)
            content = md_file.read_text(encoding="utf-8")
            parts.append(f"## {rel}\n\n{content}")

    return "\n\n---\n\n".join(parts)


def list_wiki_articles() -> list[Path]:
    """List all wiki article files."""
    articles = []
    for subdir in [CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR, MOCS_DIR]:
        if subdir.exists():
            articles.extend(sorted(subdir.glob("*.md")))
    return articles


def list_raw_files() -> list[Path]:
    """List all daily log files."""
    if not DAILY_DIR.exists():
        return []
    return sorted(DAILY_DIR.glob("*.md"))


# ── Index helpers ─────────────────────────────────────────────────────

def count_inbound_links(target: str, exclude_file: Path | None = None) -> int:
    """Count how many wiki articles link to a given target."""
    count = 0
    for article in list_wiki_articles():
        if article == exclude_file:
            continue
        content = article.read_text(encoding="utf-8")
        if f"[[{target}]]" in content:
            count += 1
    return count


def get_article_word_count(path: Path) -> int:
    """Count words in an article, excluding YAML frontmatter."""
    content = path.read_text(encoding="utf-8")
    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:]
    return len(content.split())


def build_index_entry(rel_path: str, summary: str, sources: str, updated: str) -> str:
    """Build a single index table row."""
    link = rel_path.replace(".md", "")
    return f"| [[{link}]] | {summary} | {sources} | {updated} |"
