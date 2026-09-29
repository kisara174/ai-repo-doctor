# Diagnosis evaluation dataset v1

`manifest-v1.json` freezes ten purposively selected source snapshots: four
upstream bug/fix pairs and two control behaviors. The cases span Click and
Requests. This is a small exploratory set, not a random or representative
sample of Python repositories; public issue discussions may also be present in
a model's training data.

## Provenance and labels

Every bug pair is tied to a public issue, its merged fix pull request, and the
exact fix commit. The bug checkout is the merge commit's first parent; the
fixed checkout is the merge commit. Click is distributed under BSD-3-Clause
and Requests under Apache-2.0. The license files are present and identical
within each before/fixed pair. The two controls describe a documented Click
integer-range helper and Requests HTTP Basic Auth handler. A `control` label
means only that no target issue is assigned to that selected behavior; it does
not claim that the repository has no other defects.

| Case IDs | Repository / license | Target issue | Fix PR / commit |
| --- | --- | --- | --- |
| `click-3084-bug`, `click-3084-fixed` | [pallets/click](https://github.com/pallets/click), [BSD-3-Clause](https://github.com/pallets/click/blob/ebcd548d50662bc8fa4f8b9ec7fe13cb8310bfaa/LICENSE.txt) | [#3084](https://github.com/pallets/click/issues/3084) | [#3152](https://github.com/pallets/click/pull/3152), [`ebcd548`](https://github.com/pallets/click/commit/ebcd548d50662bc8fa4f8b9ec7fe13cb8310bfaa) |
| `click-1921-bug`, `click-1921-fixed` | [pallets/click](https://github.com/pallets/click), [BSD-3-Clause](https://github.com/pallets/click/blob/e24db5732f304278e37a3d39d3546429b69f545e/LICENSE.rst) | [#1921](https://github.com/pallets/click/issues/1921) | [#2006](https://github.com/pallets/click/pull/2006), [`e24db57`](https://github.com/pallets/click/commit/e24db5732f304278e37a3d39d3546429b69f545e) |
| `requests-6628-bug`, `requests-6628-fixed` | [psf/requests](https://github.com/psf/requests), [Apache-2.0](https://github.com/psf/requests/blob/382fc2c0c6c0ef0874bc65bc1175f97c073e5086/LICENSE) | [#6628](https://github.com/psf/requests/issues/6628) | [#6629](https://github.com/psf/requests/pull/6629), [`382fc2c`](https://github.com/psf/requests/commit/382fc2c0c6c0ef0874bc65bc1175f97c073e5086) |
| `requests-7432-bug`, `requests-7432-fixed` | [psf/requests](https://github.com/psf/requests), [Apache-2.0](https://github.com/psf/requests/blob/6404f345e562d962abe6700a1c357ec1e7e18232/LICENSE) | [#7432](https://github.com/psf/requests/issues/7432) | [#7433](https://github.com/psf/requests/pull/7433), [`6404f34`](https://github.com/psf/requests/commit/6404f345e562d962abe6700a1c357ec1e7e18232) |

The primary agent read each affected implementation and upstream regression
test before approving the labels. Source fingerprints use the algorithm in the
execution plan: `tokenize.open`, inclusive `splitlines()` range, LF join with
no trailing newline, UTF-8, then SHA-256. The exact source spans, commit IDs,
symbols, issue/fix references, and review annotations are recorded per case in
the manifest.

Frozen manifest file size: 17,139 bytes. Its byte-for-byte SHA-256 is
`f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`.

## Recreating the immutable checkouts

Set `ROOT` to the `--repos-root` passed to the evaluation tool. Clone each
repository once as a bare repository, then add one detached checkout per
distinct manifest commit. The control cases reuse the fixed Click and Requests
checkouts listed below.

```sh
ROOT=/tmp/ai-repo-doctor-diagnosis-checkouts
mkdir -p "$ROOT/.bare"
git clone --bare https://github.com/pallets/click.git "$ROOT/.bare/click.git"
git clone --bare https://github.com/psf/requests.git "$ROOT/.bare/requests.git"

git --git-dir="$ROOT/.bare/click.git" worktree add --detach "$ROOT/click-7f7bbe4569ea" 7f7bbe4569ea68e8dabee232eade069ef3310aea
git --git-dir="$ROOT/.bare/click.git" worktree add --detach "$ROOT/click-ebcd548d5066" ebcd548d50662bc8fa4f8b9ec7fe13cb8310bfaa
git --git-dir="$ROOT/.bare/click.git" worktree add --detach "$ROOT/click-76cc18d1f0bd" 76cc18d1f0bd5854f14526e3ccbce631d8344cce
git --git-dir="$ROOT/.bare/click.git" worktree add --detach "$ROOT/click-e24db5732f30" e24db5732f304278e37a3d39d3546429b69f545e

git --git-dir="$ROOT/.bare/requests.git" worktree add --detach "$ROOT/requests-7a13c041dbef" 7a13c041dbef42f9f3feb14110f02626f6892e9a
git --git-dir="$ROOT/.bare/requests.git" worktree add --detach "$ROOT/requests-382fc2c0c6c0" 382fc2c0c6c0ef0874bc65bc1175f97c073e5086
git --git-dir="$ROOT/.bare/requests.git" worktree add --detach "$ROOT/requests-0b401c76b6e8" 0b401c76b6e80a4eecf3c690085b2553f6e261ca
git --git-dir="$ROOT/.bare/requests.git" worktree add --detach "$ROOT/requests-6404f345e562" 6404f345e562d962abe6700a1c357ec1e7e18232
```

The cases were scanned statically at their pinned commits. No target code,
dependencies, test suite, API, or external service was run to build this
manifest. Each target symbol resolves uniquely in the analyzer. Target source
blocks fit the 120-line budget; all prepared contexts observed during sample
selection were below 64 KiB.

## Interpretation limits

The fixed cases show one known defect removed; they are not certified
defect-free. Controls likewise cover only their stated behavior. The paired
snapshots and selected controls are correlated and intentionally chosen, so
their results must not be generalized into an estimate of overall product
quality, reliability, or security. Run/model output must remain separate from
these frozen labels, and every finding requires manual review before scoring.

## Optional DeepSeek thinking mode

By default, the prepared plan omits the `thinking` request field. This keeps
the serialized body and request fingerprint compatible with existing plans.
For a plan that explicitly disables thinking, add `--thinking-mode disabled`:

```sh
python3 -m tools.evaluate_diagnosis prepare \
  --manifest evaluation/diagnosis/manifest-v1.json \
  --repos-root "$ROOT" \
  --model deepseek-flash \
  --max-lines 120 \
  --thinking-mode disabled \
  --out-dir .local/diagnosis/plan-thinking-disabled
```

Preparation is offline. The selected mode is saved in `plan.json` and included
in every case's request fingerprint; changing or removing it invalidates the
fingerprint. A later `run` uses the plan's mode and still requires
`--allow-network`. Without `--case-id`, it executes the plan's complete case list; `--max-calls`
does not select a subset of a ten-case plan. DeepSeek documents thinking mode
and the `thinking.type` values in its [Chat Completions API reference](https://api-docs.deepseek.com/api/create-chat-completion/).

## Single-case smoke

Use `run --case-id requests-6628-bug --repeats 1 --max-calls 1` with the
usual plan, manifest, repositories, output, and `--allow-network` arguments
to send exactly one case from a fully validated prepared bundle. Unknown IDs
and repeats other than one are rejected before transport. Requests are never
retried. `--max-calls` alone still does not select a subset.

The run records `selected_case_id` and the full prepared plan hash. Review
preparation is supported, but `score` rejects this smoke as a dataset run.
A complete response and locally accepted evidence do not establish diagnostic
accuracy; inspect the findings against the pinned source and ground truth.

## Flask holdout v1

`flask-holdout-v1.json` is a separate, preregistered six-case comparison set.
It contains three new bug/fixed pairs from Flask, with no case from the
Click/Requests manifest above. The upstream issue, merged fix PR, exact
first-parent bug commit, fixed merge commit, selected symbol, ground truth,
source fingerprint, and primary-agent annotation are recorded in each case.
Flask's BSD-3-Clause license text has the same SHA-256 across all six
snapshots: `489a8e1108509ed98a37bb983e11e0f7e1d31f0bd8f99a79c8448e7ff37d07ea`.

The frozen holdout manifest SHA-256 is
`68aeaa16e4b0e400de800ea5f192c2c22c467eda8132e0e7dad7d08620333cd2`.
Keep this file byte-for-byte stable after the experiment begins. The
[experiment design](../../docs/superpowers/specs/2026-09-28-flask-holdout-design.md)
preregistered one prompt variant before any holdout model result was read.
Fixed cases are negative only for their paired defect; they are not a claim
that the selected method is entirely defect-free. There are no extra controls
in this small holdout.

To recreate the six detached, clean checkouts, set a writable local root and
clone Flask once. The evaluator verifies each checkout's HEAD and clean
status before preparing any request.

```sh
HOLDOUT_ROOT=/tmp/ai-repo-doctor-flask-holdout
mkdir -p "$HOLDOUT_ROOT/.bare"
git clone --bare https://github.com/pallets/flask.git "$HOLDOUT_ROOT/.bare/flask.git"
git --git-dir="$HOLDOUT_ROOT/.bare/flask.git" worktree add --detach "$HOLDOUT_ROOT/flask-c3f923d0e0ab" c3f923d0e0aba3ed5b6013c5d022021e4ae059cf
git --git-dir="$HOLDOUT_ROOT/.bare/flask.git" worktree add --detach "$HOLDOUT_ROOT/flask-ef3a82a28200" ef3a82a2820082f7d9f2ca963c9dff7eb1ea9687
git --git-dir="$HOLDOUT_ROOT/.bare/flask.git" worktree add --detach "$HOLDOUT_ROOT/flask-3435d2ff1589" 3435d2ff1589eb0c1a85cc294a20985910a1a606
git --git-dir="$HOLDOUT_ROOT/.bare/flask.git" worktree add --detach "$HOLDOUT_ROOT/flask-d7209a957004" d7209a957004d4758f32fd8b2f89da11f5fe5718
git --git-dir="$HOLDOUT_ROOT/.bare/flask.git" worktree add --detach "$HOLDOUT_ROOT/flask-5addaf833b2e" 5addaf833b2e8c7a616f89dd8ad5a44b07d7c000
git --git-dir="$HOLDOUT_ROOT/.bare/flask.git" worktree add --detach "$HOLDOUT_ROOT/flask-24824ff666e0" 24824ff666e096c4c07d0b75a889088571afe4a6
```

The target code and its tests must not be executed or installed by this
evaluation. The analyzer selects source statically; its largest observed
holdout context is 120 lines and 4,635 source bytes. Model claims require
source review even if the local quotation validator accepts their evidence.

## Werkzeug holdout v1

`werkzeug-holdout-v1.json` freezes three new bug/fixed pairs from Werkzeug:
[#2842](https://github.com/pallets/werkzeug/issues/2842),
[#2985](https://github.com/pallets/werkzeug/issues/2985), and
[#2994](https://github.com/pallets/werkzeug/issues/2994). Each bug checkout
is its repair commit's first parent. Exact symbols, source fingerprints,
trigger/outcome contracts, PRs, and primary-agent annotations are in the
manifest. Its byte-for-byte SHA-256 is
`09c42643a0e21f5468882c562c7326c2f731c9f0d3c3e9b00cec9bf3fe0d7bda`.
The [preregistered design](../../docs/superpowers/specs/2026-09-29-werkzeug-holdout-design.md)
uses one current-product arm; it does not reuse or relabel either earlier
dataset. No response from this cohort was read before the cases were frozen.

To recreate six detached, clean source checkouts without running target code:

```sh
WERKZEUG_ROOT=/tmp/ai-repo-doctor-werkzeug-holdout
mkdir -p "$WERKZEUG_ROOT/.bare"
git clone --bare https://github.com/pallets/werkzeug.git "$WERKZEUG_ROOT/.bare/werkzeug.git"
git --git-dir="$WERKZEUG_ROOT/.bare/werkzeug.git" worktree add --detach "$WERKZEUG_ROOT/werkzeug-4c09d1b3b08d" 4c09d1b3b08deb939803a4beb53483cbc54dfb8d
git --git-dir="$WERKZEUG_ROOT/.bare/werkzeug.git" worktree add --detach "$WERKZEUG_ROOT/werkzeug-f516c4005c7c" f516c4005c7c4510b61ae07969450771b929809d
git --git-dir="$WERKZEUG_ROOT/.bare/werkzeug.git" worktree add --detach "$WERKZEUG_ROOT/werkzeug-d1f60d68ac97" d1f60d68ac9788aec05712aca29867abd00d5cc3
git --git-dir="$WERKZEUG_ROOT/.bare/werkzeug.git" worktree add --detach "$WERKZEUG_ROOT/werkzeug-64d27f79eb84" 64d27f79eb84880b33f4451e078dab0b49c4c2c2
git --git-dir="$WERKZEUG_ROOT/.bare/werkzeug.git" worktree add --detach "$WERKZEUG_ROOT/werkzeug-1a1728ed8893" 1a1728ed88939ca68928dade168e1989be062c6f
git --git-dir="$WERKZEUG_ROOT/.bare/werkzeug.git" worktree add --detach "$WERKZEUG_ROOT/werkzeug-ea93b549a93f" ea93b549a93f65b216070e72a26cf0cc31d1e9ad
```

Pass `"$WERKZEUG_ROOT"` as `--repos-root` during offline preparation.
The six currently selected contexts range from 9 to 36 physical source
lines and 339 to 1,409 source bytes. Fixed cases cover only their paired
repair; any model finding still needs behavioral review.

The current-product JSON Schema arm completed six calls. Primary review
matched one of three known defects and found accepted false positives on two
fixed snapshots. The [run report](../../docs/evaluations/2026-09-29-werkzeug-holdout.md)
records case judgments, hashes, usage, and limits. This cohort is now visible
to the implementer and must not be reused as unseen evidence for a tuned
prompt or context change.

## Werkzeug explicit-context comparison v1

`werkzeug-explicit-context-v1.json` freezes two new bug/fixed pairs and an
explicit-context arm for each snapshot. The targets are
`Headers.__iter__` (empty WSGI special-header values, repair commit
`625362a`) and `Headers.get` (non-string keys in `EnvironHeaders`, PR #1005).
Each bug/fixed pair is represented once with the default context and once
with a named `EnvironHeaders` method selected explicitly. The arm cases use
the same commits and target source fingerprints. The default rows omit
`include_symbols`; explicit rows carry exactly one symbol. The 12,785-byte
manifest SHA-256 is
`a199434e0531b25ea6527df34696d5c66b0784dd16db2a15cfea26d0d9a2791f`.

Commit `625362a` has no associated GitHub issue or pull request, so its short
fix commit is stored in `issue_id` only as the pair-group label. The PR #1005
discussion describes the `EnvironHeaders.__getitem__` type failure and the
supplied-default contract. These historical cases are purposive and may be
present in model training data; they are not a representative quality sample.

To recreate four detached source checkouts without running target code:

```sh
EXPLICIT_ROOT=/tmp/ai-repo-doctor-werkzeug-explicit
mkdir -p "$EXPLICIT_ROOT/.bare"
git clone --bare https://github.com/pallets/werkzeug.git "$EXPLICIT_ROOT/.bare/werkzeug.git"
git --git-dir="$EXPLICIT_ROOT/.bare/werkzeug.git" worktree add --detach "$EXPLICIT_ROOT/werkzeug-0c5cad57c237" 0c5cad57c2370c4b916b3651adb4d82eb9fbf5ec
git --git-dir="$EXPLICIT_ROOT/.bare/werkzeug.git" worktree add --detach "$EXPLICIT_ROOT/werkzeug-625362a42926" 625362a429263f8d713a9ed06c18f247042d7d0f
git --git-dir="$EXPLICIT_ROOT/.bare/werkzeug.git" worktree add --detach "$EXPLICIT_ROOT/werkzeug-3790dc177329" 3790dc177329a5214bd318be6e1dfd43d680eb64
git --git-dir="$EXPLICIT_ROOT/.bare/werkzeug.git" worktree add --detach "$EXPLICIT_ROOT/werkzeug-57521600ce04" 57521600ce04fdf4d977c36f89fc51191aa8a3c9
```

Pass `"$EXPLICIT_ROOT"` as `--repos-root`. The [preregistered design](../../docs/superpowers/specs/2026-09-29-paired-explicit-context-design.md)
sets `deepseek-flash`, Responses `json_schema`, no thinking field, 120 lines,
one call per case, and no retries. Its usefulness signal is narrow: at least
one bug detected only with the explicit context, no additional fixed-case
false alarm, and all eight parseable calls. Even a positive result would not
justify a general accuracy claim or changing the product default.

The first frozen attempt stopped after one connection failure. One request
was attempted, no response was available, and seven cases were not attempted.
The [partial run report](../../docs/evaluations/2026-09-29-paired-explicit-context.md)
records the hashes and limits. Treat this cohort as consumed for holdout
purposes and do not rerun it as unseen evidence.

Before dispatching any new frozen cohort, run
`python3 -m repo_doctor doctor --deepseek --model deepseek-flash --json .`
from the analyzer checkout and
require `deepseek.status` to be `ready`. This models-list check sends no
repository source and helps catch local Key, model, and TLS setup failures
before the holdout is attempted. It does not test the Responses endpoint or
establish model quality.

## Click explicit-context comparison v1

`click-explicit-context-v1.json` freezes two fresh Click repairs, each with
bug and fixed snapshots in default and explicitly supplemented context arms.
The cases concern case-insensitive `Choice` shell completion
([issue #1692](https://github.com/pallets/click/issues/1692),
[PR #1693](https://github.com/pallets/click/pull/1693)) and `Choice` metavar
display when `show_choices=False`
([issue #2356](https://github.com/pallets/click/issues/2356),
[PR #2365](https://github.com/pallets/click/pull/2365)). The manifest records
the exact commits, source fingerprints, narrow behavioral labels, and upstream
tests. Its 13,398 bytes have SHA-256
`a3b5341bd219f734730cf7272939c890e8ecf3c458ac5cd42096b07ecfe48bd1`.
Click's BSD-3-Clause license text has SHA-256
`9a8ad106a394e853bfe21f42f4e72d592819a22805d991b5f3275029292b658d`
in all four snapshots.

To recreate four detached, clean checkouts without executing Click code:

```sh
CLICK_ROOT=/tmp/ai-repo-doctor-click-explicit
mkdir -p "$CLICK_ROOT/.bare"
git clone --bare https://github.com/pallets/click.git "$CLICK_ROOT/.bare/click.git"
git --git-dir="$CLICK_ROOT/.bare/click.git" worktree add --detach "$CLICK_ROOT/click-acc91bc4f47e" acc91bc4f47e38f43277fcdfd8ca855734c4fbbc
git --git-dir="$CLICK_ROOT/.bare/click.git" worktree add --detach "$CLICK_ROOT/click-5eb46cba463f" 5eb46cba463ff3e3894b58f6649c5a13f02a70b1
git --git-dir="$CLICK_ROOT/.bare/click.git" worktree add --detach "$CLICK_ROOT/click-02046e7a1948" 02046e7a19480f85fff7e4577486518abe47e401
git --git-dir="$CLICK_ROOT/.bare/click.git" worktree add --detach "$CLICK_ROOT/click-1a4d8c1bb1e8" 1a4d8c1bb1e8f8e214ede7223bd2c05dc2ce006a
```

Pass `"$CLICK_ROOT"` as `--repos-root`. The default arm includes the public
`Parameter` method but omits the dynamically called `Choice` method. Each
explicit row selects exactly that method through `include_symbols`. All eight
offline selections fit 120 lines and 64 KiB; the largest is 43 selected lines.
The [preregistered design](../../docs/superpowers/specs/2026-09-29-click-explicit-context-design.md)
requires `deepseek-flash`, Responses `json_schema`, one sequential call per
case, no retries, and manual source review. The provider receives selected
context only, without case labels, issue IDs, or ground truth. Even a positive
comparison would remain exploratory evidence from two purposive repairs in
one library, one model sample per arm, and one primary reviewer.

The first frozen run completed all eight calls. Primary review found no match
to either known repair and marked all four citation-checked findings false
positives; two findings occurred on fixed-arm cases. The
[run report](../../docs/evaluations/2026-09-29-click-explicit-context.md)
records case judgments, usage, and limits. This cohort is now visible and
consumed; do not reuse it as unseen evidence for a revised context or prompt.
