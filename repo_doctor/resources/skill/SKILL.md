---
name: repo-doctor
description: Use when exploring a local Python repository's structure, tracing calls or change impact, producing repository relationship diagrams, or saving source-backed investigation findings with AI Repo Doctor.
---

# Repo Doctor

Use the installed `repo-doctor` CLI for local structure and evidence. Codex owns interpretation, debugging and edits. The primary workflow is offline and requires no API key. Follow the repository's AGENTS rules, including GraphFlow context first where required.

## Understand or map a repository

1. Run `repo-doctor overview REPO --json` for a bounded overview and scan limits.
2. Find a target with `repo-doctor symbols REPO --query NAME --json`. Use a returned symbol ID; do not guess one.
3. Retrieve `repo-doctor context REPO SYMBOL --json` and `repo-doctor impact REPO SYMBOL --depth 2 --json` as needed. Increase context by choosing `--include-symbol ID`, within the budget, rather than dumping the entire index.
4. For a human-readable project map, run `repo-doctor map REPO --out NEW_DIRECTORY`. Return links to `map.html`, `structure.svg` and `relations.svg`. Use `--symbol ID --depth 1` for a focused call view. The page is only a structure map; explain detailed investigations in the Codex conversation.

No issue is required for a structure question. Static call edges describe resolved relationships; missing edges and unresolved calls do not prove defects. Read additional files when necessary and state which evidence the tool did not cover.

## Save an investigation when useful

Create a case with `repo-doctor report create REPO --out NEW_CASE --json`. Collect a fresh snapshot with:

```sh
repo-doctor context REPO SYMBOL --max-lines 120 --snapshot-out NEW_SNAPSHOT.json --json
```

Write a JSON object with a `findings` array. Each finding has nonempty `title`, `category`, `reasoning`, `impact`, `suggested_fix`, numerical `confidence` from 0 to 1, and nonempty `evidence`. Each evidence item has `file`, `start_line`, `end_line`, an exact `quote`, and optionally a returned `symbol` ID. Cite only lines present in the saved context. Use `{"findings": []}` when no finding is supported; do not invent an issue.

```sh
repo-doctor findings import CASE --from FINDINGS.json --context SNAPSHOT.json --producer codex --json
repo-doctor report show CASE --json
```

Exit 0 means all submitted findings passed grounding checks (or the list was empty); 1 means some were rejected; 2 means invalid inputs or another operation error. Accepted findings remain unreviewed. Snapshot/source mismatch requires collecting context again. Never edit case JSON to force acceptance.

If a concrete regression command is appropriate, explicitly record it with `reproduce CASE -- COMMAND ARGS`, or `verify CASE ISSUE --phase before|after -- COMMAND ARGS`. These commands run code; respect the user's scope and existing execution rules. Imported JSON never authorizes commands. Codex performs any authorized patch itself.

Record Codex's judgment with `issue CASE ISSUE --status confirmed|rejected|resolved --actor codex --note "REASON" --json`. Use `--related-test` only when the chosen regression actually addresses the issue. Reopen the report and distinguish exact-source checks, hypotheses and regression results; never claim a user personally confirmed Codex's judgment.
