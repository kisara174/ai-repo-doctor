"""Tests for analyzer Git-state checks used by evaluation commands."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.analyzer_provenance import (
    AnalyzerProvenanceError,
    analyzer_snapshot,
    require_clean_analyzer,
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class AnalyzerProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        git(self.root, "init", "-q")
        (self.root / ".gitignore").write_text(".local/\n", encoding="utf-8")
        (self.root / "app.py").write_text("value = 1\n", encoding="utf-8")
        git(self.root, "add", ".gitignore", "app.py")
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "Initial"],
            check=True,
        )
        self.commit = git(self.root, "rev-parse", "HEAD")

    def commit_empty(self, message: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", message],
            check=True,
        )

    def test_clean_repository_returns_full_head_and_clean_state(self):
        self.assertEqual(analyzer_snapshot(self.root), (self.commit, False))
        self.assertEqual(require_clean_analyzer(self.root), self.commit)

    def test_tracked_modification_is_dirty(self):
        (self.root / "app.py").write_text("value = 2\n", encoding="utf-8")

        self.assertEqual(analyzer_snapshot(self.root), (self.commit, True))
        with self.assertRaisesRegex(AnalyzerProvenanceError, "clean"):
            require_clean_analyzer(self.root)

    def test_untracked_source_is_dirty(self):
        (self.root / "new_module.py").write_text("value = 2\n", encoding="utf-8")

        self.assertEqual(analyzer_snapshot(self.root), (self.commit, True))
        with self.assertRaisesRegex(AnalyzerProvenanceError, "clean"):
            require_clean_analyzer(self.root)

    def test_ignored_local_artifact_does_not_make_repository_dirty(self):
        local = self.root / ".local"
        local.mkdir()
        (local / "result.json").write_text("{}\n", encoding="utf-8")

        self.assertEqual(analyzer_snapshot(self.root), (self.commit, False))
        self.assertEqual(require_clean_analyzer(self.root), self.commit)

    def test_head_change_during_generation_is_rejected_at_publish_check(self):
        starting_commit = require_clean_analyzer(self.root)
        self.commit_empty("Generated against another version")

        with self.assertRaisesRegex(AnalyzerProvenanceError, "changed"):
            require_clean_analyzer(self.root, expected_commit=starting_commit)


if __name__ == "__main__":
    unittest.main()
