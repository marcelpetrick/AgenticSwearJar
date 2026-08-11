#!/usr/bin/env python3
"""Build a four-slide LinkedIn carousel from a redacted aggregate report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def number(value: int | float) -> str:
    return f"{value:,.0f}"


def term_rows(terms: list[dict[str, Any]]) -> str:
    selected = terms[:5]
    maximum = max((entry["count"] for entry in selected), default=1)
    return "".join(
        f"""<div class="term-row">
          <code>{html.escape(entry["term"])}</code>
          <div class="bar"><i style="width:{entry["count"] / maximum * 100:.1f}%"></i></div>
          <b>{number(entry["count"])}</b>
        </div>"""
        for entry in selected
    )


def render(data: dict[str, Any]) -> str:
    if not data.get("terms_redacted"):
        raise ValueError("refusing to build a public carousel from unredacted terms")

    combined = data["sources"]["all"]
    claude = data["sources"]["claude"]
    codex = data["sources"]["codex"]
    totals = combined["totals"]
    peak_hour = max(range(24), key=lambda hour: combined["hourly"][hour]["hits"])
    period_start = data["period"]["first"][:10]
    period_end = data["period"]["last"][:10]
    terms = term_rows(combined["terms"])

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agentic Swear Jar — LinkedIn carousel</title>
<style>
:root{{--ink:#f7f3e9;--muted:#aaa69b;--night:#0b0b0b;--panel:#171715;--line:#34332f;--acid:#cfff2e;--pink:#ff5c8a;--blue:#63d7ff}}
*{{box-sizing:border-box}}html,body{{margin:0;background:#242424;color:var(--ink);font-family:Inter,Arial,sans-serif}}
body{{display:grid;gap:36px;padding:36px;justify-content:center}}.slide{{width:1080px;height:1080px;background:var(--night);position:relative;overflow:hidden;padding:78px;display:flex;flex-direction:column;border:1px solid #222}}
.slide:before{{content:"";position:absolute;inset:0;opacity:.16;background-image:radial-gradient(#fff .7px,transparent .7px);background-size:9px 9px;mask-image:linear-gradient(#000,transparent 78%);pointer-events:none}}
.kicker{{font:800 15px/1 ui-monospace,monospace;letter-spacing:.18em;text-transform:uppercase;color:var(--acid);position:relative}}h1,h2,p{{position:relative}}h1{{font-size:112px;line-height:.88;letter-spacing:-.075em;margin:55px 0 42px;max-width:900px}}h2{{font-size:72px;line-height:.94;letter-spacing:-.055em;margin:38px 0 45px;max-width:880px}}em{{font-style:normal;color:var(--acid)}}.lede{{font-size:29px;line-height:1.35;color:#cac6bc;max-width:820px;margin:0}}.lede strong{{color:var(--ink)}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:auto;position:relative}}.stat{{background:var(--panel);border:1px solid var(--line);border-radius:24px;padding:28px}}.stat b{{display:block;font-size:51px;letter-spacing:-.05em;line-height:1}}.stat span{{display:block;font:700 12px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-top:13px}}.stat.hot{{background:var(--acid);color:#10110a;border-color:var(--acid)}}.stat.hot span{{color:#3b4515}}
.faceoff{{display:grid;grid-template-columns:1fr 78px 1fr;align-items:stretch;position:relative;margin-top:12px}}.agent{{border:1px solid var(--line);border-radius:28px;padding:34px;background:var(--panel)}}.agent.claude{{border-color:#77572e}}.agent.codex{{border-color:#246176}}.agent h3{{font-size:28px;margin:0 0 30px}}.agent .big{{font-size:76px;font-weight:850;letter-spacing:-.07em;line-height:1}}.agent small{{display:block;color:var(--muted);font-size:17px;margin:8px 0 25px}}.agent .rate{{padding-top:24px;border-top:1px solid var(--line);font-size:19px}}.vs{{display:grid;place-items:center;font:900 12px ui-monospace,monospace;color:var(--muted)}}
.insight{{margin-top:25px;border-left:5px solid var(--acid);padding:8px 0 8px 24px;font-size:24px;color:#d9d5cc;position:relative}}.insight strong{{color:var(--acid)}}
.terms{{position:relative;display:grid;gap:18px}}.term-row{{display:grid;grid-template-columns:160px 1fr 55px;gap:20px;align-items:center}}code{{font:800 26px ui-monospace,monospace;color:var(--ink)}}.bar{{height:18px;background:#272724;border-radius:99px;overflow:hidden}}.bar i{{height:100%;display:block;background:var(--acid);border-radius:inherit}}.term-row b{{font:800 20px ui-monospace,monospace;text-align:right}}.mini-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:42px;position:relative}}.mini{{border:1px solid var(--line);border-radius:19px;padding:22px}}.mini b{{display:block;font-size:38px;letter-spacing:-.04em}}.mini span{{font:700 11px ui-monospace,monospace;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
.flow{{display:grid;grid-template-columns:1fr 46px 1fr 46px 1fr;align-items:center;position:relative;margin:18px 0 48px}}.step{{height:180px;border:1px solid var(--line);border-radius:25px;padding:27px;background:var(--panel)}}.step b{{font-size:43px;display:block;margin-bottom:18px}}.step span{{color:var(--muted);font-size:18px}}.arrow{{text-align:center;color:var(--acid);font-size:30px}}.cta{{position:relative;background:var(--acid);color:#11140a;border-radius:30px;padding:32px 38px;margin-top:auto}}.cta b{{font-size:34px;letter-spacing:-.03em}}.cta span{{display:block;font:800 16px ui-monospace,monospace;margin-top:10px}}
.footer{{position:absolute;left:78px;right:78px;bottom:35px;display:flex;justify-content:space-between;color:#77746d;font:700 11px ui-monospace,monospace;letter-spacing:.09em;text-transform:uppercase}}.slide:last-child .footer{{color:#77746d}}body.single{{padding:0;display:block;background:var(--night)}}body.single .slide{{display:none}}body.single .slide.selected{{display:flex}}
</style>
</head>
<body>
<section class="slide">
  <div class="kicker">An unnecessary experiment / excellent charts</div>
  <h1>Apparently,<br>I swear at<br><em>coding agents.</em></h1>
  <p class="lede">So I analyzed every prompt I sent to Claude Code and Codex CLI. <strong>Locally. With zero AI.</strong></p>
  <div class="stats"><div class="stat"><b>{number(totals["prompts"])}</b><span>prompts scanned</span></div><div class="stat hot"><b>{number(totals["hits"])}</b><span>matches found</span></div><div class="stat"><b>{totals["prompt_rate"]:.1f}%</b><span>spicy prompts</span></div></div>
  <div class="footer"><span>Agentic Swear Jar</span><span>01 / 04</span></div>
</section>
<section class="slide">
  <div class="kicker">Claude Code vs. Codex CLI</div>
  <h2>Which harness gets the <em>spicier</em> prompts?</h2>
  <div class="faceoff"><div class="agent claude"><h3>Claude Code</h3><div class="big">{claude["totals"]["hits_per_100_prompts"]:.2f}</div><small>matches / 100 prompts</small><div class="rate"><strong>{claude["totals"]["prompt_rate"]:.2f}%</strong> of prompts contained a match<br>{number(claude["totals"]["prompts"])} prompts total</div></div><div class="vs">VS</div><div class="agent codex"><h3>Codex CLI</h3><div class="big">{codex["totals"]["hits_per_100_prompts"]:.2f}</div><small>matches / 100 prompts</small><div class="rate"><strong>{codex["totals"]["prompt_rate"]:.2f}%</strong> of prompts contained a match<br>{number(codex["totals"]["prompts"])} prompts total</div></div></div>
  <div class="insight"><strong>Plot twist:</strong> Codex gets more spicy words per prompt. Claude sees them across more prompts.</div>
  <div class="footer"><span>Normalized, because volume lies</span><span>02 / 04</span></div>
</section>
<section class="slide">
  <div class="kicker">The vocabulary / marker safely applied</div>
  <h2>What frustration<br><em>looks like.</em></h2>
  <div class="terms">{terms}</div>
  <div class="mini-grid"><div class="mini"><b>{combined["streaks"]["longest_clean"]}</b><span>longest clean run</span></div><div class="mini"><b>{peak_hour:02d}:00</b><span>peak local hour</span></div><div class="mini"><b>{totals["hits_per_1000_words"]:.2f}</b><span>hits / 1k words</span></div></div>
  <div class="footer"><span>Only first letters survived publication</span><span>03 / 04</span></div>
</section>
<section class="slide">
  <div class="kicker">Built without a classifier</div>
  <h2>No AI was needed<br>to analyze the <em>AI work.</em></h2>
  <div class="flow"><div class="step"><b>01</b><span>Stream local JSONL histories</span></div><div class="arrow">→</div><div class="step"><b>02</b><span>Regex tokens + hash-map lexicon</span></div><div class="arrow">→</div><div class="step"><b>03</b><span>Aggregate private, redacted stats</span></div></div>
  <p class="lede">{number(totals["words"])} words analyzed in one pass. No prompts uploaded. No raw text retained. Observed {period_start} → {period_end}.</p>
  <div class="cta"><b>Would you run this on your agent history?</b><span>github.com/marcelpetrick/AgenticSwearJar</span></div>
  <div class="footer"><span>The harness is a machine. No feelings were hurt.</span><span>04 / 04</span></div>
</section>
<script>
const requested=new URLSearchParams(location.search).get('slide');
if(requested){{document.body.classList.add('single');const slide=document.querySelectorAll('.slide')[Number(requested)-1];if(slide)slide.classList.add('selected')}}
</script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
