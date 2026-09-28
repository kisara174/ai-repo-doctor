# Execution Status

Updated 2026-09-28. This file is the current project checkpoint; dated reports
below preserve the earlier experiments.

**Active branch/worktree:** `codex/diagnosis-evaluation` at
`/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`.
Latest implementation commit: `6791483f9045487285e72aebad2eee7134ce4424`
(class ancestry and used import bindings in bounded contexts). Before this
documentation update, the branch was clean and 13 commits ahead of
`origin/codex/diagnosis-evaluation`. Those commits have not been pushed or
merged. The original `codex/repo-doctor-v2-design` checkout has separate
untracked V3 documents and was left untouched.

## Delivered capabilities

| Stage | Available now | Evidence and limit |
| --- | --- | --- |
| V1 | Read-only Python repository scan; symbol, import, and static call index; bounded `context`; reverse `impact`; evidence `validate`. | Static relationships are conservative and do not execute target code. |
| V2 | Decorator and overload metadata, explicit local reexports, bounded Click command-registration relationships, and richer static call resolution. | `call_edges` and `semantic_edges` remain distinct. Dynamic dispatch is outside the current precision claim. |
| V3 | Optional, explicit `diagnose` call to DeepSeek with bounded selected source; local finding evidence checks and safe error handling. | Source quotations can be validated without proving the model's behavioral conclusion. No automatic patching. |
| Evaluation | Frozen ten-case diagnosis manifest, offline preparation, one-case and full-plan runners, manual-review template, scoring, reproducible hashes, and offline CI workflow. | The original ten-case online run is partial; no valid ten-case quality score exists. |
| Latest context change | Local class ancestor definitions and used module import bindings may join the selected source blocks within the same line budget. | Commit `6791483` has offline/manual checks but no fresh unit suite or PR CI yet. |

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

These exploratory calls use one selected case at a time. They cannot be scored
as dataset coverage, cannot estimate general model quality, and have no
independent human review. The original ten-case run remains partial and
unchanged. Model token usage is recorded; actual billing is not inferred.

## Verification scope

- Before the latest context change, the single-case runner passed 275 offline
  tests, compileall, CLI help, and diff checks. This result applies to its
  then-current commit, not to `6791483`.
- For `6791483`, `py_compile` on the two changed Python modules, manual
  `context` exports for pinned Requests bug/control snapshots, ten-case
  offline plan preparation and validation, and `git diff --check` passed.
  No unit suite ran after this context change.
- PR #6 CI covered head `3492deb7c9971c06da48477f2dff6a8836cf2226`
  on Python 3.11, 3.12, and 3.13. It does not cover the unpublished
  `diagnosis-evaluation` commits. Current-head integration checks and CI are
  a release gate, not evidence already in hand.
- Pinned target repository code, tests, and dependencies were not executed or
  installed during these diagnosis experiments. The API key and raw provider
  response bodies were not saved in the evaluation artifacts.

## Next gates

The [2026-09-28 work plan](superpowers/plans/2026-09-28-diagnosis-quality-next-stage.md)
gives exact scope, order, and stop conditions:

1. Add one focused local fixture to protect ancestor/import selection and the
   shared line budget; run only the relevant test module.
2. Review the unpublished branch once, run the full offline suite as the
   integration gate, then check CI for the actual PR head.
3. Prepare a fresh plan under the committed analyzer SHA and make at most one
   `requests-6628-bug` call with the same prompt/model/mode. Stop on another
   invalid response or input drift.
4. Only after a usable response, run and manually review the frozen ten-case
   baseline. Choose any prompt or context change from classified errors.

The earlier [post-V3 execution plan](superpowers/plans/2026-09-24-post-v3-execution.md),
[handoff audit](evaluations/2026-09-25-handoff-audit.md), and
[hardening report](evaluations/2026-09-25-hardening-offline.md) preserve the
implementation and offline evaluation history. Future agents should not
re-run completed T0–T8 steps to recreate this state.
