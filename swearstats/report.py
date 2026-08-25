"""Render a portable, dependency-free HTML dashboard."""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any


@cache
def _asset(name: str) -> str:
    """Read a dashboard asset shipped as package data."""
    asset = files("swearstats").joinpath("assets").joinpath(name)
    return asset.read_text(encoding="utf-8").strip()


def write_report(data: dict[str, Any], output: Path) -> None:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_document(payload), encoding="utf-8")


def _document(payload: str) -> str:
    style = _asset("dashboard.css")
    script = _asset("dashboard.js")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Agentic Swear Jar</title>
<style>
{style}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Local telemetry / zero judgment</div>
  <h1>Agentic<br><em>Swear Jar.</em></h1>
  <p class="lede">A field report from the moments when code fought back. <strong>The harness is a machine. No feelings were hurt.</strong></p>
  <div class="stamp">PROMPTS IN<br>NUMBERS<br>✦<br>100% LOCAL</div>
</header>
<nav class="tabs" id="tabs" aria-label="Data source"></nav>
<main class="grid" id="dashboard"></main>
<div class="privacy"><span>◉</span><span><strong>Private by construction.</strong> This file contains aggregate counts only. No prompt text, session IDs, or project paths are embedded.</span></div>
<footer><span id="period"></span><span id="generated"></span></footer>
</div>
<script id="report-data" type="application/json">{payload}</script>
<script>
{script}
</script>
</body>
</html>"""
