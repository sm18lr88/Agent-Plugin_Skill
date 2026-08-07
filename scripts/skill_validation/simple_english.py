"""Enforce mechanical Simple English rules in project Markdown files."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .core import Report

INLINE_CODE_RE = re.compile(r"`[^`]*`")
LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
WORD_RE = re.compile(r"\b[\w'-]+\b")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?](?:\s|$)")
PATTERNS = (
    ("em dash", re.compile("—")),
    ("semicolon", re.compile(";")),
    (
        "contraction",
        re.compile(r"\b(?:\w+'(?:ll|re|ve|d|m|s)|\w+n['’]t)\b", re.IGNORECASE),
    ),
    (
        "Latin abbreviation",
        re.compile(r"\b(?:e\.g\.|i\.e\.|etc\.)", re.IGNORECASE),
    ),
    ("unsupported modal", re.compile(r"\b(?:should|would|may|might|could)\b")),
    (
        "perfect tense",
        re.compile(r"\b(?:has|have|had) been\b", re.IGNORECASE),
    ),
    (
        "progressive passive",
        re.compile(r"\b(?:is|are|was|were) being\b", re.IGNORECASE),
    ),
    (
        "fact-free modifier",
        re.compile(r"\b(?:simply|easily|seamlessly|robust)\b", re.IGNORECASE),
    ),
    (
        "verbal clause",
        re.compile(
            r",\s+(?:making|allowing|enabling|ensuring)\b", re.IGNORECASE
        ),
    ),
)


def _prose(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    fenced = False
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not stripped:
            continue
        line = INLINE_CODE_RE.sub("", raw)
        line = LINK_TARGET_RE.sub("]", line)
        result.append((number, line))
    return result


def validate_simple_english(root: Path, files: Iterable[Path], report: Report) -> None:
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.error(path.relative_to(root), f"cannot check Simple English: {exc}")
            continue
        relative = path.relative_to(root)
        for line_number, line in _prose(text):
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    report.error(
                        relative,
                        f"Simple English {label} at line {line_number}",
                    )
            if line.lstrip().startswith(("|", "#", "-", "*", ">")):
                continue
            for sentence in SENTENCE_RE.findall(line):
                words = WORD_RE.findall(sentence)
                if len(words) > 25:
                    report.error(
                        relative,
                        f"Simple English sentence has {len(words)} words at line {line_number}; limit is 25",
                    )
