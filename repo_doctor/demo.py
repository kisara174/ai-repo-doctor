"""A controlled, offline repository for the installed CLI walkthrough."""

from pathlib import Path


_FILES = {
    "app.py": "def answer(:\n    return 42\n",
    "test_regression.py": (
        "import unittest\n"
        "from app import answer\n\n"
        "class AnswerTests(unittest.TestCase):\n"
        "    def test_answer(self):\n"
        "        self.assertEqual(answer(), 42)\n"
    ),
}


def create_demo(directory: Path) -> None:
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("demo directory is a symlink")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise ValueError("demo directory already exists or is not empty")
    else:
        directory.mkdir(parents=True)
    for name, content in _FILES.items():
        (directory / name).write_text(content, encoding="utf-8")
