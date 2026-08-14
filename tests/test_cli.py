from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from swearstats import __version__
from swearstats.cli import main


class CliTests(unittest.TestCase):
    def test_prints_its_version_at_startup(self) -> None:
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(stdout):
            root = Path(temp)
            main(
                [
                    "--claude-history",
                    str(root / "missing-claude"),
                    "--codex-history",
                    str(root / "missing-codex"),
                    "--output",
                    str(root / "report.html"),
                ]
            )
        self.assertEqual(stdout.getvalue().splitlines()[0], f"swear-stats {__version__}")

    def test_requires_at_least_one_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            status = main(
                [
                    "--claude-history",
                    str(root / "missing-claude"),
                    "--codex-history",
                    str(root / "missing-codex"),
                    "--output",
                    str(root / "report.html"),
                ]
            )
            self.assertEqual(status, 2)
            self.assertFalse((root / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
