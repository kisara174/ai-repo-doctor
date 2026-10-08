"""Resource boundaries must fail the whole query, without weakening source safety."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from repo_doctor.agent_tools import build_overview
from repo_doctor.case import create_case, source_fingerprint
from repo_doctor.cli import main
from repo_doctor.context import build_context, build_impact
from repo_doctor.evidence import validate_findings
from repo_doctor.index import build_index
from repo_doctor.limits import AnalysisBudget, AnalysisLimitError, AnalysisLimits
from repo_doctor.repo_map import write_map
from repo_doctor.scanner import discover_files
from repo_doctor.source import read_source


class AnalysisLimitsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / 'repo'
        self.root.mkdir()
        self.code = b'def leaf():\n    return 1\n'
        (self.root / 'a.py').write_bytes(self.code)

    def limits(self, **changes):
        return replace(AnalysisLimits(), **changes)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = main(list(map(str, argv)))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_single_file_exact_limit_and_one_byte_over(self):
        size = len(self.code)
        index = build_index(self.root, limits=self.limits(max_file_bytes=size))
        self.assertIn('a.py::leaf', index.symbols)
        with self.assertRaisesRegex(AnalysisLimitError, f'max_file_bytes.*{size - 1}.*a.py'):
            build_index(self.root, limits=self.limits(max_file_bytes=size - 1))

    def test_raw_bytes_encoding_cookie_bom_crlf_and_unicode(self):
        raw = b'\xef\xbb\xbf# coding: utf-8\r\nx = "\xe4\xb8\xad"\r\n'
        (self.root / 'a.py').write_bytes(raw)
        budget = AnalysisBudget(self.limits(max_file_bytes=len(raw), max_total_bytes=len(raw)))
        self.assertIn('中', read_source(self.root, 'a.py', budget=budget))
        self.assertEqual(budget.read_bytes, len(raw))
        with self.assertRaisesRegex(AnalysisLimitError, 'max_total_bytes'):
            read_source(self.root, 'a.py', budget=budget)
        (self.root / 'a.py').write_bytes(b'# coding: latin-1\r\nx = "\xe9"\r\n')
        self.assertIn('é', read_source(self.root, 'a.py'))

    def test_long_first_line_never_uses_unbounded_read_or_encoding_probe(self):
        (self.root / 'a.py').write_bytes(b'#' + b'x' * 1000)
        import os
        real_fdopen = os.fdopen
        requested = []

        class Reader:
            def __init__(self, fd, mode):
                self.stream = real_fdopen(fd, mode)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def fileno(self):
                return self.stream.fileno()
            def read(self, count=-1):
                requested.append(count)
                if count < 0:
                    raise AssertionError('unbounded source read')
                return self.stream.read(count)
            def readline(self, *args):
                raise AssertionError('encoding probe before bounded read')

        with patch('repo_doctor.source.os.fdopen', Reader):
            with self.assertRaisesRegex(AnalysisLimitError, 'max_file_bytes'):
                read_source(self.root, 'a.py', budget=AnalysisBudget(self.limits(max_file_bytes=8)))
        self.assertEqual(requested, [9])

    def test_total_bytes_limit_is_order_independent_and_exact(self):
        (self.root / 'b.py').write_bytes(self.code)
        size = 2 * len(self.code)
        self.assertEqual(len(build_index(self.root, limits=self.limits(max_total_bytes=size)).files), 2)
        for paths in (['a.py', 'b.py'], ['b.py', 'a.py']):
            with self.subTest(paths=paths), patch('repo_doctor.index.discover_files', return_value=(paths, 'walk')):
                with self.assertRaisesRegex(AnalysisLimitError, 'max_total_bytes'):
                    build_index(self.root, limits=self.limits(max_total_bytes=size - 1))

    def test_selected_file_count_checked_before_parsing_and_ignores_other_files(self):
        (self.root / 'readme.txt').write_text('irrelevant')
        self.assertEqual(len(build_index(self.root, limits=self.limits(max_files=1)).files), 1)
        (self.root / 'b.py').write_bytes(self.code)
        with patch('repo_doctor.index.parse_python_file') as parse:
            with self.assertRaisesRegex(AnalysisLimitError, 'max_files.*1'):
                build_index(self.root, limits=self.limits(max_files=1))
            parse.assert_not_called()

    def test_each_index_has_a_fresh_budget(self):
        limits = self.limits(max_total_bytes=len(self.code))
        first, second = build_index(self.root, limits=limits), build_index(self.root, limits=limits)
        self.assertIsNot(first.budget, second.budget)
        self.assertEqual(first.budget.read_bytes, second.budget.read_bytes)

    def test_parse_errors_remain_parse_errors_and_valid_files_survive(self):
        (self.root / 'bad.py').write_text('def broken(:\n')
        index = build_index(self.root)
        self.assertEqual(len(index.parse_errors), 1)
        self.assertIn('a.py::leaf', index.symbols)

    def test_downstream_reads_do_not_reset_the_total_budget(self):
        for query in (source_fingerprint, build_overview,
                      lambda index: build_context(index, 'a.py::leaf')):
            with self.subTest(query=query):
                index = build_index(self.root, limits=self.limits(max_total_bytes=len(self.code)))
                with self.assertRaisesRegex(AnalysisLimitError, 'max_total_bytes'):
                    query(index)

    def test_map_and_case_budget_failure_leave_no_output_directory(self):
        for generate in (write_map, create_case):
            with self.subTest(generate=generate):
                index = build_index(self.root, limits=self.limits(max_total_bytes=len(self.code)))
                destination = self.root.parent / generate.__name__
                with self.assertRaisesRegex(AnalysisLimitError, 'max_total_bytes'):
                    generate(index, destination)
                self.assertFalse(destination.exists())

    def test_findings_does_not_relabel_limit_error_as_unsafe_path(self):
        index = build_index(self.root, limits=self.limits(max_total_bytes=len(self.code)))
        finding = {key: 'example' for key in ('title', 'category', 'reasoning', 'impact', 'suggested_fix')}
        finding.update(confidence=0.5, evidence=[{'file': 'a.py', 'start_line': 1, 'end_line': 1, 'quote': 'def leaf'}])
        with self.assertRaisesRegex(AnalysisLimitError, 'max_total_bytes'):
            validate_findings(index, finding)

    def test_path_symlink_and_changed_root_identity_still_rejected(self):
        (self.root / 'link.py').symlink_to(self.root / 'a.py')
        for path, identity in [('link.py', None), ('../outside.py', None), ('a.py', (-1, -1))]:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Unsafe source path'):
                read_source(self.root, path, identity, budget=AnalysisBudget())

    def test_git_timeouts_never_fall_back_to_walk(self):
        for operation in ('rev-parse', 'ls-files'):
            calls = []
            def git(argv, **kwargs):
                calls.append(kwargs['timeout'])
                if operation in argv:
                    raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
                return subprocess.CompletedProcess(argv, 0, str(self.root).encode() + b'\n')
            with self.subTest(operation=operation), patch('repo_doctor.scanner.subprocess.run', side_effect=git), patch('repo_doctor.scanner.os.walk') as walk:
                with self.assertRaisesRegex(AnalysisLimitError, 'git_timeout_seconds.*15'):
                    discover_files(self.root)
                self.assertTrue(all(value == 15 for value in calls))
                walk.assert_not_called()

    def test_git_listing_failure_is_actionable_value_error(self):
        ok = subprocess.CompletedProcess([], 0, str(self.root).encode() + b'\n')
        error = subprocess.CalledProcessError(128, ['git', 'ls-files'])
        with patch('repo_doctor.scanner.subprocess.run', side_effect=[ok, error]):
            with self.assertRaisesRegex(ValueError, 'Git.*ls-files'):
                discover_files(self.root)

    def test_cooperative_deadline_exact_then_over(self):
        current = [10.0]
        budget = AnalysisBudget(self.limits(index_timeout_seconds=2), clock=lambda: current[0])
        current[0] = 12.0
        budget.checkpoint('fixture')
        current[0] += 0.001
        with self.assertRaisesRegex(AnalysisLimitError, 'index_timeout_seconds.*cooperative'):
            budget.checkpoint('fixture')

    def test_deadline_is_checked_after_a_parser_finishes(self):
        from repo_doctor.parser import parse_python_file
        current = [0.0]
        def parse(*args, **kwargs):
            result = parse_python_file(*args, **kwargs)
            current[0] = 61.0
            return result
        with patch('repo_doctor.limits.time.monotonic', side_effect=lambda: current[0]), patch('repo_doctor.index.parse_python_file', side_effect=parse):
            with self.assertRaisesRegex(AnalysisLimitError, 'index_timeout_seconds'):
                build_index(self.root)

    def test_depth_limits_and_exact_ten_hop_result(self):
        (self.root / 'a.py').write_text('def f0():\n    pass\n' + ''.join(f'def f{i}():\n    f{i-1}()\n' for i in range(1, 12)))
        index = build_index(self.root)
        result = build_impact(index, 'a.py::f0', 10)
        self.assertEqual(max(item['distance'] for item in result['affected_symbols']), 10)
        self.assertNotIn('a.py::f11', [item['symbol'] for item in result['affected_symbols']])
        for depth in (0, 11):
            with self.subTest(depth=depth), self.assertRaisesRegex(ValueError, '1.*10'):
                build_impact(index, 'a.py::f0', depth)
            code, out, err = self.run_cli(['impact', self.root, 'a.py::f0', '--depth', depth, '--json'])
            self.assertEqual(code, 2)
            self.assertEqual(out, '')
            self.assertTrue(err)

    def test_all_five_commands_and_map_artifact_expose_limits(self):
        destination = self.root.parent / 'map'
        for argv in (['overview', self.root], ['symbols', self.root, '--query', 'leaf'],
                     ['context', self.root, 'a.py::leaf'], ['impact', self.root, 'a.py::leaf'],
                     ['map', self.root, '--out', destination]):
            code, out, err = self.run_cli([*argv, '--json'])
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)['resource_limits'], AnalysisLimits().as_dict())
        self.assertEqual(json.loads((destination / 'map.json').read_text())['resource_limits'], AnalysisLimits().as_dict())

    def test_cli_resource_failure_is_exit_two_without_snapshot_or_map(self):
        real_build_index = build_index
        def constrained(root, **kwargs):
            return real_build_index(root, **kwargs, limits=self.limits(max_total_bytes=len(self.code)))
        snapshot, destination = self.root.parent / 'snapshot.json', self.root.parent / 'map'
        with patch('repo_doctor.cli.build_index', side_effect=constrained):
            for argv in (['overview', self.root], ['context', self.root, 'a.py::leaf', '--snapshot-out', snapshot],
                         ['map', self.root, '--out', destination]):
                code, out, err = self.run_cli([*argv, '--json'])
                self.assertEqual(code, 2)
                self.assertEqual(out, '')
                self.assertIn('max_total_bytes', err)
                self.assertFalse(snapshot.exists())
                self.assertFalse(destination.exists())

    def test_legacy_api_wait_does_not_consume_analysis_deadline(self):
        from repo_doctor.deepseek import DeepSeekResult
        current = [0.0]
        def response(*args, **kwargs):
            current[0] = 61.0
            return DeepSeekResult('deepseek-chat', {'findings': []})
        with patch('repo_doctor.limits.time.monotonic', side_effect=lambda: current[0]), patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'fixture-only'}), patch('repo_doctor.cli.complete_json', side_effect=response):
            code, out, err = self.run_cli(['diagnose', self.root, 'a.py::leaf', '--json'])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['accepted'], [])

    def test_revision_timeout_does_not_leave_a_map(self):
        index = build_index(self.root)
        destination = self.root.parent / 'timeout-map'
        with patch('repo_doctor.scanner.subprocess.run', side_effect=subprocess.TimeoutExpired(['git'], 15)):
            with self.assertRaisesRegex(AnalysisLimitError, 'git_timeout_seconds'):
                write_map(index, destination)
        self.assertFalse(destination.exists())

    def test_map_reuses_initial_discovery(self):
        index = build_index(self.root)
        with patch('repo_doctor.repo_map.discover_files', side_effect=AssertionError('unexpected rescan')):
            write_map(index, self.root.parent / 'map')


@unittest.skipUnless(importlib.util.find_spec('tree_sitter'), 'requires JS extra')
class MixedLimitsTests(unittest.TestCase):
    setUp = AnalysisLimitsTests.setUp
    limits = AnalysisLimitsTests.limits
    def test_shared_total_and_file_count_across_languages(self):
        (self.root / 'b.ts').write_text('export function add() { return 1; }\n')
        total = len(self.code) + (self.root / 'b.ts').stat().st_size
        languages = ('python', 'typescript')
        self.assertEqual(len(build_index(self.root, languages=languages, limits=self.limits(max_total_bytes=total)).files), 2)
        for changes, reason in (({'max_total_bytes': total - 1}, 'max_total_bytes'), ({'max_files': 1}, 'max_files')):
            with self.subTest(changes=changes), self.assertRaisesRegex(AnalysisLimitError, reason):
                build_index(self.root, languages=languages, limits=self.limits(**changes))
        with self.assertRaisesRegex(AnalysisLimitError, 'max_file_bytes.*b.ts'):
            build_index(self.root, languages=languages, limits=self.limits(max_file_bytes=len(self.code)))
