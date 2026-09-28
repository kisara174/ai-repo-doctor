import copy
import unittest

from tools.diagnosis_score import render_report


def presentation_fixture(completed, failed, state):
    keys = ('precision', 'recall', 'end_to_end_detection', 'grounding_rate',
            'control_false_alarm_rate', 'uncertain_rate', 'duplicate_rate')
    repeat = {
        'repeat_index': 1,
        'metrics': dict.fromkeys(keys, None),
        'metric_inputs': {k: {'numerator': 0, 'denominator': 0} for k in keys},
        'counts': dict.fromkeys(('accepted_count', 'rejected_count', 'uncertain',
                                'duplicate', 'rejected_true_positive'), 0),
        'samples': {'requested_bug_case_ids': [], 'detected_bug_case_ids': []},
        'latency_median_seconds': 2.0 if completed else None,
        'latency_values_seconds': [2.0] * completed,
        'missing_usage_records': completed,
        'observed_token_totals': {},
        'request_details': [],
    }
    repeat['counts']['failed_calls'] = failed
    return {
        'schema_version': 1, 'dataset_id': 'presentation-fixture',
        'manifest_sha256': 'a' * 64, 'plan_sha256': 'b' * 64,
        'analyzer_commit': 'c' * 40, 'requested_model': 'fixture',
        'response_models': ['fixture'] if completed > failed else [],
        'case_count': 2, 'case_ids': ['one', 'two'], 'repeats': 1,
        'run_state': state, 'by_repeat': [repeat], 'limitations': ['Fixture only.'],
        'totals': {
            'planned_calls': 2, 'attempted_calls': completed,
            'completed_calls': completed, 'failed_calls': failed,
            'unresolved_calls': 0, 'not_attempted_calls': 2 - completed,
            'call_failure_rate': failed / completed if completed else None,
            'call_failure_rate_inputs': {'numerator': failed, 'denominator': completed},
            'missing_usage_records': completed, 'observed_token_totals': {},
            'latency_median_seconds': 2.0 if completed else None,
        },
    }


class DiagnosisReportPresentationTests(unittest.TestCase):
    def test_no_success_is_explicit_for_unattempted_and_failed_runs(self):
        for completed, failed in ((0, 0), (1, 1), (2, 2)):
            with self.subTest(completed=completed):
                report = presentation_fixture(completed, failed, 'partial')
                text = render_report(report)
                self.assertIn('No successful model response was recorded; '
                              'quality conclusions are unavailable.', text)

    def test_partial_success_is_distinguished_from_no_success(self):
        text = render_report(presentation_fixture(1, 0, 'partial'))
        self.assertIn('This run is partial; unattempted requests are reported separately.', text)
        self.assertNotIn('No successful model response', text)

    def test_complete_success_has_no_partial_or_failure_banner(self):
        text = render_report(presentation_fixture(2, 0, 'complete'))
        self.assertNotIn('No successful model response', text)
        self.assertNotIn('This run is partial;', text)

    def test_elapsed_label_covers_repeat_and_totals_without_mutating_report(self):
        report = presentation_fixture(1, 1, 'partial')
        before = copy.deepcopy(report)
        text = render_report(report)
        self.assertEqual(text.count('Request elapsed median (including failed calls): 2.0000'), 2)
        self.assertNotIn('Latency median:', text)
        self.assertEqual(report, before)


if __name__ == '__main__':
    unittest.main()
