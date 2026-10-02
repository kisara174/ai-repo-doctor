import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from repo_doctor.case import create_case, load_case
from repo_doctor.index import build_index


class CaseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'app.py').write_text('def broken(:\n', encoding='utf-8')
        self.source = self.base / 'case'
        self.case = create_case(build_index(self.repo), self.source)
        self.case['tool_version'] = '0.4.1'
        self.case['issues'][0]['title'] = '中文历史问题'
        self.raw = (json.dumps(self.case, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        (self.source / 'case.json').write_bytes(self.raw)
        self.old_report = (self.source / 'report.md').read_bytes()
        self.destination = self.base / 'archive'

    def run_module(self, source=None, destination=None):
        return subprocess.run([sys.executable, '-B', '-m', 'repo_doctor.case_recovery',
                               str(self.source if source is None else source), '--out',
                               str(self.destination if destination is None else destination)],
                              cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)

    def assert_original_unchanged(self):
        self.assertEqual((self.source / 'case.json').read_bytes(), self.raw)
        self.assertEqual((self.source / 'report.md').read_bytes(), self.old_report)

    def test_archive_keeps_source_bytes_history_and_permissions(self):
        result = self.run_module()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['status'], 'read-only-archive')
        self.assertEqual(receipt['source_sha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(receipt['source_tool_version'], '0.4.1')
        self.assertEqual((self.destination / 'original-case.json').read_bytes(), self.raw)
        report = (self.destination / 'recovered-report.md').read_text(encoding='utf-8')
        self.assertIn('中文历史问题', report)
        self.assertIn('S-001', report)
        self.assertIn('只读档案', report)
        for name, expected in receipt['files_sha256'].items():
            self.assertEqual(hashlib.sha256((self.destination / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o700)
        for path in self.destination.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assert_original_unchanged()

    def test_oversized_case_is_exportable_but_not_normally_loadable(self):
        self.case['padding'] = 'p' * (9 * 1024 * 1024)
        self.raw = json.dumps(self.case, ensure_ascii=False).encode('utf-8')
        (self.source / 'case.json').write_bytes(self.raw)
        with self.assertRaisesRegex(ValueError, 'exceeds 8 MiB'):
            load_case(self.source)
        result = self.run_module()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / 'original-case.json').read_bytes(), self.raw)
        self.assert_original_unchanged()

    def test_existing_output_and_symlink_are_preserved(self):
        external = self.base / 'external'
        external.mkdir()
        (external / 'keep.txt').write_text('keep')
        self.destination.symlink_to(external, target_is_directory=True)
        result = self.run_module()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((external / 'keep.txt').read_text(), 'keep')
        self.assert_original_unchanged()

    def test_output_inside_source_is_rejected_before_creation(self):
        out = self.source / 'archive'
        result = self.run_module(destination=out)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(out.exists())
        self.assert_original_unchanged()

    def test_source_link_is_rejected(self):
        link = self.base / 'case-link'
        link.symlink_to(self.source, target_is_directory=True)
        result = self.run_module(source=link)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.destination.exists())
        self.assert_original_unchanged()

    def test_invalid_json_is_rejected_without_output_or_traceback(self):
        (self.source / 'case.json').write_text('{')
        result = self.run_module()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.source / 'case.json').read_text(), '{')

    def test_recovery_read_limit_does_not_expand_normal_capacity(self):
        self.raw = b' ' * (32 * 1024 * 1024 + 1)
        (self.source / 'case.json').write_bytes(self.raw)
        result = self.run_module()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('32 MiB', result.stderr)
        self.assertFalse(self.destination.exists())
        self.assert_original_unchanged()

    def test_failed_write_never_publishes_success_receipt(self):
        from unittest.mock import patch
        from repo_doctor.case_recovery import export_archive
        # The actual filesystem write is exercised first; fail the second write
        # to model a full disk after the raw archive has been saved.
        from repo_doctor.case_recovery import _write_new
        def fail_second(path, content):
            if path.name == 'recovered-report.md':
                raise OSError('controlled disk failure')
            return _write_new(path, content)
        with patch('repo_doctor.case_recovery._write_new', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'controlled disk failure'):
                export_archive(self.source, self.destination)
        self.assertTrue((self.destination / 'original-case.json').exists())
        self.assertFalse((self.destination / 'recovery.json').exists())
        self.assert_original_unchanged()
