"""A skill must bind a verified installation and never replace user content."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from repo_doctor._version import __version__
from repo_doctor.cli import main
from repo_doctor.skills import export_skill


class SkillBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.cli = self.make_cli("CLI 工具 ' $value", f'repo-doctor {__version__}')
        self.destination = self.base / 'new skill'

    def make_cli(self, name, version, status=0):
        path = self.base / name
        path.write_text(f'#!{sys.executable}\nimport sys\n'
                        'assert sys.argv[1:] == ["--version"]\n'
                        f'print({version!r})\nraise SystemExit({status})\n')
        path.chmod(0o755)
        return path

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = main([str(arg) for arg in argv])
            except SystemExit as exc:
                status = exc.code
        return status, out.getvalue(), err.getvalue()

    def export(self, cli=None):
        return self.run_cli('skill', 'export', '--out', self.destination,
                            '--cli', self.cli if cli is None else cli)

    def test_bound_export_records_verified_absolute_cli_even_with_spaces_and_shell_characters(self):
        status, _, err = self.export()
        self.assertEqual(status, 0, err)
        binding = json.loads((self.destination / 'installation.json').read_text())
        self.assertEqual(binding, {'schema_version': 1, 'cli': str(self.cli), 'version': __version__})
        self.assertTrue((self.destination / 'SKILL.md').is_file())

    def test_symlink_entry_is_bound_to_versioned_target_not_mutable_alias(self):
        alias = self.base / 'repo-doctor'
        alias.symlink_to(self.cli)
        status, _, err = self.export(alias)
        self.assertEqual(status, 0, err)
        binding = json.loads((self.destination / 'installation.json').read_text())
        self.assertEqual(binding['cli'], str(self.cli))
        alias.unlink()
        alias.symlink_to(self.make_cli('old cli', 'repo-doctor 0.0.1'))
        self.assertEqual(binding['cli'], str(self.cli))

    def test_unbound_native_export_remains_supported(self):
        export_skill(self.destination)
        self.assertTrue((self.destination / 'SKILL.md').is_file())
        self.assertFalse((self.destination / 'installation.json').exists())

    def test_relative_cli_is_rejected_without_creating_export(self):
        status, _, err = self.export(Path('relative/bin/repo-doctor'))
        self.assertEqual(status, 2)
        self.assertIn('absolute', err.lower())
        self.assertFalse(self.destination.exists())

    def test_missing_or_nonexecutable_cli_is_rejected_without_creating_export(self):
        nonexecutable = self.base / 'not executable'
        nonexecutable.write_text('not a command')
        for cli in (self.base / 'missing', nonexecutable, self.base):
            with self.subTest(cli=cli):
                status, _, err = self.export(cli)
                self.assertEqual(status, 2)
                self.assertIn('executable', err.lower())
                self.assertFalse(self.destination.exists())

    def test_mismatched_version_is_rejected_without_creating_export(self):
        status, _, err = self.export(self.make_cli('wrong version', 'repo-doctor 99.0.0'))
        self.assertEqual(status, 2)
        self.assertIn('version', err.lower())
        self.assertFalse(self.destination.exists())

    def test_failed_version_command_is_rejected_without_creating_export(self):
        status, _, err = self.export(self.make_cli('failing command', f'repo-doctor {__version__}', 7))
        self.assertEqual(status, 2)
        self.assertIn('version', err.lower())
        self.assertFalse(self.destination.exists())

    def test_timed_out_version_command_is_rejected_without_creating_export(self):
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired([str(self.cli), '--version'], 5)):
            status, _, err = self.export()
        self.assertEqual(status, 2)
        self.assertIn('version', err.lower())
        self.assertFalse(self.destination.exists())

    def test_existing_directory_and_binding_are_not_replaced(self):
        self.destination.mkdir()
        sentinel = self.destination / 'installation.json'
        sentinel.write_bytes(b'user settings')
        status, _, err = self.export()
        self.assertEqual(status, 2)
        self.assertIn('already exists', err)
        self.assertEqual(sentinel.read_bytes(), b'user settings')
        self.assertFalse((self.destination / 'SKILL.md').exists())

    def test_broken_output_symlink_is_not_followed_or_replaced(self):
        target = self.base / 'do not create'
        self.destination.symlink_to(target, target_is_directory=True)
        status, _, err = self.export()
        self.assertEqual(status, 2)
        self.assertIn('already exists', err)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse(target.exists())

    def test_partial_write_failure_does_not_leave_a_success_looking_export(self):
        original = Path.open
        for failure in (OSError('controlled full disk'), UnicodeError('controlled encoding failure')):
            with self.subTest(failure=failure):
                def fail_binding(path, *args, **kwargs):
                    if path.name == 'installation.json':
                        raise failure
                    return original(path, *args, **kwargs)

                with patch.object(Path, 'open', fail_binding):
                    status, _, err = self.export()
                self.assertEqual(status, 2)
                self.assertIn(str(failure), err)
                self.assertFalse(self.destination.exists())
