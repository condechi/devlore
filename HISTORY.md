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

### 6. The compile that interrupted itself

As the founding KB matured past two hundred articles, the compiler's original
design — inlining the FULL text of every existing article into every compile
prompt — quietly became its own worst enemy: prompts crossed two million
characters, some exceeded the model's context window outright ("Prompt is too
long"), and the rest spent most of the 300-second part budget just ingesting
context before writing anything. The watchdog then killed those healthy-but-slow
SDK sessions mid-write, leaving half-written articles and broken wikilinks — and
logging each kill as "Request interrupted", indistinguishable from a user
pressing Esc. A usage-insights review in August 2026 blamed the user for
"aborting" dozens of compile sessions before forensics on the transcripts showed
every single "interruption" lasted exactly the watchdog's 300 seconds. v0.9.19
fixed the architecture instead of the user: the compile agent now receives only
the wiki INDEX (the summary catalog) and Reads the specific articles it needs on
demand — shrinking prompts roughly tenfold on mature KBs — while the part
timeout tripled to 900s and the turn budget grew to accommodate the reads.
v0.9.20 closed the companion cost hole: the compile agent had always inherited
the interactive CLI's default model, so a user driving Claude Code with a
top-tier model was silently billing every compile at that tier. A
`compile_model` knob in capture-config now pins compilation to Sonnet by
default, decoupling the pipeline's spend from the user's interactive choices.
v0.9.22 swept up the last trace of the episode: the machinery's own SDK
transcripts — which had grown to 96% of the founding KB's Claude project dir
(1.5 GB of exhaust masquerading as user sessions) — are now deleted on each
compile, identified by the sentinel prompts only devlore's own sessions begin
with, with a 24-hour grace window for anything recent or in flight. v0.9.23
extended the model pin to queries (`query_model`, Sonnet by default), moved the
multi-KB registry from `~/.claude/kb-dirs` to the harness-agnostic
`~/.devlore/kb-dirs` (auto-migrated on first touch — devlore captures Codex as
well as Claude Code, and its own state belongs in its own home), and scrubbed
the last founding-KB repo names out of the tier-3 verifier's prompt, which now
derives its repo list from `scripts/code-roots` like everything else. v0.9.24
uncoupled the dispatcher from its KB: `devlore` no longer needs to be run from
inside a KB. A new `~/.devlore/registry.json` adds named KBs (the flat
`kb-dirs` file stays for legacy routing and the status line), and
`~/.devlore/state.json` holds a per-user default KB. The new subcommands are
`devlore` (lists KBs), `devlore use <name>` (sets default), `devlore which`
(prints the resolved KB for cwd). Read commands (`ask`, `status`, `compile`,
`verify`, `recheck`, `docs`, `backfill`, `obsidian`) route through cwd
detection first, the default KB second, and re-exec the resolved KB's
launcher transparently. `--kb <name>` is now a peer of the existing `--kb
<path>`. A first-detection prompt offers to register any KB the user is
standing in; declines are remembered so the launcher never nags.

### 7. Global launcher + shared machinery

Through v0.9.24 every KB on a user's machine carried its own identical copy of
all 40+ Python scripts, five hooks, `pyproject.toml`, `uv.lock`, and a full
`.venv/`. The PATH entrypoint `~/.local/bin/devlore` was a symlink into one of
the KBs — fine until that KB had a corrupted install or until you tried to
update machinery across four KBs at once. v0.9.25 splits the codebase by
responsibility. The **shared machinery** — `config.py`, `utils.py`, `kb_resolve.py`,
`kb_registry.py`, `capture_config.py`, `transcripts.py`, `activity.py`,
`kb_commit.py`, `staleness.py`, `stamp_baseline.py` — ships once into
`~/.devlore/lib/` and is shared by every KB. The **global launcher** lives at
`~/.devlore/bin/devlore` and is what `~/.local/bin/devlore` symlinks to; it
routes commands to the right KB via the same cwd-decoupling + named-registry
foundation that v0.9.24 added. KB-local scripts (`compile.py`, `query.py`,
`flush.py`, `verify.py`, `recheck.py`, the `*.sh` wrappers, the Obsidian plugin,
and the per-KB `devlore` launcher copy for backward compatibility) stay in
`<kb>/scripts/` because they own per-KB state (`state.json`, `capture-roots`,
`code-roots`, `capture-config`, runtime markers, logs). Hooks stay per-KB at
`<kb>/hooks/` so the absolute paths in every captured project's
`.claude/settings.local.json` and `.codex/hooks.json` don't need re-wiring.
`config.py` resolves the active KB from the launcher-injected `DEVLORE_KB_ROOT`
env var (falling back to `__file__`-relative when called directly) so a single
shared module serves every KB at call time. `init_kb.py` ships the per-KB
`pyproject.toml` as a stub (no deps; they live in `~/.devlore/lib/pyproject.toml`)
and `update_kb.py --to-new-layout` migrates any v0.9.24 KB in place: removes the
ten shared files from `<kb>/scripts/`, installs the shared lib, backs up the old
`pyproject.toml` to `pyproject.toml.v0924.bak`, and repoints `~/.local/bin/devlore`
to the global launcher. Slash commands (`/devlore`, `/ask`, `/compile`, `/verify`)
now invoke the per-KB launcher (`__DEVLORE_HOME__/scripts/devlore <sub> $ARGS`)
instead of `uv run` directly; the launcher injects `DEVLORE_KB_ROOT` and
`PYTHONPATH=~/.devlore/lib`. The result: a `devlore update` re-materializes only
KB-local files (was ~53, now ~30), and a fix to `kb_registry.py` lands once
instead of N times.

### 8. Capture-config preservation (v0.9.26)

The one file under `<kb>/scripts/` that the user customizes is
`capture-config` — `compile_model`, `query_model`, `bootstrap_turns`, and the
other capture-sizing knobs. Through v0.9.25 a `devlore update` would clobber
the user's values back to the dist's defaults on every run, forcing the user
to re-pin them by hand. v0.9.26 special-cases the copy: the dist's
`capture-config` is walked line by line, comments and ordering are adopted
verbatim, and any user value that differs from the dist's default is preserved.
A new key added by the dist flows through; a key the user pinned to a
non-default value survives; a key the user had but the dist no longer ships
(a typo, a deprecated knob the loader already ignores) is dropped with a log
line so the file doesn't silently grow. The merge is idempotent — re-running
`devlore update` after the user has accepted the merge produces a byte-identical
file, so the post-update auto-commit stays quiet for users who never
customized anything.

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
