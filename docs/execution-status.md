# Execution Status

Plan: `docs/superpowers/plans/2026-09-24-post-v3-execution.md`

Branch / worktree: `codex/diagnosis-evaluation` / `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`

Latest analyzer code commit: `5de005997b213cb7050ad4503af7f2a0c1dfaa88`
(`feat: add bounded single-case diagnosis smoke`). No push or merge was performed.

## Current checkpoint — 2026-09-27

The new `run --case-id` path passed 275 offline tests and sent one authorized
thinking-disabled request for `requests-6628-bug`. It completed in 2.128 seconds,
using 1,558 prompt / 498 completion / 2,056 total tokens. Two findings passed local
evidence checks; neither identified the frozen serialization bug. Primary source
review marked one uncertain and one false positive. No dataset score was made.
The single-case result is refused by the dataset scoring CLI.

See [the experiment report](evaluations/2026-09-27-thinking-disabled-smoke.md) and [the paired fixed/control report](evaluations/2026-09-27-paired-control.md) for hashes and source review. The two follow-up requests both completed; all three newly reviewed findings were false positives. The context omitted exception ancestors and a local import binding, which explains the control NameError claim and is consistent with the missed serialization defect. The ten-case run remains partial. Everything below is the historical September 25 checkpoint, including its then-pending thinking-disabled experiment and historical test counts.

## Phase

T0–T6 are implemented, validated, reviewed, and committed. T7's original offline preparation and prompt review are complete. The original ten-case run remains partial: its first call was `provider_error`, and nine calls were not attempted. A separately authorized single-sample smoke has sent four one-request attempts: the first three used the same frozen Requests payload, while the fourth used the final compact-output prompt revision. The fourth response was truncated at the 4,096-token output limit. It yielded usage metadata but no valid diagnosis payload or quality evidence. The frozen ten-case run and its request fingerprints remain unchanged. An opt-in DeepSeek thinking-mode parameter is now supported across offline preparation, request validation, execution, and scoring; no online request with that mode was sent.

The frozen ten-case manifest is unchanged at SHA-256 `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`. T5 only ran against mocks. T6 provides manual-review templates and deterministic offline scoring. Its two independent-review corrections are included: E2E denominators are calculated per repeat, and completed-call failure rate is `failed_calls / completed_calls`, with unresolved attempts separate.

## Validation

- T6 targeted score/CLI/math suite: 28 passed.
- Full suite: 221 passed.
- `python3 -m compileall -q repo_doctor tools`: passed.
- Main, `prepare-review`, and `score` CLI help: passed.
- `git diff --check`: passed.
- Independent read-only review of both T6 metric corrections: no remaining findings.
- After locally integrating merged PR #6, the combined branch passed 229 tests; focused DeepSeek transport tests passed 15/15. The 5-run baseline/challenge artifacts are preserved under `.local/diagnosis/post-review-pr6-3492deb/`.
- After safe error-detail and failure-usage recording was added: full suite 260 tests passed; `compileall`, evaluation CLI help, staged-diff review, and `git diff --check` passed. These checks were run before the latest online attempt.
- After the final post-truncation prompt revision: targeted diagnosis suite 10 tests passed, including finding-count, evidence-count, and field-length prompt bounds; full suite 261 tests passed; `compileall`, both CLI help commands, and `git diff --check` passed. The full suite prints expected error messages from negative CLI tests while exiting successfully.
- After adding opt-in `thinking_mode` support: full suite 270 tests passed; `compileall`, `python3 -m repo_doctor --help`, `python3 -m tools.evaluate_diagnosis prepare --help`, and `git diff --check` passed. Tests confirm the default wire body remains byte-for-byte unchanged, explicit mode affects the request hash, tampered modes are rejected before client calls, and score reports retain explicit mode metadata. No provider call was made during this change.

## T7 exact offline preparation

- Prepared ten request contexts for `deepseek-flash`, one repeat, at most ten requests, 120 source lines maximum per request, and 4,096 generated tokens maximum per request.
- All ten payloads were inspected. They contain the fixed diagnostic prompt, one case's selected public source, and static call evidence; no ground-truth labels, issue/fix metadata, local absolute paths, or credentials are included.
- The exact request hashes, context hashes, content scope, and DeepSeek price-sheet notes are in ignored local file `.local/diagnosis/provider-notes-2026-09-25.md`; prepared payloads are under ignored `.local/diagnosis/plan-v1/`.
- Official docs currently identify `deepseek-flash` as DeepSeek-V4.1-Flash. Current `max_tokens=4096` yields an output-only peak-price ceiling of about $0.05 for ten calls. Input is extra; exact input token and cache split are unknown, so total cost estimate is null. Ten calls are not a hard dollar cap.
- At preparation time `DEEPSEEK_API_KEY` was absent. It is now available to a zsh login shell; the value was not displayed or written to the repository. A local format check and local proxy TCP check passed, but neither verifies provider authorization or balance.
- The user approved the exact payloads and usage-based billing. The first case (`click-3084-bug`) was attempted and recorded as `provider_error`; no usage data or valid response was returned. The runner stopped as designed, without retrying, and the other nine requests were not sent. Billing for the failed request is unknown.

The separate `requests-6628-bug` smoke preserved the T7 run. Attempt 4 used analyzer checkout `1eb28b79879db2718bd620888a5a0f3ce11d40a2` (analyzer code `7e563c1`), target commit `7a13c041dbef`, context SHA-256 `742c6ef1…ab50d7d2`, canonical request SHA-256 `a2beca72…6487f900`, and wire SHA-256 `1cf6c6d9…e11e98840` (6,073 bytes). It returned `invalid_response/truncated` with usage 1,583 prompt, 4,096 completion, and 5,679 total tokens. Its local artifacts are under `.local/diagnosis/m06-online-requests-6628-attempt4-1eb28b7/`; the response body and key were not saved. The compact-output bounds did not prevent truncation in this one request, and the result does not establish the cause. See `docs/evaluations/2026-09-25-live-smoke.md` for the attempt ledger.

## T8 report

`docs/evaluations/2026-09-25-diagnosis-v1.md` records the manifest and analyzer hashes, all ten context/request hashes, request and token limits, cost uncertainty, the partial provider failure, and the limits of the resulting offline score. `README.md` links to the report. The partial report separates the one failed call and nine unattempted calls; quality ratios are undefined, and its 0/4 end-to-end count is explicitly not treated as a model-quality estimate.

## Remaining gates

1. The original ten-case run remains partial and was not retried. The separately authorized one-sample smoke has four recorded requests; attempt 4 used the final prompt and was truncated. The compact-output bounds have not been shown to prevent truncation. Opt-in `thinking_mode` support landed in `b8974505d35611a806a4388176df4e46f156754c`, preserving the old default request body and fingerprints. Prepare a new plan from the clean current commit with `--thinking-mode disabled`, inspect the new hashes, and keep the sample, final prompt, schema, and token limit fixed. The [official Chat Completions API documentation](https://api-docs.deepseek.com/api/create-chat-completion/) says thinking defaults to enabled, `reasoning_effort` defaults to high, and `max_tokens` caps generated tokens; this is a hypothesis test, not a finding about the cause. Do not reuse any previous plan/hash or modify the original ten-case plan. The `run` CLI executes all cases in a plan; `--max-calls` does not select one. No request with thinking disabled has been sent.
2. The partial record, zero-row review template, and offline score are complete. The quality evaluation remains inconclusive until a run returns usable model responses.
3. PR #6 head `3492deb7c9971c06da48477f2dff6a8836cf2226` was merged into `codex/repo-doctor-v1` at `ec5041d3b98e07dc42532336e36ebe9ac2e82f12`. Both CI runs passed on Python 3.11, 3.12, and 3.13 (six green jobs total); the updated PR worktree also passed all 163 tests, compileall, CLI help, and whitespace checks. This is independent of the original partial ten-case DeepSeek run; the separately tracked single-sample smokes above did not modify that run.

The original workspace `/Users/kisara/Documents/ChatGPT/AI Repo Doctor` remains untouched. Target repository code, tests, and dependencies were not executed or installed.

## 2026-09-25 CI evidence scope clarification

PR #6 CI applies to PR head `3492deb7c9971c06da48477f2dff6a8836cf2226`. It does not validate the unpublished diagnosis-evaluation changes. The integrated evaluation branch has a historical local result of 229 passing tests; that result is not a fresh CI result. Before publishing or merging the evaluation changes, record the actual evaluation PR head SHA and its own Python 3.11/3.12/3.13 CI results. This clarification does not change the stopped live run or establish model quality.
