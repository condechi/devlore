---
description: Ingest hand-written doc file(s) or a directory into the knowledge base (daily log -> wiki)
argument-hint: "@file.md | <dir> [more ...] | --ingest-all-context [flags]"
allowed-tools: Bash(uv run --directory __DEVLORE_HOME__ python:*), Read
---

Add the user's documentation to the knowledge pipeline so it becomes wiki articles.
The same path compiles a daily log, so any decision a doc revises will supersede the
old one (history kept in `knowledge/log.md`).

Paths to ingest (from the command arguments): **$ARGUMENTS**

**Special mode — `--ingest-all-context`:** the GATED batch backfill of never-flushed
conversations (PR D). Run
`uv run --directory __DEVLORE_HOME__ python __DEVLORE_HOME__/scripts/ingest_all_context.py`
passing through any extra flags. It is DRY-RUN by default — show the user the plan +
cost estimate it prints and STOP for their explicit confirmation; only re-run with
`--yes` after they approve the spend (it is compile-dominated, ~$6/conversation-part).
Per-conversation failures are auto-quarantined to `quarantine/<sid>.md` — report any.
Then skip the steps below.

Do this:

1. Parse the path(s) from the arguments above. Strip any leading `@`. A relative
   path is relative to the current working directory; an absolute path is used as-is;
   a **directory** ingests every top-level `*.md` inside it. If no path was given,
   ask the user which file or directory to ingest and stop.

2. Append the doc(s) to today's daily log (deterministic, no summarization):

   `uv run --directory __DEVLORE_HOME__ python __DEVLORE_HOME__/scripts/ingest_doc.py <path1> <path2> ...`

3. Compile into the wiki:

   `uv run --directory __DEVLORE_HOME__ python __DEVLORE_HOME__/scripts/compile.py`

   (Note: compile takes a single global lock. If it prints "Another compile is
   already running", a background compile is active — wait a moment and re-run, or
   tell the user it will be picked up by the next compile.)

4. Report the result concisely: which wiki articles were **created** / **updated**,
   and any **supersede** entries — read the tail of
   `__DEVLORE_HOME__/knowledge/log.md` to find them. Do not dump
   article bodies; just summarize what landed.
