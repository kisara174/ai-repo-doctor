# Werkzeug diagnosis holdout baseline

Date: 2026-09-29. The [preregistered design](../superpowers/specs/2026-09-29-werkzeug-holdout-design.md)
fixed six cases, one current-product arm, and a decision threshold before any
model output was read. This is a purposive, single-repository sample with
primary-agent review only. It cannot estimate general diagnostic accuracy.

## Frozen run

- Dataset: `diagnosis-werkzeug-holdout-v1`, three upstream bug/fixed pairs from
  [Werkzeug #2842](https://github.com/pallets/werkzeug/issues/2842),
  [#2985](https://github.com/pallets/werkzeug/issues/2985), and
  [#2994](https://github.com/pallets/werkzeug/issues/2994). Their commits,
  target source SHA-256 values, and narrow ground truth are in
  [the manifest](../../evaluation/diagnosis/werkzeug-holdout-v1.json). Its
  byte SHA-256 is `09c42643a0e21f5468882c562c7326c2f731c9f0d3c3e9b00cec9bf3fe0d7bda`.
- Analyzer commit: `a9155dea9f89504966e7ac4eb3c8c0d33f85381b`.
  Canonical plan SHA-256: `5a5b49a368da68d56245d6a3b2c6cb3f40261b8807456629c10c0aa4974d8609`.
  All six source fingerprints, context SHA-256 values, and independently
  rebuilt serialized request SHA-256 values matched the frozen plan before
  dispatch. The largest request was 5,636 bytes; source selections ranged
  from 9 to 36 lines and 339 to 1,409 source bytes.
- Six sequential requests used `deepseek-flash`, Responses `json_schema`,
  `reasoning.effort=none`, 4,096 maximum output tokens, one call per case,
  and no retry. All six returned parseable findings. The local evidence gate
  accepted eight and rejected none. It checks quotations, not behavior.
  The key and raw provider response bodies were not saved in the evaluation
  artifacts; target repository code, tests, and dependencies were not run.

## Primary source review

| Case | Verdict | Source-based reason |
| --- | --- | --- |
| `werkzeug-2843-bug` | Accepted 0: TP | It identified `int(None)` raising an uncaught `TypeError` instead of returning the `get` default. [PR #2843](https://github.com/pallets/werkzeug/pull/2843) adds exactly that catch and a regression check. |
| `werkzeug-2843-fixed` | Accepted 0–1: FP | Missing keys from the pinned `MultiDict.__getitem__` raise a `KeyError` subclass, which `get` catches. The selected fixed docstring already names both `ValueError` and `TypeError`; the second finding overlooked it. |
| `werkzeug-2985-bug` | No findings | It missed the header block containing only the final CRLF when inherited `Headers.__str__` reads `_list` on a populated `EnvironHeaders`. The selected nine-line context omitted the subclass implementation; this is a plausible context cause, not a proven explanation of the miss. |
| `werkzeug-2985-fixed` | No findings | No false alarm on the repaired `to_wsgi_list()` path. |
| `werkzeug-2994-bug` | Accepted 0: uncertain; 1: FP; 2: uncertain | Empty collection key retention lacks an established contract here; treating strings as scalar values is intentional. The broad `Collection` annotation may be a separate type concern, but that finding never named bytes input or integer-splitting output. The known bytes defect was missed despite its branch being selected. |
| `werkzeug-2994-fixed` | Accepted 0: uncertain; 1: FP | Whether an explicit empty sequence should retain a key was not established. The claimed unreachable `continue` is demonstrably reachable, and the finding's own reasoning acknowledged that. |

The review records and scorer output are retained under the ignored local
`.local/diagnosis/werkzeug-run-20260929/` directory. There was no independent
second adjudicator. Uncertain rows are excluded from adjudicated precision,
and a fixed case is negative only for its paired repaired contract.

| Measure | Result | Meaning |
| --- | ---: | --- |
| Completed requests | 6/6 | No provider or format failure in this run. |
| Known bug detection | 1/3 | Only the TypeError case matched a preregistered defect. |
| Precision among adjudicated accepted findings | 1/5 | One TP and four FP; three uncertain rows excluded. |
| Citation grounding | 8/8 | Exact local source evidence only. |
| Fixed-case false alarms | 2/3 | The #2843 and #2994 fixed cases had an accepted FP. |
| Uncertain findings | 3/8 | No validated defect claim from those rows. |

Provider-reported usage was 7,913 prompt tokens and 1,818 completion tokens,
9,731 total. These are observed token counts, not a billing estimate. The
median request duration was 2.648 seconds for these six calls.

## Decision

The preregistered gate required at least two detected bug cases, at most one
fixed-case false alarm, six parseable responses, and later independent review.
Only the parseability condition was met. Keep optional cloud diagnosis
explicitly experimental; do not promote its findings to verified bugs or
switch the default protocol. The #2985 miss points to missing subclass
context, while #2994 shows a reasoning miss with the relevant constructor
branch already present. A next change should address one independently
measurable failure mode and be judged on further unseen cases, not on a
rerun of this visible cohort. The three existing cohorts should not be
pooled into a representative accuracy estimate.
