# Execution Status

Updated 2026-09-28. This file is the current project checkpoint; dated reports
below preserve the earlier experiments.

**Active branch/worktree:** `codex/stability-value-v0.2` at
`/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`.
Latest implementation commit: `0eb8361` (offline request preview, SHA-256
pinning, and selected-source freshness checks). The prior evaluation branch
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
| Evaluation | Frozen ten-case diagnosis manifest, offline preparation, one-case and full-plan runners, manual-review template, scoring, reproducible hashes, and offline CI workflow. | The original ten-case online run is partial; no valid ten-case quality score exists. |
| Latest context change | Local class ancestor definitions and used module import bindings may join the selected source blocks within the same line budget. | Focused fixture covers ancestry order, relevant imports, and the shared budget; current branch passed the full offline suite and PR CI. |
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

These exploratory calls use one selected case at a time. They cannot be scored
as dataset coverage, cannot estimate general model quality, and have no
independent human review. The original ten-case run remains partial and
unchanged. Model token usage is recorded where available; actual billing is
not inferred.

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
- Pinned target repository code, tests, and dependencies were not executed or
  installed during these diagnosis experiments. The API key and raw provider
  response bodies were not saved in the evaluation artifacts.

## Next gates

The current stability sequence has completed the offline/local parts of P0:

- `doctor` now checks local readiness by default and optional DeepSeek model
  access only when requested (`7239c4c`, `3900bac`).
- An opt-in Responses JSON Schema diagnosis path was added after a controlled
  single-case comparison (`a11d526`, `b70e446`). See the
  [structured-output report](evaluations/2026-09-28-structured-output.md).
- `diagnose --preview` produces the exact request body without network or Key;
  `--expect-request-sha256` locks a later upload to those bytes. Selected
  source lines are checked before and after the provider call (`0eb8361`).
  The 303-test suite, `compileall`, CLI help, and diff check passed at that
  source state. A reviewer subagent could not finish its independent review
  because of account limits; primary diff and test review was performed.
- Two pinned real repositories produced byte-identical repeat scans with zero
  parse errors and clean worktrees. See the
  [scanner checkpoint](evaluations/2026-09-28-scanner-stability.md).
- The wheel built in an isolated environment and the installed CLI scanned
  and previewed outside the source tree. See the
  [installed CLI checkpoint](evaluations/2026-09-28-wheel-smoke.md). CI for
  the new branch head remains to be checked.

The next evidence gate is a reviewed diagnosis-quality baseline. The one
parseable structured-output sample has only local citation acceptance; its
behavioral claims have not been adjudicated. It does not justify switching the
default or reporting a success rate. Preserve the frozen manifest and prior
partial runs, and use new output directories for subsequent experiments.

The earlier [post-V3 execution plan](superpowers/plans/2026-09-24-post-v3-execution.md),
[handoff audit](evaluations/2026-09-25-handoff-audit.md), and
[hardening report](evaluations/2026-09-25-hardening-offline.md) preserve the
implementation and offline evaluation history. Future agents should not
re-run completed T0–T8 steps to recreate this state.
