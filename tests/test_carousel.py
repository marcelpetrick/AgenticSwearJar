from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import ModuleType

from swearstats import __version__
from swearstats.analyzer import analyze, load_lexicon, redact_terms, serialize

CAROUSEL_PATH = Path(__file__).resolve().parent.parent / "scripts" / "buildLinkedInCarousel.py"


def load_carousel() -> ModuleType:
    """Import the carousel builder, which lives outside the installable package."""
    spec = importlib.util.spec_from_file_location("buildLinkedInCarousel", CAROUSEL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


carousel = load_carousel()


class CarouselTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        lexicon_path = self.root / "words.tsv"
        lexicon_path.write_text(
            "heck\theck\texpletive\t1\nblast\tblast\texpletive\t2\n", encoding="utf-8"
        )
        self.lexicon = load_lexicon([lexicon_path])

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_jsonl(self, name: str, rows: list[object]) -> Path:
        path = self.root / name
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def build(
        self, *, redact: bool = True, both: bool = True, dated: bool = True
    ) -> dict[str, object]:
        claude_row: dict[str, object] = {"display": "what the heck"}
        codex_row: dict[str, object] = {"text": "blast it"}
        if dated:
            claude_row["timestamp"] = 1_725_235_200_000
            codex_row["ts"] = 1_725_408_000
        claude = self.write_jsonl("claude.jsonl", [claude_row])
        codex = self.write_jsonl("codex.jsonl", [codex_row])
        sources = {"claude": claude, "codex": codex} if both else {"codex": codex}
        data = serialize(analyze(sources.items(), self.lexicon), sources, len(self.lexicon))
        if redact:
            redact_terms(data)
        return data

    def test_renders_four_slides_from_a_redacted_report(self) -> None:
        rendered = carousel.render(self.build())

        self.assertEqual(rendered.count('<section class="slide">'), 4)
        self.assertIn("04 / 04", rendered)
        self.assertNotIn("heck", rendered)

    def test_every_slide_stamps_the_tool_version(self) -> None:
        rendered = carousel.render(self.build())

        stamp = f'<span class="stamp">swear-stats v{__version__}</span>'
        self.assertEqual(rendered.count(stamp), 4)

    def test_refuses_to_render_unredacted_terms(self) -> None:
        with self.assertRaises(ValueError) as raised:
            carousel.render(self.build(redact=False))

        self.assertIn("unredacted", str(raised.exception))

    def test_refuses_a_single_source_report(self) -> None:
        with self.assertRaises(ValueError) as raised:
            carousel.render(self.build(both=False))

        self.assertIn("claude", str(raised.exception))

    def test_refuses_a_report_without_an_observation_period(self) -> None:
        with self.assertRaises(ValueError) as raised:
            carousel.render(self.build(dated=False))

        self.assertIn("dated prompts", str(raised.exception))

    def test_cli_reports_a_rejected_input_without_writing_output(self) -> None:
        source = self.root / "report.json"
        source.write_text(json.dumps(self.build(both=False)), encoding="utf-8")
        target = self.root / "out" / "carousel.html"

        with unittest.mock.patch.object(
            sys, "argv", ["buildLinkedInCarousel", str(source), str(target)]
        ):
            status = carousel.main()

        self.assertEqual(status, 2)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
