"""Verify an installed base or JS preview using static CLI commands only.

This validator has no imports from the source checkout and never executes fixture code.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from xml.etree import ElementTree as ET

VERSION = "0.6.0a5"
FIXTURES = {'bad.js': 'export function broken( {\n', 'consumer.ts': "import {inc as step} from './core.js';\nexport function run() {\n  return step(2);\n}\n", 'core.js': 'export function add(a, b) {\n  return a + b;\n}\nexport const twice = value => add(value, value);\nexport class Box {\n  get() { return this.value; }\n}\nexport default function main() {\n  return twice(2);\n}\n', 'core.ts': 'export function inc(value: number): number {\n  return value + 1;\n}\nexport function entry(value: number): number {\n  return inc(value);\n}\nexport function overloaded(value: string): string;\nexport function overloaded(value: number): number;\nexport function overloaded(value: string | number): string | number {\n  return value;\n}\nexport class Counter {\n  next(value: number): number { return inc(value); }\n}\n', 'declarations.d.ts': 'export declare function onlyType(): void;\n', 'duplicate.ts': 'export function same() { return 1; }\nexport function same() { return 2; }\n', 'dynamic.js': 'export function entry(obj) {\n  return obj.run();\n}\nexport function later(name) {\n  return import(name);\n}\n', 'shadow.js': 'function add(value) { return value + 1; }\nexport function entry(add) {\n  return add(1);\n}\n', 'type_only.ts': "import type {inc} from './core.js';\nexport function bad() {\n  return inc(1);\n}\n", 'unicode.js': '// 中文与 emoji 😀\nexport function café(value) {\n  return value;\n}\n', 'unsupported.cjs': 'module.exports = () => 1;\n', 'unsupported.tsx': 'export const View = () => <div />;\n'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(mode, python, cli, out):
    require(all(p.is_absolute() for p in (python, cli, out)), "paths must be absolute")
    require(not out.exists() and not out.is_symlink(), "output already exists")
    out.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "DEEPSEEK_API_KEY"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    commands = []

    def run(name, argv, expected=0):
        argv = list(map(str, argv))
        start = time.monotonic()
        result = subprocess.run(argv, cwd=out, env=env, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
        record = dict(argv=argv, cwd=str(out), exit_code=result.returncode,
                      duration_seconds=time.monotonic()-start, stdout=result.stdout,
                      stderr=result.stderr)
        filename = f"{len(commands)+1:02d}-{name}.json"
        write(out / filename, record)
        commands.append(dict(name=name, record=filename, exit_code=result.returncode))
        require(result.returncode == expected, f"{name}: expected {expected}, see {filename}")
        return result

    def rd(name, *args, expected=0):
        return run(name, [cli, *args], expected)

    def data(name, *args):
        return json.loads(rd(name, *args, "--json").stdout)

    metadata = json.loads(run("metadata", [python, "-B", "-c",
        "import json,sys,importlib.util,repo_doctor; from importlib.metadata import version; "
        "print(json.dumps({'version':version('ai-repo-doctor'),'path':repo_doctor.__file__,"
        "'extras':{n:importlib.util.find_spec(n) is not None for n in "
        "('tree_sitter','tree_sitter_javascript','tree_sitter_typescript')},"
        "'loaded':[n for n in sys.modules if n.startswith('tree_sitter')]}))"]).stdout)
    require(metadata["version"] == VERSION, "wrong installed version")
    require("site-packages" in Path(metadata["path"]).parts, "source checkout imported")
    require(rd("version", "--version").stdout.strip() == "repo-doctor " + VERSION, "CLI version mismatch")
    rd("help", "--help")
    require(all(metadata["extras"].values()) if mode == "js" else not any(metadata["extras"].values()),
            "mode does not match actual optional dependencies")
    require(not metadata["loaded"], "base import eagerly loaded optional backend")

    repo = out / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def value():\n    return 1\ndef entry():\n    return value()\n", encoding="utf-8")
    for filename, text in FIXTURES.items():
        path = repo / "contract" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    unique = repo / "unique"
    unique.mkdir()
    for filename in ("core.ts", "consumer.ts", "type_only.ts"):
        (unique / filename).write_text(FIXTURES[filename], encoding="utf-8")
    before = {str(p.relative_to(repo)): digest(p) for p in repo.rglob("*") if p.is_file()}

    overview = data("python-overview", "overview", repo)
    require(overview["stats"]["python_files"] == 1, "default Python selection changed")
    matches = data("python-symbols", "symbols", repo, "--query", "value")["matches"]
    sid = next(row["id"] for row in matches if row["id"] == "app.py::value")
    data("python-context", "context", repo, sid)
    impact = data("python-impact", "impact", repo, sid)
    require(any(a["symbol"] == "app.py::entry" for a in impact["affected_symbols"]), "Python call lost")
    data("python-map", "map", repo, "--out", out / "python-map")

    if mode == "base":
        failure = rd("missing-extra", "overview", repo, "--languages", "javascript", expected=2)
        require("ai-repo-doctor[js]" in failure.stderr, "missing extra not explained")
    else:
        languages = "python,javascript,typescript"
        overview = data("mixed-overview", "overview", repo, "--languages", languages)
        require(overview["analysis"]["requested_languages"] == ["python", "javascript", "typescript"], "scope missing")
        require(overview["stats"]["parse_errors"], "bad syntax was silently accepted")
        matches = data("js-symbols", "symbols", repo, "--query", "contract/core.js", "--languages", languages)["matches"]
        ids = {row["id"] for row in matches}
        require({"contract/core.js::add", "contract/core.js::twice"} <= ids, "fixture IDs missing")
        sid = next(row["id"] for row in matches if row["id"] == "contract/core.js::add")
        context = data("js-context", "context", repo, sid, "--include-symbol", "contract/core.js::twice",
                       "--max-lines", "120", "--languages", languages)
        count = 0
        for block in context["blocks"]:
            lines = (repo / block["file"]).read_text(encoding="utf-8").splitlines()
            for line in block["lines"]:
                require(lines[line["line"]-1] == line["text"], "wrong context source line")
                count += 1
        require(count <= 120 and not context["budget_exhausted"], "context budget contract failed")
        impact = data("js-impact", "impact", repo, sid, "--depth", "2", "--languages", languages)
        require(impact["status"] == "bounded", "JS scope not bounded")
        require({"contract/core.js::twice", "contract/core.js::main"} <= {a["symbol"] for a in impact["affected_symbols"]},
                "finite reverse call path missing")
        for row in impact["affected_symbols"]:
            for hop in row["call_path_evidence"]:
                require(hop["line"] >= 1 and hop["file"] in before, "impact source evidence missing")
        ts = data("ts-symbols", "symbols", unique, "--query", "inc", "--languages", "typescript")["matches"]
        tsid = next(row["id"] for row in ts if row["id"] == "core.ts::inc")
        tsimpact = data("ts-impact", "impact", unique, tsid, "--languages", "typescript")
        require({a["symbol"] for a in tsimpact["affected_symbols"]} == {"consumer.ts::run", "core.ts::entry"}, "type-only call invented")
        require(next(a for a in tsimpact["affected_symbols"] if a["symbol"] == "consumer.ts::run")["call_path_evidence"][0]["line"] == 3, "wrong imported call line")
        empty = rd("empty-impact", "impact", unique, "consumer.ts::run", "--languages", "typescript").stdout
        require("empty results do not prove no impact" in empty, "empty impact overclaimed")
        mapping = data("mixed-map", "map", repo, "--languages", languages, "--out", out / "mixed-map")
        saved = json.loads(Path(mapping["map_json"]).read_text(encoding="utf-8"))
        require(saved["analysis"] == mapping["analysis"], "map scope mismatch")
        ids = {n["id"] for n in saved["views"]["relations"]["nodes"]}
        require({"file:app.py", "file:contract/core.js", "file:contract/core.ts"} <= ids, "mixed relation projection missing")
        for view in saved["views"].values():
            node_ids = {n["id"] for n in view["nodes"]}
            require(all(e["source"] in node_ids and e["target"] in node_ids for e in view["edges"]), "dangling map endpoint")
        rd("invalid-language", "overview", repo, "--languages", "auto", expected=2)
        forbidden = out / "forbidden" / "snapshot.json"
        rd("disabled-snapshot", "context", repo, sid, "--languages", languages,
           "--snapshot-out", forbidden, "--json", expected=2)
        require(not forbidden.parent.exists(), "rejected snapshot wrote artifacts")

    maps = {}
    for directory in (out / "python-map", out / "mixed-map"):
        if not directory.exists():
            continue
        require({p.name for p in directory.iterdir()} == {"map.json", "map.html", "structure.svg", "relations.svg"}, "wrong map files")
        for name in ("structure.svg", "relations.svg"):
            ET.parse(directory / name)
        maps[directory.name] = {p.name: digest(p) for p in directory.iterdir()}
    require(before == {str(p.relative_to(repo)): digest(p) for p in repo.rglob("*") if p.is_file()}, "target source modified")
    summary = dict(status="passed", mode=mode, version=VERSION, installed_metadata=metadata,
                   python=str(python), cli=str(cli), commands=commands, maps_sha256=maps,
                   source_fingerprint=overview["source_fingerprint"] if "source_fingerprint" in overview
                   else json.loads((out / ("mixed-map" if mode == "js" else "python-map") / "map.json").read_text())["repository"]["source_fingerprint"],
                   target_code_executed=False, target_sources_unchanged=True)
    write(out / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("base", "js"), required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = validate(args.mode, args.python, args.cli, args.out)
    except (ValueError, OSError, subprocess.TimeoutExpired, KeyError, StopIteration) as exc:
        parser.exit(2, f"Installed validation failed: {exc}\n")
    print(json.dumps({"status": summary["status"], "mode": args.mode, "version": VERSION}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
