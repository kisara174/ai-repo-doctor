# Diagnosis Quality Next Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Read the applicable `AGENTS.md`. The primary agent owns
> defect judgments, experiment design, API decisions, review, and acceptance.
> A `luna_executor` may receive only a separately bounded mechanical packet
> that meets the local routing policy.

**Goal:** Obtain a trustworthy first diagnosis-quality baseline for the
expanded context while protecting its source-selection contract and delivering
the unpublished evaluation branch.

**Architecture:** Keep the frozen ten-case manifest and the existing
single-case runner. First check the exact behavior changed by commit
`6791483`, then validate the release candidate once. Reprepare under the
current clean analyzer commit, make one controlled bug-snapshot call, and
start the ten-case run only if that call yields a usable response. Review model
claims against source before scoring or changing the prompt.

**Tech Stack:** Python 3.11–3.13, `unittest`, the existing
`tools.evaluate_diagnosis` CLI, Git worktrees, and the optional DeepSeek API.

**Spec:** [V3 design](../specs/2026-09-24-repo-doctor-v3-design.md),
[evaluation execution contract](2026-09-24-post-v3-execution.md), and
[the current experiment report](../../evaluations/2026-09-28-context-expansion.md).

## Global constraints

- Work in `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`
  on `codex/diagnosis-evaluation`. The original V2-design checkout has
  untracked plans; leave it alone.
- Preserve the frozen manifest, SHA-256
  `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
  Do not relabel cases or overwrite existing plans, runs, or reports.
- Keep source scanning read-only. Do not execute evaluated repositories, their
  tests, or their dependencies.
- The online experiment changes one input at a time. Keep model
  `deepseek-flash`, disabled thinking, the current prompt/schema, and
  `max_tokens=4096` fixed through Task 4. No automatic retry or alternate
  provider.
- Do not print or persist the API key, raw provider response, or private
  source. Existing evaluation artifacts hold reviewed public snippets only.
- A local evidence match proves a quote and source location, not a behavioral
  bug. Primary review must be labeled as such; a single-case smoke cannot
  become a dataset score.
- Run checks only for a named risk or release gate. Record the command, exit
  code, and commit it actually checked. Prior results do not validate new code.

## Files and responsibilities

| File or directory | Responsibility in this stage |
| --- | --- |
| `tests/test_context.py` | Guard the added ancestry, import, ordering, and line-budget behavior with a small local fixture. |
| `repo_doctor/context.py` | Change only if the focused fixture exposes a real defect; review any such change separately. |
| `docs/execution-status.md` | Keep the branch, verification scope, and experiment state current. |
| `docs/evaluations/2026-09-28-context-expansion.md` | Preserve the current three-run evidence and primary review. |
| `.local/diagnosis/` | Ignored local plans, public-sample contexts, and run records; create new output directories for new experiments. |
| `evaluation/diagnosis/manifest-v1.json` | Immutable case IDs, commits, and ground truth. |

## Task 1 — Prove the new context behavior

**Question:** Does `build_context` include a resolvable local base chain and
only import bindings used by selected source while obeying `max_lines`?

- [ ] Confirm a clean `codex/diagnosis-evaluation` checkout and record `git
  rev-parse HEAD`. Read the existing `ContextTests` fixture style.
- [ ] Add one focused fixture in `tests/test_context.py` with separate import
  statements for `Decoder` and `unrelated`, followed by:

  ```python
  from compat import Decoder
  from compat import unrelated

  class GrandError(Exception): pass
  class BaseError(GrandError): pass
  class ChildError(BaseError):
      def decode(self):
          return Decoder()
  ```

  Assert that `build_context(index, "errors.py::ChildError", max_lines=6)` emits the
  target, `BaseError`, and `GrandError` in that order; includes the
  `Decoder` import binding; and excludes the separately declared
  `unrelated` import.
- [ ] On the same fixture, use `max_lines=5`. Assert that emitted physical
  lines total at most five, `omitted_imports == 1`, and
  `budget_exhausted is True`. This protects the actual new budget path.
- [ ] Run only `python3 -m unittest tests.test_context -v` and
  `git diff --check`. If a focused test fails, identify the cause before
  editing `repo_doctor/context.py`. A behavior fix gets a separate diff review.
- [ ] Commit the focused test, and any reviewed fix, before preparing another
  provider request. Save the new commit SHA in `docs/execution-status.md`.

**Acceptance:** The fixture proves ancestry order, relevant import selection,
and the shared physical-line budget. No wider test sweep is needed for this
task. **Stop:** A case requires parser redesign, external dependency
resolution, or a changed context schema; the primary agent must re-scope it.

## Task 2 — Verify and deliver the unpublished branch

**Question:** Does the complete evaluation branch still satisfy its existing
offline contract, and does CI check the exact head proposed for integration?

- [ ] Review `git diff` and `git log origin/codex/diagnosis-evaluation..HEAD`,
  including every unpublished commit and Task 1. Check that only
  intended code, tests, and documentation are included.
- [ ] Run the full local `python3 -m unittest discover -s tests -q` once as
  the branch integration gate, followed by
  `python3 -m compileall -q repo_doctor tools` and `git diff --check`.
  Record counts and exit codes. Resolve only concrete failures.
- [ ] Push the reviewed branch and open or update its PR under the standing
  project authorization. Confirm the repository's current default branch
  before selecting the PR base; the last locally recorded default was
  `codex/repo-doctor-v1`. Attach the PR to this task. Check its Python
  3.11, 3.12, and 3.13 CI jobs on the actual PR head. PR #6's earlier green
  jobs do not cover this branch.
- [ ] Record the PR URL, head SHA, CI job results, and any remaining issue in
  `docs/execution-status.md`. If that documentation creates a new commit,
  check CI again on the new head. Merge only after the current head and
  review state have been checked.

**Acceptance:** Local integration checks and all required CI jobs apply to
the same reviewed code. **Stop:** An unexpected merge conflict or behavioral
regression appears; do not repair it by changing frozen case expectations.

## Task 3 — Close the expanded-context bug comparison with one call

**Question:** With ancestry and bindings present, can the existing prompt
return a parseable, source-supported finding for `requests-6628-bug`?

- [ ] From a clean, committed analyzer checkout, prepare a new plan in
  `.local/diagnosis/plan-quality-20260928/` using:

  ```bash
  python3 -m tools.evaluate_diagnosis prepare \
    --manifest evaluation/diagnosis/manifest-v1.json \
    --repos-root .local/diagnosis/checkouts-20260927 \
    --model deepseek-flash --thinking-mode disabled --max-lines 120 \
    --out-dir .local/diagnosis/plan-quality-20260928
  ```

  The plan directory must be new. The tool must verify all ten pinned,
  clean target checkouts before any request.
- [ ] Compare the new bug, fixed, and control `context_sha256`,
  `request_sha256`, and wire SHA-256 with the audited values in
  [the current report](../../evaluations/2026-09-28-context-expansion.md)
  and ignored audit JSON. If only tests/docs changed, these payload hashes
  should match. Explain any difference and stop the paired comparison if
  the transmitted payload changed.
- [ ] Confirm the API key is present without displaying it. Inspect the exact
  selected public-source scope, request size, plan metadata, and empty new
  output directory. Make at most one request:

  ```bash
  python3 -m tools.evaluate_diagnosis run \
    --plan-dir .local/diagnosis/plan-quality-20260928 \
    --manifest evaluation/diagnosis/manifest-v1.json \
    --repos-root .local/diagnosis/checkouts-20260927 \
    --out-dir .local/diagnosis/quality-bug-one-call-20260928 \
    --case-id requests-6628-bug --repeats 1 --max-calls 1 \
    --allow-network
  ```

- [ ] Record status, hashes, safe error category, usage, and elapsed time.
  If the response is usable, review every accepted claim against the pinned
  buggy source and fix commit `382fc2c0c6c0ef0874bc65bc1175f97c073e5086`.
  Compare only if the per-case transmitted payload hashes match the previous
  audit and the prompt, model, thinking mode, and response schema stayed fixed.

**Acceptance:** One recorded call and an explicit primary-reviewed outcome
for the known `__reduce__` defect, or one recorded failure with its exact
limit. **Stop:** Invalid content, truncation, provider failure, checkout
drift, or payload-hash drift. Do not silently make a second call.

## Task 4 — Run the frozen ten-case baseline only after Task 3 succeeds

**Question:** Across all ten preselected cases, how often are findings
source-supported and correct after primary source review?

- [ ] Use the same clean analyzer commit and frozen plan from Task 3. Confirm
  all ten context and request hashes, the 120-line/64-KiB source limits, the
  256-KiB wire cap, and a fresh output directory.
- [ ] Run the existing sequential runner with no `--case-id`:

  ```bash
  python3 -m tools.evaluate_diagnosis run \
    --plan-dir .local/diagnosis/plan-quality-20260928 \
    --manifest evaluation/diagnosis/manifest-v1.json \
    --repos-root .local/diagnosis/checkouts-20260927 \
    --out-dir .local/diagnosis/quality-ten-cases-20260928 \
    --repeats 1 --max-calls 10 --allow-network
  ```

  One provider failure stops the run; leave its remaining calls unattempted.
- [ ] For each completed finding, record TP, FP, uncertain, or duplicate
  against the pinned source and documented fix/control contract. Keep
  evidence rejection distinct from human correctness review. Generate the
  existing review template, fill every `verdict`, `rationale`, `reviewer`,
  issue match, and duplicate pointer required by the schema, and score only
  after the review rows are complete:

  ```bash
  python3 -m tools.evaluate_diagnosis prepare-review \
    --run-dir .local/diagnosis/quality-ten-cases-20260928 \
    --out-file .local/diagnosis/quality-ten-cases-20260928/review-primary.json
  python3 -m tools.evaluate_diagnosis score \
    --manifest evaluation/diagnosis/manifest-v1.json \
    --run-dir .local/diagnosis/quality-ten-cases-20260928 \
    --review .local/diagnosis/quality-ten-cases-20260928/review-primary.json \
    --json-out .local/diagnosis/quality-ten-cases-20260928/report.json \
    --markdown-out .local/diagnosis/quality-ten-cases-20260928/report.md
  ```

  Label the review as primary-agent review until independently checked.
- [ ] Report completed, failed, unresolved, and unattempted calls separately;
  show token usage without equating it to billed dollars. If partial, say
  exactly which conditional metrics are defined and do not present an
  end-to-end quality estimate as if all ten returned.

**Acceptance:** A provenance-linked review and score for a complete run, or
an honest partial-run report. **Stop:** A provider error, unexpectedly changed
case input, or a finding whose truth cannot be established from source.

## Task 5 — Choose one evidence-led product change

- [ ] If Task 3 again returns `invalid_content_json`, investigate the
  provider-format failure using safe metadata and current official API
  documentation. Specify one falsifiable output-format change before coding
  or paying for another call. Keep response bodies and secrets out of reports.
- [ ] If Task 3 succeeds but the full baseline misses confirmed defects or
  repeats false positives, classify each failure as context omission,
  unsupported reasoning, or output-format noncompliance. Propose one
  prompt-or-context change and a frozen before/after comparison; avoid tuning
  solely to Requests #6628.
- [ ] If quality is adequate for the defined scope, publish the current
  limits and seek independently reviewed new cases before broadening product
  features. UI, automatic patches, multi-provider routing, and background
  scanning have no evidence-based priority in this stage.

**Acceptance:** A short decision record naming the evidence, one chosen
change or an explicit hold, and the next measurable outcome.

## Self-review and execution rule

The five tasks cover the current code-risk gap, unpublished branch, unusable
bug response, missing dataset baseline, and next product choice. Each task has
a distinct acceptance question. The primary agent should update
`docs/execution-status.md` after each gate. This plan does not authorize a
bounded executor to decide defect truth, API behavior, release readiness, or
future architecture.
