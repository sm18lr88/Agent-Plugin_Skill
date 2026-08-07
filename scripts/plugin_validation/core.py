"""Provide shared findings, path checks, JSON parsing, and version constants."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

from skills_ref.validator import validate_metadata

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
SUPPORTED_VERSION = "1.0.0"
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
NAMESPACE_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
)


def valid_skill_name(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return not validate_metadata(
        {"name": value, "description": "Use when validating a skill name."},
        Path(value),
    )


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    code: str
    scope: str
    path: str
    message: str
    runtime_effect: str
    recommendation: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class Report:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def add(
        self,
        severity: str,
        code: str,
        scope: str,
        path: str | Path,
        message: str,
        runtime_effect: str,
        recommendation: str = "",
    ) -> None:
        self.findings.append(
            Finding(
                severity,
                code,
                scope,
                str(path).replace(os.sep, "/"),
                message,
                runtime_effect,
                recommendation,
            )
        )

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.add("error", *args, **kwargs)

    def warn(self, *args: Any, **kwargs: Any) -> None:
        self.add("warning", *args, **kwargs)

    @property
    def errors(self) -> list[Finding]:
        return [item for item in self.findings if item.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [item for item in self.findings if item.severity == "warning"]

    def sorted(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda item: (
                item.path,
                item.scope,
                item.severity,
                item.code,
                item.message,
            ),
        )

    def as_dict(self, root: Path) -> dict[str, Any]:
        return {
            "validator": "agent-plugin v1.0.0 offline validator",
            "root": str(root),
            "specification": SUPPORTED_VERSION,
            "summary": {"errors": len(self.errors), "warnings": len(self.warnings)},
            "findings": [item.to_dict() for item in self.sorted()],
        }


class DuplicateKeyError(ValueError):
    pass


class PackageContainmentError(ValueError):
    pass


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def read_text(
    path: Path, report: Report, scope: str, runtime_effect: str
) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        report.error(
            "FILE_READ", scope, path, f"cannot read file: {exc}", runtime_effect
        )
        return None
    if b"\x00" in data:
        report.error(
            "FILE_NUL", scope, path, "text file contains a NUL byte", runtime_effect
        )
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error(
            "FILE_UTF8", scope, path, f"file is not valid UTF-8: {exc}", runtime_effect
        )
        return None


def load_json(
    path: Path, report: Report, scope: str, runtime_effect: str
) -> Any | None:
    text = read_text(path, report, scope, runtime_effect)
    if text is None:
        return None
    try:
        return json.loads(text, object_pairs_hook=_unique_pairs)
    except DuplicateKeyError as exc:
        report.error("JSON_DUPLICATE_KEY", scope, path, str(exc), runtime_effect)
    except json.JSONDecodeError as exc:
        report.error(
            "JSON_SYNTAX",
            scope,
            path,
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            runtime_effect,
        )
    return None


def safe_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def resolve_within(
    root: Path, path: Path, *, strict: bool = False
) -> tuple[bool, Path | None, str | None]:
    try:
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=strict)
        common = Path(os.path.commonpath((str(resolved_root), str(resolved_path))))
    except (OSError, ValueError) as exc:
        return False, None, str(exc)
    return common == resolved_root, resolved_path, None


def is_link_or_reparse(path: Path) -> bool:
    metadata = path.lstat()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def opened_file_path(stream: BinaryIO, fallback: Path) -> Path:
    if os.name != "nt":
        return fallback.resolve(strict=True)
    import ctypes
    import msvcrt
    from ctypes import wintypes

    capacity = 32768
    buffer = ctypes.create_unicode_buffer(capacity)
    handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
    length = ctypes.windll.kernel32.GetFinalPathNameByHandleW(
        handle, buffer, capacity, 0
    )
    if length == 0 or length >= capacity:
        error = ctypes.get_last_error()
        raise OSError(error, "cannot resolve the opened file handle")
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def validate_package_root(root: Path, report: Report) -> Path | None:
    try:
        root = root.expanduser().absolute()
    except OSError as exc:
        report.error(
            "PLUGIN_ROOT_RESOLVE",
            "plugin",
            str(root),
            f"cannot normalize plugin root: {exc}",
            "Reject plugin.",
        )
        return None
    if not root.exists():
        report.error(
            "PLUGIN_ROOT_MISSING",
            "plugin",
            str(root),
            "plugin root does not exist",
            "Reject plugin.",
        )
        return None
    if not root.is_dir():
        report.error(
            "PLUGIN_ROOT_KIND",
            "plugin",
            str(root),
            "plugin root is not a directory",
            "Reject plugin.",
        )
        return None
    try:
        return root.resolve(strict=True)
    except OSError as exc:
        report.error(
            "PLUGIN_ROOT_RESOLVE",
            "plugin",
            str(root),
            f"cannot resolve plugin root: {exc}",
            "Reject plugin.",
        )
        return None


def validate_symlink_containment(root: Path, report: Report) -> None:
    for current, dirs, files in os.walk(str(root), followlinks=False):
        current_path = Path(current)
        entries: list[Path] = []
        retained_dirs: list[str] = []
        for name in dirs:
            path = current_path / name
            try:
                linked = is_link_or_reparse(path)
            except OSError as exc:
                report.error(
                    "PACKAGE_LINK_INSPECT",
                    "package",
                    safe_relative(path, root),
                    f"cannot inspect link or reparse-point metadata: {exc}",
                    "Deny access at the narrowest component or path boundary.",
                )
                continue
            if linked:
                entries.append(path)
            else:
                retained_dirs.append(name)
        dirs[:] = retained_dirs
        for name in files:
            path = current_path / name
            try:
                if is_link_or_reparse(path):
                    entries.append(path)
            except OSError as exc:
                report.error(
                    "PACKAGE_LINK_INSPECT",
                    "package",
                    safe_relative(path, root),
                    f"cannot inspect link or reparse-point metadata: {exc}",
                    "Deny access at the narrowest component or path boundary.",
                )
        for path in entries:
            relative = safe_relative(path, root)
            try:
                target = path.resolve(strict=True)
            except OSError as exc:
                report.error(
                    "PACKAGE_LINK_BROKEN",
                    "package",
                    relative,
                    f"link or reparse point cannot be resolved: {exc}",
                    "Deny access at the narrowest component or path boundary.",
                )
                continue
            contained, _, _ = resolve_within(root, target, strict=True)
            if not contained:
                report.error(
                    "PACKAGE_LINK_ESCAPE",
                    "package",
                    relative,
                    f"link or reparse point resolves outside plugin root to {target}",
                    "Deny access at the narrowest component or path boundary.",
                    "Keep links inside the resolved plugin root or replace them with regular package files.",
                )


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(str(root), followlinks=False):
        current_path = Path(current)
        dirs[:] = [
            name for name in sorted(dirs) if not is_link_or_reparse(current_path / name)
        ]
        for name in sorted(files):
            yield current_path / name


def schema_version(value: Any, kind: str) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        rf"https://agent-plugins\.org/schemas/([^/]+)/{re.escape(kind)}\.schema\.json",
        value,
    )
    return match.group(1) if match else None


def is_string(value: Any) -> bool:
    return isinstance(value, str)
