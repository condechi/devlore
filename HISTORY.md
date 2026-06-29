# The History of devlore

> *"Claude Code deletes your transcripts after 30 days. This makes them immortal."*

devlore is a knowledge-base pipeline that compiles AI coding-session logs into a
structured, queryable wiki. It drives the Claude Agent SDK from three callers —
compile, query, and a memory-flush hook — turning ephemeral conversation
transcripts into durable institutional memory about a codebase. This is the
story of how it got here.

## Origins: a memory compiler in a single repo

devlore began on May 22, 2026, not as a product but as a clone of
[coleam00's claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler)
dropped into a single private project directory. That first install wired up the
full capture → compile → inject loop end to end: uv as the Python runner, a
daily auto-compile keyed to the local evening, and SessionStart / PreCompact /
SessionEnd hooks registered in `.claude/settings.json`. Capture was deliberately
scoped to that one repo and nothing else.

The conceptual lineage runs back further still — to Andrej Karpathy's idea of an
LLM that reads your conversations and compiles them into a personal knowledge
base. That original framing assumed one person, one knowledge domain, and a
completely open schema. It was a clean starting point, and the pipeline outgrew
it almost immediately.

The upstream skeleton — daily logs treated as immutable source material, an LLM
compiler that distills them, a knowledge wiki as the output, and context
injected back at the start of each session — is still the shape of the system
today. But over the following weeks nearly every mechanism inside that skeleton
was rebuilt:

- Fixed capture windows became **delta markers**, so the compiler processes
  exactly what is new.
- A single monolithic compile call became **entry-aware chunking**.
- The flat, open schema became a **project / subsystem namespace**, introduced
  the moment a single flat wiki started blending tooling knowledge with the
  founding project's domain knowledge.

## The motivation: transcripts don't survive

A formative lesson arrived through data loss. Claude Code deletes its local
`.jsonl` transcripts after `cleanupPeriodDays` — 30 by default — and that
deletion permanently destroyed an entire project's sessions before any knowledge
base could be built from them. The takeaway was blunt and became a design
principle: **a knowledge base is only as good as the source material that
survives long enough to be compiled.**

That episode is, quite literally, the product's tagline: *"Claude Code deletes
your transcripts after 30 days. This makes them immortal."*

## From personal pipeline to product

Two steps turned a personal, single-project setup into something anyone could
use.

### 1. Making it replicable

Everywhere the pipeline silently assumed it was running against its founding
repo, that assumption was pulled out and moved behind configuration: a
`code-roots` config file, a dict-valued `code_baseline`, and a multi-KB
status-line dispatcher. A new `scripts/init_kb.py` was built to scaffold a
complete, working knowledge base for any codebase from scratch.

The proof came from running it live against a second, unrelated project. The
compiler invented its own thirteen-subsystem taxonomy appropriate to that
codebase, with zero vocabulary from the founding project leaking through —
confirmation that the system was genuinely portable rather than a one-repo tool
wearing a disguise.

### 2. Renaming and publishing

By this point the pipeline was called **wikiLLM**, and the plan was to ship it
under that name. But the `wikillm` GitHub slug was already taken, so it was
renamed **devlore** and published at
[github.com/condechi/devlore](https://github.com/condechi/devlore).

The rename was carried out by `build_dist.py`, using case-insensitive regex
across both file contents and filenames, since the legacy name appeared in
several different casings. A security review ahead of release found and fixed
ten issues. Then a live `devlore add` smoke test — building a "meta-KB of the KB
itself" from the pipeline's own daily logs — surfaced eight more fixes across
v0.9.1 through v0.9.8. That work culminated in the `devlore update` command,
which keeps an installed KB's machinery current without ever touching its
knowledge, daily logs, markers, or git history.

### 3. The Emancipation

Through v0.9.12 the source of truth still lived *inside* the founding private
KB — making it the one knowledge base that could not be managed by the very
CLI it produced. On June 11, 2026 (v0.9.13) the source was extracted into a
dedicated development repo, seeded from the distribution itself — which by
then was brand-clean and placeholder-pathed, so the legacy rename pass was
retired from the build. The founding KB became a normal consumer, updated by
`devlore update` like every other install.

### 4. Beyond Claude Code: Codex, tags, and worktrees

With development now in its own repo, v0.9.14 landed the first wave of
post-Emancipation features in a single release. devlore stopped being
Claude-Code-only: a shared transcript normalizer (`scripts/transcripts.py`)
lets it capture **Codex** sessions too, wiring `.codex/hooks.json` alongside
Claude Code's hooks and discovering past Codex transcripts for backfill (the
Agent SDK still does the compile/query work). Alongside it shipped
project-slug-first **frontmatter tags** for Obsidian, **git-worktree capture**
(sessions in `.claude/worktrees/` now map to their project for capture,
recall, and backfill), and **owning-KB routing** so a bare `devlore add` finds
the right knowledge base when several are installed.

### 5. Fire-and-forget capture

The delta-marker work made the compiler process exactly what was new — but only
*after* a session's first flush, which fired on compaction or exit. A long
session that did neither captured nothing, and its eventual first flush kept only
the most recent `max_turns` turns, hiding the rest behind the very marker it
wrote (the "first-flush footgun"). v0.9.16 closed that gap with a Claude `Stop`
hook that fires the first flush **automatically** once a session reaches
`bootstrap_turns` (default 45), with a safety valve for sessions that run long
without compacting. Capture stopped asking the developer to exit and wait;
PreCompact's first-flush truncation also became visible instead of silent.
(Codex already captured every turn through its `Stop` event, so the gap was
Claude-Code-only.) The same release auto-excluded code-root symlinks from the
KB's own git and tagged each daily entry with its source project.

## The lineage, in one line

coleam00's claude-memory-compiler (installed May 22, 2026) → heavily adapted
inside one production repo → renamed wikiLLM → de-hardcoded and made
bootstrappable → productized and published as **devlore** → emancipated from
its founding repo into a dedicated source repo → opened up to Codex alongside
Claude Code.

---

*Provenance: this history was not written from memory. It was reconstructed by
asking devlore's own meta-KB — the knowledge base the smoke test built about the
project itself — with `devlore ask "How did devlore come to exist?"`. The
product documented its own origin story.*
