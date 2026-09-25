# DeepSeek Thinking Mode Experiment Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in DeepSeek thinking mode to the existing diagnosis evaluation path so a later one-request experiment can be prepared, fingerprinted, and sent reproducibly.

**Architecture:** Keep the current request contract byte-for-byte unchanged when no mode is supplied. When explicitly selected, serialize `thinking: {"type": "enabled"|"disabled"}`, include that object in the canonical request fingerprint and prepared plan, validate it again before sending, and record the selected mode in the run summary and scored report. Existing plans and run records without the field remain valid. No provider call is part of this implementation.

**Tech Stack:** Python 3.11+, standard library `unittest`, JSON serialization, existing DeepSeek client and evaluation CLI.

**Spec:** The controlled next-step recommendation in `docs/evaluations/2026-09-25-live-smoke.md`; official [DeepSeek Chat Completions API documentation](https://api-docs.deepseek.com/api/create-chat-completion/).

## Global Constraints

- Do not call any provider or read, print, or write API credentials during this task.
- Omitted thinking mode must preserve the existing serialized request bytes and canonical request hashes.
- An explicit mode is limited to `enabled` or `disabled` and must be present in both the serialized request and its fingerprint.
- Existing plans that omit `thinking_mode` remain valid and retain their existing hashes.
- Preserve the fixed endpoint, JSON response format, `max_tokens=4096`, timeout, and no-retry behavior.
- Do not modify the frozen evaluation manifest, old run plans, target checkouts, or quality labels.

---

### Task 1: Add reproducible opt-in thinking-mode support

**Files:**
- Modify: `repo_doctor/deepseek.py`
- Modify: `tools/diagnosis_data.py`
- Modify: `tools/diagnosis_runner.py`
- Modify: `tools/diagnosis_score.py`
- Modify: `tools/evaluate_diagnosis.py`
- Modify: `evaluation/diagnosis/README.md`
- Modify: `docs/evaluations/2026-09-25-live-smoke.md`
- Modify: `docs/execution-status.md`
- Test: `tests/test_deepseek.py`
- Test: `tests/test_diagnosis_data.py`
- Test: `tests/test_diagnosis_runner.py`
- Test: `tests/test_diagnosis_score.py`
- Test: `tests/test_diagnosis_evaluation_cli.py`

**Interface:**
- `complete_json(..., thinking_mode: str | None = None)` accepts only `None`, `"enabled"`, or `"disabled"`.
- `prepare_cases(..., thinking_mode: str | None = None)` keeps the plan and request hash unchanged for `None`; for an explicit mode it adds `thinking_mode` to the plan and adds `{"type": mode}` under `thinking` in the canonical request shape.
- `evaluate_diagnosis prepare` gains optional `--thinking-mode {enabled,disabled}`; omission remains the default.
- The runner validates the plan mode, rebuilds the same request fingerprint and wire-size check, passes the selected mode to the client, and includes `thinking_mode` in `run.json` only when explicit.
- Scoring accepts either the legacy run schema or that schema plus a valid `thinking_mode`, preserves the field in review metadata, and includes it in the scored JSON/Markdown report only when explicit.

- [x] **Step 1: Write failing client tests**

Add tests proving the default request omits `thinking`, explicit `disabled` serializes as `{"thinking": {"type": "disabled"}}`, and an unsupported mode is rejected before transport.

- [x] **Step 2: Run the client tests and verify the expected failure**

Run: `python3 -m unittest tests.test_deepseek -v`
Expected: the new API tests fail because the serializer/client does not yet accept `thinking_mode`.

- [x] **Step 3: Write failing plan and runner tests**

Add tests proving that an explicit mode changes the canonical request hash and appears in the plan, while omitted mode preserves the existing request hash. Add a runner test proving the validated explicit mode reaches the client and the run summary. Add a tampered-mode test proving a stale request hash is rejected before any client call. Add score tests proving a valid explicit mode survives review metadata and appears in the scored report, while a legacy run with no mode still scores unchanged.

- [x] **Step 4: Run the focused evaluation tests and verify the expected failure**

Run: `python3 -m unittest tests.test_diagnosis_data tests.test_diagnosis_runner tests.test_diagnosis_evaluation_cli -v`
Expected: new mode assertions fail because plan preparation, CLI, runner, and scorer do not yet carry the mode.

- [x] **Step 5: Implement the minimal client, plan, CLI, runner, and scorer changes**

Use the exact same optional mode in wire serialization and canonical request shape. Only add the plan/run-summary field when a mode was explicitly supplied; do not change existing hashes or serialized bytes for old/default plans. Keep existing request safety checks and no-retry control intact. Let the scorer accept the old run key set and the old set plus `thinking_mode`; validate the optional value and include it in output only when present.

- [x] **Step 6: Document the offline prepare flow and network gate**

Update `evaluation/diagnosis/README.md` with a command using `prepare --thinking-mode disabled`, explain that this changes the request hash, and state that preparing a plan does not make a provider call. Explain that a later `run` uses the plan's mode, requires `--allow-network`, and executes the complete plan; `--max-calls` does not select a subset of the ten-case plan. After the code commit, update `docs/evaluations/2026-09-25-live-smoke.md` and `docs/execution-status.md` with the implementation commit SHA and the fact that no provider request has yet used thinking disabled. Do not instruct the user to call the provider during this implementation.

- [x] **Step 7: Run focused tests**

Run: `python3 -m unittest tests.test_deepseek tests.test_diagnosis_data tests.test_diagnosis_runner tests.test_diagnosis_score tests.test_diagnosis_evaluation_cli -v`
Expected: all focused tests pass, including existing default-mode tests and the new disabled-mode fingerprint/transport tests.

- [x] **Step 8: Run the full offline verification set**

Run: `python3 -m unittest discover -s tests -v`
Run: `python3 -m compileall -q repo_doctor tools`
Run: `python3 -m repo_doctor --help`
Run: `python3 tools/evaluate_diagnosis.py prepare --help`
Run: `git diff --check`
Expected: all tests and commands exit successfully; no provider or target-repository code is invoked.

- [ ] **Step 9: Review and commit the implementation**

Inspect the full diff for default-body/hash stability, exact parameter handling, and no live calls. Commit the plan, code, tests, and evaluation README update with message `feat: support DeepSeek thinking mode in evaluation`. Then write the implementation commit SHA into the two status/evaluation docs, inspect that diff, run `git diff --check`, and commit those status updates separately.
