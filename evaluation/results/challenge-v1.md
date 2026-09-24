# AI Repo Doctor V2 challenge evaluation

- Dataset: `challenge-v1`
- Generated: `2026-09-24T07:42:55.709037+00:00`
- Analyzer commit: `06fa4f5b392da8f974f74c396d0ec6c6784c7a85`
- Python: `3.14.5 (v3.14.5:5607950ef23, May 10 2026, 07:38:09) [Clang 21.0.0 (clang-2100.0.123.102)]`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O` / `arm64`

Precision and recall below cover only the manually annotated probes,
not every relation in a repository. Timing is comparable within the
same environment; filesystem cache state is not controlled.

## click

Source: https://github.com/pallets/click.git at `06b2a678741131fd577ce170e23e5ca0aeba0309`

| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| reexport | sampled | 0 | 1 | 0 | 0 | 0 | — | — |
| command_registration | sampled | 3 | 0 | 3 | 0 | 0 | 1.000 | 1.000 |
| overload_resolution | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| overload_signature | sampled | 1 | 0 | 4 | 0 | 0 | 1.000 | 1.000 |

Scan seconds: 1.533, 1.509, 1.495, 1.563, 1.549
Median 1.533; minimum 1.495; maximum 1.563.
Mismatched probes: none.
Scanner stats: `{"ambiguous_symbols": 12, "classes": 173, "code_lines": 23119, "functions": 1358, "local_import_edges": 338, "methods": 468, "parse_errors": 0, "python_files": 91, "python_lines": 30174, "resolved_calls": 1600, "unresolved_calls": 3451}`

## requests

Source: https://github.com/psf/requests.git at `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`

| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | sampled | 1 | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| reexport | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| command_registration | not_sampled | 0 | 0 | 0 | 0 | 0 | — | — |
| overload_resolution | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| overload_signature | sampled | 1 | 0 | 2 | 0 | 0 | 1.000 | 1.000 |

Scan seconds: 0.422, 0.416, 0.422, 0.420, 0.414
Median 0.420; minimum 0.414; maximum 0.422.
Mismatched probes: none.
Scanner stats: `{"ambiguous_symbols": 0, "classes": 96, "code_lines": 9048, "functions": 181, "local_import_edges": 129, "methods": 510, "parse_errors": 0, "python_files": 37, "python_lines": 12032, "resolved_calls": 769, "unresolved_calls": 1727}`

## flask

Source: https://github.com/pallets/flask.git at `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35`

| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| call | sampled | 0 | 2 | 0 | 0 | 0 | — | — |
| reexport | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| command_registration | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| overload_resolution | sampled | 1 | 0 | 1 | 0 | 0 | 1.000 | 1.000 |
| overload_signature | sampled | 1 | 0 | 2 | 0 | 0 | 1.000 | 1.000 |

Scan seconds: 0.757, 0.756, 0.773, 0.755, 0.778
Median 0.757; minimum 0.755; maximum 0.778.
Mismatched probes: none.
Scanner stats: `{"ambiguous_symbols": 11, "classes": 148, "code_lines": 13301, "functions": 1054, "local_import_edges": 309, "methods": 367, "parse_errors": 0, "python_files": 83, "python_lines": 18345, "resolved_calls": 665, "unresolved_calls": 2654}`
