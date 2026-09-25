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
