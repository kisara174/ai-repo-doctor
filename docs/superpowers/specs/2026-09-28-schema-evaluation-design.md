# JSON Schema diagnosis evaluation design

## Purpose and boundary

Make the existing ten-case, manifest-pinned diagnosis evaluation runnable with
the opt-in DeepSeek Responses JSON Schema path. A run must record which
protocol it used and verify its exact request before network access. This
enables human review of defect claims; it does not make citation acceptance a
truth verdict or change the product's default Chat protocol.

## Plan formats

- Existing Chat plans remain schema version 1, with unchanged fields and
  `request_sha256` calculation. Previously prepared plans and reports remain
  readable. `prepare` defaults to this format.
- `prepare --response-format json-schema` writes a schema version 2 plan with
  `response_format: "json-schema"`. Each case's `request_sha256` is the SHA-256
  of the exact UTF-8 JSON body produced by the production Responses serializer.
  The selected context and its hash keep the version 1 format. No request
  body, key, or model response is saved by preparation.
- Schema plans reject `--thinking-mode`; their wire body already fixes
  `reasoning.effort` to `none`. Unknown formats, incompatible plan versions,
  malformed hashes, changed serializers/prompts/contexts, or oversized bodies
  fail before creating a run directory or calling the provider.

## Execution and reporting

- `run` chooses the Chat or Responses client solely from the validated plan.
  It has no protocol override flag. It rebuilds and compares every case's
  context and request fingerprint, checks the complete plan and pinned clean
  checkouts, then executes sequentially with the existing call cap, single
  case option, safe error metadata, atomic records, and stop-on-first-failure
  behavior. Target repository code and tests are never executed.
- A Responses run includes `response_format: "json-schema"` in `run.json`,
  the review bundle's embedded run, scored JSON, and Markdown. Chat runs keep
  their prior output shape. The plan hash and each record's request hash link
  the run to the prepared protocol; raw responses remain unrecorded.
- Existing evidence validation remains the same. Accepted findings require
  primary source review before TP/FP labels. A single-case smoke cannot be
  scored as a dataset result. A partial run reports failures and unattempted
  cases separately.

## Verification and online gate

Focused tests must show legacy Chat plan hashes unchanged, schema plan wire
hashes matching the production serializer, plan tampering rejected before the
client, correct client selection, no retry, and protocol metadata through
scoring. The full offline suite and installed CLI gate run on the final code.
After a clean commit, prepare into a new ignored directory and compare all
ten selected context hashes with the frozen Chat plan. Only then make one
controlled schema request for `requests-6628-bug`, with the existing source,
request-size, timeout, and output-token limits. Review every accepted claim
against the pinned source before deciding whether to attempt the full ten-case
run. A provider failure stops this checkpoint; there is no automatic retry or
default switch.
