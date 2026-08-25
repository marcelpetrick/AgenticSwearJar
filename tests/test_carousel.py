from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

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

    def build(self, *, redact: bool = True) -> dict[str, object]:
        claude = self.write_jsonl(
            "claude.jsonl", [{"display": "what the heck", "timestamp": 1_725_235_200_000}]
        )
        codex = self.write_jsonl("codex.jsonl", [{"text": "blast it", "ts": 1_725_408_000}])
        sources = {"claude": claude, "codex": codex}
        data = serialize(analyze(sources.items(), self.lexicon), sources, len(self.lexicon))
        if redact:
            redact_terms(data)
        return data

    def test_renders_four_slides_from_a_redacted_report(self) -> None:
        rendered = carousel.render(self.build())

        self.assertEqual(rendered.count('<section class="slide">'), 4)
        self.assertIn("04 / 04", rendered)
        self.assertNotIn("heck", rendered)

    def test_refuses_to_render_unredacted_terms(self) -> None:
        with self.assertRaises(ValueError) as raised:
            carousel.render(self.build(redact=False))

        self.assertIn("unredacted", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
