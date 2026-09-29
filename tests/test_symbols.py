import unittest
from pathlib import Path

from repo_doctor.model import RepoIndex, Symbol
from repo_doctor.symbols import search_symbols


def make_symbol(symbol_id, name, qualname=None, file="src/app.py", start_line=1):
    return Symbol(
        id=symbol_id,
        file=file,
        name=name,
        qualname=qualname or name,
        kind="function",
        start_line=start_line,
        end_line=start_line,
        parent=None,
    )


def make_index(*symbols):
    return RepoIndex(
        root=Path("."),
        scan_mode="test",
        root_identity=(0, 0),
        symbols={symbol.id: symbol for symbol in symbols},
    )


class SearchSymbolsTests(unittest.TestCase):
    def test_matches_id_name_and_qualname_case_insensitively(self):
        index = make_index(
            make_symbol("src/Parser.py::parse", "parse", "Parser.parse", start_line=10),
            make_symbol("src/main.py::run", "run", "main.run", start_line=20),
        )

        self.assertEqual(
            ["src/Parser.py::parse"],
            [item["id"] for item in search_symbols(index, "PARSER.PARSE")],
        )
        self.assertEqual(
            ["src/Parser.py::parse"],
            [item["id"] for item in search_symbols(index, "PARSER.PY")],
        )
        self.assertEqual(
            ["src/main.py::run"],
            [item["id"] for item in search_symbols(index, "MAIN.RUN")],
        )

    def test_orders_exact_then_prefix_then_substring_and_id(self):
        index = make_index(
            make_symbol("z/mod.py::needle", "needle_tail"),
            make_symbol("b/mod.py::needles", "other"),
            make_symbol("c/mod.py::needle_exact", "needle"),
            make_symbol("a/mod.py::needle_exact", "other"),
        )

        self.assertEqual(
            [
                "c/mod.py::needle_exact",
                "z/mod.py::needle",
                "a/mod.py::needle_exact",
                "b/mod.py::needles",
            ],
            [item["id"] for item in search_symbols(index, "needle")],
        )

    def test_returns_only_requested_symbol_fields_and_obeys_limit(self):
        index = make_index(
            make_symbol("a.py::find_one", "find_one", "mod.find_one", start_line=3),
            make_symbol("b.py::find_two", "find_two", "mod.find_two", start_line=7),
        )

        results = search_symbols(index, "find", limit=1)

        self.assertEqual(1, len(results))
        self.assertEqual(
            {"id", "file", "name", "qualname", "kind", "start_line"},
            set(results[0]),
        )
        self.assertEqual(3, results[0]["start_line"])

    def test_empty_query_and_invalid_limits_raise_value_error(self):
        index = make_index(make_symbol("a.py::run", "run"))

        for query in ("", "   "):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    search_symbols(index, query)

        for limit in (0, 101):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    search_symbols(index, "run", limit=limit)

    def test_fuzzy_fallback_returns_deduplicated_sorted_candidates(self):
        index = make_index(
            make_symbol("z.py::calculate_total", "calculate_total", "z.calculate_total"),
            make_symbol("a.py::calculate_total", "calculate_total", "a.calculate_total"),
        )

        results = search_symbols(index, "calculte_total")

        self.assertEqual(
            ["a.py::calculate_total", "z.py::calculate_total"],
            [item["id"] for item in results],
        )

    def test_no_match_returns_empty_candidates(self):
        index = make_index(make_symbol("a.py::run", "run"))

        self.assertEqual([], search_symbols(index, "zzzzzzzzzzzz"))


if __name__ == "__main__":
    unittest.main()
