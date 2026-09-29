"""Symbol search helpers for indexed repositories."""

from difflib import get_close_matches

from repo_doctor.model import RepoIndex, Symbol


def search_symbols(index: RepoIndex, query: str, limit: int = 20) -> list[dict]:
    """Find indexed symbols by name, qualified name, or id."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    normalized_query = query.strip().casefold()
    if not normalized_query:
        raise ValueError("query must not be empty")

    symbols = list(index.symbols.values())
    direct_matches = []
    for symbol in symbols:
        symbol_id = symbol.id.casefold()
        name = symbol.name.casefold()
        qualname = symbol.qualname.casefold()
        if not any(normalized_query in value for value in (symbol_id, name, qualname)):
            continue

        if normalized_query in (symbol_id, name):
            rank = 0
        elif symbol_id.startswith(normalized_query) or name.startswith(normalized_query):
            rank = 1
        else:
            rank = 2
        direct_matches.append((rank, symbol.id, symbol))

    if direct_matches:
        ordered_symbols = [
            symbol
            for _, _, symbol in sorted(direct_matches, key=lambda match: (match[0], match[1]))
        ]
    else:
        by_id = {}
        by_name = {}
        for symbol in symbols:
            by_id.setdefault(symbol.id.casefold(), []).append(symbol)
            by_name.setdefault(symbol.name.casefold(), []).append(symbol)

        candidate_ids = set()
        for candidate in get_close_matches(normalized_query, list(by_id), n=limit):
            candidate_ids.update(symbol.id for symbol in by_id[candidate])
        for candidate in get_close_matches(normalized_query, list(by_name), n=limit):
            candidate_ids.update(symbol.id for symbol in by_name[candidate])

        ordered_symbols = sorted(
            (symbol for symbol in symbols if symbol.id in candidate_ids),
            key=lambda symbol: symbol.id,
        )

    return [
        {
            "id": symbol.id,
            "file": symbol.file,
            "name": symbol.name,
            "qualname": symbol.qualname,
            "kind": symbol.kind,
            "start_line": symbol.start_line,
        }
        for symbol in ordered_symbols[:limit]
    ]
