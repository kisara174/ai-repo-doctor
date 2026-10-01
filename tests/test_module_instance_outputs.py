import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from repo_doctor.cli import main
from repo_doctor.context import build_context, build_impact
from repo_doctor.index import build_index


SOURCE = (
    "class Client:\n    def send(self):\n        return 1\n"
    "client = Client()\ndef run():\n    return client.send()\n"
    "def dynamic(obj):\n    return obj.send()\n"
)
CALLER = "app.py::run"
TARGET = "app.py::Client.send"
EVIDENCE = {
    "caller": CALLER, "callee": TARGET, "file": "app.py", "line": 6,
    "via_reexports": [],
}


class ModuleInstanceOutputTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / "app.py").write_text(SOURCE, encoding="utf-8")
        self.index = build_index(self.repo)

    def test_context_supplies_public_caller_with_source_evidence(self):
        context = build_context(self.index, TARGET)
        self.assertIn(EVIDENCE, context["call_evidence"])
        self.assertTrue(any(block["symbol"] == CALLER for block in context["blocks"]))
        self.assertFalse(any(edge["caller"] == "app.py::dynamic" for edge in context["call_evidence"]))

    def test_impact_follows_public_caller_without_guessing_dynamic_receiver(self):
        impact = build_impact(self.index, TARGET, depth=2)
        self.assertEqual(impact["affected_symbols"], [{
            "symbol": CALLER, "distance": 1, "path": [TARGET, CALLER],
            "call_path_evidence": [EVIDENCE],
        }])

    def test_focused_map_exports_same_call_and_keeps_unresolved_count(self):
        output = self.base / "map"
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main([
                "map", str(self.repo), "--out", str(output),
                "--symbol", TARGET, "--depth", "1", "--json",
            ])
        self.assertEqual(status, 0, stderr.getvalue())
        data = json.loads((output / "map.json").read_text())
        self.assertEqual(data["coverage"]["unresolved_calls"], 1)
        edges = [edge for edge in data["edges"] if edge["kind"] == "call"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["source"], f"symbol:{CALLER}")
        self.assertEqual(edges[0]["target"], f"symbol:{TARGET}")
        self.assertEqual(edges[0]["evidence"], [{"file": "app.py", "line": 6}])
        view = data["views"]["relations"]
        ids = {node["id"] for node in view["nodes"]}
        self.assertTrue({f"symbol:{CALLER}", f"symbol:{TARGET}"} <= ids)
        self.assertIn(edges[0], view["edges"])
        self.assertNotIn("symbol:app.py::dynamic", ids)
        for filename in ("map.html", "structure.svg", "relations.svg", "map.json"):
            self.assertTrue((output / filename).is_file(), filename)
        for filename in ("structure.svg", "relations.svg"):
            ET.parse(output / filename)


if __name__ == "__main__":
    unittest.main()
