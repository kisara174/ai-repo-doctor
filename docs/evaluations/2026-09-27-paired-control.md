# Paired fixed and control smoke — 2026-09-27

## Result

Two separately prepared single-case runs completed, one request each, with no retries. Both used `deepseek-flash`, the same system prompt, the same disabled-thinking setting, the same response schema, and the same 4,096 completion-token limit. The fixed Requests snapshot returned in 2.922 seconds with 1,772 prompt / 611 completion / 2,383 total tokens. The Requests HTTP Basic Auth control returned in 1.530 seconds with 1,499 prompt / 312 completion / 1,811 total tokens. Both produced complete responses and all three total findings passed local source-location and quote checks; none were rejected.

Primary-agent review marked all three as false positives. The repaired snapshot produced the same unsupported constructor concern as the original buggy snapshot, plus an exception-chaining concern. The control finding claimed `basestring` was undefined. None identified the fixed sample's known `__reduce__` serialization defect. These are two exploratory samples, reviewed by the primary agent; they are not independent review or a dataset score.

## Provenance

- Analyzer commit: `d3822dedc19bd133920c3a2ac3fa525b4ef418dd`.
- Manifest SHA-256: `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.
- Thinking mode: `disabled`.
- Model ID: `deepseek-flash` (requested and returned).
- Fixed target: `requests-6628-fixed`, commit `382fc2c0c6c0ef0874bc65bc1175f97c073e5086`; context SHA-256 `7605f805d5d09df09a5bf7c7cbe5618f3aa96cb21d1326e9ebadaa41dd6e5fe3`; request SHA-256 `a21faf22ef5e1f448a18bc507417a061adc4df92663e80295909fc256da62fea`; wire body 6,884 bytes.
- Control target: `requests-control-httpbasicauth`, commit `6404f345e562d962abe6700a1c357ec1e7e18232`; context SHA-256 `67e4af7e6639dea2943f006ec8548a17350c062cff5ac79c9fc1adf6d5453380`; request SHA-256 `621514de94e4bf83ad46ad4585c81462272278f4c29b4c0a225b35dde977e255`; wire body 5,684 bytes.
- Plan and execution artifacts are ignored local files under `.local/diagnosis/plan-paired-control-d3822de/`, `.local/diagnosis/smoke-requests-fixed-20260927/`, and `.local/diagnosis/smoke-requests-control-20260927/`. They retain validated findings and run metadata, not raw provider response bodies or the API key. Human judgments are in each run's `review-primary.json`.

The plan includes ten frozen cases, but each `run --case-id` selected only the named case, constrained to one repeat and one maximum call. Complete-bundle source preflight ran before each request. These smoke outputs were not scored as a dataset; the CLI explicitly rejects scoring single-case runs. The older ten-case partial run remains unchanged.

## What the outputs show

The paired buggy and fixed contexts both include `JSONDecodeError` and `Response.json`. The buggy context includes `exceptions.py` lines 31–42; the fixed context includes lines 31–52, including the added `__reduce__` method. Neither context includes the definitions of the `InvalidJSONError` and `RequestException(IOError)` ancestors or the imported compatibility `JSONDecodeError` implementation. Understanding why an omitted `__reduce__` resolves to the wrong reducer depends on that inheritance path. The fixed run's prompt did include the repair itself, but the model still repeated the same unsupported constructor concern.

The HTTP Basic Auth control context includes `_basic_auth_str` lines 34–75, where `basestring` is used, but omits the module's line 18 import `from .compat import basestring, str, urlparse`. The model reported a NameError because the required import was outside its supplied context.

This is consistent with a context-retrieval gap, not proof that context omission alone caused every model error. `repo_doctor.context.build_context` currently selects the target, static callees, callers, tests, and Click command-registration neighbors; it does not add class ancestors or local import bindings. Therefore it drops both the inheritance path relevant to the known defect and the import needed to interpret the control. Local evidence validation correctly verified that quotes occur in submitted source, but cannot establish that the claim follows from code outside those snippets.

The prior baseline, fixed case, and control requests all completed with disabled thinking. This small sequence does not establish that the mode generally prevents truncation or compare model quality reliably. It only shows those three requests were complete.

## Proposed next change

Add deterministic, bounded context neighbors for direct class bases and resolvable repository-local import bindings. Preserve current target-first ordering, deduplicate existing neighbors, exclude unresolved third-party imports, and spend from the same line budget. Keep the fixed prompt and validator unchanged for the first experiment. Tests should show the Requests exception context includes its local ancestor chain and compatibility decoder implementation, and that the control includes the `basestring` binding; unrelated imports remain excluded and all additions respect the existing 120-line and 64-KiB limits.

This changes prepared contexts and request fingerprints, so old plans must remain untouched and the paired samples must be freshly prepared for the next experiment. Review the actual context diff before making another provider call.
