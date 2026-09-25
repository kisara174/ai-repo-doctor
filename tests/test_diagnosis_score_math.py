import unittest

from tools.diagnosis_score_math import calculate_repeat_metrics


def make_counts(**changes):
    counts = {
        "accepted_tp": 1,
        "accepted_fp": 1,
        "uncertain": 1,
        "duplicate": 1,
        "accepted_count": 4,
        "rejected_count": 1,
        "detected_known_bug_cases": 1,
        "successful_bug_cases": 2,
        "all_requested_bug_cases": 3,
        "successful_control_cases_with_accepted_fp": 1,
        "successful_fixed_and_control_cases": 2,
        "failed_calls": 1,
        "rejected_true_positive": 1,
    }
    counts.update(changes)
    return counts


class DiagnosisScoreMathTests(unittest.TestCase):
    def test_calculates_hand_checked_counts_and_ratios(self):
        counts = make_counts()

        result = calculate_repeat_metrics(counts)

        self.assertEqual(result["counts"], counts)
        self.assertEqual(result["metrics"], {
            "precision": 1 / 2,
            "recall": 1 / 2,
            "end_to_end_detection": 1 / 3,
            "grounding_rate": 4 / 5,
            "control_false_alarm_rate": 1 / 2,
            "uncertain_rate": 1 / 5,
            "duplicate_rate": 1 / 5,
        })

    def test_empty_findings_and_no_requested_bug_cases_use_null_ratios(self):
        result = calculate_repeat_metrics(make_counts(
            accepted_tp=0,
            accepted_fp=0,
            uncertain=0,
            duplicate=0,
            accepted_count=0,
            rejected_count=0,
            detected_known_bug_cases=0,
            successful_bug_cases=0,
            all_requested_bug_cases=0,
            successful_control_cases_with_accepted_fp=0,
            successful_fixed_and_control_cases=0,
            failed_calls=0,
            rejected_true_positive=0,
        ))

        self.assertEqual(result["metrics"], {
            "precision": None,
            "recall": None,
            "end_to_end_detection": None,
            "grounding_rate": None,
            "control_false_alarm_rate": None,
            "uncertain_rate": None,
            "duplicate_rate": None,
        })

    def test_no_true_positive_gives_zero_precision_but_undefined_recall_without_success(self):
        result = calculate_repeat_metrics(make_counts(
            accepted_tp=0,
            accepted_fp=2,
            uncertain=0,
            duplicate=0,
            accepted_count=2,
            rejected_count=0,
            detected_known_bug_cases=0,
            successful_bug_cases=0,
            all_requested_bug_cases=3,
            successful_control_cases_with_accepted_fp=0,
            successful_fixed_and_control_cases=0,
            failed_calls=3,
            rejected_true_positive=0,
        ))

        self.assertEqual(result["metrics"]["precision"], 0.0)
        self.assertIsNone(result["metrics"]["recall"])
        self.assertEqual(result["metrics"]["end_to_end_detection"], 0.0)
        self.assertEqual(result["metrics"]["grounding_rate"], 1.0)
        self.assertIsNone(result["metrics"]["control_false_alarm_rate"])

    def test_rejects_missing_extra_boolean_or_negative_counts(self):
        counts = make_counts()
        malformed_inputs = [
            {key: value for key, value in counts.items() if key != "failed_calls"},
            {**counts, "unexpected": 0},
            {**counts, "failed_calls": True},
            {**counts, "failed_calls": -1},
        ]

        for malformed in malformed_inputs:
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    calculate_repeat_metrics(malformed)

    def test_all_rejected_findings_keep_precision_undefined(self):
        counts = dict.fromkeys(make_counts(), 0)
        counts.update(rejected_count=2, successful_bug_cases=1,
                      all_requested_bug_cases=1)
        metrics = calculate_repeat_metrics(counts)['metrics']
        self.assertIsNone(metrics['precision'])
        self.assertEqual(metrics['recall'], 0.0)
        self.assertEqual(metrics['end_to_end_detection'], 0.0)
        self.assertEqual(metrics['grounding_rate'], 0.0)
        self.assertEqual(metrics['uncertain_rate'], 0.0)
        self.assertEqual(metrics['duplicate_rate'], 0.0)
        self.assertIsNone(metrics['control_false_alarm_rate'])

    def test_uncertain_only_is_not_counted_as_false_positive(self):
        counts = dict.fromkeys(make_counts(), 0)
        counts.update(accepted_count=2, uncertain=2,
                      successful_bug_cases=1, all_requested_bug_cases=1)
        result = calculate_repeat_metrics(counts)
        self.assertIsNone(result['metrics']['precision'])
        self.assertEqual(result['metrics']['grounding_rate'], 1.0)
        self.assertEqual(result['metrics']['uncertain_rate'], 1.0)
        self.assertEqual(result['metrics']['recall'], 0.0)
        self.assertEqual(result['counts']['accepted_fp'], 0)

    def test_returned_counts_do_not_alias_caller_counts(self):
        counts = make_counts()
        result = calculate_repeat_metrics(counts)
        result['counts']['accepted_tp'] = 99
        self.assertEqual(counts['accepted_tp'], 1)
        counts['accepted_fp'] = 88
        self.assertEqual(result['counts']['accepted_fp'], 1)


if __name__ == "__main__":
    unittest.main()
