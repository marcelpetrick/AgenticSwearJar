from __future__ import annotations

import contextlib
import io
import json
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


class CliEndToEndTests(unittest.TestCase):
    """Exercise the paths a user actually runs, not only the early failures."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.lexicon = self.root / "words.tsv"
        self.lexicon.write_text(
            "heck\theck\texpletive\t1\nblast\tblast\texpletive\t2\n", encoding="utf-8"
        )
        self.claude = self.write_jsonl(
            "claude.jsonl",
            [
                {"display": "what the heck", "timestamp": 1_725_235_200_000, "sessionId": "a"},
                {"display": "a calm question", "timestamp": 1_725_321_600_000, "sessionId": "a"},
            ],
        )
        self.codex = self.write_jsonl(
            "codex.jsonl", [{"text": "blast it", "ts": 1_725_408_000, "session_id": "b"}]
        )
        self.report = self.root / "out" / "report.html"
        self.json_output = self.root / "out" / "report.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_jsonl(self, name: str, rows: list[object]) -> Path:
        path = self.root / name
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def run_cli(self, *extra: str) -> tuple[int, str]:
        stdout = io.StringIO()
        argv = [
            "--claude-history",
            str(self.claude),
            "--codex-history",
            str(self.codex),
            "--lexicon",
            str(self.lexicon),
            "--replace-lexicon",
            "--output",
            str(self.report),
            *extra,
        ]
        with contextlib.redirect_stdout(stdout):
            status = main(argv)
        return status, stdout.getvalue()

    def test_writes_a_report_and_summarizes_both_sources(self) -> None:
        status, output = self.run_cli()

        self.assertEqual(status, 0)
        self.assertTrue(self.report.is_file())
        rendered = self.report.read_text(encoding="utf-8")
        self.assertIn("Agentic Swear Jar", rendered)
        self.assertIn("Scanned 3 prompts from 2 tools", output)
        self.assertIn("Claude Code:", output)
        self.assertIn("Codex CLI:", output)

    def test_json_output_mirrors_the_report_aggregates(self) -> None:
        status, _ = self.run_cli("--json", str(self.json_output))

        self.assertEqual(status, 0)
        data = json.loads(self.json_output.read_text(encoding="utf-8"))
        self.assertEqual(data["sources"]["all"]["totals"]["prompts"], 3)
        self.assertEqual(data["sources"]["all"]["totals"]["hits"], 2)
        self.assertNotIn("terms_redacted", data)

    def test_redact_terms_reaches_both_outputs(self) -> None:
        status, _ = self.run_cli("--redact-terms", "--json", str(self.json_output))

        self.assertEqual(status, 0)
        data = json.loads(self.json_output.read_text(encoding="utf-8"))
        self.assertTrue(data["terms_redacted"])
        self.assertNotIn("heck", json.dumps(data))
        self.assertNotIn("heck", self.report.read_text(encoding="utf-8"))

    def test_strict_inputs_fails_when_a_history_is_missing(self) -> None:
        self.codex = self.root / "absent.jsonl"

        status, _ = self.run_cli("--strict-inputs")

        self.assertEqual(status, 2)
        self.assertFalse(self.report.exists())

    def test_replace_lexicon_without_a_lexicon_is_rejected(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = main(
                [
                    "--claude-history",
                    str(self.claude),
                    "--codex-history",
                    str(self.codex),
                    "--replace-lexicon",
                    "--output",
                    str(self.report),
                ]
            )
        self.assertEqual(status, 2)
        self.assertFalse(self.report.exists())


if __name__ == "__main__":
    unittest.main()
