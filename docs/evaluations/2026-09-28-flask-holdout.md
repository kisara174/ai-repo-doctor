# Flask holdout diagnosis comparison

Date: 2026-09-28. This is a six-case, purposively selected Flask experiment
with primary-agent review. It does not estimate general diagnostic accuracy.
The [design](../superpowers/specs/2026-09-28-flask-holdout-design.md) fixed the
one prompt edit and its decision rule before any holdout model result was read.

## Fixed inputs

- Dataset: `diagnosis-flask-holdout-v1`, three upstream bug/fixed pairs from
  [Flask #4170](https://github.com/pallets/flask/issues/4170),
  [#5391](https://github.com/pallets/flask/issues/5391), and
  [#5786](https://github.com/pallets/flask/issues/5786). Their fixed merge
  commits and first-parent bug commits are pinned in
  [the manifest](../../evaluation/diagnosis/flask-holdout-v1.json). Manifest
  byte SHA-256: `68aeaa16e4b0e400de800ea5f192c2c22c467eda8132e0e7dad7d08620333cd2`.
  The prior Click/Requests manifest stayed at
  `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
- Baseline analyzer commit: `14da7b4cb4349247e258af1ae7c15573a0cd4b09`.
  Baseline plan's canonical SHA-256, which is recorded in its run:
  `a334ea084d7ef2d13a4a913c64cb92a28e7ff866a460a7c779ff9f8e6ae6a312`.
- Prompt-variant analyzer commit: `c206da6d8e30042498b4635cc956c33d3b1ea83c`.
  Variant plan's canonical SHA-256:
  `38b23e1a3fb38d8b2fb818e5c7f764221c99888b54cf56f122f49115c537aac2`.
  All six context files and context SHA-256 values were identical between
  arms. Reconstructed serialized request hashes matched both plans; each
  request changed only by the exact two preregistered system-prompt sentences.
  The largest baseline request was 12,203 bytes and the variant added 239
  bytes. The largest selected source context was 120 lines and 4,635 bytes.
- Both arms requested `deepseek-flash` through Responses `json_schema`, with
  `reasoning.effort=none`, 4,096 output tokens, the same evidence gate, and
  one call per case. No Flask code, tests, or dependencies were executed.
  The API key and raw provider responses were not saved in tracked files or
  printed here.

## Current-prompt baseline

All six requests completed with parseable findings; none had a provider
error. The local evidence gate accepted eight findings and rejected zero.
It proves that their selected quotations are present, not that the claims
are true. The primary agent reviewed every finding against pinned source and
the upstream fix; no independent second review was performed.

| Case | Primary verdict | Source-based reason |
| --- | --- | --- |
| `flask-4170-bug` | Accepted 0: FP | Claimed surprising mutation of a supplied args list, without a demonstrated failing caller or the sole-`**kwargs` positional argument defect. |
| `flask-4170-fixed` | Accepted 0–1: FP | Both factory discovery paths guard with `inspect.isfunction`; a missing warning `stacklevel` is not a selected-contract failure. |
| `flask-5391-bug` | No findings | Missed the Python-before-3.12 `super()` comprehension failure. |
| `flask-5391-fixed` | Accepted 0: FP | Explicitly described the bound `super().convert` pattern as valid and proposed no needed change. |
| `flask-5786-bug` | Accepted 0: uncertain; accepted 1: FP | An exception-path context leak was not established; `_copy_environ({})` does merge the client defaults. Neither finding identified reversed context restoration. |
| `flask-5786-fixed` | Accepted 0: uncertain; accepted 1: FP | Nested mutable environ sharing was not shown to violate a contract; `preserve_context` is intentionally enabled by `with client`. |

| Measure | Baseline | Meaning |
| --- | ---: | --- |
| Known bug detection | 0/3 | No accepted, primary-reviewed match among the three bug cases. |
| Precision among adjudicated accepted findings | 0/6 | Six FPs; two accepted findings remain uncertain and are excluded. |
| Citation grounding | 8/8 | Exact source validation only. |
| Fixed-case false alarms | 3/3 | Every repaired snapshot had at least one accepted FP. |
| Uncertain findings | 2/8 | Separate, unverified concerns. |

Observed usage: 13,400 prompt tokens and 1,848 completion tokens, 15,248
total. These are provider-reported counts, not a billing estimate. The
ignored local run, review, and score are under
`.local/diagnosis/holdout-run-baseline-20260928/`.

The `flask-5391-bug` request supplied only seven source lines: the selected
method body and two import lines. It did not supply the enclosing class header
or supported Python versions. This is an observed context limitation that
may affect diagnosability; one missed result cannot establish its cause.

## Preregistered prompt-variant run

The first of six requests, `flask-4170-bug`, returned an `invalid_response`
record with safe detail `invalid_content_json`. Its provider-reported usage
was 3,325 prompt and 282 completion tokens, 3,607 total. No usable finding
was published. The runner stopped as designed: five requests were unattempted,
and there was no retry or scored variant dataset. The safe metadata does not
establish why the content was invalid.

The preregistered decision rule required two complete arms. It was not met,
so the prompt edit was reverted in commit `d66ec4c`. The production prompt is
byte-identical to the baseline commit. This experiment cannot show whether
the edit helps or hurts diagnostic quality.

## Product decision

Keep the existing prompt and JSON Schema opt-in. The new baseline independently
reinforces the practical gap between quotation grounding and useful defect
detection, but the single-repository, primary-reviewed sample is too small for
a release-quality claim. A next experiment should first distinguish malformed
provider output from truncation using safe, non-content metadata, then test a
context-completeness change on further unseen cases. Do not tune only against
these now-visible Flask examples, and do not pool them with the Click/Requests
ten-case run.
