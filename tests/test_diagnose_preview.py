import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_doctor.cli import main
from repo_doctor.context import build_context
from repo_doctor.deepseek import DeepSeekResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DiagnosePreviewTests(unittest.TestCase):
    def make_repo(self, root):
        (root / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")

    def run_main(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(["diagnose", *map(str, args)])
        return status, stdout.getvalue(), stderr.getvalue()

    def preview(self, root, *args):
        return subprocess.run(
            [sys.executable, "-m", "repo_doctor", "diagnose", str(root), "app.py::target", "--preview", *args],
            cwd=PROJECT_ROOT,
            env={**os.environ, "DEEPSEEK_API_KEY": ""},
            capture_output=True,
        )

    def test_preview_emits_exact_chat_body_hash_without_key_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            result = self.preview(root)

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        body = json.loads(result.stdout)
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        context = json.loads(body["messages"][1]["content"])
        self.assertEqual(context["blocks"][0]["lines"][1]["text"], "    return 1")
        digest = hashlib.sha256(result.stdout).hexdigest()
        self.assertIn(digest, result.stderr.decode())
        self.assertNotIn("DEEPSEEK_API_KEY is required", result.stderr.decode())

    def test_preview_matches_schema_protocol_body(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            result = self.preview(root, "--response-format", "json-schema")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        body = json.loads(result.stdout)
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertEqual(body["reasoning"], {"effort": "none"})
        self.assertEqual(body["input"][1]["role"], "user")
        self.assertIn(hashlib.sha256(result.stdout).hexdigest(), result.stderr.decode())

    def test_preview_bytes_match_actual_transport_for_both_protocols(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            for format_args in ((), ("--response-format", "json-schema")):
                with self.subTest(format_args=format_args):
                    preview = self.preview(root, *format_args)
                    self.assertEqual(preview.returncode, 0, preview.stderr.decode())
                    request_bodies = []

                    def fake_transport(request, timeout):
                        request_bodies.append(request.data)
                        if format_args:
                            envelope = {
                                "object": "response", "status": "completed", "model": "deepseek-flash",
                                "output": [{"type": "message", "role": "assistant", "content": [
                                    {"type": "output_text", "text": '{"findings": []}'},
                                ]}],
                            }
                        else:
                            envelope = {
                                "model": "deepseek-flash", "choices": [{
                                    "finish_reason": "stop", "message": {"content": '{"findings": []}'},
                                }],
                            }
                        return json.dumps(envelope).encode("utf-8")

                    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                        "repo_doctor.deepseek._read_response", side_effect=fake_transport
                    ):
                        status, stdout, stderr = self.run_main(
                            root, "app.py::target", *format_args,
                            "--expect-request-sha256", hashlib.sha256(preview.stdout).hexdigest(),
                            "--json",
                        )

                    self.assertEqual(status, 0, stderr)
                    self.assertEqual(json.loads(stdout)["accepted"], [])
                    self.assertEqual(request_bodies, [preview.stdout])

    def test_expected_hash_rejects_changed_source_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            preview = self.preview(root)
            digest = hashlib.sha256(preview.stdout).hexdigest()
            (root / "app.py").write_text("def target():\n    return 2\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json"
            ) as client:
                status, stdout, stderr = self.run_main(
                    root, "app.py::target", "--expect-request-sha256", digest
                )

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("request SHA-256", stderr)
        client.assert_not_called()

    def test_source_mutation_while_provider_runs_discards_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            def mutate_source(*args, **kwargs):
                (root / "app.py").write_text("def target():\n    return 2\n", encoding="utf-8")
                return DeepSeekResult("deepseek-flash", {"findings": []})

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json", side_effect=mutate_source
            ) as client:
                status, stdout, stderr = self.run_main(root, "app.py::target", "--json")

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Selected source changed", stderr)
        client.assert_called_once()

    def test_source_mutation_during_context_build_blocks_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            def build_then_mutate(*args):
                context = build_context(*args)
                (root / "app.py").write_text("def target():\n    return 2\n", encoding="utf-8")
                return context

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.build_context", side_effect=build_then_mutate
            ), patch("repo_doctor.cli.complete_json") as client:
                status, stdout, stderr = self.run_main(root, "app.py::target")

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Selected source changed", stderr)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
