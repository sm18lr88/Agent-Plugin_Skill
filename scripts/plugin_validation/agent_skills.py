"""Apply the pinned official Agent Skills validation rules to UTF-8 text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skills_ref.errors import ParseError
from skills_ref.parser import parse_frontmatter
from skills_ref.validator import validate_metadata


@dataclass(frozen=True, slots=True)
class AgentSkillResult:
    metadata: dict[str, Any] | None
    body: str
    errors: tuple[str, ...]


def validate_agent_skill_text(text: str, skill_dir: Path) -> AgentSkillResult:
    try:
        metadata, body = parse_frontmatter(text)
    except ParseError as exc:
        return AgentSkillResult(None, "", (str(exc),))
    errors = tuple(validate_metadata(metadata, skill_dir))
    return AgentSkillResult(metadata, body, errors)
