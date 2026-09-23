import subprocess
import tempfile
import unittest
from pathlib import Path

from repo_doctor.scanner import discover_python_files


class ScannerTests(unittest.TestCase):
    def test_git_scan_includes_tracked_and_untracked_but_obeys_ignore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("ignored.py\n.venv/\n", encoding="utf-8")
            (root / "tracked.py").write_text("pass\n", encoding="utf-8")
            (root / "new.py").write_text("pass\n", encoding="utf-8")
            (root / "ignored.py").write_text("pass\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "hidden.py").write_text("pass\n", encoding="utf-8")
            (root / "link.py").symlink_to(root / "tracked.py")
            subprocess.run(["git", "-C", str(root), "add", "tracked.py", "link.py"], check=True)

            files, mode = discover_python_files(root)

            self.assertEqual(mode, "git")
            self.assertEqual(files, ["new.py", "tracked.py"])

    def test_walk_scan_skips_generated_directories_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "module.py").write_text("pass\n", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "cache.py").write_text("pass\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "installed.py").write_text("pass\n", encoding="utf-8")
            (root / "link.py").symlink_to(root / "pkg" / "module.py")

            files, mode = discover_python_files(root)

            self.assertEqual(mode, "walk")
            self.assertEqual(files, ["pkg/module.py"])
