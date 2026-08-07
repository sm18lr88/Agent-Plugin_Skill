"""Coordinate Agent Plugin validation across independent component types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import (
    NAMESPACE_RE,
    Report,
    validate_package_root,
    validate_symlink_containment,
)
from .manifest import ManifestResult, validate_manifest
from .mcp import validate_mcp
from .security import validate_package_security
from .skills import validate_skills


@dataclass(frozen=True, slots=True)
class ValidationResult:
    root: Path | None
    manifest: dict[str, Any] | None
    specification_version: str | None
    skills: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    report: Report


def _validate_extensions(
    root: Path, manifest: dict[str, Any] | None, report: Report
) -> None:
    declared = set()
    if isinstance(manifest, dict) and isinstance(manifest.get("extensions"), dict):
        declared = set(manifest["extensions"])
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or not NAMESPACE_RE.fullmatch(child.name):
            continue
        if child.name not in declared:
            report.warn(
                "EXTENSION_FILE_ONLY",
                f"extension:{child.name}",
                child.name,
                "reverse-domain extension directory has no matching manifest entry; file-only extensions are permitted",
                "Only clients implementing this namespace assign semantics; portable core remains unaffected.",
            )
    for namespace in sorted(declared):
        directory = root / namespace
        if directory.exists() and not directory.is_dir():
            report.warn(
                "EXTENSION_DIRECTORY_KIND",
                f"extension:{namespace}",
                namespace,
                "extension path exists but is not a directory",
                "Owning client defines extension failure handling; portable core remains independent.",
            )


def validate_plugin(root: Path) -> ValidationResult:
    report = Report()
    normalized = validate_package_root(root, report)
    if normalized is None:
        return ValidationResult(None, None, None, (), (), report)
    validate_symlink_containment(normalized, report)
    manifest_result: ManifestResult = validate_manifest(normalized, report)
    if manifest_result.fatal:
        validate_package_security(normalized, report)
        return ValidationResult(
            normalized,
            manifest_result.data,
            manifest_result.version,
            (),
            (),
            report,
        )
    skills = validate_skills(normalized, report)
    servers = validate_mcp(normalized, manifest_result.version, report)
    _validate_extensions(normalized, manifest_result.data, report)
    validate_package_security(normalized, report)
    return ValidationResult(
        normalized,
        manifest_result.data,
        manifest_result.version,
        tuple(skills),
        tuple(servers),
        report,
    )
