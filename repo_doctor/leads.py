"""Deterministic source-backed entries for a human repository review."""

from collections import defaultdict

from .model import RepoIndex


def build_review_leads(index: RepoIndex, static_issues: list[dict]) -> list[dict]:
    """Order coverage blockers, import cycles, then shared call targets."""
    leads = []
    for issue in static_issues:
        if issue["category"] == "parse_error":
            review_order = 1
            next_step = "Inspect the reported syntax line, then rescan the repository."
        elif issue["category"] == "import_cycle":
            review_order = 2
            next_step = "Inspect the listed import edges if initialization order matters."
        else:
            continue
        leads.append({
            "kind": issue["category"],
            "review_order": review_order,
            "subject": issue["title"],
            "issue_id": issue["id"],
            "reason": issue["reasoning"],
            "next_step": next_step,
            "evidence": issue["evidence"],
        })

    test_files = {item.path for item in index.files if item.is_test}
    callers_by_target: dict[str, dict[str, int]] = defaultdict(dict)
    for edge in index.call_edges:
        if edge.caller in index.ambiguous_symbols or edge.callee in index.ambiguous_symbols:
            continue
        caller = index.symbols.get(edge.caller)
        target = index.symbols.get(edge.callee)
        if (
            caller is None or target is None or caller.id == target.id
            or caller.file in test_files or target.file in test_files
            or target.kind not in {"function", "method"}
        ):
            continue
        earlier = callers_by_target[target.id].get(caller.id)
        if earlier is None or edge.line < earlier:
            callers_by_target[target.id][caller.id] = edge.line

    shared_targets = sorted(
        ((target_id, callers) for target_id, callers in callers_by_target.items()
         if len(callers) >= 3),
        key=lambda item: (-len(item[1]), item[0]),
    )[:5]
    for target_id, callers in shared_targets:
        evidence = sorted(
            ({"file": index.symbols[caller_id].file, "start_line": line,
              "end_line": line, "caller": caller_id}
             for caller_id, line in callers.items()),
            key=lambda item: (item["file"], item["start_line"], item["caller"]),
        )
        leads.append({
            "kind": "shared_call_target",
            "review_order": 3,
            "subject": target_id,
            "caller_count": len(callers),
            "reason": "This symbol has at least three distinct resolved production callers; this is an impact entry, not evidence of a defect.",
            "next_step": "Inspect the listed callers before changing this symbol; use impact for indirect paths.",
            "evidence": evidence,
        })
    return leads
