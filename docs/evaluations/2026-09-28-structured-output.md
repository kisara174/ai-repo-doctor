# Structured output comparison — 2026-09-28

## Fixed input and method

The comparison used frozen case `requests-6628-bug` from manifest SHA-256
`f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
The analyzer checkout was clean at `3900bac9060987f6234ecc482d4b1edfc44d2b5a`.
All ten prepared context and Chat request hashes matched the previous audited
plan. The selected context hash was
`66c7db85bcde18004ab3704a801a5ebcb9f887007e51f30a15e3d3af99750088`:
83 source lines, 3,350 source bytes. Model `deepseek-flash`, the system/user
prompts, disabled thinking, the selected target, and the 4,096 output-token
limit were held fixed. The API protocol and requested output format differed.

The Chat arm used `/chat/completions` with `response_format=json_object`. Its
prepared request hash was
`a72ce12ec9a0797945f52483d81c530bd3a05c58cde524d862d2e884f54226b4`.
The Responses arm used `/responses` with `text.format=json_schema`, name
`repo_doctor_findings`, and the finding schema now recorded in
`repo_doctor/diagnosis.py`. It sent the same prompt strings as two input
messages, set `reasoning.effort=none`, `stream=false`, `store=false`, and
`max_output_tokens=4096`. Its schema hash was
`f3358dccfe66d97c6a3667692c8f01e5bc8f29ab190653c7a5ca87de4030a40a`;
both Responses attempts had the same 10,947-byte wire body with SHA-256
`77ad9764b601ab4d3885bd0f8f33a48b890367e042fb798be82190573140b32a`.
No automatic retry occurred. The local Python 3.14 installation needed the
trusted system CA bundle at `/etc/ssl/cert.pem` to establish TLS; certificate
verification remained enabled.

## Observed outcomes

| Arm | Calls | Provider status | Local result | Token usage |
| --- | ---: | --- | --- | --- |
| Chat JSON | 1 | HTTP completion | `invalid_content_json` | 2,711 prompt / 410 completion |
| Responses JSON Schema, first probe | 1 | `completed` | `invalid_response`; the first probe did not record a safe subcategory | 2,927 input / 341 output |
| Responses JSON Schema, instrumented probe | 1 | `completed` | Parsed finding object; 2 locally accepted, 0 rejected | 2,927 input / 473 output |

The instrumented Responses probe recorded exactly one `output_text` part of
1,825 characters. It did not save or print the raw provider response. Local
acceptance means its citations matched the source and submitted context; the
two behavioral claims have **not** been independently reviewed or scored.
The first Responses failure cannot be classified further from the saved safe
metadata. These three calls do not estimate a population success rate. The
Chat failure also repeated an earlier `invalid_content_json` on the same
prompt and context hash, but the earlier attempt belongs to a separate
checkpoint.

Local records are under ignored `.local/diagnosis/format-chat-one-20260928-3900bac/`,
`.local/diagnosis/format-responses-one-20260928-3900bac/`, and
`.local/diagnosis/format-responses-detail-20260928-3900bac/`. The report keeps
only hashes, status, counts, and usage; it contains no API key or raw model
response.

## Product decision

Offer Responses JSON Schema through an explicit `diagnose --response-format
json-schema` option while keeping Chat JSON as the default. Both paths retain
the same source budget, preflight notice, local evidence validation, and one
request without retry. The successful probe establishes that the alternative
can produce a parseable payload, but the first failure prevents a stability
claim. The frozen ten-case evaluation runner remains on its existing Chat
protocol; a Responses baseline requires its own prepared request fingerprints
and human claim review before any quality comparison or default change.

DeepSeek's [Chat API](https://api-docs.deepseek.com/api/create-chat-completion/)
documents `json_object` for Chat output. Its
[Responses API](https://api-docs.deepseek.com/api/create-response/) documents
`text.format=json_schema`; the [JSON Output guide](https://api-docs.deepseek.com/guides/json_mode/)
warns that JSON mode may occasionally return empty content. These docs support
trying the alternative; they do not establish its reliability for this task.
