"""Resolve only unique local ESM source dependencies in the selected index."""
from dataclasses import replace
import posixpath

from .model import AnalysisLimit, ImportEdge, RepoIndex
from .scanner import discover_files


def resolve_esm_graph(index: RepoIndex, *, resolve_calls: bool = True) -> None:
    # B1 deliberately does not connect ordinary calls.
    paths, _ = discover_files(index.root)
    path_set = set(paths)
    failed = {row.file for row in index.parse_errors}

    def target_for(file, specifier):
        if not specifier.startswith(("./", "../")) or "\\" in specifier:
            return None, "external-or-alias"
        candidate = posixpath.normpath(posixpath.join(posixpath.dirname(file), specifier))
        options = [candidate]
        if file.endswith(".ts") and specifier.endswith(".js"):
            stem = candidate[:-3]
            options = [stem + suffix for suffix in (".ts", ".tsx", ".d.ts", ".js", ".jsx")]
        matches = [path for path in options if path in path_set]
        if len(matches) == 1 and matches[0] in index.file_languages and matches[0] not in failed:
            target = matches[0]
            if index.file_languages[target] != "python":
                return target, "unique-local-source"
        return None, "ambiguous-or-unsupported-local-source"

    edges = set(index.import_edges)
    resolved = []
    for ref in [*index.esm_imports, *index.esm_exports]:
        if ref.specifier is None:
            continue
        target, reason = target_for(ref.file, ref.specifier)
        if target is not None:
            edges.add(ImportEdge(ref.file, target, ref.start_line))
        else:
            row = AnalysisLimit(ref.file, ref.start_line, reason, "Module " + ref.specifier + " was not resolved")
            if row not in index.analysis_limits:
                index.analysis_limits.append(row)
        if hasattr(ref, "resolved_file"):
            resolved.append(replace(ref, resolved_file=target, resolution_kind=reason))
    index.esm_imports = resolved
    index.import_edges = sorted(edges, key=lambda row: (row.source, row.target, row.line))
