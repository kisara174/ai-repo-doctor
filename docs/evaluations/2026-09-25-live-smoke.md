# DeepSeek single-sample online attempts — 2026-09-25

## Latest result

The fourth user-authorized smoke sent exactly one request for `requests-6628-bug`, using the final compact-output prompt revision. The API response envelope was readable, but the completion ended with `finish_reason=length` at the client's 4,096-token output limit. The client recorded `invalid_response` with safe detail `truncated` and usage of 1,583 prompt, 4,096 completion, and 5,679 total tokens. Elapsed time was 17.361 seconds.

The final prompt's visible-output bounds did not prevent this one request from reaching the token limit. This result does not establish why it happened or measure the prompt revision's general effectiveness. There is no valid diagnosis payload, no findings, no manual review rows, and no model-quality evidence. Usage is not a billing amount; no charge is inferred. The raw provider response and API key were not stored. There was no retry. After the provider call, local review-template generation initially failed because `repeat_index` was missing; the local artifacts were repaired offline and the API was not called again.

## Captured exact-payload attempts

The first three attempts below used the same 5,594-byte frozen wire body, model, target commit, context hash, canonical request hash, and no-retry behavior. Attempt 4 used the final compact-output prompt and therefore has a different canonical request hash and wire body. Each row represents one actual provider request.

| Started (UTC) | Analyzer commit | Result | Usage | Elapsed |
| --- | --- | --- | --- | ---: |
| 2026-09-25 03:53:14 | `9a77fa6` | `provider_error` / `connection`; no HTTP status or usage | unavailable | 0.021 s |
| 2026-09-25 04:55:39 | `9a77fa6` | `invalid_response`; the client did not yet preserve a safe detail or usage | unavailable in the saved record | 15.981 s |
| 2026-09-25 05:17:26 | `f5ecae3ab0ef50c4eba1f48d01155220a5de8d3d` | `invalid_response` / `truncated` | 1,483 / 4,096 / 5,579 tokens | 17.040 s |
| 2026-09-25 05:55:41 | `1eb28b79879db2718bd620888a5a0f3ce11d40a2` | `invalid_response` / `truncated` | 1,583 / 4,096 / 5,679 tokens | 17.361 s |

Local attempt artifacts, excluding raw provider content, are in ignored paths:

- `.local/diagnosis/m06-online-requests-6628-9a77fa6/`
- `.local/diagnosis/m06-online-requests-6628-attempt2-9a77fa6/`
- `.local/diagnosis/m06-online-requests-6628-attempt3-f5ecae3/`
- `.local/diagnosis/m06-online-requests-6628-attempt4-1eb28b7/`

The third and fourth artifacts contain `attempt.json`, `result.json`, `report.md`, and an empty `review-template.json`. The persisted results have no response payload or response body.

## Attempt 3 frozen-request audit

- Sample: manifest case `requests-6628-bug`.
- Target: Requests commit `7a13c041dbef42f9f3feb14110f02626f6892e9a`, checkout `requests-7a13c041dbef`.
- Symbol: `src/requests/exceptions.py::JSONDecodeError`.
- Analyzer for attempt 3: clean commit `f5ecae3ab0ef50c4eba1f48d01155220a5de8d3d`.
- Context SHA-256: `742c6ef12db73d6e77c725fd3b23fcec40f39d5c5d5e984a7d889d43ab50d7d2`.
- Canonical request SHA-256: `1d4f44fcf85af62c9dae49bc341302a7c250059b64a1be6af13cabd5026519a1`.
- Wire body: 5,594 bytes; SHA-256 `319afcb1be294ef3f976ab6d34a04c8497483ff3d076bf25db5b74877577faa7`.

Before attempt 3, the frozen payload was reconstructed from the pinned checkout. Its selected source blocks and call sites matched the reviewed context. The analyzer adds V2-derived context metadata; those derived fields were excluded from the frozen prompt. The exact serialized request bytes matched the earlier reviewed body. The prompt contains only the diagnostic instructions and allowlisted `symbol`, `blocks`, and `call_evidence`; it excludes issue labels, ground truth, credentials, and local absolute paths.

TLS was verified through the configured loopback proxy using the process-scoped Homebrew CA bundle at `/opt/homebrew/etc/openssl@3/cert.pem`. No global trust or proxy settings were changed.

## Attempt 4 final-prompt audit

- Started at: `2026-09-25T05:55:41.803462Z`.
- Analyzer checkout commit: `1eb28b79879db2718bd620888a5a0f3ce11d40a2`; analyzer code commit: `7e563c18222d400653f099020306ec49881ff584`.
- Target: Requests commit `7a13c041dbef42f9f3feb14110f02626f6892e9a`, checkout `requests-7a13c041dbef`.
- Context SHA-256: `742c6ef12db73d6e77c725fd3b23fcec40f39d5c5d5e984a7d889d43ab50d7d2` (same selected sample context as attempt 3).
- Canonical request SHA-256: `a2beca725fdf56513bddd1d69b1668101c4a2c88563d6e3634e181946487f900`.
- Wire body: 6,073 bytes; SHA-256 `1cf6c6d990e4dc80b871abbf39971b2a8ca4867c7faaaf5fe440f62e11e98840`.
- The final prepared plan and request fingerprints were checked offline before sending the single selected case. The prompt retained the allowlisted context fields and used the field-length and finding-count bounds described below. No raw request or provider response body was persisted.

## Earlier unpinned CLI smoke

An earlier CLI smoke, recorded in the first version of this note, selected Requests checkout `0b401c76b6e80a4eecf3c690085b2553f6e261ca` instead of the manifest-pinned snapshot. That request was 6,620 bytes with SHA-256 `4b0d2f67be93a44051d6ba0c875d709722a79ed6cac116f0a0af129731e32faf`; it returned a connection error and produced no usable response or usage. It is separate from the four pinned-checkout attempts above and is not used as diagnosis evidence.

## Next step

Keep the ten-case T7 run and its frozen payloads unchanged. The final offline prompt revision asks for at most three findings, two evidence items per finding, exact evidence quotes up to 240 characters, titles up to 120 characters, categories up to 40 characters, and reasoning/impact/suggested-fix fields up to 240 characters each. The existing JSON fields, validator, `max_tokens=4096`, and thinking parameters are unchanged. The fourth smoke still truncated, so these bounds have not been shown to prevent truncation.

The current client and offline planner do not represent a thinking-mode setting. Before a trial, add an explicit opt-in `thinking` field to request serialization and request fingerprinting while preserving the current default request body, then test those offline. The next discriminating experiment is one separately prepared and fingerprinted request for the same sample that changes only the thinking mode, for example by setting `{"thinking": {"type": "disabled"}}`. DeepSeek's [Chat Completions API documentation](https://api-docs.deepseek.com/api/create-chat-completion/) says thinking is enabled by default, `reasoning_effort` defaults to `high`, and `max_tokens` limits generated tokens. This makes the thinking setting a testable hypothesis, not an established cause of these truncations. Keep the sample, final prompt, schema, and `max_tokens` fixed; generate and inspect new request hashes that include the changed parameter. Do not reuse an earlier plan or request hash. No request with thinking disabled has been sent. Until a complete response passes local validation and manual review, do not score this single sample or make model-quality claims.

An intermediate local plan was generated before the final per-field character limits were added. It is superseded and must not be used for a provider run; regenerate from the final committed prompt revision.
