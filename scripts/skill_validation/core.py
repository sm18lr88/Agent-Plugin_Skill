"""Provide shared checks for this skill project's release artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from plugin_validation.agent_skills import validate_agent_skill_text

REQUIRED_PATHS = (
    "SKILL.md",
    "README.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "RELEASING.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    "agents/openai.yaml",
    "licenses/Apache-2.0.txt",
    "licenses/StrictYAML-MIT.txt",
    "references/core.md",
    "references/package-model.md",
    "references/manifest.md",
    "references/skills.md",
    "references/mcp.md",
    "references/failure-boundaries.md",
    "references/client-extensions.md",
    "references/migration.md",
    "references/client-implementation.md",
    "references/security-and-supply-chain.md",
    "references/testing-and-evaluation.md",
    "references/client-compatibility.md",
    "references/research-notes.md",
    "references/schemas/1.0.0/plugin.schema.json",
    "references/schemas/1.0.0/mcp.schema.json",
    "assets/plugin-minimal.json",
    "assets/plugin-full.json",
    "assets/mcp-stdio.json",
    "assets/mcp-http.json",
    "assets/mcp-mixed.json",
    "assets/skill-template.md",
    "assets/plugin-review.md",
    "assets/migration-map.md",
    "assets/client-conformance-review.md",
    "assets/threat-model.md",
    "assets/example-plugin/plugin.json",
    "assets/example-plugin/skills/release-notes/SKILL.md",
    "scripts/new_plugin.py",
    "scripts/validate_plugin.py",
    "scripts/package_plugin.py",
    "scripts/package_skill.py",
    "scripts/portability_check.py",
    "scripts/validate_skill.py",
    "scripts/plugin_validation/__init__.py",
    "scripts/plugin_validation/agent_skills.py",
    "scripts/plugin_validation/core.py",
    "scripts/plugin_validation/manifest.py",
    "scripts/plugin_validation/skills.py",
    "scripts/plugin_validation/mcp.py",
    "scripts/plugin_validation/security.py",
    "scripts/plugin_validation/package.py",
    "scripts/plugin_validation/selftest.py",
    "scripts/skill_validation/__init__.py",
    "scripts/skill_validation/core.py",
    "scripts/skill_validation/layout.py",
    "scripts/skill_validation/metadata.py",
    "scripts/skill_validation/package.py",
    "scripts/skill_validation/python_safety.py",
    "scripts/skill_validation/selftest.py",
    "scripts/skill_validation/simple_english.py",
    "evals/README.md",
    "evals/rubric.md",
    "evals/scenarios.jsonl",
    "maintenance/UPSTREAM_REVIEW.md",
    "maintenance/upstreams.lock.json",
)
LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    message: str


class Report:
    def __init__(self) -> None:
        self.errors: list[Finding] = []
        self.warnings: list[Finding] = []

    def error(self, path: str | Path, message: str) -> None:
        self.errors.append(Finding(str(path).replace("\\", "/"), message))

    def warn(self, path: str | Path, message: str) -> None:
        self.warnings.append(Finding(str(path).replace("\\", "/"), message))


class DuplicateKeyError(ValueError):
    pass


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise DuplicateKeyError(f"duplicate key {key!r}")
        result[key] = value
    return result


def read_text(path: Path, report: Report) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        report.error(path, f"cannot read: {exc}")
        return None
    if b"\x00" in data:
        report.error(path, "contains a NUL byte")
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error(path, f"is not valid UTF-8: {exc}")
        return None


def load_json(path: Path, report: Report) -> Any | None:
    text = read_text(path, report)
    if text is None:
        return None
    try:
        return json.loads(text, object_pairs_hook=_pairs)
    except (DuplicateKeyError, json.JSONDecodeError) as exc:
        report.error(path, f"invalid JSON: {exc}")
        return None


def validate_required(root: Path, report: Report) -> None:
    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            report.error(relative, "required path is missing")


def validate_skill_file(root: Path, report: Report) -> None:
    path = root / "SKILL.md"
    text = read_text(path, report) if path.is_file() else None
    if text is None:
        return
    result = validate_agent_skill_text(text, root)
    for message in result.errors:
        report.error("SKILL.md", f"official Agent Skills validator: {message}")
    line_count = len(text.splitlines())
    if line_count > 500:
        report.warn(
            "SKILL.md",
            f"Agent Skills recommends fewer than 500 lines; found {line_count}",
        )


def _clean_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    if re.search(r"\s+[\"']", value):
        return re.split(r"\s+[\"']", value, maxsplit=1)[0]
    return value


def validate_links(root: Path, files: Iterable[Path], report: Report) -> None:
    resolved_root = root.resolve()
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        text = read_text(path, report)
        if text is None:
            continue
        for match in LINK_RE.finditer(text):
            raw = _clean_target(match.group("target"))
            if (
                not raw
                or raw.startswith(("#", "//"))
                or SCHEME_RE.match(raw)
            ):
                continue
            candidate = (path.parent / unquote(urlsplit(raw).path)).resolve(
                strict=False
            )
            try:
                candidate.relative_to(resolved_root)
            except ValueError:
                report.error(
                    path.relative_to(root), f"local link escapes skill folder: {raw}"
                )
            else:
                if not candidate.exists():
                    report.error(path.relative_to(root), f"broken local link: {raw}")


def validate_json_files(root: Path, files: Iterable[Path], report: Report) -> None:
    for path in files:
        if path.suffix.lower() == ".json":
            load_json(path, report)


def validate_eval_jsonl(root: Path, report: Report) -> None:
    path = root / "evals/scenarios.jsonl"
    text = read_text(path, report) if path.is_file() else None
    if text is None:
        return
    seen: set[str] = set()
    count = 0
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        count += 1
        try:
            item = json.loads(raw, object_pairs_hook=_pairs)
        except (DuplicateKeyError, json.JSONDecodeError) as exc:
            report.error(path.relative_to(root), f"line {number}: invalid JSON: {exc}")
            continue
        if not isinstance(item, dict):
            report.error(
                path.relative_to(root), f"line {number}: scenario must be an object"
            )
            continue
        identifier = item.get("id")
        if (
            not isinstance(identifier, str)
            or not KEBAB_RE.fullmatch(identifier)
            or identifier in seen
        ):
            report.error(
                path.relative_to(root),
                f"line {number}: id must be unique lowercase kebab-case",
            )
        else:
            seen.add(identifier)
        if item.get("kind") not in {"activation", "behavior"}:
            report.error(
                path.relative_to(root),
                f"line {number}: kind must be activation or behavior",
            )
        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
            report.error(
                path.relative_to(root), f"line {number}: prompt must be non-empty"
            )
        if not isinstance(item.get("expected_activation"), bool):
            report.error(
                path.relative_to(root),
                f"line {number}: expected_activation must be boolean",
            )
        for field in ("references", "expectations", "anti_expectations"):
            value = item.get(field)
            if not isinstance(value, list) or not all(
                isinstance(entry, str) and entry for entry in value
            ):
                report.error(
                    path.relative_to(root),
                    f"line {number}: {field} must be a list of non-empty strings",
                )
    if count < 20:
        report.error(
            path.relative_to(root), f"only {count} scenarios; require at least 20"
        )
