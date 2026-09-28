# Expanded-context diagnosis smoke — reviewed 2026-09-28

## Question and scope

Would adding source-visible class ancestry and used module import bindings remove
the observed missing-context error, and would it make the known Requests
`JSONDecodeError.__reduce__` defect detectable? Commit
`6791483f9045487285e72aebad2eee7134ce4424` added those context neighbors
while retaining the 120-line source budget. This follow-up used three
separately prepared, single-case requests from the unchanged frozen manifest.
Each run selected one case with one repeat and one maximum call. There were no
automatic retries.

All three used `deepseek-flash`, disabled thinking, the existing system prompt,
finding schema, and 4,096 completion-token limit. The complete ten-case bundle
passed offline preparation and preflight before these calls. Its other seven
cases were not sent. The original ten-case online run remains a separate partial
experiment.

## Reproducibility

- Analyzer commit: `6791483f9045487285e72aebad2eee7134ce4424`.
- Frozen manifest SHA-256: `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
- Offline audit: ignored local file `.local/diagnosis/context-expansion-audit-6791483.json`.
- Prepared plan: ignored local directory `.local/diagnosis/plan-context-expansion-6791483/`.
- Pinned target checkouts: ignored local directory `.local/diagnosis/checkouts-20260927/`. Target code, tests, and dependencies were not executed or installed.

| Case | Target commit | Context SHA-256 | Request SHA-256 | Source lines / bytes | Wire bytes |
| --- | --- | --- | --- | ---: | ---: |
| `requests-6628-bug` | `7a13c041dbef42f9f3feb14110f02626f6892e9a` | `66c7db85bcde18004ab3704a801a5ebcb9f887007e51f30a15e3d3af99750088` | `a72ce12ec9a0797945f52483d81c530bd3a05c58cde524d862d2e884f54226b4` | 83 / 3,350 | 10,100 |
| `requests-6628-fixed` | `382fc2c0c6c0ef0874bc65bc1175f97c073e5086` | `003e4c0be6cbe447f38142f84fde83045b8d85c4cb23dc322fb04dd35d1c5e54` | `ed1af3aa6c6300886a68d68c5acf175e57689d964ee08d127685ab952dd38875` | 93 / 3,799 | 10,877 |
| `requests-control-httpbasicauth` | `6404f345e562d962abe6700a1c357ec1e7e18232` | `28aa48a06c995c9af68fb45acb5e821b56231493137c5856129bcc2acbf6cb2f` | `21138d6a1faa7bfaf7d65f3195fc0809d8c3b1daa4cda6ac5d0924dde812779b` | 49 / 2,018 | 6,796 |

The full wire SHA-256 values are recorded in the audit file. Each selected
context is within the 120-line and 64-KiB source limits, and each serialized
request is within the 256-KiB transport limit.

The new Requests exception contexts contain the `InvalidJSONError` and
`RequestException` class definitions and the local binding for
`CompatJSONDecodeError`. The fixed snapshot also contains the added
`__reduce__` method. The control contains the `basestring` import binding at
`requests/auth.py:20`. These bindings clarify what names refer to; they do not
include every external dependency implementation.

## Online results

| Case | Run state and response | Accepted / rejected | Prompt / completion / total tokens | Elapsed |
| --- | --- | ---: | ---: | ---: |
| Bug snapshot | Partial; `invalid_response` with safe detail `invalid_content_json` | 0 / 0 | 2,711 / 380 / 3,091 | 2.248 s |
| Fixed snapshot | Complete response | 2 / 0 | 2,925 / 493 / 3,418 | 2.246 s |
| HTTP Basic Auth control | Complete response | 0 / 0 | 1,825 / 6 / 1,831 | 0.355 s |

The run records are under
`.local/diagnosis/context-v2-requests-bug-20260927/`,
`.local/diagnosis/context-v2-requests-fixed-20260927/`, and
`.local/diagnosis/context-v2-requests-control-20260927/`. They contain
validated findings and usage metadata, not the raw provider response body or
API key. Usage is a token count, not a billing amount.

## Primary source review

The fixed snapshot's first finding says the constructor should pass
`**kwargs` to the compatibility JSON decoder. The supplied constructor and
`RequestException` contract do not establish that those arguments belong to
the JSON decoder; forwarding request/response arguments as suggested is
unsupported. The second finding says the wrapped decoder error loses its
original exception context. Raising within the `except` block already gives
the new exception an implicit `__context__`. Both are false positives on
primary-agent source review. Passing source-location and quote validation did
not validate either behavioral claim.

The old, narrower control context omitted the `basestring` import line and
yielded a false NameError claim. The new control context includes that
line and this one response returned no findings. That is a useful observation
for the missing-import hypothesis, not a measured false-positive rate or proof
of causation.

The bug snapshot returned no parseable finding payload, so this experiment
cannot say whether the expanded context helps detect the known missing
`__reduce__` dispatch. The safe error detail does not identify why the
provider's content was invalid JSON. No independent human review or dataset
score was performed.

## Engineering evidence and next gate

For the new context code, `py_compile`, manual `context` exports for the bug and
control, the complete offline plan preflight, and `git diff --check` passed.
No fresh unit suite ran after commit `6791483`. The earlier 275-test result
covers the single-case runner before this context change. The previous fixed
and control review is in [the paired report](2026-09-27-paired-control.md).

The [next-stage plan](../superpowers/plans/2026-09-28-diagnosis-quality-next-stage.md)
first protects this context behavior and verifies the unpublished branch. A
single new bug-snapshot call with controlled inputs can then complete the
paired comparison. A broader ten-case run is conditional on a usable response.
