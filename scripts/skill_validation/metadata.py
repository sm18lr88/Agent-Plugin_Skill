"""Validate project metadata, source pins, notices, and schema snapshots."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .core import Report, load_json, read_text

OPENAI_YAML = 'interface:\n  display_name: "Agent Plugin"\n  short_description: "Build and audit portable Agent Plugins"\n'
SCHEMAS = {
    "references/schemas/1.0.0/plugin.schema.json": {
        "sha256": "0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883",
        "id": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    },
    "references/schemas/1.0.0/mcp.schema.json": {
        "sha256": "6539175bfcdf43085855183e86da40ea94b166547a72b47ae9a0a390516d3acb",
        "id": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
    },
}
SOURCES = {
    "agent-plugins-spec": (
        "https://github.com/agentplugins/agent-plugins-spec.git",
        "main",
        "bd383552095128f6effe895b9257cfd580a6d179",
        "adopted",
    ),
    "agent-plugins-example": (
        "https://github.com/agentplugins/agent-plugins-example.git",
        "main",
        "5f3f5084a821aefa792e79500dd8f0462ab83473",
        "adapted",
    ),
    "agent-skills": (
        "https://github.com/agentskills/agentskills.git",
        "main",
        "217be548739f21d6008915c29aefe320ea1a90af",
        "adapted",
    ),
    "model-context-protocol": (
        "https://github.com/modelcontextprotocol/modelcontextprotocol.git",
        "main",
        "2de0727d3c2d6f2f32b3fefbba0bf8395b2e7324",
        "referenced",
    ),
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_openai_metadata(root: Path, report: Report) -> None:
    path = root / "agents/openai.yaml"
    text = read_text(path, report) if path.is_file() else None
    if text is None:
        return
    if text.replace("\r\n", "\n") != OPENAI_YAML:
        report.error(
            path.relative_to(root),
            "does not match the exact OpenAI presentation metadata contract",
        )


def validate_schema_snapshots(root: Path, report: Report) -> None:
    for relative, expected in SCHEMAS.items():
        path = root / relative
        if not path.is_file():
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected["sha256"]:
            report.error(
                relative,
                f"vendored schema hash changed: {digest}; expected {expected['sha256']}",
            )
        parsed = load_json(path, report)
        if isinstance(parsed, dict):
            if parsed.get("$id") != expected["id"]:
                report.error(relative, f"schema $id must be {expected['id']!r}")
            if parsed.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                report.error(relative, "schema draft identifier changed")


def _date(value: Any, field: str, path: Path, report: Report) -> date | None:
    if not isinstance(value, str):
        report.error(path, f"{field} must be an ISO date string")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        report.error(path, f"{field} is not a valid ISO date: {value!r}")
        return None


def validate_upstream_ledger(root: Path, report: Report) -> None:
    path = root / "maintenance/upstreams.lock.json"
    data = load_json(path, report) if path.is_file() else None
    if not isinstance(data, dict):
        return
    relative = path.relative_to(root)
    if data.get("schema_version") != 1 or data.get("product") != "agent-plugin":
        report.error(
            relative,
            "ledger identity must be schema_version 1 for product agent-plugin",
        )
    if data.get("agent_plugins_specification") != "1.0.0":
        report.error(relative, "ledger must target Agent Plugins specification 1.0.0")
    reviewed = _date(data.get("reviewed_at"), "reviewed_at", relative, report)
    if reviewed and reviewed > datetime.now(UTC).date():
        report.error(relative, "reviewed_at cannot be in the future")
    sources = data.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCES):
        report.error(relative, f"sources must be exactly {sorted(SOURCES)}")
        return
    for name, expected in SOURCES.items():
        source = sources.get(name)
        if not isinstance(source, dict):
            report.error(relative, f"source {name!r} must be an object")
            continue
        repository, branch, commit, outcome = expected
        if source.get("repository") != repository or source.get("branch") != branch:
            report.error(
                relative,
                f"source {name!r} repository or branch changed without validator update",
            )
        if source.get("reviewed_commit") != commit or not SHA_RE.fullmatch(
            str(source.get("reviewed_commit", ""))
        ):
            report.error(
                relative, f"source {name!r} reviewed_commit must be pinned to {commit}"
            )
        if source.get("review_outcome") != outcome:
            report.error(
                relative, f"source {name!r} review_outcome must be {outcome!r}"
            )
        if not isinstance(source.get("role"), str) or not source["role"]:
            report.error(relative, f"source {name!r} needs a non-empty role")
        if not isinstance(source.get("policy"), str) or not source["policy"]:
            report.error(relative, f"source {name!r} needs a non-empty policy")
        if not isinstance(source.get("paths"), list) or not all(
            isinstance(item, str) and item for item in source["paths"]
        ):
            report.error(relative, f"source {name!r} paths must be non-empty strings")
        license_data = source.get("license")
        if (
            not isinstance(license_data, dict)
            or not isinstance(license_data.get("url"), str)
            or commit not in license_data["url"]
        ):
            report.error(
                relative,
                f"source {name!r} license URL must be pinned to its reviewed commit",
            )
    volatile = data.get("volatile_sources")
    if (
        not isinstance(volatile, list)
        or len(volatile) != 1
        or not isinstance(volatile[0], dict)
    ):
        report.error(
            relative, "volatile_sources must contain the compatible-clients snapshot"
        )
    else:
        item = volatile[0]
        if (
            item.get("url") != "https://agent-plugins.org/compatible-clients"
            or item.get("policy") != "recheck-before-release"
        ):
            report.error(
                relative, "volatile client compatibility source contract changed"
            )
        _date(
            item.get("reviewed_at"), "volatile_sources[0].reviewed_at", relative, report
        )


def validate_notice(root: Path, report: Report) -> None:
    path = root / "THIRD_PARTY_NOTICES.md"
    text = read_text(path, report) if path.is_file() else None
    if text is None:
        return
    required = (
        "bd383552095128f6effe895b9257cfd580a6d179",
        "8fed0e1fe45d0464aee880d3fbab228b71ecfc1e",
        "a9139a4259b932c60b5351c8d9da6a5c60c97646",
        "Apache-2.0",
        "CC BY 4.0",
    )
    for value in required:
        if value not in text:
            report.error(
                path.relative_to(root),
                f"required schema attribution value missing: {value}",
            )
