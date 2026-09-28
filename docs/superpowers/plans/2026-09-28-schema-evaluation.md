# JSON Schema Diagnosis Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. The primary agent owns protocol decisions, review, provider calls, and acceptance. The local Luna policy permits only separately bounded mechanical packets.

**Goal:** Add a reproducible JSON Schema protocol option to the frozen diagnosis evaluation without changing legacy Chat plan hashes.

**Architecture:** Keep version 1 Chat plans byte compatible. Prepare a version 2 schema plan whose per-case request hash covers exact production wire bytes; the runner verifies that hash and dispatches by plan version. Add protocol metadata to schema run and score outputs only.

**Tech Stack:** Python 3.11+, standard library `unittest`, existing `repo_doctor` and `tools.evaluate_diagnosis` modules.

**Spec:** [JSON Schema diagnosis evaluation design](../specs/2026-09-28-schema-evaluation-design.md).

## Global constraints

- Keep `evaluation/diagnosis/manifest-v1.json` byte-for-byte unchanged (SHA-256 `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`).
- Do not execute target repository code, tests, or dependencies. Do not store Key, raw request body, or raw provider response in tracked files.
- Preserve schema version 1 Chat plan fields and request hashes, including optional `thinking_mode`.
- Use production `_serialize_schema_request_body` to fingerprint schema wire bytes; reject >256 KiB before network.
- Keep one request per case/repeat, stop on the first provider failure, and never change the default Chat format automatically.
- Work in `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`; preserve existing commits and ignored experiments.

## File map

| File | Responsibility |
| --- | --- |
| `tools/diagnosis_data.py` | Prepare version 2 plan and exact schema request hashes. |
| `tools/diagnosis_runner.py` | Revalidate protocol and hash, then execute existing bounded runner. |
| `tools/evaluate_diagnosis.py` | Accept prepare format and select provider client from the plan. |
| `tools/diagnosis_score.py` | Validate and show schema run metadata without changing Chat reports. |
| `tests/test_diagnosis_data.py`, `tests/test_diagnosis_runner.py`, `tests/test_diagnosis_score.py` | Focused red/green contract tests. |
| `docs/evaluations/` | Record offline and authorized online evidence without raw response. |

## Task 1 — Offline schema preparation

- [ ] Add a failing `tests/test_diagnosis_data.py` test calling `prepare_cases(..., response_format="json-schema")`. Assert `schema_version == 2`, `response_format == "json-schema"`, absent `thinking_mode`, and `request_sha256 == hashlib.sha256(_serialize_schema_request_body(system_prompt, user_prompt, "test-model")).hexdigest()` for the fixture. Assert no request was opened.
- [ ] Add a failing test that `response_format="json-schema", thinking_mode="disabled"` raises `EvaluationDataError`; add one for an unknown format. Run `python3 -m unittest tests.test_diagnosis_data -q` and confirm the failure is due to the absent format interface.
- [ ] Add `response_format: str = "chat-json"` as a keyword argument to `prepare_cases`; validate allowed values and the incompatible thinking option. Keep the Chat branch's existing request shape/hash and plan keys untouched. For schema, serialize with `_serialize_schema_request_body`, check the body size, hash raw bytes, and set version 2 plus `response_format` on the plan.
- [ ] Add `--response-format {chat-json,json-schema}` to `prepare` in `tools/evaluate_diagnosis.py`, passing it to `prepare_cases`. Run the focused tests green. Compare a fixture's default Chat plan with the pre-change expected shape/hash in existing tests. Commit this independently testable preparation change.

## Task 2 — Runner protocol verification and dispatch

- [ ] Add failing runner tests preparing a schema fixture and calling `run_cases` with a mock client. Assert two calls, no `thinking_mode` kwarg, `run.json` has `response_format="json-schema"`, and records carry the prepared hash. Tamper the schema request hash and assert no output directory and zero calls. Also assert an oversized schema body rejects before output creation. Run `python3 -m unittest tests.test_diagnosis_runner -q` red.
- [ ] In `_validate_plan_and_contexts`, accept only version 1 Chat or version 2 `json-schema`; for version 2 require the format field and no thinking field. Rebuild each context, serialize the schema wire request with the production helper, enforce the byte limit, and compare its SHA-256 with `request_sha256`. Preserve the version 1 Chat hash calculation exactly.
- [ ] In `run_cases`, select the matching serializer for its size preflight and add `response_format` to the summary only for version 2. Keep the injected `client` signature, call cap, record schema, and error behavior. In `_run`, choose `complete_json_schema` only after loading a version 2 schema plan; otherwise choose `complete_json`. Run the focused runner tests green; run CLI help and a rejected tampered-plan check. Commit.

## Task 3 — Scoring provenance

- [ ] Add a failing scoring test with a complete schema run fixture: `score_records` must carry `response_format`, and `render_report` must print it. Add a test rejecting a run that combines `response_format` and `thinking_mode` or supplies an unknown format. Run `python3 -m unittest tests.test_diagnosis_score -q` red.
- [ ] In `tools/diagnosis_score.py`, allow only the existing Chat run key shapes or the base key set plus `response_format="json-schema"`. Copy the protocol to scored JSON and Markdown. Preserve old Chat report bytes for unchanged inputs. Run focused tests green, then the full `python3 -m unittest discover -s tests -q`, `python3 -m compileall -q repo_doctor tools`, and `git diff --check`. Review the actual diff and commit.

## Task 4 — Frozen offline plan and gated online checkpoint

- [ ] Confirm the analyzer checkout is clean and committed, the manifest SHA matches the frozen value, and all pinned target worktrees match expected commits with clean status. Prepare a new ignored directory with `python3 -m tools.evaluate_diagnosis prepare --manifest evaluation/diagnosis/manifest-v1.json --repos-root .local/diagnosis/checkouts-20260927 --model deepseek-flash --max-lines 120 --response-format json-schema --out-dir .local/diagnosis/plan-schema-20260928`.
- [ ] Compare all ten `context_sha256` values with the frozen prior Chat plan and independently recompute every schema `request_sha256` from the production serializer. Record protocol, plan hash, source budgets, and hashes in a concise evaluation report; do not copy source into tracked docs.
- [ ] If the Key is present and the prepared inputs pass review, run exactly one `requests-6628-bug` attempt in a new output directory with `--repeats 1 --max-calls 1 --case-id requests-6628-bug --allow-network`. Record safe status, usage, and whether local citations were accepted. If successful, review all returned claims against the pinned source and fix; a source match alone is not TP.
- [ ] Start a full ten-case run only if that one response is parseable and its claims are reviewable. Stop at the first provider failure. Prepare human review rows, adjudicate each completed finding, score only a complete reviewed dataset, and report partial coverage honestly. Never overwrite old plans, runs, or reports.

## Self-review

This plan covers preparation, transport provenance, dispatch, scoring, offline
reproducibility, and the conditional provider checkpoint. It preserves the
legacy request-hash convention for Chat and changes no target repository.
There is no automatic retry, protocol fallback, or claim of general model
quality from a single smoke test.
