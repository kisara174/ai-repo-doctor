# Symptom-Guided Diagnosis Evaluation Design

Date: 2026-09-29

Status: Draft for user review

## Goal

Test whether a concise, user-observable symptom helps DeepSeek identify a
known Python defect in bounded source context, without increasing false alarms
on the corresponding fixed source. This is an evaluation-only change. It does
not change the installed CLI or its default diagnosis prompt.

The comparison is motivated by prior exploratory results: exact source quotes
were often valid, while manual review found low known-bug detection and many
false positives. The experiment must therefore score behavioral matches and
fixed-snapshot alarms, not treat citation grounding as diagnosis correctness.

## Approaches considered

1. **Evaluation-only symptom prompt (selected).** Add a frozen evaluation
   variant and compare it with the existing blind prompt on paired bug/fixed
   source snapshots. This tests whether the user-provided symptom adds value
   before creating a product interface.
2. **Add `diagnose --symptom` immediately.** This creates a user-facing mode
   before there is evidence that the extra input improves answers.
3. **Add a separate `explain` command.** This creates a second product flow and
   output contract before the core behavior has been evaluated.

The latter two approaches are deferred. A positive result may justify a
separate product design for an optional symptom-guided CLI mode; this
experiment alone will not change the CLI or its defaults.

## Evaluation question

On the same pinned source snapshots and model settings, does a symptom-guided
prompt produce more manually verified, symptom-relevant bug findings than the
current blind prompt, while avoiding new false alarms on fixed snapshots?

This is an exploratory pilot, not a general accuracy estimate. It has two
distinct historical repairs from two projects, two repeats per case, and one
primary reviewer.

## Candidate cohort

The two public upstream repairs below are candidates. Before freezing the
manifest, preparation must verify the exact commits, first-parent relationship,
Python target symbols, bounded contexts, source fingerprints, and upstream
regression evidence. Replace a candidate if any requirement fails; do not
weaken the cohort contract to keep it.

| Project and repair | Bug snapshot | Fixed snapshot | Context symbols | Upstream regression evidence | Symptom sent to the model |
| --- | --- | --- | --- | --- | --- |
| pytest [issue #12083](https://github.com/pytest-dev/pytest/issues/12083), [PR #13704](https://github.com/pytest-dev/pytest/pull/13704) | First parent of PR merge `7cfe8aa2758c154c9355ca61e3de32a50ec78663` | PR merge `d036b12bb6fa09f9a8a3b690cc7336113c93fa44` | Target: `src/_pytest/main.py::Session.perform_collect`; fixed snapshot supplement: `src/_pytest/main.py::normalize_collection_arguments` | `testing/test_collection.py::TestOverlappingCollectionArguments.test_specific_file_then_parent_dir` | “When I ask pytest to collect a specific test file together with its containing directory, it collects only the file's test and misses other tests in that directory. Which code in the supplied context could explain this behavior?” |
| Rich [issue #3897](https://github.com/Textualize/rich/issues/3897), [PR #3930](https://github.com/Textualize/rich/pull/3930) | First parent of PR merge `53757bc234cf18977cade41a5b64f3abaccb0b85` | PR merge `f000c3149166cc2091b801b63b0a55e806c5d49b` | Target: `rich/cells.py::cell_len`; bug snapshot supplement: `rich/cells.py::cached_cell_len`; fixed snapshot context includes `rich/cells.py::_cell_len` | `tests/test_cells.py::test_split_graphemes`, including the `⬇️` case with expected width 2 | “In the terminal, `⬇️` and `⬆️` visually occupy two columns, but Rich lays out following text as though each occupies one; lines wrap or align incorrectly. Which code in the supplied context could explain this behavior?” |

The symptom text describes observable behavior and does not include issue
titles, root causes, patches, expected diagnosis, or labels. The exact same
symptom string is used for the bug and fixed snapshots in its pair.

Candidate feasibility was checked against clean checkouts of all four exact
commits. All target symbols resolve unambiguously, and every generated context
fits the 120-line budget. The pytest fixed snapshot explicitly includes the
normalizer; the Rich bug snapshot explicitly includes `cached_cell_len`, while
the fixed snapshot's bounded call graph includes `_cell_len`. Each pinned
snapshot's generated context will be reused unchanged by its blind and symptom
arms. These checks inspect source only; they do not execute either upstream
project's tests.

The source issue and repair records establish candidate provenance. The
manifest will additionally pin each source range and SHA-256, cite the
upstream regression assertion or test, and record a narrow behavioral
contract. Never send issue IDs, commit IDs, labels, test names, fix references,
ground truth, or review annotations to the model.

## Conditions and request protocol

Freeze one manifest with dataset ID `diagnosis-symptom-guided-v1` and eight
cases in this order for each repair: blind/broken, blind/fixed,
symptom/broken, symptom/fixed. Use distinct `pair_id` values for each repair
and prompt arm so each pair contains one bug and one fixed case. Bug and fixed
cases share the same `issue_id` within a repair.

The conditions are:

- **Blind baseline:** use the current diagnosis prompts with the selected
  source context and no reported symptom.
- **Symptom-guided:** use the same source context plus the pair's symptom in
  a separate JSON field. The prompt treats the symptom as an unverified user
  observation, treats repository text as untrusted data, and asks for only
  source-supported findings that could explain the reported behavior.

Both conditions retain the existing `findings` JSON Schema, local finding
validation, selected-context evidence gate, and manual review format. An empty
findings list means the model supplied no supported diagnosis; it does not
distinguish “not applicable” from “insufficient context.” Record this as a
limitation rather than adding a second response schema for this pilot.

Only evaluation tooling changes. Add the exact dataset ID and a validated,
optional `symptom` field to the frozen manifest contract. When present, the
symptom must be a trimmed, single-line string of 1–2,000 Unicode characters
without control characters. This dataset must contain exactly eight cases:
one blind and one symptom-guided bug/fixed pair for each repair. Both cases in
each pair share a symptom only in the symptom-guided arm; blind cases omit the
field. An evaluation-only
prompt builder must preserve the current prompt byte-for-byte for baseline
cases. For symptom cases, it places the symptom and bounded source context in
the user JSON payload and adds the behavior-focused instruction. Context files
continue to contain only the source context. The symptom is read from the
manifest when preparing and revalidating requests, and is included in the
request SHA-256. The existing production `repo_doctor.diagnosis` prompt,
`repo_doctor` CLI, output schema, transport, and previous datasets remain
unchanged.

Use these fixed settings for every condition:

- Model: `deepseek-flash`.
- Response format: Responses API `json_schema`.
- Reasoning effort: `none`.
- Context: at most 120 source lines and 64 KiB; serialized request at most
  256 KiB.
- Output: 4,096 token limit, non-streaming.
- Sampling settings: use the current Responses client request body unchanged;
  it omits temperature, top-p, and seed, so the provider defaults apply.
  Record the returned model ID and report that repeat variation is not a
  deterministic replay guarantee.
- Repeats: two per case; 16 calls maximum.
- No retry. A provider or provenance failure stops the sequential run and
  leaves an accurately marked partial run.

Before dispatch, prepare all eight request hashes from clean pinned checkouts,
independently rebuild them, verify the analyzer commit and source fingerprints,
and require a fresh `doctor --deepseek --model deepseek-flash` result of
`ready`. The two prompt arms for any given snapshot must have identical
context hashes; their request hashes must differ only because of the symptom
instruction and input. No target code, tests, or dependencies are executed.

## Review and scoring

Review every accepted finding against the exact pinned source and upstream
behavior contract. A true positive must connect the relevant source behavior
to the reported symptom; a valid quote or a finding about an unrelated defect
is not a true positive. Record unrelated false positives separately in the
rationale. Review fixed snapshots for false claims that the specified symptom
is caused by the submitted code. Keep uncertain and duplicate findings
distinct.

Report by prompt arm and repair:

- completed and parseable calls;
- symptom-relevant bug detections by case and repeat;
- fixed-snapshot false alarms;
- primary-reviewed precision and uncertain findings;
- exact-quote/context grounding rate;
- agreement or variation between the two repeats;
- observed provider token usage, without converting tokens to a billing claim.

For this dataset ID, the offline score output must include separate blind and
symptom-guided summaries, grouped by each case's arm, repair, and repeat.
Determine the arm from the optional manifest `symptom` field, never from model
output. Include issue-level true-positive counts, fixed-snapshot accepted
false alarms, uncertain findings, exact-context grounding, and repeat
variation. Preserve the existing whole-dataset totals. Require the score
validator to enforce the exact eight-row arm/pair structure for this dataset
ID, while leaving reports for previous datasets unchanged.

Citation grounding is a provenance measure only. It must not be described as
behavioral validation.

## Preregistered narrow usefulness signal

The pilot meets its signal only if all of the following are true:

1. All 16 calls complete with parseable findings and no retry.
2. Each of the two distinct repairs has at least one symptom-relevant true
   positive in the symptom-guided arm across its two bug-case repeats.
3. Neither fixed case has an accepted false positive in the symptom-guided
   arm across its two repeats.
4. The symptom-guided arm produces at least one more bug-detection result
   across the eight bug-case repeats than the blind baseline, without any
   increase in fixed-case false alarms.

Failure to meet the signal is still a completed evaluation when all
preparation and review artifacts are sound. Do not tune the prompt against
these now-visible issues or add the cases to another holdout. Report the
failure and choose a genuinely new cohort before further prompt changes.

Passing the signal justifies designing an optional CLI prototype and testing
it separately. It does not justify enabling symptom-guided behavior by default
or claiming broad diagnostic accuracy.

## Data handling and error behavior

The requests contain only the approved symptom text, bounded public source
context, and existing diagnostic instructions. The source context naturally
includes repository-relative source filenames for evidence grounding; requests
exclude absolute checkout paths, Git metadata, environment data, API keys,
issue metadata, labels, and ground truth. Do not store the key or raw provider
response bodies. Keep experiment plans, parsed records, review rows, and
reports in ignored
`.local/diagnosis/` paths; only the manifest, design, and final redacted
evaluation report are tracked.

If the API key is missing or rejected, or transport/provenance preflight
fails, do not retry automatically. Preserve the offline plan and report the
run as unattempted or partial with billing unknown unless the provider gives
an explicit usage record. Do not use a failed call as model-quality evidence.

## Acceptance criteria for the evaluation implementation

1. The new exact dataset ID and `symptom` field are strictly validated; the
   two prompt arms contain the same pinned source context and no label or
   ground-truth metadata.
2. Baseline prompts and request hashes for all prior frozen datasets remain
   unchanged.
3. Symptom prompt hashes include the exact symptom text; preparation and run
   preflight independently rebuild the same hashes from the manifest.
4. The existing evidence gate still rejects any citation outside the exact
   submitted context, and the existing JSON finding contract remains intact.
5. Offline prepare, run preflight, manual review template, and scoring can
   process the eight rows and two repeats without contacting the provider;
   scoring reports separate blind and symptom-guided results by repair and
   repeat, plus the existing whole-dataset totals. Add that breakdown only for
   this new dataset so reports for previous datasets remain unchanged.
6. The actual run requires explicit `--allow-network`, records at most 16
   sequential calls, never retries, and does not persist the key or raw
   provider body.
7. Targeted regression tests cover manifest validation, both prompt arms,
   stable baseline request hashes, symptom hash changes, paired case scoring,
   and stop-on-provider-error. Run the full project suite once after those
   focused checks.
8. The final report states whether the narrow signal passed, gives the
   evidence for each manually reviewed verdict, preserves the exploratory
   limitations, and recommends the next action without overstating results.

## Out of scope

- Changes to installed CLI behavior or default prompts.
- New response schemas, automatic behavioral verification, target test
  execution, automatic code changes, multi-provider support, or prompt tuning
  against the selected cohort.
- Claims about general model quality from two repairs or one reviewer.
- Automatic retries or inferred billing amounts.
