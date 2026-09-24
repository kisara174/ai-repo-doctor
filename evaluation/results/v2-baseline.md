# AI Repo Doctor V2 baseline

- Dataset: `baseline-v1`
- Generated: `2026-09-24T06:36:00.631001+00:00`
- Analyzer commit: `36ebbb8207ea477292018373390143772d625996`
- Python: `3.14.5 (v3.14.5:5607950ef23, May 10 2026, 07:38:09) [Clang 21.0.0 (clang-2100.0.123.102)]`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O` / `arm64`

Precision and recall below cover only the manually annotated probes,
not every relation in a repository. Timing is comparable within the
same environment; filesystem cache state is not controlled.

## click

Source: https://github.com/pallets/click.git at `06b2a678741131fd577ce170e23e5ca0aeba0309`

| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | sampled | 6 | 2 | 6 | 0 | 0 | 1.000 | 1.000 |
| reexport | sampled | 4 | 0 | 4 | 0 | 0 | 1.000 | 1.000 |
| command_registration | sampled | 5 | 5 | 5 | 0 | 0 | 1.000 | 1.000 |
| overload_resolution | sampled | 3 | 0 | 3 | 0 | 0 | 1.000 | 1.000 |
| overload_signature | sampled | 3 | 0 | 6 | 0 | 0 | 1.000 | 1.000 |

Scan seconds: 1.436, 1.450, 1.446, 1.453, 1.451
Median 1.450; minimum 1.436; maximum 1.453.
Mismatched probes: none.
Scanner stats: `{"ambiguous_symbols": 12, "classes": 173, "code_lines": 23119, "functions": 1358, "local_import_edges": 338, "methods": 468, "parse_errors": 0, "python_files": 91, "python_lines": 30174, "resolved_calls": 1600, "unresolved_calls": 3451}`

## requests

Source: https://github.com/psf/requests.git at `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`

| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | sampled | 6 | 2 | 6 | 0 | 0 | 1.000 | 1.000 |
| reexport | sampled | 4 | 0 | 4 | 0 | 0 | 1.000 | 1.000 |
| command_registration | not_sampled | 0 | 0 | 0 | 0 | 0 | — | — |
| overload_resolution | sampled | 3 | 0 | 3 | 0 | 0 | 1.000 | 1.000 |
| overload_signature | sampled | 3 | 0 | 6 | 0 | 0 | 1.000 | 1.000 |

Scan seconds: 0.412, 0.408, 0.407, 0.410, 0.406
Median 0.408; minimum 0.406; maximum 0.412.
Mismatched probes: none.
Scanner stats: `{"ambiguous_symbols": 0, "classes": 96, "code_lines": 9048, "functions": 181, "local_import_edges": 129, "methods": 510, "parse_errors": 0, "python_files": 37, "python_lines": 12032, "resolved_calls": 769, "unresolved_calls": 1727}`

## flask

Source: https://github.com/pallets/flask.git at `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35`

| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | sampled | 6 | 2 | 6 | 0 | 0 | 1.000 | 1.000 |
| reexport | sampled | 4 | 0 | 4 | 0 | 0 | 1.000 | 1.000 |
| command_registration | not_sampled | 0 | 0 | 0 | 0 | 0 | — | — |
| overload_resolution | sampled | 3 | 0 | 3 | 0 | 0 | 1.000 | 1.000 |
| overload_signature | sampled | 3 | 0 | 6 | 0 | 0 | 1.000 | 1.000 |

Scan seconds: 0.717, 0.711, 0.715, 0.718, 0.720
Median 0.717; minimum 0.711; maximum 0.720.
Mismatched probes: none.
Scanner stats: `{"ambiguous_symbols": 11, "classes": 148, "code_lines": 13301, "functions": 1054, "local_import_edges": 309, "methods": 367, "parse_errors": 0, "python_files": 83, "python_lines": 18345, "resolved_calls": 665, "unresolved_calls": 2654}`
