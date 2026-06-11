---
description: Ask the knowledge wiki a question (index-guided retrieval, no RAG)
argument-hint: "\"question\" [--project <slug>] [--file-back] [--dev]"
allowed-tools: Bash(uv run --directory __DEVLORE_HOME__ python:*), Read
---

Answer a question from the compiled knowledge base. The retrieval reads
`knowledge/index.md`, picks the few most relevant articles, reads only those, and
synthesizes a cited answer — no RAG. Add `--file-back` to file the answer as a
`knowledge/qa/` article (the compounding loop), `--project <slug>` to restrict
retrieval to one project, or `--dev` to also resolve the answer's cited symbols to
live `file:line` code pointers (grep at query time — experimental, never stored).

Question and flags (from the command arguments): **$ARGUMENTS**

Do this:

1. If no question was given, ask the user what they want to know and stop.

2. Run (keep the question quoted as a single argument; pass `--project` / `--file-back`
   through verbatim if present):

   `uv run --directory __DEVLORE_HOME__ python __DEVLORE_HOME__/scripts/query.py $ARGUMENTS`

3. Relay the answer the script prints (it is already cited with `[[wikilinks]]`). Do
   not re-research or pad it.

4. If `--file-back` was used, also report where it was filed (the script prints
   `— filed to knowledge/qa/<slug>.md`) — that article, a new `index.md` row, and a
   `query` entry in `knowledge/log.md` were just added.
