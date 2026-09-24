# Execution Status

Plan: `docs/superpowers/plans/2026-09-24-post-v3-execution.md`

Branch / worktree: `codex/diagnosis-evaluation` / `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`

Latest implementation commit: `5044a94` (`eval: score human-reviewed diagnosis results`), on top of T5 commit `81fa9d3`.

## Phase

T0–T6 are implemented, validated, reviewed, and committed. T7's offline preparation and prompt review are complete; the live-run approval gate is still pending. T8's offline status report and README link are prepared, while final T6 cross-version CI and any live-result report remain pending.

The frozen ten-case manifest is unchanged at SHA-256 `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`. T5 only ran against mocks. T6 provides manual-review templates and deterministic offline scoring. Its two independent-review corrections are included: E2E denominators are calculated per repeat, and completed-call failure rate is `failed_calls / completed_calls`, with unresolved attempts separate.

## Validation

- T6 targeted score/CLI/math suite: 28 passed.
- Full suite: 221 passed.
- `python3 -m compileall -q repo_doctor tools`: passed.
- Main, `prepare-review`, and `score` CLI help: passed.
- `git diff --check`: passed.
- Independent read-only review of both T6 metric corrections: no remaining findings.

## T7 exact offline preparation

- Prepared ten request contexts for `deepseek-flash`, one repeat, at most ten requests, 120 source lines maximum per request, and 4,096 generated tokens maximum per request.
- All ten payloads were inspected. They contain the fixed diagnostic prompt, one case's selected public source, and static call evidence; no ground-truth labels, issue/fix metadata, local absolute paths, or credentials are included.
- The exact request hashes, context hashes, content scope, and DeepSeek price-sheet notes are in ignored local file `.local/diagnosis/provider-notes-2026-09-25.md`; prepared payloads are under ignored `.local/diagnosis/plan-v1/`.
- Official docs currently identify `deepseek-flash` as DeepSeek-V4.1-Flash. Current `max_tokens=4096` yields an output-only peak-price ceiling of about $0.05 for ten calls. Input is extra; exact input token and cache split are unknown, so total cost estimate is null. Ten calls are not a hard dollar cap.
- At preparation time `DEEPSEEK_API_KEY` was absent. Only presence was checked; no secret was displayed or stored. No live call was made.
- The user still needs to approve uploading these exact public-source contexts and accepting usage-based charges at the checked rates. After approval, the key must be configured before execution.

## T8 report

`docs/evaluations/2026-09-25-diagnosis-v1.md` records infrastructure complete / real results pending, the manifest and analyzer hashes, all ten context/request hashes, request and token limits, cost uncertainty, two representative input cases, offline review/scoring commands, and limitations. `README.md` links to the report. No result metrics are represented as zero when they are unavailable.

## Remaining gates

1. Obtain one-time approval for the exact model, ten prepared requests, output-token cap, and variable billing scope; configure `DEEPSEEK_API_KEY` in the execution environment.
2. Execute once with no retries. Preserve partial records on any failure, manually review every finding, and score offline.
3. After authorization to publish the branch, push/update PR #6 and verify the Python 3.11–3.13 CI matrix. No push or merge has been performed; the plan does not authorize merging PR #6.

The original workspace `/Users/kisara/Documents/ChatGPT/AI Repo Doctor` remains untouched. Target repository code, tests, and dependencies were not executed or installed.
