# Reproduction-Backed Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The primary agent owns safety, design, review, and acceptance under `AGENTS.md`; no executor may decide these.

**Goal:** Let an installed CLI record an explicit failing command before any AI issue exists, then optionally bind a source-current diagnosis and later repair check to it.

**Architecture:** Add case-level reproduction records using the existing `run_verification` runner. An explicit diagnosis selector adds one bounded, untrusted observation to the request; default request bytes remain unchanged. Link each resulting AI issue to a compact `before` verification record so the existing explicit `after` flow can close it.

**Tech Stack:** Python 3.11+, `argparse`, existing case schema v1, `unittest`, existing wheel/CI workflow.

**Spec:** [reproduction-backed design](../specs/2026-09-30-reproduction-backed-diagnosis-design.md).

## Global constraints

- No automatic target command execution. Only `reproduce CASE -- argv` and existing `verify` execute code; both use the existing runner's 1–300 second timeout, 16-KiB output cap, minimal environment, and `shell=False`.
- `--reproduction ID` requires `--case`, a failed latest run for its exact argv, unchanged scanned Python source during that run, and the current source fingerprint equal to the recorded one.
- A reproduction-backed live request requires the matching `--expect-request-sha256`; both preview and live use the same serialized body and 256-KiB wire cap. Recheck the full Python source fingerprint after the provider response.
- Preserve case schema v1 compatibility and the existing blind fixture request hash `2d1d7ca4b298c17d511d01dc6e70e8bad41d7120cbec1844540959862bf3fd12`.
- AI findings remain unreviewed hypotheses. No model precision claim or external target repository execution follows from this work.

## File map

| File | Responsibility |
| --- | --- |
| `repo_doctor/case.py` | Save, locate, and validate case-level reproductions; link optional ID and compact before-record to AI issues. |
| `repo_doctor/cli.py` | Parse explicit argv, add `reproduce` command and opt-in diagnosis guard; keep preview/live bytes aligned. |
| `repo_doctor/diagnosis.py` | Add an optional untrusted reproduction payload without changing the blind prompt. |
| `repo_doctor/report.py` | Distinguish observed command failure from AI hypothesis and show the provenance link. |
| `tests/test_reproduction.py` | Focused CLI, prompt, source-staleness, case-reopen, and repair-closure tests. |
| `README.md`, `docs/PRODUCT_GUIDE.md`, `docs/execution-status.md` | Installable user path and explicit quality boundary. |

## Task 1: Save a pre-issue reproduction

**Interfaces:** `record_reproduction(case: dict, result: dict) -> dict` assigns `R-001` and appends it; `require_reproduction(case: dict, id: str, current_fingerprint: str) -> dict` validates one opt-in run. The CLI's `reproduce CASE [--timeout N] [--json] -- argv` uses `run_verification` unchanged.

- [ ] Write a focused test that creates a case without issues, executes `python -c 'raise RuntimeError("observed")'` via `reproduce`, and asserts exit 1, stable `R-001`, saved failed status/output, equal before/after Python fingerprints, and a readable reopened case.
- [ ] Run `python3 -m unittest tests.test_reproduction.ReproductionTests.test_record_before_issue -v`; verify failure because `reproduce` is not recognized.
- [ ] Add the parser branch and `--` argv split parallel to `verify`. Compute fingerprints before and after the explicit runner, append the record, save the case, and return 0 only for a passed command.
- [ ] Add a focused passing-run test and a test that a later pass of the same argv supersedes an earlier failure. Validate missing ID, timeout, command error, and source drift before provider use.
- [ ] Run `python3 -m unittest tests.test_reproduction -v` and `git diff --check`; commit the coherent command/data change.

## Task 2: Bind one reproduction to the exact diagnosis request

**Interfaces:** `build_diagnosis_prompts(context: dict, *, reproduction: dict | None = None) -> tuple[str, str]` leaves the `None` path byte-identical. `diagnose --reproduction R-001 --case CASE` selects only a validated run. `record_preview`, `record_diagnosis`, and `record_diagnosis_failure` receive optional `reproduction_id: str | None` and omit the field for blind calls.

- [ ] Write tests for the pre-change blind request SHA above; a selected failure adds `reproduction` metadata/output to the user payload, changes the request hash, and includes an untrusted-observation instruction. Test both `chat-json` and `json-schema` preview/live byte parity with a fake transport.
- [ ] Run the new targeted tests and observe expected failure before changing production code.
- [ ] Add the optional prompt payload. In CLI, validate `--case`, failed/latest/source-current run, and required live preview hash before Key/network; recheck full Python fingerprint after the provider response. Preserve the default serializer calls unchanged.
- [ ] Add negative tests proving pass, stale Python source, source mutation during the provider call, missing hash, and wrong preview hash all block upload or discard findings. Check that blind diagnosis ignores saved reproductions.
- [ ] Run `python3 -m unittest tests.test_reproduction tests.test_diagnose_preview tests.test_diagnosis_prompt -v` and `git diff --check`; commit the opt-in request path.

## Task 3: Close the report and repair path

**Interfaces:** On an accepted AI finding with `reproduction_id`, `record_diagnosis` copies only the selected run's ID, argv, status, timestamps, exit code, duration, and source fingerprints into issue `verification` with `phase: before`; it does not duplicate output. `render_report` uses optional fields for old cases.

- [ ] Write a test in `tests/test_reproduction.py` with a controlled `app.value()==2` failure, fake quote-backed finding, source edit to return 2, explicit `verify ... --phase after -- same argv`, and `issue --status resolved --related-test`; assert report says `有修复证据` only after human confirmation.
- [ ] Run that test first and observe failure due missing linkage/report behavior.
- [ ] Add compact before-record linkage, reproduction and diagnosis sections in Markdown, and clear `observed failure` versus `AI hypothesis` labels. Render old schema-v1 cases without a `reproductions` key.
- [ ] Add one test that a quote-verified finding alone remains unreviewed and one that a different after command does not close the repair state.
- [ ] Run `python3 -m unittest tests.test_reproduction tests.test_product_cli tests.test_product_verify tests.test_product_case -v`; commit the report/linkage change.

## Task 4: Verify the installed workflow and deliver

- [ ] Update README and product/status docs with exact `reproduce`, preview, live, and after commands. State that command output may contain secrets and must be inspected before upload; Python fingerprint does not cover non-Python files. Keep the model-quality boundary explicit.
- [ ] Run the full offline suite once: `python3 -m unittest discover -s tests -q`; run `python3 -m compileall -q repo_doctor tools` and `git diff --check`. Repair concrete failures and rerun affected checks.
- [ ] Build a wheel from the exact committed head, install it into a clean virtual environment outside source, and exercise the controlled demo through `report create → reproduce failure → diagnose --preview → source fix → stale reproduction refusal`. The mocked transport tests cover live wire parity without spending an unregistered provider call.
- [ ] Inspect the full branch diff and status, push, create and attach a PR, wait for all Python 3.11–3.13 CI jobs on its head, then merge. Verify default-branch commit and report any remaining diagnostic-quality limit.
