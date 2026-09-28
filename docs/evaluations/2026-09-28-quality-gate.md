# Diagnosis quality gate — 2026-09-28

## Fixed input and one-call result

The frozen ten-case manifest has SHA-256
`f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
The new offline plan at `.local/diagnosis/plan-quality-20260928/` was prepared
under analyzer commit `05b5bc94af2d5fd999740892db8021f19dbb4248`.
All ten pinned target checkouts passed preparation. The plan uses
`deepseek-flash`, disabled thinking, the existing prompt and response schema,
4,096 maximum completion tokens, and a 120-line source limit.

For `requests-6628-bug`, `requests-6628-fixed`, and
`requests-control-httpbasicauth`, the new context, request, and serialized
wire SHA-256 values all equal the [previous audited values](2026-09-28-context-expansion.md).
The selected bug request contains 83 source lines / 3,350 source bytes and is
10,100 bytes on the wire. The comparison therefore changed the analyzer commit
identifier only; it did not change the provider input for these cases.

The one permitted `requests-6628-bug` request began at
`2026-09-28T10:56:37.838957Z` and returned `provider_error` with safe code
`connection` after 0.163 seconds. It produced no provider response model,
accepted finding, rejected finding, or token usage. The one-case run is
`partial`, with 1 attempted call out of 1 planned. Its local record is
`.local/diagnosis/quality-bug-one-call-20260928/`; the plan SHA-256 is
`d6220919ec4636bb1ce8d477022ab9174865d31d2d3f5e5df9df0f354cbc2a7e`.
The API key and raw provider response were not written to this report or run.
No automatic retry occurred.

## Review and decision

This connection failure does not test whether expanded context detects the
known Requests `JSONDecodeError.__reduce__` defect. It also cannot confirm or
disprove the earlier `invalid_content_json` response. There is no new
finding to review against source. Under the plan's stop rule, the ten-case
online run was not started; its ten calls remain unattempted, so no dataset
quality score is available.

**Product decision: hold prompt and context changes.** The input hashes are
stable, and the observed failure occurred before any model content was
available. A prompt or context edit has no evidence-based target here. The
next measurable gate is to confirm provider connectivity, prepare a fresh
versioned checkpoint, and obtain one usable bug response before committing
to the ten-case run. That future call needs its own explicit bounded record;
this checkpoint's one-call limit is exhausted. The local CLI and wheel
installation are assessed separately from model diagnosis quality.
