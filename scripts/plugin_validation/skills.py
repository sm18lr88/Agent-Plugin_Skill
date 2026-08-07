"""Discover Agent Skills and validate each skill without affecting siblings."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .agent_skills import validate_agent_skill_text
from .core import Report, read_text, resolve_within, safe_relative

LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _local_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    elif re.search(r"\s+[\"']", value):
        value = re.split(r"\s+[\"']", value, maxsplit=1)[0]
    return value


def _validate_links(skill_dir: Path, root: Path, report: Report) -> None:
    try:
        paths = sorted(skill_dir.rglob("*.md"))
    except OSError as exc:
        report.error(
            "SKILL_DIRECTORY_READ",
            f"skill:{skill_dir.name}",
            safe_relative(skill_dir, root),
            f"cannot inspect skill files: {exc}",
            "Skip this skill. Continue other skills and component types.",
        )
        return
    for path in paths:
        if path.is_symlink():
            continue
        text = read_text(
            path,
            report,
            f"skill:{skill_dir.name}",
            "Skip this skill if its required content cannot be read.",
        )
        if text is None:
            continue
        for match in LINK_RE.finditer(text):
            raw = _local_target(match.group("target"))
            if not raw or raw.startswith(("#", "//")) or SCHEME_RE.match(raw):
                continue
            candidate = (path.parent / unquote(urlsplit(raw).path)).resolve(
                strict=False
            )
            contained, _, _ = resolve_within(skill_dir, candidate, strict=False)
            location = safe_relative(path, root)
            if not contained:
                report.warn(
                    "SKILL_LINK_ESCAPE",
                    f"skill:{skill_dir.name}",
                    location,
                    f"local Markdown link escapes the skill directory: {raw}",
                    "Agent Skills does not define a parse failure for this link. A client can refuse access outside the skill directory.",
                    "Keep referenced files inside the skill directory. Test the skill in each target client.",
                )
            elif not candidate.exists():
                report.warn(
                    "SKILL_LINK_MISSING",
                    f"skill:{skill_dir.name}",
                    location,
                    f"local Markdown link target does not exist: {raw}",
                    "Agent Skills does not define a parse failure for this link. The reference will not resolve as written.",
                    "Repair or remove the reference. Test the skill in each target client.",
                )


def _validate_one(skill_dir: Path, root: Path, report: Report) -> None:
    scope = f"skill:{skill_dir.name}"
    skill_file = skill_dir / "SKILL.md"
    relative = safe_relative(skill_file, root)
    if not skill_file.exists() and not skill_file.is_symlink():
        report.warn(
            "SKILL_CHILD_IGNORED",
            scope,
            safe_relative(skill_dir, root),
            "immediate child directory has no exact SKILL.md and is not discovered as a skill",
            "Ignore this directory. Continue discovery.",
        )
        return
    if not skill_file.is_file():
        report.error(
            "SKILL_FILE_KIND",
            scope,
            relative,
            "SKILL.md does not resolve to a regular file",
            "Skip this skill. Continue other skills and component types.",
        )
        return
    contained, resolved, problem = resolve_within(root, skill_file, strict=True)
    if not contained:
        report.error(
            "SKILL_FILE_ESCAPE",
            scope,
            relative,
            f"SKILL.md resolves outside plugin root: {problem or resolved}",
            "Skip this skill. Continue other skills and component types.",
        )
        return
    text = read_text(
        skill_file,
        report,
        scope,
        "Skip this skill. Continue other skills and component types.",
    )
    if text is None:
        return
    reference = validate_agent_skill_text(text, skill_dir)
    for message in reference.errors:
        report.error(
            "AGENT_SKILLS_REFERENCE",
            scope,
            relative,
            message,
            "Skip this skill. Continue other skills and component types.",
            "Correct the skill with the pinned official skills-ref validator.",
        )
    if reference.errors or reference.metadata is None:
        return

    description = reference.metadata.get("description")
    if isinstance(description, str) and not re.search(
        r"\b(use|when|whenever|for)\b", description, re.IGNORECASE
    ):
        report.warn(
            "SKILL_DESCRIPTION_TRIGGER",
            scope,
            relative,
            "description does not clearly state when the skill applies",
            "The official validator accepts this description. Skill activation quality can decrease.",
        )
    if not reference.body.strip():
        report.warn(
            "SKILL_BODY_EMPTY",
            scope,
            relative,
            "SKILL.md has no Markdown instructions after frontmatter",
            "The official validator accepts the skill, but it provides no instructions.",
        )
    line_count = len(text.splitlines())
    if line_count > 500:
        report.warn(
            "SKILL_PROGRESSIVE_DISCLOSURE",
            scope,
            relative,
            f"SKILL.md has {line_count} lines; Agent Skills recommends fewer than 500 lines",
            "This is a recommendation, not a validation failure.",
        )
    _validate_links(skill_dir, root, report)


def validate_skills(root: Path, report: Report) -> list[str]:
    skills_root = root / "skills"
    if not skills_root.exists() and not skills_root.is_symlink():
        return []
    if not skills_root.is_dir():
        report.error(
            "SKILLS_ROOT_KIND",
            "skills",
            "skills",
            "present fixed skills location does not resolve to a directory",
            "Treat the skills component type as invalid. Continue other component types.",
        )
        return []
    contained, resolved, problem = resolve_within(root, skills_root, strict=True)
    if not contained:
        report.error(
            "SKILLS_ROOT_ESCAPE",
            "skills",
            "skills",
            f"skills fixed location resolves outside plugin root: {problem or resolved}",
            "Treat the skills component type as invalid. Continue other component types.",
        )
        return []
    try:
        children = sorted(skills_root.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        report.error(
            "SKILLS_ROOT_READ",
            "skills",
            "skills",
            f"cannot inspect skills directory: {exc}",
            "Treat the skills component type as invalid. Continue other component types.",
        )
        return []

    discovered: list[str] = []
    for child in children:
        if not child.is_dir():
            report.warn(
                "SKILLS_ROOT_ENTRY_IGNORED",
                "skills",
                safe_relative(child, root),
                "non-directory entry under skills/ is not discoverable as a skill",
                "Ignore this entry. Continue discovery.",
            )
            continue
        contained, resolved, problem = resolve_within(root, child, strict=True)
        if not contained:
            report.error(
                "SKILL_DIRECTORY_ESCAPE",
                f"skill:{child.name}",
                safe_relative(child, root),
                f"skill directory resolves outside plugin root: {problem or resolved}",
                "Skip this skill. Continue other skills and component types.",
            )
            continue
        if (child / "SKILL.md").exists() or (child / "SKILL.md").is_symlink():
            discovered.append(child.name)
        _validate_one(child, root, report)

    immediate = {skills_root / name / "SKILL.md" for name in discovered}
    try:
        nested_files = sorted(skills_root.rglob("SKILL.md"))
    except OSError as exc:
        report.error(
            "SKILLS_ROOT_READ",
            "skills",
            "skills",
            f"cannot inspect nested skill files: {exc}",
            "Stop nested discovery. Keep results from immediate children.",
        )
        return discovered
    for nested in nested_files:
        if nested not in immediate and nested.is_file():
            report.warn(
                "SKILL_NESTED_NOT_DISCOVERED",
                "skills",
                safe_relative(nested, root),
                "SKILL.md is not in an immediate child directory of skills/ and is not portably discovered",
                "Ignore it as a core skill. Client-specific behavior is outside portable discovery.",
            )
    return discovered
