# Symptom-Guided Diagnosis Evaluation V2

Date: 2026-09-29

Status: Approved to execute; the user waived a separate review checkpoint.

## Goal

Repeat the evaluation-only comparison of the blind diagnosis prompt and the
symptom-guided prompt on four new Python repositories. The first cohort did not
meet its registered signal, so this cohort uses new defects and repositories
without changing either prompt in response to the first result.

This work does not change the installed CLI, its default prompt, or the
provider transport. It measures whether an observable user symptom helps
DeepSeek find a known defect while avoiding false alarms on its fixed source
snapshot.

## Cohort

The cohort has four repairs from four repositories that do not appear in the
earlier diagnosis datasets: Pydantic, Jinja, Black, and Typer. Each source
snapshot is the exact merge commit for the fix or its first parent for the
unfixed state. The regression evidence and source blocks are inspected
statically; upstream code, tests, and dependencies are not executed.

| Repository and provenance | Unfixed snapshot | Fixed snapshot | Target symbol and regression evidence | Symptom shown to the model |
| --- | --- | --- | --- | --- |
| Pydantic [issue #13520](https://github.com/pydantic/pydantic/issues/13520), [PR #13521](https://github.com/pydantic/pydantic/pull/13521) | `a187a65467a588ccc00761d80f325b45381ca819` | `05bc5da8b40540eee8491ec5e81622b36f7db12f` | `pydantic/_internal/_typing_extra.py::safe_get_annotations`; `tests/test_edge_cases.py::test_safe_get_annotations_from_dict` | After an integration inspects class annotations during import, some generic Pydantic models treat defaulted fields as required and fail to substitute their type variables. The behavior depends on the order in which the integration and model are loaded. |
| Jinja [issue #1921](https://github.com/pallets/jinja/issues/1921), [PR #1984](https://github.com/pallets/jinja/pull/1984) | `20be10e566a505cc47bdec5fa6ad56d5fbdfb4ae` | `3ef3ba885bc7a465b022abfd525d6bb4a1c8dd3c` | `src/jinja2/filters.py::do_int`; `tests/test_filters.py::TestFilter.test_int` | Passing a very large scientific-notation string such as `31e1170` through the `int` filter raises `OverflowError` instead of returning the configured fallback. |
| Black [issue #4640](https://github.com/psf/black/issues/4640), [PR #4993](https://github.com/psf/black/pull/4993) | `ff094acc4e00f8d50f48023cc218ede17879774a` | `88e78334afa2ff046e8689dc8a8e848dd87792b6` | `src/black/nodes.py::is_one_sequence_between`; `tests/data/cases/comments_in_lambda_default.py`, exercised by Black's format-case test | Formatting a lambda whose tuple default contains a standalone comment and a trailing comma raises `LookupError` rather than producing formatted output. |
| Typer [discussion #1068](https://github.com/fastapi/typer/discussions/1068), [PR #1069](https://github.com/fastapi/typer/pull/1069) | `85ca5b5adc086dc76e6eccc3878727c3c7297edd` | `4f04666db67a231b4afd0d5b6de86b30242aa70c` | `typer/completion.py::shell_complete`; `tests/test_completion/test_completion_complete_rich.py` | With Rich installed, fish-shell completions display help text with escaped spaces such as `\ \ \`, leaving completion descriptions malformed. |

Each symptom is an unverified user observation, not a diagnosis. It does not
include the issue or pull-request number, test name, source location, commit,
root cause, patch, or label. The exact same symptom is sent for the bug and
fixed snapshots in a pair.

## Experimental design

The exact dataset ID is `diagnosis-symptom-guided-v2`. It contains 16 rows:
four cases per repair, ordered as blind/broken, blind/fixed,
symptom-guided/broken, symptom-guided/fixed. The two arms use identical source
context for a given snapshot. A symptom is present only on the two
symptom-guided rows and is identical within that bug/fixed pair.

The blind arm uses the existing production diagnosis prompts byte-for-byte.
The symptom arm adds the symptom as a separate user-payload field and retains
the existing instruction to treat it as unverified, repository content as
untrusted, and findings as requiring exact source evidence. The response
schema, source-evidence gate, and review rubric stay unchanged.

V2 omits blocks from test files and call-evidence edges originating in test
files so the model does not receive regression test names. Preparation and
run-time provenance checks apply the same evaluator-only filter; the installed
CLI context behavior remains unchanged.

Use the established settings: `deepseek-flash`, Responses API `json_schema`,
reasoning effort `none`, 120 source lines, 64 KiB context, 256 KiB serialized
request, 4,096 output tokens, non-streaming, and two repeats. Do not add
temperature, top-p, or seed. Record the returned model and provider usage.
Send at most 32 requests sequentially, without automatic retries. On the first
provider or provenance failure, preserve partial records and stop.

## Registered signal

The cohort passes only if all of these hold:

1. The run has exactly two repeats and all 32 planned calls produced parseable
   successful records.
2. The symptom arm has at least one accepted, manually verified bug detection
   for each of the four repairs across the two repeats.
3. The symptom arm has zero accepted false alarms on fixed snapshots.
4. Across the eight bug-case requests per arm (four bug cases times two
   repeats), the symptom arm has at least one more accepted bug detection than
   the blind arm.
5. The symptom arm's accepted false alarms on fixed snapshots do not exceed
   the blind arm's count.

Report every component even when the run is partial. A partial or failed run
cannot pass the signal. Rejected findings, uncertain findings, and findings
that merely quote correct source are not accepted bug detections.

## Interpretation limits

This is a purposive four-repair pilot, not a random or representative sample.
The public reports and fixes may occur in model training data. Bug/fixed
snapshots are correlated; repeats are repeated calls rather than independent
defects. One primary reviewer will label findings against the pinned source
and the stated behavior. The result can guide another evaluation or product
design, but cannot establish overall diagnostic accuracy or reliability.

## Artifacts

- Frozen dataset: `evaluation/diagnosis/symptom-guided-v2.json`.
- Implementation plan: `docs/superpowers/plans/2026-09-29-symptom-guided-v2.md`.
- Prepared plans, contexts, provider records, and review JSON remain under the
  ignored `.local/diagnosis/` directory.
- The final redacted result is tracked at
  `docs/evaluations/2026-09-29-symptom-guided-v2.md`.
