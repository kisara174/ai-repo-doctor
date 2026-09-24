"""Offline and online entry point for diagnosis evaluation tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .diagnosis_data import EvaluationDataError, prepare_cases


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evaluate_diagnosis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="validate samples and prepare offline contexts")
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--repos-root", required=True)
    prepare.add_argument("--model", required=True)
    prepare.add_argument("--max-lines", type=int, default=120)
    prepare.add_argument("--out-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            return _prepare(args)
    except (EvaluationDataError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
