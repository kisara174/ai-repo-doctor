"""Bounded, source-backed receipts for the six-question JS/TS experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time
from datetime import datetime, timezone


QUESTIONS = ("J1", "J2", "J3", "T1", "T2", "T3")
COMMANDS = ("overview", "symbols", "context", "impact", "map")
MAX_BYTES = 1024 * 1024
FIXTURES = {
    "core.js": "export function add(a, b) {\n  return a + b;\n}\nexport const twice = value => add(value, value);\nexport class Box {\n  get() { return this.value; }\n}\nexport default function main() {\n  return twice(2);\n}\n",
    "core.ts": "export function inc(value: number): number {\n  return value + 1;\n}\nexport function entry(value: number): number {\n  return inc(value);\n}\nexport function overloaded(value: string): string;\nexport function overloaded(value: number): number;\nexport function overloaded(value: string | number): string | number {\n  return value;\n}\nexport class Counter {\n  next(value: number): number { return inc(value); }\n}\n",
    "consumer.ts": "import {inc as step} from './core.js';\nexport function run() {\n  return step(2);\n}\n",
    "shadow.js": "function add(value) { return value + 1; }\nexport function entry(add) {\n  return add(1);\n}\n",
    "dynamic.js": "export function entry(obj) {\n  return obj.run();\n}\nexport function later(name) {\n  return import(name);\n}\n",
    "type_only.ts": "import type {inc} from './core.js';\nexport function bad() {\n  return inc(1);\n}\n",
    "unicode.js": "// 中文与 emoji 😀\nexport function café(value) {\n  return value;\n}\n",
    "bad.js": "export function broken( {\n",
    "duplicate.ts": "export function same() { return 1; }\nexport function same() { return 2; }\n",
    "unsupported.cjs": "module.exports = () => 1;\n",
    "unsupported.tsx": "export const View = () => <div />;\n",
    "declarations.d.ts": "export declare function onlyType(): void;\n",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inside(root: Path, value: str | Path) -> Path:
    path = Path(value).resolve()
    require(path.is_relative_to(root.resolve()), "evidence path escapes its root")
    return path


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
        cwd=root, text=True, timeout=30,
    )


def sources(evidence: Path) -> dict[str, dict]:
    data = read_json(evidence / "sources.json")
    items = {item["name"]: item for item in data["sources"]}
    require(set(items) == {"np", "ts-extras"}, "expected the two frozen repositories")
    for name, item in items.items():
        require(re.fullmatch(r"[0-9a-f]{40}", item["commit"]) is not None, "invalid commit")
        root = inside(evidence / "repos", item["root"])
        require(root.name == name, "repository path/name mismatch")
        require(git(root, "rev-parse", "HEAD").strip() == item["commit"], "source HEAD changed")
        require(not git(root, "status", "--porcelain").strip(), "target source was modified")
    return items


def check_protected(evidence: Path) -> None:
    for name, expected in read_json(evidence / "baseline.json")["protected_hashes"].items():
        require(digest(Path(name).read_bytes()) == expected, "protected file changed: " + name)


def check_oracle(evidence: Path) -> None:
    repos = sources(evidence)
    entries = read_json(evidence / "oracle.json")["questions"]
    require([q["id"] for q in entries] == list(QUESTIONS), "six question IDs/order required")
    symbol_sets = {name: set() for name in repos}
    edge_sets = {name: set() for name in repos}
    for entry in entries:
        item = repos[entry["repo"]]
        root = Path(item["root"])
        require(entry["baseline_steps"] and entry["reference_symbols"] and entry["source_evidence"],
                "oracle needs baseline, symbols and source evidence")
        for action in entry["baseline_steps"]:
            record = read_json(inside(evidence, action))
            require(record["exit_code"] == 0, "unsuccessful baseline action")
        for proof in entry["source_evidence"]:
            relative = proof["file"]
            require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "bad source path")
            raw = subprocess.check_output(["git", "show", item["commit"] + ":" + relative], cwd=root, timeout=30)
            require(digest(raw) == proof["file_sha256"], "oracle file hash mismatch")
            start, end = proof["start_line"], proof["end_line"]
            lines = raw.decode("utf-8-sig").splitlines()
            require(1 <= start <= end <= len(lines), "oracle line bounds mismatch")
            require("\n".join(lines[start - 1:end]) == proof["quote"], "oracle quote mismatch")
            expected_url = item["url"].removesuffix(".git") + "/blob/" + item["commit"] + "/" + relative
            require(proof["url"] == expected_url, "oracle commit URL mismatch")
        for symbol in entry["reference_symbols"]:
            require(symbol["id"] == symbol["file"] + "::" + symbol["qualname"], "oracle symbol ID mismatch")
            require(any(
                p["file"] == symbol["file"] and p["start_line"] <= symbol["start_line"]
                and p["end_line"] >= symbol["end_line"] for p in entry["source_evidence"]
            ), "symbol lacks source-span evidence")
            symbol_sets[entry["repo"]].add(symbol["id"])
        for edge in entry["reference_edges"]:
            require((root / edge["target"]).is_file(), "oracle target missing")
            require(any(p["file"] == edge["source"] and p["start_line"] <= edge["line"] <= p["end_line"]
                        for p in entry["source_evidence"]), "edge lacks source evidence")
            edge_sets[entry["repo"]].add((edge["source"], edge["target"]))
    require(all(len(ids) >= 3 for ids in symbol_sets.values()), "three reference symbols per repo required")
    require(all(len(edges) >= 2 for edges in edge_sets.values()), "two reference file edges per repo required")


def check_fixtures(root: Path) -> None:
    require(root.is_dir(), "fixture root missing")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(actual == set(FIXTURES), "expected exactly the twelve fixture files")
    for name, text in FIXTURES.items():
        path = root / name
        require(not path.is_symlink(), "fixture symlink rejected")
        require(path.read_bytes() == text.encode("utf-8"), "fixture content differs: " + name)


def bounded_run(argv: list[str], cwd: Path) -> dict:
    """Use the existing verification runner's selector/deadline pattern, with two pipes."""
    env_names = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "SYSTEMROOT")
    environment = {name: os.environ[name] for name in env_names if name in os.environ}
    start = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    output = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=False, start_new_session=True)
    except OSError:
        return {"argv": argv, "cwd": str(cwd), "started_at": started,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.monotonic() - start, "exit_code": None,
                "status": "command_error", "stdout": "", "stderr": "Could not start the command.",
                "truncated": False}
    timed_out = False
    deadline = start + 30

    def kill_group() -> None:
        process.poll()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        with selectors.DefaultSelector() as selector:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    timed_out = True
                    break
                for key, _ in selector.select(remaining_time):
                    try:
                        chunk = os.read(key.fd, 8192)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = output[key.data]
                    available = max(0, MAX_BYTES - len(buffer))
                    buffer.extend(chunk[:available])
                    truncated[key.data] |= len(chunk) > available
        if not timed_out:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
        if timed_out:
            kill_group()
            process.wait()
    finally:
        if process.poll() is None:
            kill_group()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    return {
        "argv": argv, "cwd": str(cwd), "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - start, 6), "exit_code": process.returncode,
        "status": "timeout" if timed_out else "passed" if process.returncode == 0 else "failed",
        "stdout": bytes(output["stdout"]).decode("utf-8", errors="replace"),
        "stderr": bytes(output["stderr"]).decode("utf-8", errors="replace"),
        "truncated": any(truncated.values()), "stream_truncated": truncated,
    }


def record(evidence: Path, question: str, producer: str, destination: Path, argv: list[str]) -> dict:
    require(question in QUESTIONS, "unknown question")
    baseline = read_json(evidence / "baseline.json")
    if producer == "stable":
        prefix = [baseline["stable_cli"]]
    elif producer == "spike":
        prefix = [str(evidence / "parser-venv/bin/python"), "-m", "experiments.js_ts.spike"]
    else:
        preview = read_json(evidence / "preview-cli.json")
        prefix = [preview["cli"]]
    require(argv[:len(prefix)] == prefix, "producer executable does not match frozen receipt")
    args = argv[len(prefix):]
    require(len(args) >= 2 and args[0] in COMMANDS, "only five static commands are allowed")
    repos = sources(evidence)
    repo_name = "np" if question.startswith("J") else "ts-extras"
    require(Path(args[1]).resolve() == Path(repos[repo_name]["root"]).resolve(), "wrong target repository")
    require("--" not in args and "--pre" not in args and "--snapshot-out" not in args,
            "unsupported command extension")
    if args[0] == "map":
        require("--out" in args, "map output must be explicit")
        target = inside(evidence, args[args.index("--out") + 1])
        require(not target.exists(), "map output already exists")
    destination = inside(evidence, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        result = bounded_run(argv, Path(baseline["worktree"]))
        result.update({"schema_version": 1, "question": question, "producer": producer})
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


def check_trial(evidence: Path) -> list[dict]:
    check_oracle(evidence)
    entries = read_json(evidence / "trial.json")["questions"]
    require([q["id"] for q in entries] == list(QUESTIONS), "trial requires six questions")
    for entry in entries:
        require(entry["status"] in {"answered", "bounded", "blocked"}, "invalid trial status")
        if entry["status"] == "blocked":
            require(entry["remaining_limits"] and entry["blocker_evidence"], "blocked trial lacks evidence")
            for path in entry["blocker_evidence"]:
                require(inside(evidence, path).is_file(), "missing blocker evidence")
            continue
        require(entry["command_records"] and entry["source_evidence"], "trial lacks command/source records")
        for path in entry["command_records"]:
            result = read_json(inside(evidence, path))
            require(result["question"] == entry["id"] or path in entry["reused_records"],
                    "cross-question reuse must be explicit")
            require(result["status"] == "passed" and result["exit_code"] == 0
                    and not result["truncated"] and result["duration_seconds"] < 30,
                    "unsuccessful command cannot be accepted")
        for step in entry["baseline_steps"] + entry["trial_steps"]:
            require(inside(evidence, step).is_file(), "missing action record")
    check_protected(evidence)
    return entries


def check_gate(evidence: Path) -> None:
    entries = check_trial(evidence)
    gate = read_json(evidence / "gate.json")
    require(gate["decision"] in {"go", "no-go"}, "invalid gate decision")
    checks = gate["checks"]
    require(len(checks) == 5 and all(type(c["met"]) is bool for c in checks), "five boolean gates required")
    for check in checks:
        require(check["evidence_paths"], "gate needs evidence paths")
        for path in check["evidence_paths"]:
            require(inside(evidence, path).is_file(), "missing gate evidence")
    if gate["decision"] == "go":
        require(all(c["met"] for c in checks), "go requires all five checks")
        answered = [q for q in entries if q["status"] == "answered"]
        require(len(answered) >= 4 and all(
            sum(q["repo"] == name for q in answered) >= 2 for name in ("np", "ts-extras")
        ), "answer gate not met")
        require(all(any(
            q["repo"] == name and len(q["baseline_steps"]) - len(q["trial_steps"]) >= 1
            for q in entries if q["status"] != "blocked"
        ) for name in ("np", "ts-extras")), "observed action benefit not met")
    else:
        require(not all(c["met"] for c in checks) and gate["reason"], "no-go needs a failed gate and reason")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check-sources", "check-oracle", "check-trial", "check-gate"):
        child = sub.add_parser(name)
        child.add_argument("--evidence-root", type=Path, required=True)
    fixture = sub.add_parser("check-fixtures")
    fixture.add_argument("--root", type=Path, required=True)
    child = sub.add_parser("record")
    child.add_argument("--evidence-root", type=Path, required=True)
    child.add_argument("--question", choices=QUESTIONS, required=True)
    child.add_argument("--producer", choices=("stable", "spike", "preview"), required=True)
    child.add_argument("--out", type=Path, required=True)
    child.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == "check-fixtures":
            check_fixtures(args.root)
        elif args.command == "record":
            argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            result = record(args.evidence_root.resolve(), args.question, args.producer, args.out, argv)
            print(json.dumps({"record": str(args.out), "status": result["status"],
                              "exit_code": result["exit_code"], "truncated": result["truncated"]}))
            return 0 if result["status"] == "passed" and not result["truncated"] else 1
        else:
            {"check-sources": sources, "check-oracle": check_oracle,
             "check-trial": check_trial, "check-gate": check_gate}[args.command](args.evidence_root.resolve())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(str(error))
        return 1
    print(json.dumps({"status": "passed", "check": args.command}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
