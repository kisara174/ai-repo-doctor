"""Build selected source indexes, resolving Python before adding ESM data."""

from dataclasses import replace
from pathlib import Path

from .limits import AnalysisBudget, AnalysisLimits
from .graph import resolve_graph
from .model import AnalysisLimit, RepoIndex
from .parser import parse_python_file
from .scanner import discover_files
from .languages import language_for_path, normalize_languages
from .semantics import resolve_semantic_edges


def build_index(root: Path, *, languages: tuple[str, ...] = ("python",),
                limits: AnalysisLimits | None = None) -> RepoIndex:
    budget = AnalysisBudget(limits)
    if not isinstance(languages, tuple) or not all(isinstance(name, str) for name in languages):
        raise ValueError("languages must be a tuple of source language names")
    languages = normalize_languages(",".join(languages))
    root = Path(root).resolve()
    root_stat = root.stat()
    root_identity = (root_stat.st_dev, root_stat.st_ino)
    paths, scan_mode = discover_files(root, budget=budget)
    selected = [path for path in paths if language_for_path(path) in languages]
    budget.checkpoint("selected file count")
    budget.check_file_count(len(selected))
    index = RepoIndex(root=root, scan_mode=scan_mode, root_identity=root_identity,
                      budget=budget, discovered_paths=tuple(paths))
    candidates_by_id = {}
    for path in selected:
        if language_for_path(path) != "python":
            continue
        index.file_languages[path] = "python"
        parsed = parse_python_file(root, path, root_identity=root_identity, budget=budget)
        budget.checkpoint(path)
        index.files.append(parsed.file)
        for symbol in parsed.symbols:
            candidates_by_id.setdefault(symbol.id, []).append(symbol)
        index.imports.extend(parsed.imports)
        index.calls.extend(parsed.calls)
        index.registration_calls.extend(parsed.registration_calls)
        index.attribute_rebindings.extend(parsed.attribute_rebindings)
        index.module_bindings[path] = parsed.module_bindings
        index.module_instances[path] = parsed.module_instances
        if parsed.error:
            index.parse_errors.append(parsed.error)
    for symbol_id, candidates in candidates_by_id.items():
        if len(candidates) == 1:
            index.symbols[symbol_id] = candidates[0]
            continue
        overload_candidates = [symbol for symbol in candidates if symbol.is_overload]
        concrete_candidates = [symbol for symbol in candidates if not symbol.is_overload]
        if (
            len(concrete_candidates) == 1
            and len(overload_candidates) == len(candidates) - 1
            and all(symbol.overload_signature is not None for symbol in overload_candidates)
        ):
            overload_signatures = tuple(
                symbol.overload_signature
                for symbol in sorted(overload_candidates, key=lambda candidate: candidate.start_line)
                if symbol.overload_signature is not None
            )
            index.symbols[symbol_id] = replace(concrete_candidates[0], overloads=overload_signatures)
        else:
            index.ambiguous_symbols.add(symbol_id)
    for symbol_id, symbol in list(index.symbols.items()):
        if any(f"{symbol.file}::{'.'.join(symbol.qualname.split('.')[:part])}" in index.ambiguous_symbols for part in range(1, len(symbol.qualname.split('.')))):
            del index.symbols[symbol_id]
            index.ambiguous_symbols.add(symbol_id)
    budget.checkpoint("Python graph")
    resolve_graph(index)
    budget.checkpoint("Python semantics")
    resolve_semantic_edges(index)
    index.analysis_languages = languages
    js_candidates = {}
    if any(language != "python" for language in languages):
        from .js_ts import parse_js_ts_file, _parser
        for language in languages:
            if language != "python":
                _parser(language)
        for path in paths:
            if path.endswith((".cjs", ".mts", ".cts", ".d.ts")):
                index.analysis_limits.append(AnalysisLimit(path, None, "unsupported-source-kind",
                    "Path is displayed but this source kind is not analyzed"))
        for path in selected:
            if language_for_path(path) == "python":
                continue
            data = parse_js_ts_file(root, path, root_identity=root_identity, budget=budget)
            budget.checkpoint(path)
            parsed = data.parsed
            index.files.append(parsed.file)
            index.file_languages[path] = language_for_path(path)
            index.calls.extend(parsed.calls)
            if parsed.error:
                index.parse_errors.append(parsed.error)
            for symbol in parsed.symbols:
                js_candidates.setdefault(symbol.id, []).append(symbol)
            index.esm_imports.extend(data.esm_imports)
            index.esm_exports.extend(data.esm_exports)
            index.identifier_uses.extend(data.identifier_uses)
            index.unsafe_js_bindings[path] = data.unsafe_bindings
            index.class_header_spans.update(data.class_header_spans)
            index.analysis_limits.extend(data.limits)
            index.js_top_level_symbols.update(data.top_level_symbols)
        for sid, candidates in js_candidates.items():
            if len(candidates) == 1:
                index.symbols[sid] = candidates[0]
            else:
                index.ambiguous_symbols.add(sid)
        for sid, symbol in list(index.symbols.items()):
            if any(f"{symbol.file}::{'.'.join(symbol.qualname.split('.')[:part])}" in index.ambiguous_symbols
                   for part in range(1, len(symbol.qualname.split('.')))):
                del index.symbols[sid]
                index.ambiguous_symbols.add(sid)
        from .esm import resolve_esm_graph
        budget.checkpoint("ESM graph")
        resolve_esm_graph(index)
    index.files.sort(key=lambda item: item.path)
    budget.checkpoint("index complete")
    return index
