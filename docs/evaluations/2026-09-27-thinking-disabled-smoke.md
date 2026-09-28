# Thinking-disabled single-case experiment — 2026-09-27

## Result

Exactly one request completed successfully for `requests-6628-bug`, without a
retry. It used `thinking: {"type": "disabled"}` and the unchanged compact
prompt, selected context, model ID, JSON schema, and 4,096-token output cap.
Elapsed time was 2.128 seconds. Usage was 1,558 prompt / 498 completion / 2,056
total tokens. Two findings passed local evidence validation; zero were rejected.
The raw provider envelope and API key were not persisted. The evaluation runner
saved validated findings and metadata in its ignored local results directory.

This attempt did not truncate. It supports using disabled thinking for the next
bounded experiment, but one request across two dates does not establish a
universal truncation fix or isolate provider-side changes.

## Provenance and reproduction

- Analyzer: `5de005997b213cb7050ad4503af7f2a0c1dfaa88`.
- Target: Requests `7a13c041dbef42f9f3feb14110f02626f6892e9a`.
- Manifest: `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
- Context: `742c6ef12db73d6e77c725fd3b23fcec40f39d5c5d5e984a7d889d43ab50d7d2`.
- Canonical request: `9cd181621e0ae0282ed994c45242a70dbe0d862e78a5252aaf2f50b9a2335629`.
- Wire body: 6,107 bytes, SHA-256 `9b68ae7ad61d182aa6beaec6f3095b384df58e46fc22bb34367b1413a62c269d`.
- Started UTC: `2026-09-27T09:54:37.359249Z`.
- Requested/returned model ID: `deepseek-flash`.
- Plan: `.local/diagnosis/plan-single-5de0059/`.
- Output: `.local/diagnosis/smoke-thinking-disabled-20260927/`.
- Full prepared-plan hash: `94edd6839b86aab0496f4a4d349ec0840a5367fa9a3265fe05440ddbd49f866f`.

The previous temporary checkout directory was absent. Eight unique pinned
checkouts were restored under `.local/diagnosis/checkouts-20260927/` using the
manifest's exact Git revisions. No target code, tests, or dependencies ran.
All ten prepared contexts passed the existing complete-bundle preflight.
Reconstructing the wire body without the thinking field reproduced attempt 4's
wire hash exactly; adding disabled thinking was the sole request-body change.
The existing process-scoped CA bundle was retained and TLS verification stayed enabled.

The new CLI selection was `run --case-id requests-6628-bug --repeats 1
--max-calls 1 --allow-network`, with the above plan/output, frozen manifest, and
restored repositories. The run records `selected_case_id`; the original ten-case
run and older prepared plans were not modified. Old plans require their recorded
analyzer commit; prepare a new plan when the analyzer checkout changes.

## Primary-agent source review

This is primary-agent review, not independent human review. The two pending rows
are preserved in `review-template.json`; judgments are in `review-primary.json`.

| Finding | Judgment | Evidence |
| --- | --- | --- |
| Constructor does not forward kwargs to JSON parent | Uncertain / insufficient support | No supported keyword-construction contract or failing call was established. RequestException explicitly consumes request/response kwargs. Forwarding all kwargs to the JSON parent is not justified. |
| Passing self.args duplicates positional arguments | False positive | The standard JSON decoder stores one formatted message in self.args; giving that tuple to OSError preserves it. The paired fix leaves these constructor calls unchanged. |

Neither finding identifies the known missing `__reduce__` dispatch or its
pickling/unpickling consequence. The paired repair at
`382fc2c0c6c0ef0874bc65bc1175f97c073e5086` adds exactly that dispatch. The model
received only JSONDecodeError and Response.json source blocks, not the full
ancestor implementations. This limits what the submitted evidence can prove.

Local evidence acceptance checks location, quote, schema, and submitted scope;
it does not prove a causal defect. One quote was 439 characters, exceeding the
prompt's 240-character guidance. That guidance is not a validator-enforced
constraint today. This should be reported as output noncompliance, not concealed
by labeling the whole diagnosis correct.

No dataset score was generated. The single-case CLI result is explicitly
rejected by `score` to prevent a smoke from being presented as dataset coverage.
Usage is not a billing amount. One missed known defect does not estimate general
model quality.

## Verification and next work

The single-case entry point passed 275 offline tests, compileall, run CLI help,
and git diff checks. Tests cover exact one-case selection, complete-bundle
validation, unknown IDs, repeat restrictions, no retries, and score rejection.

Next, run the paired fixed snapshot and a control with the same prompt/mode,
review findings against their sources, and inspect whether missing ancestor
context explains the missed serialization defect before altering the prompt or
context builder. Keep those exploratory runs separate from the frozen dataset
score. A ten-case run remains a distinct experiment.
