# Flask holdout diagnosis comparison

## Decision and purpose

Evaluate the existing opt-in Responses JSON Schema diagnosis on new, pinned
Flask source snapshots before changing its prompt. Then compare one
preregistered prompt edit on the same inputs. This is a small, purposively
selected holdout from a new repository; one response per case cannot estimate
general diagnostic reliability.

The current ten-case Click/Requests manifest, its hashes, run records, and
score remain unchanged. Flask ground truth and fix commits are never supplied
to the model. Target repository code, tests, and dependencies are not run.

## Frozen inputs

Create `evaluation/diagnosis/flask-holdout-v1.json` with manifest schema 1 and
dataset ID `diagnosis-flask-holdout-v1`. The six cases are three bug/fixed
pairs, in this order:

| Issue / fix PR | Bug: merge first parent | Fixed: merge commit | Selected symbol |
| --- | --- | --- | --- |
| [Flask #4170](https://github.com/pallets/flask/issues/4170) / [#4174](https://github.com/pallets/flask/pull/4174) | `c3f923d0e0aba3ed5b6013c5d022021e4ae059cf` | `ef3a82a2820082f7d9f2ca963c9dff7eb1ea9687` | `src/flask/cli.py::call_factory` |
| [Flask #5391](https://github.com/pallets/flask/issues/5391) / [#5393](https://github.com/pallets/flask/pull/5393) | `3435d2ff1589eb0c1a85cc294a20985910a1a606` | `d7209a957004d4758f32fd8b2f89da11f5fe5718` | `src/flask/cli.py::SeparatedPathType.convert` |
| [Flask #5786](https://github.com/pallets/flask/issues/5786) / [#5797](https://github.com/pallets/flask/pull/5797) | `5addaf833b2e8c7a616f89dd8ad5a44b07d7c000` | `24824ff666e096c4c07d0b75a889088571afe4a6` | `src/flask/testing.py::FlaskClient.open` |

The bug contracts are, respectively: a sole `**kwargs` app factory must not
receive a positional `script_info`; on Python before 3.12, no-argument
`super()` inside the path-list comprehension fails when a CLI path option is
converted; after a followed redirect, the preserved request contexts must be
reentered oldest to newest so the final response's session is current. A
fixed case is negative only for its paired contract, not certified defect-free.
No additional controls are selected; the three fixed cases are the negative
examples. The repository's BSD-3-Clause license text is identical across the
six pinned snapshots.

Each manifest case records the exact target source span and SHA-256, public
issue/PR/commit references, a trigger and expected outcome, and primary-agent
approval. Source fingerprints use `tokenize.open`, inclusive `splitlines()`
ranges, LF joining with no trailing newline, UTF-8, and SHA-256. The evaluator
must verify full commit IDs, clean checkouts, unique symbols, and fingerprints
before producing a plan. Only the two explicit IDs `diagnosis-v1` and
`diagnosis-flask-holdout-v1` are accepted by the diagnosis manifest validator.

## Paired experiment

Prepare and run the current committed prompt first. Keep model
`deepseek-flash`, Responses `json_schema`, `reasoning.effort=none`, max 120
selected lines, 64 KiB selected source, 256 KiB request body, 4,096 output
tokens, one call per case, and the existing evidence gate. The analyzer and
all six target checkouts must be clean at preparation and run time. New ignored
directories retain the plan, safe run records, primary review, and score. A
provider failure stops that arm without retry. A missing or rejected key is
reported and online work stops; offline preparation remains valid.

Before seeing holdout model results, preregister exactly one prompt edit. Add
these two sentences to the system prompt after the current source-support
instruction:

> For each finding, name the concrete triggering input or state and the incorrect observable outcome in reasoning or impact. If either cannot be established from supplied lines, omit that finding; omitted source is not evidence of a defect.

Do not change context selection, schema, model, decoding settings, evidence
validation, or source budgets in the variant. Prepare a new plan under the
variant's clean commit. Its six context hashes must equal the baseline's; its
request hashes must change because the system prompt changed. Run the same six
cases once with no automatic retry.

## Review and decision rule

The primary agent reviews every accepted and rejected finding against the
pinned source and upstream repair. A quote match alone is not a true positive.
Use TP, FP, uncertain, or duplicate; disclose that no second reviewer has
adjudicated the labels. Score each complete arm separately and compare paired
case outcomes. Do not pool the two arms or the earlier ten-case dataset.

The prompt edit is a candidate for a later release only if both arms complete,
it removes at least one fixed-case accepted false alarm, does not reduce the
number of known bug cases detected, and does not increase the total accepted
false-positive findings. Even then, these six purposive cases only justify a
larger independently reviewed evaluation, not a default switch. If results are
partial, tied, or worse, keep the current prompt and record the observed
failure mode. Report token usage as observed counts, never as billed cost.
