# Symptom-Guided Diagnosis Evaluation

**Date:** 2026-09-29
**Dataset:** `diagnosis-symptom-guided-v1`
**Outcome:** Partial run; preregistered usefulness signal not met.

## Scope and frozen cohort

This experiment compared the existing blind diagnosis prompt with an evaluator-only prompt that also supplied a user-reported symptom. It covered two paired Python repairs: pytest issue `pytest-dev/pytest#12083` and Rich issue `Textualize/rich#3897`. Each repair had a bug and fixed snapshot in each prompt arm. The sample was deliberately small and selected for this evaluation; it is not representative of general repositories.

The product diagnosis prompt and CLI were not changed. Source snapshots were inspected statically from the frozen manifest; upstream code, tests, and dependencies were not run.

- Manifest SHA-256: `a6cebc451a6fdb38447a1927f03ba400b4e2c6d800a1d1bdd727f1c9ceebcf89`
- Prepared plan SHA-256: `57178b1212d1ed50ce17102aa61c08420ef45886527b40616159d4502b08082e`
- Analyzer commit: `f24e90f6079cc44ad00174c9a00f46a6142b3ceb`
- Requested and returned model: `deepseek-flash`
- Response format: Responses API `json-schema`

## Run outcome

The DeepSeek readiness check reported ready, and the bounded sequential run was started once with two repeats and a 16-call maximum. It stopped on call 14, `rich-3897-blind-fixed`, repeat 2, after an `invalid_content_json` response. The run preserved that failure and sent no retries. The final two symptom-arm calls were not sent.

| Result | Count |
| --- | ---: |
| Planned calls | 16 |
| Attempted and recorded calls | 14 |
| Successful parseable responses | 13 |
| Invalid responses | 1 |
| Not attempted after stop | 2 |
| State | `partial` |

All 14 recorded calls included provider usage: 55,669 prompt tokens and 6,427 completion tokens (62,096 total). These are observed token counts, not a billing estimate. The request omitted temperature, top-p, and seed, so repeats are not deterministic replays. No API key or raw provider response body is included in the tracked report.

## Manual source review

All 22 parsed findings were checked against the pinned source and the paired issue behavior. The review marked 3 accepted true positives, 12 accepted false positives, 1 rejected false positive, and 6 uncertain findings. Among accepted findings, precision excluding uncertain findings was 3/15 (20%). Exact source-context grounding was 21/22; grounding confirms citation provenance only, not behavioral correctness.

| Repair and arm | Bug snapshot | Fixed snapshot |
| --- | --- | --- |
| pytest, blind | No true positive in either repeat; unrelated or uncertain findings | Accepted false alarms in both successful repeats |
| pytest, symptom-guided | True positive in both repeats | One accepted false alarm in repeat 1; no accepted false alarm in repeat 2, though one false claim was rejected |
| Rich, blind | No true positive in either repeat; unrelated or uncertain findings | Repeat 1 had accepted false alarms; repeat 2 was the invalid response that stopped the run |
| Rich, symptom-guided | True positive in repeat 1; repeat 2 was not attempted | Repeat 1 had an accepted false alarm; repeat 2 was not attempted |

The symptom-guided pytest result repeated consistently. The Rich bug result was positive only in the one attempted symptom-guided repeat. The symptom-guided fixed snapshots produced two accepted false alarms in repeat 1, so the zero-false-alarm condition failed.

## Preregistered usefulness signal

The signal required all 16 calls to parse, at least one symptom-relevant true positive per repair, no symptom-arm fixed false alarms, and more bug detections than blind without more fixed alarms.

- **Complete parseable run:** failed. There were 13 parseable responses, one invalid response, and two unattempted calls.
- **At least one symptom-guided true positive per repair:** observed for both repairs; Rich has only one attempted repeat.
- **Zero symptom-arm fixed false alarms:** failed. Two successful fixed cases had accepted false alarms.
- **More bug detections without more fixed alarms:** incomplete. The observed calls had 3 symptom-guided true-positive bug detections versus 0 blind detections, but two symptom-arm calls were missing, so the full planned comparison cannot be established.

**Overall: the preregistered signal was not met.** The observed gain on bug snapshots came with false alarms on both symptom-guided fixed snapshots in repeat 1, and the run stopped before the paired comparison was complete.

## Limits and next step

This is an exploratory result from two purposively selected repairs and one model configuration. Public issue discussions or fixes may have appeared in training data; bug and fixed snapshots are correlated; and two repeats do not create independent cases. The partial run further limits arm comparison.

Keep symptom guidance evaluation-only. Before changing the product prompt or CLI, create and freeze a genuinely new cohort, then repeat the bounded comparison there. Do not tune against these now-reviewed cases. The partial records, manual review, and machine-readable score remain under the ignored `.local/diagnosis/` directory; the manifest and this redacted report are tracked.
