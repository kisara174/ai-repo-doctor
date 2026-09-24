"""Measure Repo Doctor against pinned, manually annotated repository probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


class EvaluationError(ValueError):
    """An evaluation input cannot be used as trustworthy evidence."""


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} must be nonempty text")
    return value


def _safe_relative_file(value: object, label: str) -> str:
    name = _text(value, label)
    parts = name.split("/")
    if (PurePosixPath(name).is_absolute() or any(part in {"", ".", ".."} for part in parts)
            or PurePosixPath(name).as_posix() != name):
        raise EvaluationError(f"{label} must be a safe repository-relative POSIX path")
    return name


def _evidence_fields(value: object, label: str) -> tuple[str, int, int, str]:
    evidence = _mapping(value, label)
    file = _safe_relative_file(evidence.get("file"), f"{label}.file")
    start = evidence.get("start_line")
    end = evidence.get("end_line")
    if type(start) is not int or type(end) is not int or start < 1 or end < start:
        raise EvaluationError(f"{label} needs a valid 1-based line range")
    digest = evidence.get("sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise EvaluationError(f"{label}.sha256 must be 64 lowercase hex characters")
    return file, start, end, digest


def source_fingerprint(path: Path, start_line: int, end_line: int) -> str:
    """Hash inclusive source lines after normalizing line endings to LF."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise EvaluationError(f"cannot read evidence file {path}: {exc}") from exc
    if (type(start_line) is not int or type(end_line) is not int
            or start_line < 1 or end_line < start_line or end_line > len(lines)):
        raise EvaluationError(f"invalid evidence line range {path}:{start_line}-{end_line}")
    selected = "\n".join(lines[start_line - 1:end_line])
    return hashlib.sha256(selected.encode("utf-8")).hexdigest()


def validate_evidence(repo_root: Path, probe: dict[str, object]) -> None:
    """Check a probe's source range against one pinned checkout."""
    probe_id = _text(probe.get("id"), "probe.id")
    file, start, end, digest = _evidence_fields(probe.get("evidence"), f"{probe_id}.evidence")
    root = repo_root.resolve()
    try:
        source = (root / file).resolve(strict=True)
        source.relative_to(root)
    except (OSError, ValueError) as exc:
        raise EvaluationError(f"{probe_id}: evidence file escapes or is absent: {file}") from exc
    if not source.is_file() or source_fingerprint(source, start, end) != digest:
        raise EvaluationError(f"{probe_id}: evidence fingerprint mismatch: {file}:{start}-{end}")


def validate_manifest_data(manifest: dict[str, object]) -> None:
    """Validate annotation shape and distinct probe selectors."""
    root = _mapping(manifest, "manifest")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise EvaluationError("manifest.schema_version must be 1")
    if root.get("dataset_id") not in ("baseline-v1", "challenge-v1"):
        raise EvaluationError("manifest.dataset_id must be baseline-v1 or challenge-v1")
    repositories = root.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise EvaluationError("manifest.repositories must be a nonempty list")

    repo_ids: set[str] = set()
    probe_ids: set[str] = set()
    selectors: set[tuple[object, ...]] = set()
    for repo_value in repositories:
        repo = _mapping(repo_value, "repository")
        repo_id = _text(repo.get("id"), "repository.id")
        if re.fullmatch(r"[a-z][a-z0-9_-]*", repo_id) is None:
            raise EvaluationError(f"{repo_id}: repository ID is not a safe directory name")
        if repo_id in repo_ids:
            raise EvaluationError(f"duplicate repository ID: {repo_id}")
        repo_ids.add(repo_id)
        url = _text(repo.get("https_url"), f"{repo_id}.https_url")
        parsed_url = urlsplit(url)
        if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.username:
            raise EvaluationError(f"{repo_id}.https_url must be an HTTPS repository URL")
        commit = repo.get("commit")
        if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise EvaluationError(f"{repo_id}.commit must be a 40-character lowercase Git SHA")
        probes = repo.get("probes")
        if not isinstance(probes, list) or not probes:
            raise EvaluationError(f"{repo_id}.probes must be a nonempty list")

        for probe_value in probes:
            probe = _mapping(probe_value, f"{repo_id}.probe")
            probe_id = _text(probe.get("id"), f"{repo_id}.probe.id")
            if probe_id in probe_ids:
                raise EvaluationError(f"duplicate probe ID: {probe_id}")
            probe_ids.add(probe_id)
            kind = probe.get("kind")
            if not isinstance(kind, str) or kind not in {
                "call", "reexport", "command_registration", "overload"
            }:
                raise EvaluationError(f"{probe_id}.kind is unsupported")
            file, line, _, _ = _evidence_fields(probe.get("evidence"), f"{probe_id}.evidence")
            _text(probe.get("rationale"), f"{probe_id}.rationale")

            if kind in {"call", "reexport"}:
                target = probe.get("expected_target")
                reason = probe.get("unresolved_reason")
                if target is not None:
                    _text(target, f"{probe_id}.expected_target")
                if reason is not None:
                    _text(reason, f"{probe_id}.unresolved_reason")
                has_target = target is not None
                has_reason = reason is not None
                if has_target == has_reason:
                    raise EvaluationError(
                        f"{probe_id} needs exactly one of expected_target and unresolved_reason"
                    )
                selector_name = ("caller", "expression") if kind == "call" else ("exported_name",)
                for field in selector_name:
                    _text(probe.get(field), f"{probe_id}.{field}")
                selector = ((repo_id, kind, file, probe["caller"], line) if kind == "call"
                            else (repo_id, kind, file, line, probe["exported_name"]))
            elif kind == "command_registration":
                _text(probe.get("parent_symbol"), f"{probe_id}.parent_symbol")
                _text(probe.get("callback_symbol"), f"{probe_id}.callback_symbol")
                if type(probe.get("expect_edge")) is not bool:
                    raise EvaluationError(f"{probe_id}.expect_edge must be Boolean")
                if not probe["expect_edge"]:
                    _text(probe.get("unresolved_reason"), f"{probe_id}.unresolved_reason")
                elif probe.get("unresolved_reason") is not None:
                    raise EvaluationError(f"{probe_id}.unresolved_reason conflicts with expect_edge")
                selector = (repo_id, kind, file, line)
            else:
                symbol_id = _text(probe.get("symbol_id"), f"{probe_id}.symbol_id")
                state = probe.get("expected_state")
                signatures = probe.get("expected_signatures")
                if not isinstance(state, str) or state not in {"resolved", "ambiguous"}:
                    raise EvaluationError(f"{probe_id}.expected_state is invalid")
                if (not isinstance(signatures, list)
                        or any(not isinstance(s, str) or not s.strip() for s in signatures)
                        or (state == "resolved" and not signatures)
                        or (state == "ambiguous" and signatures)):
                    raise EvaluationError(f"{probe_id}.expected_signatures is invalid")
                selector = (repo_id, kind, symbol_id)
            if selector in selectors:
                raise EvaluationError(f"{probe_id}: duplicate relation selector")
            selectors.add(selector)


def load_manifest(path: Path) -> dict[str, object]:
    """Read and validate the hand-reviewed probe manifest."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot load manifest {path}: {exc}") from exc
    validate_manifest_data(data)
    return data


def _score(
    expected: set[tuple[str, ...]], predicted: set[tuple[str, ...]]
) -> dict[str, int | float | None]:
    """Score predicted relations against the expected relation set."""
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
    }


def _probe_relations(
    probe: dict[str, object], scan: dict[str, object]
) -> dict[str, tuple[set[tuple[str, ...]], set[tuple[str, ...]]]]:
    """Project one annotated source site to comparable relationship sets."""
    probe_id = probe["id"]
    kind = probe["kind"]
    evidence = probe["evidence"]
    file = evidence["file"]
    line = evidence["start_line"]

    if kind == "call":
        caller = probe["caller"]
        sites = [item for item in scan["calls"]
                 if item["caller"] == caller and item["line"] == line]
        if (len(sites) != 1 or sites[0]["file"] != file
                or sites[0]["expression"] != probe["expression"]):
            raise EvaluationError(f"{probe_id}: call probe does not select one exact call site")
        expected = ({(probe_id, "call", caller, probe["expected_target"])}
                    if probe.get("expected_target") is not None else set())
        predicted = {
            (probe_id, "call", caller, edge["callee"])
            for edge in scan["call_edges"]
            if edge["caller"] == caller and edge["line"] == line
        }
        return {"call": (expected, predicted)}

    if kind == "reexport":
        name = probe["exported_name"]
        expected = ({(probe_id, "reexport", file, name, probe["expected_target"])}
                    if probe.get("expected_target") is not None else set())
        predicted = {
            (probe_id, "reexport", edge["source_file"], name, edge["target_symbol"])
            for edge in scan["semantic_edges"]
            if (edge["kind"] == "reexport" and edge["evidence_file"] == file
                and edge["line"] == line and edge["exported_name"] == name)
        }
        return {"reexport": (expected, predicted)}

    if kind == "command_registration":
        expected = ({(probe_id, "command_registration", probe["parent_symbol"],
                      probe["callback_symbol"])} if probe["expect_edge"] else set())
        predicted = {
            (probe_id, "command_registration", edge["source_symbol"], edge["target_symbol"])
            for edge in scan["semantic_edges"]
            if (edge["kind"] == "command_registration"
                and edge["evidence_file"] == file and edge["line"] == line)
        }
        return {"command_registration": (expected, predicted)}

    if kind == "overload":
        symbol_id = probe["symbol_id"]
        symbols = [item for item in scan["symbols"] if item["id"] == symbol_id]
        if len(symbols) > 1:
            raise EvaluationError(f"{probe_id}: duplicate canonical symbol in scan")
        implementation = (symbols[0] if symbols and symbol_id not in scan["ambiguous_symbols"]
                          else None)
        expected_resolution = ({(probe_id, "overload_resolution", symbol_id, symbol_id)}
                               if probe["expected_state"] == "resolved" else set())
        predicted_resolution = ({(probe_id, "overload_resolution", symbol_id, symbol_id)}
                                if implementation is not None else set())
        expected_signatures = {
            (probe_id, "overload_signature", symbol_id, signature)
            for signature in probe["expected_signatures"]
        }
        predicted_signatures = ({
            (probe_id, "overload_signature", symbol_id, item["signature"])
            for item in implementation["overloads"]
        } if implementation is not None else set())
        return {
            "overload_resolution": (expected_resolution, predicted_resolution),
            "overload_signature": (expected_signatures, predicted_signatures),
        }

    raise EvaluationError(f"{probe_id}: unsupported probe kind {kind}")


def _git_read(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise EvaluationError(f"cannot run Git in {repo}: {exc}") from exc
    if result.returncode != 0:
        raise EvaluationError(f"Git check failed in {repo}: {result.stderr.strip()}")
    return result.stdout.strip()


def validate_snapshot(repo: Path, expected_commit: str) -> None:
    """Require a clean Git checkout rooted at the expected immutable commit."""
    try:
        root = repo.resolve(strict=True)
    except OSError as exc:
        raise EvaluationError(f"repository checkout is absent: {repo}") from exc
    if not root.is_dir():
        raise EvaluationError(f"repository checkout is not a directory: {repo}")
    git_root = Path(_git_read(root, "rev-parse", "--show-toplevel")).resolve()
    if git_root != root:
        raise EvaluationError(f"repository path is not the Git checkout root: {repo}")
    actual_commit = _git_read(root, "rev-parse", "HEAD")
    if actual_commit != expected_commit:
        raise EvaluationError(
            f"repository {repo} is at {actual_commit}, expected {expected_commit}"
        )
    status = _git_read(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise EvaluationError(f"repository checkout has tracked/untracked changes: {repo}")


def preflight_repositories(
    manifest: dict[str, object], repos_root: Path
) -> dict[str, Path]:
    """Validate every source and checkout before starting any scanner process."""
    validate_manifest_data(manifest)
    roots: dict[str, Path] = {}
    for entry in manifest["repositories"]:
        repo_id = entry["id"]
        repo = repos_root / repo_id
        validate_snapshot(repo, entry["commit"])
        for probe in entry["probes"]:
            validate_evidence(repo, probe)
        roots[repo_id] = repo
    return roots


def scan_repository(project_root: Path, repo: Path) -> tuple[dict[str, object], float]:
    """Run the actual read-only Repo Doctor scan CLI and time its wall clock."""
    command = [sys.executable, "-m", "repo_doctor", "scan", str(repo), "--json"]
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command, cwd=project_root, capture_output=True, text=True,
            shell=False, check=False,
        )
    except OSError as exc:
        raise EvaluationError(f"cannot start Repo Doctor scan for {repo}: {exc}") from exc
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise EvaluationError(
            f"Repo Doctor scan failed for {repo} (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    try:
        scan = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"Repo Doctor scan returned invalid JSON for {repo}: {exc}") from exc
    if not isinstance(scan, dict) or type(scan.get("schema_version")) is not int \
            or scan["schema_version"] != 2:
        raise EvaluationError(f"Repo Doctor scan schema is not version 2 for {repo}")
    if not isinstance(scan.get("stats"), dict) or any(
        not isinstance(scan.get(key), list)
        for key in ("calls", "call_edges", "semantic_edges", "symbols", "ambiguous_symbols")
    ):
        raise EvaluationError(f"Repo Doctor scan output lacks required arrays for {repo}")
    return scan, elapsed


def canonical_scan_digest(scan: dict[str, object]) -> str:
    """Hash the complete scan JSON without depending on mapping key order."""
    encoded = json.dumps(scan, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_snapshot(
    repo_entry: dict[str, object], repo: Path, project_root: Path, runs: int
) -> dict[str, object]:
    """Repeat a repository scan and reject changes in its complete JSON output."""
    if type(runs) is not int or runs < 1:
        raise EvaluationError("runs must be a positive integer")
    scans = [scan_repository(project_root, repo) for _ in range(runs)]
    hashes = [canonical_scan_digest(scan) for scan, _ in scans]
    if len(set(hashes)) != 1:
        raise EvaluationError(f"{repo_entry['id']}: unstable scan output across runs")
    for probe in repo_entry.get("probes", []):
        if probe["kind"] == "call":
            _probe_relations(probe, scans[0][0])
    return {
        "scan": scans[0][0],
        "durations_seconds": [elapsed for _, elapsed in scans],
        "scan_hashes": hashes,
    }


_RELATION_FAMILIES = (
    "call", "reexport", "command_registration", "overload_resolution", "overload_signature"
)


def build_report(
    manifest: dict[str, object], results: list[dict[str, object]],
    repo_doctor_commit: str, runs: int,
) -> dict[str, object]:
    """Score only annotated relationships, retaining each probe's full evidence."""
    report: dict[str, object] = {
        "schema_version": 1,
        "dataset_id": manifest["dataset_id"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_doctor_commit": repo_doctor_commit,
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "runs": runs,
        "repositories": [],
    }
    for result in results:
        entry = result["entry"]
        scan = result["scan"]
        durations = result["durations_seconds"]
        families = {name: {"expected": set(), "predicted": set(),
                           "positive_probes": 0, "negative_probes": 0}
                    for name in _RELATION_FAMILIES}
        probe_details = []
        for probe in entry["probes"]:
            relations = _probe_relations(probe, scan)
            relation_details = {}
            for name, (expected, predicted) in relations.items():
                family = families[name]
                family["expected"].update(expected)
                family["predicted"].update(predicted)
                family["positive_probes" if expected else "negative_probes"] += 1
                relation_details[name] = {
                    "expected": [list(item) for item in sorted(expected)],
                    "predicted": [list(item) for item in sorted(predicted)],
                    "tp": [list(item) for item in sorted(expected & predicted)],
                    "fp": [list(item) for item in sorted(predicted - expected)],
                    "fn": [list(item) for item in sorted(expected - predicted)],
                }
            probe_details.append({
                "id": probe["id"], "kind": probe["kind"],
                "evidence": probe["evidence"], "rationale": probe["rationale"],
                "relations": relation_details,
            })
        metrics = {}
        for name, family in families.items():
            count = family["positive_probes"] + family["negative_probes"]
            metrics[name] = ({
                "status": "sampled", "positive_probes": family["positive_probes"],
                "negative_probes": family["negative_probes"],
                **_score(family["expected"], family["predicted"]),
            } if count else {"status": "not_sampled", "positive_probes": 0,
                             "negative_probes": 0, "tp": 0, "fp": 0, "fn": 0,
                             "precision": None, "recall": None})
        report["repositories"].append({
            "id": entry["id"], "https_url": entry["https_url"],
            "commit": entry["commit"], "stats": scan["stats"],
            "timing": {
                "runs_seconds": durations,
                "median_seconds": statistics.median(durations),
                "minimum_seconds": min(durations),
                "maximum_seconds": max(durations),
            },
            "scan_hashes": result["scan_hashes"],
            "metrics": metrics, "probes": probe_details,
        })
    return report


def render_markdown(report: dict[str, object]) -> str:
    """Show sampled metrics, mismatches, and timing without hiding empty ratios."""
    def cell(value: object) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value).replace("|", "\\|").replace("\n", " ")

    title = ("baseline" if report["dataset_id"] == "baseline-v1"
             else "challenge evaluation")
    lines = [f"# AI Repo Doctor V2 {title}", "",
             f"- Dataset: `{report['dataset_id']}`",
             f"- Generated: `{report['generated_at_utc']}`",
             f"- Analyzer commit: `{report['repo_doctor_commit']}`",
             f"- Python: `{cell(report['python_version'])}`",
             f"- Platform: `{cell(report['platform'])}` / `{cell(report['architecture'])}`", "",
             "Precision and recall below cover only the manually annotated probes,",
             "not every relation in a repository. Timing is comparable within the",
             "same environment; filesystem cache state is not controlled.", ""]
    for repo in report["repositories"]:
        lines.extend([
            f"## {repo['id']}", "",
            f"Source: {repo['https_url']} at `{repo['commit']}`", "",
            "| Relation | Status | Positive probes | Negative probes | TP | FP | FN | Precision | Recall |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for name in _RELATION_FAMILIES:
            item = repo["metrics"][name]
            fields = [name, item["status"], item["positive_probes"],
                      item["negative_probes"], item["tp"], item["fp"], item["fn"],
                      item["precision"], item["recall"]]
            lines.append("| " + " | ".join(cell(field) for field in fields) + " |")
        timing = repo["timing"]
        durations = ", ".join(cell(value) for value in timing["runs_seconds"])
        mismatches = [probe["id"] for probe in repo["probes"]
                      if any(values["fp"] or values["fn"]
                             for values in probe["relations"].values())]
        lines.extend(["", f"Scan seconds: {durations}",
                      f"Median {cell(timing['median_seconds'])}; "
                      f"minimum {cell(timing['minimum_seconds'])}; "
                      f"maximum {cell(timing['maximum_seconds'])}.",
                      f"Mismatched probes: {', '.join(mismatches) if mismatches else 'none'}.",
                      f"Scanner stats: `{json.dumps(repo['stats'], ensure_ascii=False, sort_keys=True)}`",
                      ""])
    return "\n".join(lines)


_BASELINE_PINS = {
    "click": ("https://github.com/pallets/click.git",
              "06b2a678741131fd577ce170e23e5ca0aeba0309"),
    "requests": ("https://github.com/psf/requests.git",
                 "611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60"),
    "flask": ("https://github.com/pallets/flask.git",
              "d73fa1cdcbd8b1465c151db8924ba58b1dd14e35"),
}

_DATASET_PINS = {
    "baseline-v1": _BASELINE_PINS,
    "challenge-v1": _BASELINE_PINS,
}


def validate_dataset_pins(manifest: dict[str, object]) -> None:
    """Keep every published dataset tied to its approved repository snapshots."""
    dataset_id = manifest["dataset_id"]
    if not isinstance(dataset_id, str):
        raise EvaluationError("manifest.dataset_id must be text")
    expected = _DATASET_PINS.get(dataset_id)
    if expected is None:
        raise EvaluationError(f"unsupported dataset ID: {dataset_id}")
    actual = {entry["id"]: (entry["https_url"], entry["commit"])
              for entry in manifest["repositories"]}
    if actual != expected:
        raise EvaluationError(f"{dataset_id} repository URLs or commits differ from approved pins")


def validate_baseline_pins(manifest: dict[str, object]) -> None:
    """Backward-compatible name for the original baseline pin validator."""
    validate_dataset_pins(manifest)


def _write_reports(outputs: list[tuple[Path, str]]) -> None:
    """Stage both reports and restore earlier destinations on a replace failure."""
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    installed: list[Path] = []
    try:
        for destination, content in outputs:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=destination.parent,
                prefix=f".{destination.name}.", delete=False,
            ) as handle:
                staged[destination] = Path(handle.name)
                handle.write(content)
        for destination, _ in outputs:
            if destination.exists():
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent, prefix=f".{destination.name}.backup.",
                    delete=False,
                ) as handle:
                    backups[destination] = Path(handle.name)
                shutil.copyfile(destination, backups[destination])
        for destination, _ in outputs:
            os.replace(staged[destination], destination)
            installed.append(destination)
    except OSError:
        for destination in reversed(installed):
            if destination in backups:
                os.replace(backups[destination], destination)
            else:
                destination.unlink(missing_ok=True)
        raise
    finally:
        for temporary in [*staged.values(), *backups.values()]:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate pinned Repo Doctor probes")
    parser.add_argument("--repos-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).resolve().parents[1] / "evaluation/baseline-v1.json")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.runs < 1:
            raise EvaluationError("runs must be positive")
        if args.json_out.resolve() == args.markdown_out.resolve():
            raise EvaluationError("JSON and Markdown output paths must differ")
        manifest = load_manifest(args.manifest)
        validate_dataset_pins(manifest)
        roots = preflight_repositories(manifest, args.repos_root)
        project_root = Path(__file__).resolve().parents[1]
        results = []
        for entry in manifest["repositories"]:
            results.append({"entry": entry, **evaluate_snapshot(
                entry, roots[entry["id"]], project_root, args.runs
            )})
        report = build_report(manifest, results, _git_read(project_root, "rev-parse", "HEAD"),
                              args.runs)
        _write_reports([
            (args.json_out, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
            (args.markdown_out, render_markdown(report)),
        ])
    except (EvaluationError, OSError) as exc:
        print(f"baseline evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
