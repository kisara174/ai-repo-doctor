import tempfile
import unittest
from pathlib import Path

from repo_doctor.evidence import validate_findings
from repo_doctor.index import build_index


class EvidenceTests(unittest.TestCase):
    def make_finding(self):
        return {
            "title": "Division by zero",
            "category": "reliability",
            "confidence": 0.9,
            "evidence": [
                {
                    "file": "app.py",
                    "start_line": 2,
                    "end_line": 2,
                    "quote": "return 1 / 0",
                    "symbol": "app.py::unsafe",
                }
            ],
            "reasoning": "The denominator is zero.",
            "impact": "Calling unsafe raises ZeroDivisionError.",
            "suggested_fix": "Use a nonzero denominator.",
        }

    def make_index(self, root):
        (root / "app.py").write_text(
            "def unsafe():\n    return 1 / 0\n\ndef safe():\n    return 1\n",
            encoding="utf-8",
        )
        return build_index(root)

    def test_accepts_exact_source_quote_and_matching_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))
            result = validate_findings(index, self.make_finding())

        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(result["rejected"], [])

    def test_rejects_false_evidence_with_specific_reasons(self):
        cases = [
            ({"file": "made_up.py"}, "scanned"),
            ({"file": "../app.py"}, "Unsafe"),
            ({"start_line": 99, "end_line": 99}, "range"),
            ({"quote": "return 2 / 0"}, "quote"),
            ({"symbol": "app.py::missing"}, "symbol"),
            ({"symbol": "app.py::safe"}, "overlap"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))
            for change, message in cases:
                with self.subTest(change=change):
                    finding = self.make_finding()
                    finding["evidence"][0].update(change)

                    result = validate_findings(index, finding)

                    self.assertEqual(result["accepted"], [])
                    self.assertIn(message.lower(), " ".join(result["rejected"][0]["reasons"]).lower())

    def test_rejects_malformed_confidence_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))
            finding = self.make_finding()
            finding["confidence"] = 1.5
            finding["evidence"] = []

            result = validate_findings(index, finding)

        self.assertEqual(result["accepted"], [])
        self.assertEqual(len(result["rejected"]), 1)
        self.assertIn("confidence", " ".join(result["rejected"][0]["reasons"]))
        self.assertIn("evidence", " ".join(result["rejected"][0]["reasons"]))

    def test_very_large_confidence_is_rejected_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))
            finding = self.make_finding()
            finding["confidence"] = 10**1000

            result = validate_findings(index, finding)

        self.assertEqual(result["accepted"], [])
        self.assertIn("confidence", " ".join(result["rejected"][0]["reasons"]))

    def test_rejects_source_file_replaced_by_symlink_after_scan(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            index = self.make_index(root)
            (root / "app.py").unlink()
            (Path(outside) / "app.py").write_text("def unsafe():\n    return 1 / 0\n", encoding="utf-8")
            (root / "app.py").symlink_to(Path(outside) / "app.py")

            result = validate_findings(index, self.make_finding())

        self.assertEqual(result["accepted"], [])
        self.assertIn("Unsafe", " ".join(result["rejected"][0]["reasons"]))
