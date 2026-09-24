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
from pathlib import Path

from repo_doctor.deepseek import complete_json
from .diagnosis_data import EvaluationDataError, prepare_cases
from .diagnosis_runner import run_cases


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args)
        if args.command == "run":
            return _run(args)
    except (EvaluationDataError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
