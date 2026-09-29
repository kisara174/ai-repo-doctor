# Execution Status

Updated 2026-09-29. This file is the current project checkpoint; dated reports
below preserve the earlier experiments.

**Active branch/worktree:** `codex/werkzeug-holdout-v0.5` at
`/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`.
The stability branch was merged in
[PR #8](https://github.com/kisara174/ai-repo-doctor/pull/8) at `5d72890`,
and the separate Flask holdout was merged in
[PR #9](https://github.com/kisara174/ai-repo-doctor/pull/9) at `dbd8a1c`.
The method-owner context change was merged in
[PR #10](https://github.com/kisara174/ai-repo-doctor/pull/10) at `74da767`.
The experimental prompt was reverted before PR #9 merged. The current branch
freezes a third-repository Werkzeug holdout and records one current-product
baseline without changing the prompt; see the
[Werkzeug report](evaluations/2026-09-29-werkzeug-holdout.md).
The prior evaluation branch
was integrated at `86d1022`; its context implementation commit was
`6791483f9045487285e72aebad2eee7134ce4424`. Focused context
coverage was committed at `0ad91c8a456941dda8e7c0f6ebba351d038b6e61`.
Wheel installation instructions and CI acceptance were committed at
`05b5bc94af2d5fd999740892db8021f19dbb4248`. Those changes were reviewed
in [PR #7](https://github.com/kisara174/ai-repo-doctor/pull/7). The original `codex/repo-doctor-v2-design`
checkout has separate untracked V3 documents and was left untouched.

## Delivered capabilities

| Stage | Available now | Evidence and limit |
| --- | --- | --- |
| V1 | Read-only Python repository scan; symbol, import, and static call index; bounded `context`; reverse `impact`; evidence `validate`. | Static relationships are conservative and do not execute target code. |
| V2 | Decorator and overload metadata, explicit local reexports, bounded Click command-registration relationships, and richer static call resolution. | `call_edges` and `semantic_edges` remain distinct. Dynamic dispatch is outside the current precision claim. |
| V3 | Optional, explicit `diagnose` call to DeepSeek with bounded selected source; local finding evidence checks and safe error handling. | Source quotations can be validated without proving the model's behavioral conclusion. No automatic patching. |
| Evaluation | Frozen ten-case diagnosis manifest, separate six-case Flask and Werkzeug holdouts, offline preparation, one-case and full-plan runners, manual-review template, scoring, reproducible hashes, and offline CI workflow. | The original Chat ten-case online run is partial; later JSON Schema runs are complete with primary-only review. |
| Latest context change | Local class ancestor definitions and used module import bindings may join the selected source blocks within the same line budget. | Focused fixture covers ancestry order, relevant imports, and the shared budget; PR #8 passed the full offline suite and CI. |
| Method-owner context | A method target can include its enclosing class declaration as a separate bounded block. | Pinned offline comparisons preserve target lines and existing imports; PR #10 passed local and CI gates. |
| Distribution | The `0.1.0` wheel installs `repo-doctor` in a clean virtual environment; the public repository can serve as a pip source after integration. | Wheel contents and installed `scan`, `context`, `impact`, and `validate` were checked outside the source tree. The evaluation-only `tools` package is intentionally absent from the wheel. |

The original post-V3 plan's T0–T6 implementation and T7 offline preparation
were completed. T7's first ten-case online run stopped after one
`provider_error`; nine calls were unattempted. T8 accurately reported that
partial run. Its frozen manifest SHA-256 remains
`f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
The [original report](evaluations/2026-09-25-diagnosis-v1.md) remains the
record of that run.

## Model-quality evidence so far

- The old-context, disabled-thinking `requests-6628-bug` request returned two
  locally accepted findings. Primary source review marked one uncertain and
  one false positive; neither identified the known missing `__reduce__`
  dispatch. See [single-case report](evaluations/2026-09-27-thinking-disabled-smoke.md).
- The paired old-context fixed and HTTP Basic Auth control requests returned
  three accepted findings in total, all false positives on primary review.
  The control's `basestring` claim appeared when its import binding was
  missing from the supplied context.
  See [paired report](evaluations/2026-09-27-paired-control.md).
- Under expanded context at `6791483`, the bug request returned
  `invalid_content_json` with no usable finding; the fixed request returned
  two false positives on primary review; the control returned zero findings.
  The import line was present in the control context. See
  [expanded-context report](evaluations/2026-09-28-context-expansion.md).
- A new plan under `05b5bc9` reproduced the three audited payloads exactly.
  Its one permitted bug call stopped with `provider_error/connection` before
  model content arrived. The full ten-case run was not started. See
  [quality-gate report](evaluations/2026-09-28-quality-gate.md).
- At analyzer commit `091dc2d`, the opt-in Responses JSON Schema evaluator
  completed a frozen ten-case run. Primary review found one match among four
  known bug cases, seven accepted false positives, six uncertain findings,
  and one rejected false positive. The corrected fixed/control false-alarm
  count is 3/6. See the
  [ten-case baseline](evaluations/2026-09-28-schema-ten-case-baseline.md).
- At analyzer commit `14da7b4`, a new pinned Flask six-case baseline completed
  6/6 calls. Primary review found no match among three known bug cases, six
  accepted false positives, two uncertain findings, and false alarms on all
  three fixed cases. A preregistered prompt variant at `c206da6` stopped
  after its first call returned `invalid_content_json`; five calls were not
  attempted. The prompt was reverted at `d66ec4c`. See the
  [Flask holdout report](evaluations/2026-09-28-flask-holdout.md).
- At analyzer commit `a9155de`, the pinned Werkzeug six-case baseline
  completed 6/6 calls. Primary review found one match among three known bug
  cases, four accepted false positives, three uncertain findings, and fixed
  case false alarms in two of three repaired snapshots. All eight findings
  passed quotation grounding. The preregistered quality gate failed; see the
  [Werkzeug holdout report](evaluations/2026-09-29-werkzeug-holdout.md).

The earlier exploratory calls used one selected case at a time and cannot be
scored as dataset coverage. The original Chat ten-case run remains partial
and unchanged; the new JSON Schema ten-case run is complete and has a primary
review, but no independent second review. The Flask and Werkzeug baselines
also have only primary review and are too small to estimate general model
quality. Model token usage is recorded where available; actual billing is not
inferred.

## Verification scope

- The context test module passed 12 tests at `0ad91c8`. The full offline suite
  passed 276 tests after that change; `compileall` and `git diff --check`
  passed. These checks ran before the documentation/CI-only `05b5bc9` commit.
- At `05b5bc9`, a wheel built successfully and installed with `pip --no-index`
  into a clean Python 3.14 virtual environment outside the source tree.
  Installed CLI help plus offline scan, context, impact, and validation passed.
- PR #7 head `05b5bc94af2d5fd999740892db8021f19dbb4248` passed all Python
  3.11, 3.12, and 3.13 jobs in both push and pull-request CI runs. Each job
  built and smoke-tested the installed wheel. See PR #7 for the CI result on
  its final integration head.
- PR #8 head `2ffd9fe093f1057631ed1d314307e88a5710b441` passed all Python
  3.11, 3.12, and 3.13 jobs in push and pull-request CI. Its local suite
  passed 313 tests; reviewer-found source-encoding mutation was fixed before
  integration.
- PR #9 head `d902aefa54c00c6325477363660783819140a946` passed all Python
  3.11, 3.12, and 3.13 jobs in push and pull-request CI. Its local suite
  passed 314 tests. The prompt variant stopped after one malformed-content
  response and was reverted before integration.
- The method-owner context branch passed 318 local offline tests, `compileall`,
  and `git diff --check` on 2026-09-29. Its two pinned offline sets retained
  all target-method lines and previously selected import bindings; see the
  [comparison](evaluations/2026-09-29-method-owner-context.md).
- PR #10 head `5d7fd59c61805e81323829bceb51a18010bcdf67` passed Python
  3.11, 3.12, and 3.13 in both push and pull-request CI before merging.
- The Werkzeug dataset-ID focused test and all 26 diagnosis-data tests passed
  after the exact allowlist extension. Six clean target checkouts, source
  fingerprints, context budgets, and serialized request hashes were checked
  before the online run. The current branch passed 319 local offline tests and
  `compileall` on 2026-09-29; current-head CI is still pending.
- Pinned target repository code, tests, and dependencies were not executed or
  installed during these diagnosis experiments. The API key and raw provider
  response bodies were not saved in the evaluation artifacts.

## Next gates

The stability sequence completed these P0 and P1 gates:

- `doctor` now checks local readiness by default and optional DeepSeek model
  access only when requested (`7239c4c`, `3900bac`).
- An opt-in Responses JSON Schema diagnosis path was added after a controlled
  single-case comparison (`a11d526`, `b70e446`). See the
  [structured-output report](evaluations/2026-09-28-structured-output.md).
- `diagnose --preview` produces the exact request body without network or Key;
  `--expect-request-sha256` locks a later upload to those bytes. Selected
  source lines are checked before and after the provider call (`0eb8361`).
  The 303-test suite, `compileall`, CLI help, and diff check passed at that
  source state. A subsequent reviewer found the source-encoding edge case
  described above; no other actionable issue was reported.
- Two pinned real repositories produced byte-identical repeat scans with zero
  parse errors and clean worktrees. See the
  [scanner checkpoint](evaluations/2026-09-28-scanner-stability.md).
- The wheel built in an isolated environment and the installed CLI scanned
  and previewed outside the source tree. See the
  [installed CLI checkpoint](evaluations/2026-09-28-wheel-smoke.md).
- JSON Schema preparation, run dispatch, and scoring are implemented at
  `24736c0`, `9bcc18b`, and `091dc2d`. The scorer correction at `420495b`
  has a red/green regression test. The source-encoding regression also failed
  before its fix and passed after it; the full offline suite passed 313 tests,
  along with `compileall` and `git diff --check`. The
  ten-case provider run is pinned to the earlier clean analyzer commit
  `091dc2d`; the corrected score is a later offline derivation from unchanged
  run records and completed primary review.

The provider parser already separates incomplete, missing-content, and
invalid-JSON responses with safe error categories. The method-owner change
removed one observed context omission, but the Werkzeug holdout still missed
two known bugs and failed its preregistered usefulness gate. In particular,
the `Headers.__str__` case did not supply the subclass implementation needed
to recognize the inherited-storage mismatch; the `MultiDict.__init__` case
supplied its relevant branch but the model missed the bytes behavior. Keep
cloud diagnosis experimental. Next, choose one measurable failure mode and
evaluate it on further unseen cases with independent behavioral review. Do
not tune against the now-visible three cohorts or switch the default
protocol. Preserve all frozen manifests and partial run records. The current
branch needs final diff review and current-head CI before integration.

The earlier [post-V3 execution plan](superpowers/plans/2026-09-24-post-v3-execution.md),
[handoff audit](evaluations/2026-09-25-handoff-audit.md), and
[hardening report](evaluations/2026-09-25-hardening-offline.md) preserve the
implementation and offline evaluation history. Future agents should not
re-run completed T0–T8 steps to recreate this state.
