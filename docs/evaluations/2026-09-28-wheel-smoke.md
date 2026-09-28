# Installed CLI checkpoint

Date: 2026-09-28. Source commit: `0eb8361` plus the CI-only preview smoke
change in this checkpoint. The package version remains `0.1.0`.

An initial local attempt with `pip wheel --no-build-isolation` failed because
the host's Python 3.14 environment has no `setuptools.build_meta`. The normal
isolated command, `python3 -m pip wheel --no-deps --wheel-dir TEMP .`, built
`ai_repo_doctor-0.1.0-py3-none-any.whl` successfully. The wheel installed
with `pip install --no-index --no-deps` into a fresh virtual environment
outside the source tree.

From outside the checkout, the installed `repo-doctor` entry point scanned a
one-file Python sample with one parsed file and zero parse errors. With
`DEEPSEEK_API_KEY` removed, installed `diagnose --preview` returned a JSON
request body containing the selected sample line; its SHA-256 matched the
digest printed on standard error
(`14f62774307baeb470c597d355119a2ee8e6e4f1627af9a9ebac87496c5aa832`).
No provider request was made. CI now also smoke-tests this installed preview
on Python 3.11, 3.12, and 3.13 when the branch runs; those jobs have not yet
been observed for this head.
