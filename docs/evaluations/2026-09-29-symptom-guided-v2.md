# Symptom-Guided Diagnosis Evaluation V2

- **Date:** 2026-09-29
- **Dataset:** `diagnosis-symptom-guided-v2`
- **Outcome:** Partial run; registered usefulness signal failed.

## Scope and frozen cohort

This evaluation compared the blind diagnosis prompt with the evaluation-only
symptom-guided prompt on four paired Python repairs from four repositories:

| Repair | Upstream reference | Bug commit → fixed commit |
| --- | --- | --- |
| Pydantic | [pydantic/pydantic#13520](https://github.com/pydantic/pydantic/issues/13520) | `a187a654` → `05bc5da8` |
| Jinja | [pallets/jinja#1921](https://github.com/pallets/jinja/issues/1921) | `20be10e5` → `3ef3ba88` |
| Black | [psf/black#4640](https://github.com/psf/black/issues/4640) | `ff094acc` → `88e78334` |
| Typer | [fastapi/typer discussion #1068](https://github.com/fastapi/typer/discussions/1068) | `85ca5b5a` → `4f04666d` |

Each repair had a blind bug/fixed pair and a symptom-guided bug/fixed pair,
for 16 cases total. The symptom text was identical within each paired
bug/fixed sample. Blind and symptom-guided requests used byte-identical source
contexts; their only registered differences were the symptom-guidance
instruction and symptom field. The V2 context builder excluded test-file
blocks and test-origin caller evidence so regression test names did not leak
into the requests.

The product prompt, CLI, findings schema, and provider transport were not
changed for this experiment. Upstream code, tests, and dependencies were not
executed or installed. The pre-dispatch full local suite had 345 passing tests.

- Manifest SHA-256: `e41870376e594aa9a4be1b2a8f3528cd3208d8f68fc2b4a7a9061c38a8daaa81`
- Run-recorded canonical plan-content SHA-256: `bc43e36939cb8aa9e6bbba358a315a3178d755cdf51fd0e898032d6c29e17321`
- Saved `plan.json` raw-byte SHA-256: `568dae50c077bcec012e52e95b8711f14273720488455a2b132805997fa4541e`
- Analyzer commit: `7a145bde9fefea5e300c216c6d64b9032aa4fbeb`
- Requested and returned model: `deepseek-flash`
- Response format: Responses API `json-schema`; reasoning mode `none`
- Context limits: 120 source lines, 64 KiB context, 256 KiB request; maximum 4,096 output tokens
- Repeats: 2; maximum planned calls: 32; sequential dispatch; no retries

The runner records a canonical hash of the plan object in `run.json`; the
separate raw-byte hash above identifies the saved JSON file including its
formatting. Temperature, top-p, and seed were not set, so repeats are not
deterministic replays.

## Run outcome

DeepSeek readiness passed before dispatch. The run stopped on attempt 19,
`pydantic-symptom-bug`, repeat 2, after an invalid JSON response
(`invalid_content_json`). The runner preserved the response status and stopped
without retrying. No later requests were sent.

| Result | Count |
| --- | ---: |
| Planned calls | 32 |
| Attempted and recorded calls | 19 |
| Successful parseable responses | 18 |
| Invalid responses | 1 |
| Unresolved calls | 0 |
| Not attempted after stop | 13 |
| State | `partial` |

Repeat 1 completed all 16 cases. Repeat 2 completed the first two blind
Pydantic cases and then stopped on the invalid symptom-guided Pydantic bug
response. All 19 records contained usage data: 52,081 prompt tokens and 7,879
completion tokens, 59,960 total. These are provider-reported usage counts,
not a billing estimate.

## Manual source review

All 29 findings from successful responses were reviewed against the pinned
source and the paired behavior contract. The review marked 4 true positives,
11 false positives, 14 uncertain findings, and no duplicates. The four true
positives were all in the first symptom-guided repeat, one per repair:

- Pydantic: a `safe_get_annotations` issue affecting field defaults/type
  variable mapping.
- Jinja: a missing `OverflowError` fallback in `do_int`.
- Black: a missing opening-leaf branch in `is_one_sequence_between`.
- Typer: applying Rich rendering to the Fish completion output protocol.

The complete first repeat showed a clear bug-detection difference, with four
symptom-guided detections and none in the blind arm. It also produced accepted
false alarms on fixed snapshots: three symptom-guided false-alarm findings in
two cases (two Jinja findings and one Typer finding), and one blind-arm false
alarm finding on Black. Pydantic's fixed snapshot had no accepted false alarm.

| Repair | Blind bug detections (repeat 1) | Blind fixed false-alarm findings | Symptom bug detections (repeat 1) | Symptom fixed false-alarm findings |
| --- | ---: | ---: | ---: | ---: |
| Pydantic | 0/1 | 0 | 1/1 | 0 |
| Jinja | 0/1 | 0 | 1/1 | 2, in one case |
| Black | 0/1 | 1 | 1/1 | 0 |
| Typer | 0/1 | 0 | 1/1 | 1, in one case |

The repeat-2 Pydantic blind bug and fixed requests both parsed and added no
bug detection or fixed false alarm. The only repeat-2 symptom-guided request
was the invalid response, so the symptom arm has no completed second repeat.

Across all 29 findings, accepted-only precision was 4/14 (28.6%) when
excluding uncertain, duplicate, and rejected findings. In repeat 1 alone, the
scorer reports 4/12 (33.3%). Exact source-context grounding is only a citation
provenance measure; it does not establish behavioral correctness.

## Registered usefulness signal

The preregistered signal required 32 successful parseable calls over two
repeats, at least one symptom-guided true positive for every repair, zero
symptom-guided fixed false alarms, more symptom-guided bug detections than
blind, and no increase in symptom-guided fixed false alarms.

| Check | Result | Evidence |
| --- | --- | --- |
| Complete successful two-repeat run | Failed | 18/32 successful; run stopped at call 19 |
| Symptom-guided detection on every repair | Passed for observed cases | 4/4 repairs detected in repeat 1; repeat 2 incomplete |
| Zero symptom-guided fixed false alarms | Failed | 3 accepted false-alarm findings |
| More symptom-guided bug detections than blind | Passed for observed cases | 4 versus 0 |
| Symptom-guided false alarms no higher than blind | Failed | 3 versus 1 accepted false-alarm findings |

**Overall: the registered signal was not met.** The first complete repeat
suggests symptom guidance helped surface these four selected bugs, but that
gain came with false alarms on fixed code. The stopped second repeat leaves
stability and full paired comparison unestablished.

## Limits and next decision

This is an exploratory evaluation of four purposively selected repairs, one
model configuration, and one complete repeat. Public issue discussions or
fixes may be present in model training data; each bug/fixed pair is correlated;
and repeated calls are not independent repairs. The partial run further
limits the comparison. These results do not establish general product quality
or reliability.

Keep symptom guidance evaluation-only; do not adopt it in the product prompt
from this result. Preserve this cohort as reviewed and do not tune against its
cases. The next useful evaluation should use a fresh held-out cohort and
retain the fixed-snapshot false-alarm checks. Track any provider invalid-JSON
handling work separately so it does not change the frozen comparison or
silently add retries.

The machine-readable score, review annotations, run records, and prepared
contexts remain in the ignored `.local/diagnosis/` tree. No API key or raw
provider response body is included in this tracked report.
