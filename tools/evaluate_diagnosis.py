"""Offline and online entry point for diagnosis evaluation tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath

from repo_doctor.deepseek import complete_json
from .diagnosis_data import EvaluationDataError, _analyzer_commit, prepare_cases
from .diagnosis_runner import run_cases
from .diagnosis_score import make_review_template, render_report, score_records


def _read_manifest(path: Path) -> tuple[dict, str]:
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationDataError("cannot read a valid UTF-8 JSON manifest") from exc
    if not isinstance(manifest, dict):
        raise EvaluationDataError("manifest must be a JSON object")
    return manifest, hashlib.sha256(raw).hexdigest()


def _write_prepared(output: Path, prepared: dict) -> None:
    output = Path(output).absolute()
    if os.path.lexists(output):
        raise EvaluationDataError("output directory already exists")
    parent = output.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=parent))
    except OSError as exc:
        raise EvaluationDataError("cannot create prepared output directory") from exc
    try:
        for case_id, context in prepared["contexts"].items():
            (temporary / f"{case_id}.json").write_text(
                json.dumps(context, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        (temporary / "plan.json").write_text(
            json.dumps(prepared["plan"], ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if os.path.lexists(output):
            raise EvaluationDataError("output directory already exists")
        _analyzer_commit(expected_commit=prepared["plan"]["analyzer_commit"])
        os.rename(temporary, output)
    except OSError as exc:
        raise EvaluationDataError("cannot atomically publish prepared output") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _prepare(args: argparse.Namespace) -> int:
    output = Path(args.out_dir).absolute()
    if os.path.lexists(output):
        raise EvaluationDataError("output directory already exists")
    if not args.model.strip():
        raise EvaluationDataError("model must be nonempty text")
    manifest, manifest_hash = _read_manifest(Path(args.manifest))
    prepared = prepare_cases(
        manifest,
        Path(args.repos_root),
        args.model,
        args.max_lines,
        manifest_sha256=manifest_hash,
    )
    _write_prepared(output, prepared)
    print(f"Prepared {len(prepared['plan']['cases'])} cases in {output}")
    return 0


def _read_prepared_bundle(plan_dir: Path) -> tuple[dict, dict[str, dict]]:
    try:
        root = Path(plan_dir).resolve(strict=True)
        if not root.is_dir() or Path(plan_dir).is_symlink():
            raise EvaluationDataError("plan directory must be a real directory")
        plan_path = root / "plan.json"
        if plan_path.is_symlink() or not plan_path.is_file():
            raise EvaluationDataError("plan directory does not contain plan.json")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationDataError("cannot read a valid prepared plan") from exc
    if not isinstance(plan, dict) or not isinstance(plan.get("cases"), list):
        raise EvaluationDataError("prepared plan must contain a cases list")
    contexts = {}
    for case in plan["cases"]:
        if not isinstance(case, dict):
            raise EvaluationDataError("prepared plan contains an invalid case")
        case_id = case.get("id")
        if not isinstance(case_id, str) or re.fullmatch(r"[A-Za-z0-9_-]+", case_id) is None:
            raise EvaluationDataError("prepared plan contains an unsafe case ID")
        filename = f"{case_id}.json"
        if case.get("context_file") != filename:
            raise EvaluationDataError(f"{case_id}: unexpected context file path")
        context_path = root / filename
        if context_path.is_symlink() or not context_path.is_file():
            raise EvaluationDataError(f"{case_id}: prepared context is missing or is a symlink")
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise EvaluationDataError(f"{case_id}: cannot read a valid context JSON") from exc
        contexts[case_id] = context
    return plan, contexts


def _run(args: argparse.Namespace) -> int:
    if not args.allow_network:
        raise EvaluationDataError("--allow-network is required to call the provider")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key.strip():
        raise EvaluationDataError("DEEPSEEK_API_KEY is required")
    manifest, manifest_hash = _read_manifest(Path(args.manifest))
    plan, contexts = _read_prepared_bundle(Path(args.plan_dir))
    summary = run_cases(
        plan,
        contexts,
        Path(args.repos_root),
        repeats=args.repeats,
        max_calls=args.max_calls,
        api_key=api_key,
        client=complete_json,
        output_dir=Path(args.out_dir),
        manifest=manifest,
        manifest_sha256=manifest_hash,
    )
    print(
        f"Run {summary['state']}: {summary['attempted_calls']}/{summary['planned_calls']} "
        f"requests attempted in {args.out_dir}"
    )
    return 0 if summary["state"] == "complete" else 2


def _read_json_object(path: Path, label: str) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise EvaluationDataError(f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationDataError(f"cannot read a valid {label}") from exc
    if not isinstance(value, dict):
        raise EvaluationDataError(f"{label} must be a JSON object")
    return value


def _load_run_bundle(run_dir: Path) -> tuple[dict, list[dict], Path]:
    root = Path(run_dir)
    if root.is_symlink() or not root.is_dir():
        raise EvaluationDataError("run directory must be a real directory")
    root = root.resolve(strict=True)
    run = _read_json_object(root / "run.json", "run.json")
    record_files = run.get("record_files")
    if not isinstance(record_files, list):
        raise EvaluationDataError("run record_files must be a list")
    records_dir = root / "records"
    if records_dir.is_symlink() or not records_dir.is_dir():
        if record_files:
            raise EvaluationDataError("run records directory is missing or is a symlink")
    records = []
    for relative in record_files:
        if not isinstance(relative, str) or "\\" in relative:
            raise EvaluationDataError("run record_files contains an unsafe path")
        posix = PurePosixPath(relative)
        if (
            posix.is_absolute()
            or posix.as_posix() != relative
            or len(posix.parts) != 2
            or posix.parts[0] != "records"
            or re.fullmatch(r"[A-Za-z0-9_-]+\.json", posix.parts[1]) is None
        ):
            raise EvaluationDataError("run record_files contains an unsafe path")
        record_path = root / relative
        if record_path.is_symlink() or not record_path.is_file():
            raise EvaluationDataError("a listed run record is missing or is a symlink")
        try:
            record_path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError) as exc:
            raise EvaluationDataError("a listed run record escapes its run directory") from exc
        records.append(_read_json_object(record_path, "run record"))
    return run, records, root


def _stage_output(path: Path, content: str) -> Path:
    if Path(path).is_symlink():
        raise EvaluationDataError("output path cannot be a symlink")
    destination = Path(path).resolve(strict=False)
    if not destination.parent.is_dir():
        raise EvaluationDataError("output parent directory must already exist")
    if os.path.lexists(destination):
        raise EvaluationDataError("output file already exists; choose a new filename")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.tmp-", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return temporary
    except OSError as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise EvaluationDataError("cannot stage output file") from exc


def _publish_new_files(outputs: list[tuple[Path, str]]) -> None:
    if any(Path(path).is_symlink() for path, _ in outputs):
        raise EvaluationDataError("output paths cannot be symlinks")
    destinations = [Path(path).resolve(strict=False) for path, _ in outputs]
    if len(set(destinations)) != len(destinations):
        raise EvaluationDataError("output paths must be different")
    if any(os.path.lexists(path) for path in destinations):
        raise EvaluationDataError("output file already exists; choose new filenames")

    staged: list[Path] = []
    published: list[Path] = []
    try:
        for path, (_, content) in zip(destinations, outputs, strict=True):
            staged.append(_stage_output(path, content))
        for temporary, destination in zip(staged, destinations, strict=True):
            os.link(temporary, destination)
            published.append(destination)
    except OSError as exc:
        for destination in published:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        raise EvaluationDataError("cannot publish output files") from exc
    except BaseException:
        for destination in published:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        for temporary in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _prepare_review(args: argparse.Namespace) -> int:
    run, records, _ = _load_run_bundle(Path(args.run_dir))
    if run.get("state") == "running":
        raise EvaluationDataError("cannot prepare a review for a running experiment")
    if run.get("completed_calls") != len(records):
        raise EvaluationDataError("run completed_calls does not match listed records")
    review = make_review_template(records)
    review["run"] = run
    content = json.dumps(review, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    _publish_new_files([(Path(args.out_file), content)])
    print(f"Prepared {len(review['rows'])} review rows in {args.out_file}")
    return 0


def _score(args: argparse.Namespace) -> int:
    manifest, manifest_sha256 = _read_manifest(Path(args.manifest))
    run, records, _ = _load_run_bundle(Path(args.run_dir))
    review = _read_json_object(Path(args.review), "review file")
    if run.get("manifest_sha256") != manifest_sha256:
        raise EvaluationDataError("run manifest SHA-256 does not match the supplied manifest bytes")
    if not isinstance(review.get("run"), dict) or review["run"] != run:
        raise EvaluationDataError("review run metadata does not match run.json")
    report = score_records(manifest, records, review)
    rendered = render_report(report)
    json_content = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    _publish_new_files([
        (Path(args.json_out), json_content),
        (Path(args.markdown_out), rendered),
    ])
    print(f"Scored {report['totals']['completed_calls']} completed calls in {args.run_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evaluate_diagnosis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="validate samples and prepare offline contexts")
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--repos-root", required=True)
    prepare.add_argument("--model", required=True)
    prepare.add_argument("--max-lines", type=int, default=120)
    prepare.add_argument("--out-dir", required=True)
    run = subparsers.add_parser("run", help="send an explicitly authorized diagnosis evaluation")
    run.add_argument("--plan-dir", required=True)
    run.add_argument("--manifest", required=True)
    run.add_argument("--repos-root", required=True)
    run.add_argument("--out-dir", required=True)
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--max-calls", type=int, required=True)
    run.add_argument("--allow-network", action="store_true")
    prepare_review = subparsers.add_parser(
        "prepare-review", help="create a pending manual review template from a run"
    )
    prepare_review.add_argument("--run-dir", required=True)
    prepare_review.add_argument("--out-file", required=True)
    score = subparsers.add_parser("score", help="score a manually reviewed offline run")
    score.add_argument("--manifest", required=True)
    score.add_argument("--run-dir", required=True)
    score.add_argument("--review", required=True)
    score.add_argument("--json-out", required=True)
    score.add_argument("--markdown-out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args)
        if args.command == "run":
            return _run(args)
        if args.command == "prepare-review":
            return _prepare_review(args)
        if args.command == "score":
            return _score(args)
    except (EvaluationDataError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
