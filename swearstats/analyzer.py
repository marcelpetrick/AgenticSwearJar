"""Streaming history readers and aggregate-only analysis."""

from __future__ import annotations

import csv
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
SOURCE_NAMES = {"claude": "Claude Code", "codex": "Codex CLI"}
# The dashboard's activity calendar renders 53 weeks, so emitting more daily
# buckets than that only inflates the report. A single out-of-range timestamp
# would otherwise stretch the range over decades of empty days.
DAILY_WINDOW_DAYS = 371
LENGTH_BUCKETS = (
    (0, 10, "1–10"),
    (11, 30, "11–30"),
    (31, 75, "31–75"),
    (76, 150, "76–150"),
    (151, 10**18, "151+"),
)


@dataclass(frozen=True)
class Lexeme:
    canonical: str
    category: str
    severity: int


@dataclass(frozen=True)
class Prompt:
    source: str
    text: str
    timestamp: datetime | None
    session: str | None = None
    project: str | None = None


@dataclass
class Bucket:
    prompts: int = 0
    profane_prompts: int = 0
    hits: int = 0
    words: int = 0
    score: int = 0

    def add(self, word_count: int, hits: list[Lexeme]) -> None:
        self.prompts += 1
        self.words += word_count
        self.hits += len(hits)
        self.score += sum(hit.severity for hit in hits)
        self.profane_prompts += bool(hits)

    def as_dict(self) -> dict[str, int | float]:
        return {
            "prompts": self.prompts,
            "profane_prompts": self.profane_prompts,
            "hits": self.hits,
            "words": self.words,
            "score": self.score,
            "prompt_rate": round(100 * self.profane_prompts / self.prompts, 2)
            if self.prompts
            else 0,
            "hits_per_100_prompts": round(100 * self.hits / self.prompts, 2) if self.prompts else 0,
            "hits_per_1000_words": round(1000 * self.hits / self.words, 2) if self.words else 0,
        }


@dataclass
class Analysis:
    totals: dict[str, Bucket] = field(default_factory=lambda: defaultdict(Bucket))
    terms: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    categories: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    severity: dict[str, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    daily: dict[str, dict[str, Bucket]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(Bucket))
    )
    monthly: dict[str, dict[str, Bucket]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(Bucket))
    )
    weekday: dict[str, dict[int, Bucket]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(Bucket))
    )
    hourly: dict[str, dict[int, Bucket]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(Bucket))
    )
    lengths: dict[str, dict[str, Bucket]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(Bucket))
    )
    sessions: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    profane_sessions: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    projects: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    events: list[tuple[datetime, bool, str]] = field(default_factory=list)
    malformed: Counter[str] = field(default_factory=Counter)
    missing_timestamp: Counter[str] = field(default_factory=Counter)
    undated_excluded: Counter[str] = field(default_factory=Counter)


def load_lexicon(paths: Iterable[Path]) -> dict[str, Lexeme]:
    lexicon: dict[str, Lexeme] = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = csv.reader(handle, delimiter="\t")
            for line_number, row in enumerate(rows, 1):
                if not row or row[0].lstrip().startswith("#"):
                    continue
                if len(row) != 4:
                    raise ValueError(f"{path}:{line_number}: expected 4 tab-separated fields")
                variant, canonical, category, severity_text = (cell.strip() for cell in row)
                try:
                    severity = int(severity_text)
                except ValueError as error:
                    raise ValueError(
                        f"{path}:{line_number}: severity must be 1, 2 or 3, got {severity_text!r}"
                    ) from error
                if not variant or not canonical or not category or severity not in (1, 2, 3):
                    raise ValueError(f"{path}:{line_number}: invalid lexicon entry")
                normalized = normalize_word(variant)
                lexicon[normalized] = Lexeme(normalize_word(canonical), category, severity)
    if not lexicon:
        raise ValueError("the lexicon is empty")
    return lexicon


def normalize_word(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace("’", "'")


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = float(value)
            if seconds > 10_000_000_000:
                seconds /= 1000
            return datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone()
        if isinstance(value, str):
            candidate = value.strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone()
    except (OverflowError, OSError, ValueError):
        return None
    return None


def read_history(path: Path, source: str, analysis: Analysis) -> Iterator[Prompt]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                analysis.malformed[source] += 1
                continue
            if not isinstance(record, dict):
                analysis.malformed[source] += 1
                continue
            if source == "codex":
                text = record.get("text")
                timestamp = parse_timestamp(record.get("ts"))
                session = record.get("session_id")
                project = None
            else:
                text = record.get("display")
                timestamp = parse_timestamp(record.get("timestamp"))
                session = record.get("sessionId") or record.get("session_id")
                project = record.get("project")
            if not isinstance(text, str):
                analysis.malformed[source] += 1
                continue
            if timestamp is None:
                analysis.missing_timestamp[source] += 1
            yield Prompt(
                source=source,
                text=text,
                timestamp=timestamp,
                session=str(session) if session else None,
                project=str(project) if project else None,
            )


def analyze(
    inputs: Iterable[tuple[str, Path]],
    lexicon: dict[str, Lexeme],
    since: datetime | None = None,
    until: datetime | None = None,
) -> Analysis:
    result = Analysis()
    # A prompt with no timestamp cannot be shown to fall inside a requested
    # window, so it is excluded whenever one is given. Unfiltered runs keep it.
    windowed = since is not None or until is not None
    for source, path in inputs:
        for prompt in read_history(path, source, result):
            if prompt.timestamp is None:
                if windowed:
                    result.undated_excluded[source] += 1
                    continue
            elif (since and prompt.timestamp < since) or (until and prompt.timestamp >= until):
                continue
            words = [normalize_word(match.group()) for match in WORD_RE.finditer(prompt.text)]
            hits = [lexicon[word] for word in words if word in lexicon]
            _record(result, prompt, len(words), hits)
    return result


def _record(result: Analysis, prompt: Prompt, word_count: int, hits: list[Lexeme]) -> None:
    keys = ("all", prompt.source)
    for key in keys:
        result.totals[key].add(word_count, hits)
        result.terms[key].update(hit.canonical for hit in hits)
        result.categories[key].update(hit.category for hit in hits)
        result.severity[key].update(hit.severity for hit in hits)
        result.lengths[key][_length_bucket(word_count)].add(word_count, hits)

    if prompt.session:
        result.sessions[prompt.source].add(prompt.session)
        if hits:
            result.profane_sessions[prompt.source].add(prompt.session)
    if prompt.project:
        result.projects[prompt.source].add(prompt.project)
    if not prompt.timestamp:
        return

    result.events.append((prompt.timestamp, bool(hits), prompt.source))
    day = prompt.timestamp.date().isoformat()
    month = day[:7]
    for key in keys:
        result.daily[key][day].add(word_count, hits)
        result.monthly[key][month].add(word_count, hits)
        result.weekday[key][prompt.timestamp.weekday()].add(word_count, hits)
        result.hourly[key][prompt.timestamp.hour].add(word_count, hits)


def _length_bucket(count: int) -> str:
    for low, high, label in LENGTH_BUCKETS:
        if low <= count <= high:
            return label
    raise AssertionError("unreachable")


def _date_range(first: date, last: date) -> Iterator[date]:
    current = first
    while current <= last:
        yield current
        current = date.fromordinal(current.toordinal() + 1)


@dataclass
class _Streak:
    """Running longest-run state for one source key."""

    longest_clean: int = 0
    longest_profane: int = 0
    current_clean: int = 0
    current_profane: int = 0

    def add(self, is_profane: bool) -> None:
        if is_profane:
            self.current_profane += 1
            self.longest_profane = max(self.longest_profane, self.current_profane)
            self.current_clean = 0
        else:
            self.current_clean += 1
            self.longest_clean = max(self.longest_clean, self.current_clean)
            self.current_profane = 0

    def as_dict(self) -> dict[str, int]:
        return {"longest_clean": self.longest_clean, "longest_profane": self.longest_profane}


def _streaks(
    events: list[tuple[datetime, bool, str]], keys: list[str]
) -> dict[str, dict[str, int]]:
    """Fold every key's streaks in one chronological pass over the events.

    The previous implementation sorted and copied the event list once per key,
    which tripled peak memory during serialization for no extra information.
    """
    running = {key: _Streak() for key in keys}
    for _, is_profane, source in sorted(events, key=lambda event: event[0]):
        if "all" in running:
            running["all"].add(is_profane)
        if source in running:
            running[source].add(is_profane)
    return {key: streak.as_dict() for key, streak in running.items()}


def serialize(result: Analysis, sources: dict[str, Path], lexicon_size: int) -> dict[str, Any]:
    source_keys = [key for key in ("claude", "codex") if key in sources]
    keys = ["all", *source_keys]
    first = min((event[0] for event in result.events), default=None)
    last = max((event[0] for event in result.events), default=None)
    streaks = _streaks(result.events, keys)

    daily: dict[str, list[dict[str, Any]]] = {}
    if first and last:
        window_end = last.date()
        window_start = max(first.date(), window_end - timedelta(days=DAILY_WINDOW_DAYS - 1))
        for key in keys:
            daily[key] = [
                {"date": day.isoformat(), **result.daily[key][day.isoformat()].as_dict()}
                for day in _date_range(window_start, window_end)
            ]

    source_details: dict[str, Any] = {}
    for key in keys:
        hit_counts = [bucket.hits for bucket in result.daily[key].values() if bucket.hits]
        source_details[key] = {
            "label": "Combined" if key == "all" else SOURCE_NAMES[key],
            "totals": result.totals[key].as_dict(),
            "terms": [
                {"term": term, "count": count} for term, count in result.terms[key].most_common()
            ],
            "categories": dict(result.categories[key].most_common()),
            "severity": {str(level): result.severity[key][level] for level in (1, 2, 3)},
            "monthly": [
                {"month": month, **bucket.as_dict()}
                for month, bucket in sorted(result.monthly[key].items())
            ],
            "weekday": [result.weekday[key][index].as_dict() for index in range(7)],
            "hourly": [result.hourly[key][index].as_dict() for index in range(24)],
            "lengths": [
                {"label": label, **result.lengths[key][label].as_dict()}
                for _, _, label in LENGTH_BUCKETS
            ],
            "streaks": streaks[key],
            "median_active_day_hits": statistics.median(hit_counts) if hit_counts else 0,
        }

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {
            "first": first.isoformat(timespec="seconds") if first else None,
            "last": last.isoformat(timespec="seconds") if last else None,
        },
        "lexicon_size": lexicon_size,
        "sources": source_details,
        "source_meta": {
            source: {
                "label": SOURCE_NAMES[source],
                "sessions": len(result.sessions[source]),
                "profane_sessions": len(result.profane_sessions[source]),
                "projects": len(result.projects[source]),
                "malformed_lines": result.malformed[source],
                "missing_timestamps": result.missing_timestamp[source],
                "undated_excluded": result.undated_excluded[source],
            }
            for source in sources
        },
        "daily": daily,
        "privacy": "Aggregate counts only; no prompt text is retained in this report.",
    }


def redact_terms(data: dict[str, Any]) -> None:
    """Redact observed term labels in-place before creating public artifacts."""
    for source in data["sources"].values():
        for entry in source["terms"]:
            term = entry["term"]
            entry["term"] = term[:1] + "█" * max(0, len(term) - 1)
    data["terms_redacted"] = True
    data["privacy"] += " Observed term labels are redacted after their first character."


def parse_boundary(value: str | None, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"invalid date {value!r}; use YYYY-MM-DD") from error
    boundary = datetime.combine(parsed_date, time.min).astimezone()
    if end:
        return datetime.combine(
            date.fromordinal(parsed_date.toordinal() + 1), time.min
        ).astimezone()
    return boundary
