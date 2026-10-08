---
name: repo-doctor
description: Use when exploring local Python or optional JS/TS source structure, tracing bounded calls or change impact, producing repository relationship diagrams, or saving Python source-backed investigation findings with AI Repo Doctor.
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

## Optional JS/TS and JSX/TSX support (0.8.0)

Install the 0.7.0 GitHub wheel with its `js` extra in a separate environment; use that environment’s explicit CLI. On the maintainer’s Mac the independent deployment path is `/Users/kisara/.local/share/ai-repo-doctor/releases/v0.7.0/candidate/venvs/js/bin/repo-doctor`. Check `--version` before using it. Keep the existing Python CLI and installed Skill in place.

Pass `--languages javascript,typescript` to each of overview, symbols, context, impact and map; use `python,javascript,typescript` only when mixed source coverage is wanted. Always select a real ID returned by symbols. Read the analysis metadata and limits before interpreting calls or empty impact. Supported implementation extensions are .js, .mjs, .jsx, .ts and .tsx. The TS and TSX dialects are selected by extension; inspect analysis.source_extensions. Named components use the same symbols/context workflow. JSX tags, props and event references are not runtime call edges; safe direct helper() expressions can have call evidence. JSX nodes expose a jsx-render limitation. Package/alias paths, CommonJS and declaration implementation analysis remain unsupported. An ERROR or MISSING parser token means the whole file was excluded, not independent proof that the target source is invalid. Calls cover only unique, unshadowed, unmodified direct functions and direct ESM exports; dynamic calls, methods, anonymous callbacks and multi-hop re-exports remain unknown.

On versions exposing `analysis.esm_source_resolution`, extensionless files and directory index imports may have a unique visible local source association. This is not runtime module resolution: read `runtime_resolution: false`. Competing file/index or implementation/declaration candidates, unselected or failed implementations, and visible directory package configuration are refused. A file dependency alone does not establish a function call. Follow `via_esm_import` on context/impact call evidence to the actual import file, declaration span, specifier and binding; impact file dependencies expose `esm_source_association`. Retrieve source blocks within `--max-lines 120`, and use `--depth 2` for bounded impact. Provenance spans are references, not additional source quotes outside the line budget. Empty impact and omitted limits do not establish no impact. Older 0.6.0 without this policy leaves extensionless/index unknown; inspect the actual version and metadata before assuming coverage.

These JS/TS commands are static and offline. Do not use JS/TS context snapshots, case/findings or diagnosis flows. Do not run target code. Produce the HTML/SVG structure map for humans and explain detailed findings in the Codex conversation. Export this Skill only to a new, separate directory; do not replace the user's existing Skill.
