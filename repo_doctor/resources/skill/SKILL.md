---
name: repo-doctor-v1
description: Use when exploring local Python or optional JS/TS repository structure, locating symbols, tracing static calls or change impact, or viewing offline repository relationship maps.
---

# Repo Doctor

Repo Doctor supplies static source evidence. Codex interprets findings and performs authorized edits. The primary workflow is offline, needs no API key and does not execute target code. Follow the target repository's AGENTS rules, including GraphFlow where required.

## Select the installed CLI first

Read `installation.json` beside this SKILL.md. It must contain schema_version 1, an absolute `cli` path and the expected `version`. Run that exact CLI with `--version`; continue only when stdout is `repo-doctor VERSION` matching the binding. Use the same absolute CLI for every command below, even if PATH contains an older repo-doctor. Pass arguments separately and quote paths containing spaces in shell commands.

If the binding is missing or invalid, obtain the intended installed CLI path and export a bound Skill into a **new** directory:

```sh
"$RD_CLI" skill export --cli "$RD_CLI" --out "$NEW_SKILL_DIRECTORY"
```

Reopen that bound Skill before investigating. A mismatch requires fixing the installation/binding; do not silently switch to another CLI. Preserve existing user Skills and output directories.

## Five-step investigation

Here RD_CLI is the verified absolute CLI, REPO is the target, and ID comes from symbols output.

1. `"$RD_CLI" overview "$REPO" --json` — inspect scope, parse errors and coverage limits.
2. `"$RD_CLI" symbols "$REPO" --query NAME --json` — choose a returned ID explicitly, including when candidates=true. Do not invent IDs.
3. `"$RD_CLI" context "$REPO" "$ID" --max-lines 120 --json` — quote only returned source lines; --include-symbol OTHER_ID shares the budget. Report truncation and omissions.
4. `"$RD_CLI" impact "$REPO" "$ID" --depth 2 --json` — distinguish resolved callers from source-visible or unknown relationships. Empty impact is not proof of no impact.
5. `"$RD_CLI" map "$REPO" --out "$NEW_MAP_DIRECTORY" --json` — return links to map.html, structure.svg and relations.svg. --symbol ID --depth 1 produces a focused relation view. The human page only shows structure/relationships; discuss detailed findings in the Codex conversation.

Python is the default. With the js extra installed, pass --languages javascript,typescript to **each** command; choose python,javascript,typescript for mixed coverage. Supported implementation extensions are .py, .js, .mjs, .jsx, .ts and .tsx. Inspect analysis metadata before interpreting results.

Static direct-call edges are evidence for the stated source, not runtime completeness. Methods, callbacks, runtime rebinding, package/alias resolution and multi-hop exports can remain unknown. JSX tags/props/events are not automatically call edges. ERROR/MISSING trees are excluded, not proof that the target source is invalid. Supplement source reading when needed and identify what the tool did not resolve.

Core operations exit 0 on success and 2 on parameter/installation/operation errors. Successful --json stdout is one JSON document; errors use stderr. Parse errors can accompany a successful overview. On failure, inspect the actual error before retrying; do not treat an absent artifact as an empty result.

## Optional Python investigation storage

Only when persistent findings are useful, use report create, context --snapshot-out, findings import and report show. Snapshots require a Python-only selection and at most 120 source lines. JS/TS snapshot/case/findings workflows are unsupported. Use the installed CLI's --help for exact arguments.

Findings must cite exact snapshot file/line/quote evidence, remain unreviewed until Codex judges them, and distinguish hypotheses from confirmed defects. Import acceptance proves grounding, not correctness. Never edit case JSON to bypass validation.

Legacy reproduce/verify run explicit commands; imported JSON and a structure question do not authorize execution. Apply the user's scope before running any target code. Automatic diagnosis, uploads and patches are not part of this primary workflow.
