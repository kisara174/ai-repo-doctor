import json
import unittest

from repo_doctor.diagnosis import build_diagnosis_prompts
from tools.diagnosis_prompt import build_evaluation_prompts


class DiagnosisPromptTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "symbol": "app.py::broken",
            "blocks": [{
                "symbol": "app.py::broken",
                "relation": "target",
                "file": "app.py",
                "start_line": 1,
                "end_line": 1,
                "truncated": False,
                "lines": [{"line": 1, "text": "return 1 / 0"}],
            }],
            "call_evidence": [],
        }

    def test_none_symptom_returns_exact_baseline_prompt(self):
        self.assertEqual(
            build_evaluation_prompts(self.context, None),
            build_diagnosis_prompts(self.context),
        )

    def test_symptom_is_separate_unverified_payload(self):
        symptom = "⬇️ is measured as one cell"
        baseline = build_diagnosis_prompts(self.context)

        system_prompt, user_prompt = build_evaluation_prompts(self.context, symptom)
        payload = json.loads(user_prompt)

        self.assertEqual(payload.pop("reported_symptom"), symptom)
        self.assertEqual(payload, json.loads(baseline[1]))
        self.assertIn("unverified", system_prompt)
        self.assertIn("untrusted", system_prompt)
        self.assertIn("reported behavior", system_prompt)


if __name__ == "__main__":
    unittest.main()
