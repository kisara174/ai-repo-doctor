# Source First Challenge Evaluation Plan

> **For agentic workers:** Execute inline using the existing evaluation interfaces. Preserve `baseline-v1` and its report.

**Goal:** Add a separate source-first challenge set that exposes difficult call, export, registration, and overload cases on the same pinned repositories.

**Architecture:** Reuse the standard-library evaluator and existing manifest schema. Permit `challenge-v1` as a second dataset ID, retain the same three immutable repository pins, and write separate challenge reports. Select and justify probes from source before comparing scanner output.

**Tech Stack:** Python standard library, Git, Repo Doctor scan CLI.

**Spec:** `docs/superpowers/specs/2026-09-24-baseline-evaluation-design.md`

## Global Constraints

- Keep `baseline-v1` manifest and report unchanged.
- Use Click, Requests, and Flask at the already approved commit SHAs.
- Do not clone or execute target code from the evaluator.
- Treat challenge metrics separately from the original baseline metrics.
- Document source-first sample selection and every mismatch.

---

### Task 1: Support a second pinned dataset

**Files:** `tools/evaluate_baseline.py`

- Accept `challenge-v1` in manifest validation.
- Apply the same exact URL and commit pins to both approved dataset IDs.
- Preserve the current `baseline-v1` validation API and report heading.
- Render a challenge-specific report heading when the manifest ID is `challenge-v1`.

### Task 2: Add reviewed challenge probes

**Files:** `evaluation/challenge-v1.json`, `evaluation/README.md`

- Choose probes from source patterns before inspecting scan predictions.
- Include direct method dispatch, dynamic imports/attribute lookup, lazy package attributes, same-line multi-name reexports, explicit `add_command` registration, and overload groups with multiple variants.
- Record exact evidence hashes, source rationale, and expected targets or absence of a statically supported edge.
- Describe any relation model limitation revealed by the run.

### Task 3: Record a separate challenge report

**Files:** `evaluation/results/challenge-v1.json`, `evaluation/results/challenge-v1.md`

- Run five scans per pinned repository using the common evaluator.
- Confirm all repeated hashes agree and review each challenge probe against its source evidence.
- Keep the challenge report distinct from `v2-baseline.*`.
