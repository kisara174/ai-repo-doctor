import copy
import unittest

from repo_doctor.case import update_issue
from repo_doctor.report import repair_state


def record(phase, argv, status, source):
    return {'phase': phase, 'argv': argv, 'status': status,
            'source_fingerprint': source, 'source_fingerprint_after': source}


class RepairStateTests(unittest.TestCase):
    def make_issue(self):
        return {'id': 'A-001', 'human_status': 'resolved',
                'human_history': [{'status': 'resolved', 'related_test': True,
                                   'actor': 'codex', 'related_test_argv': ['check-a']}],
                'verification': [record('before', ['check-a'], 'failed', 'one'),
                                 record('after', ['check-a'], 'passed', 'two')]}

    def test_after_cannot_skip_latest_before_with_another_command(self):
        issue = self.make_issue()
        issue['verification'] += [record('before', ['check-b'], 'failed', 'three'),
                                  record('after', ['check-a'], 'passed', 'three')]
        self.assertEqual(repair_state(issue), '仍需复核')

    def test_changed_command_requires_its_own_related_confirmation(self):
        issue = self.make_issue()
        issue['verification'] += [record('before', ['check-b'], 'failed', 'three'),
                                  record('after', ['check-b'], 'passed', 'four')]
        self.assertEqual(repair_state(issue), '仍需复核')
        update_issue({'issues': [issue]}, 'A-001', 'resolved', 'B checks this issue',
                     related_test=True, actor='codex')
        self.assertEqual(issue['human_history'][-1]['related_test_argv'], ['check-b'])
        self.assertIn('Codex 确认关联', repair_state(issue))

    def test_legacy_single_command_does_not_rewrite_issue(self):
        issue = self.make_issue()
        del issue['human_history'][-1]['related_test_argv']
        original = copy.deepcopy(issue)
        self.assertIn('有修复证据', repair_state(issue))
        self.assertEqual(issue, original)

    def test_legacy_multiple_commands_need_confirmation_without_rewriting(self):
        issue = self.make_issue()
        del issue['human_history'][-1]['related_test_argv']
        issue['verification'] += [record('before', ['check-b'], 'failed', 'three'),
                                  record('after', ['check-b'], 'passed', 'four')]
        original = copy.deepcopy(issue)
        self.assertEqual(repair_state(issue), '仍需复核')
        self.assertEqual(issue, original)

    def test_same_command_new_cycle_keeps_its_association(self):
        issue = self.make_issue()
        issue['verification'] += [record('before', ['check-a'], 'failed', 'three'),
                                  record('after', ['check-a'], 'passed', 'four')]
        self.assertIn('有修复证据', repair_state(issue))

    def test_incomplete_or_unstable_pair_does_not_claim_repair(self):
        for change in ('no_before', 'latest_before', 'other_argv', 'source_changed', 'same_source'):
            with self.subTest(change=change):
                issue = self.make_issue()
                if change == 'no_before':
                    issue['verification'] = issue['verification'][1:]
                elif change == 'latest_before':
                    issue['verification'].append(record('before', ['check-a'], 'failed', 'three'))
                elif change == 'other_argv':
                    issue['verification'][-1]['argv'] = ['check-b']
                elif change == 'source_changed':
                    issue['verification'][-1]['source_fingerprint_after'] = 'three'
                else:
                    issue['verification'][-1]['source_fingerprint'] = 'one'
                    issue['verification'][-1]['source_fingerprint_after'] = 'one'
                self.assertEqual(repair_state(issue), '仍需复核')

    def test_failed_after_keeps_failure_state(self):
        issue = self.make_issue()
        issue['verification'][-1]['status'] = 'failed'
        self.assertEqual(repair_state(issue), '复查未通过')

    def test_related_confirmation_without_command_does_not_mutate_issue(self):
        issue = self.make_issue()
        issue['verification'] = []
        original = copy.deepcopy(issue)
        with self.assertRaisesRegex(ValueError, 'recorded.*command'):
            update_issue({'issues': [issue]}, 'A-001', 'resolved', 'No check yet', related_test=True)
        self.assertEqual(issue, original)
