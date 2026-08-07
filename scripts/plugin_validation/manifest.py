"""Validate the required Agent Plugins manifest and its failure boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .core import (
    NAMESPACE_RE,
    PLUGIN_NAME_RE,
    PLUGIN_SCHEMA,
    SEMVER_RE,
    SUPPORTED_VERSION,
    Report,
    load_json,
    resolve_within,
    schema_version,
)

ALLOWED_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
AUTHOR_FIELDS = {"name", "email", "url"}


@dataclass(frozen=True, slots=True)
class ManifestResult:
    data: dict[str, Any] | None
    version: str | None
    fatal: bool


def _error(
    report: Report, code: str, path: str, message: str, *, fatal: bool = True
) -> bool:
    effect = (
        "Reject plugin; do not discover or execute components."
        if fatal
        else "Report and ignore this field; continue if the remaining manifest is valid."
    )
    report.error(code, "manifest", path, message, effect)
    return fatal


def _url_advisory(report: Report, field: str, value: str) -> None:
    if not value:
        report.warn(
            "MANIFEST_EMPTY_METADATA",
            "manifest",
            f"plugin.json#/{field}",
            f"{field} is empty",
            "No required client failure; metadata quality advisory.",
        )
        return
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        report.warn(
            "MANIFEST_URL_ADVISORY",
            "manifest",
            f"plugin.json#/{field}",
            f"{field} is not an absolute HTTP(S) URL",
            "No required client failure; core validates this field only as a string.",
            "Use a stable HTTPS URL for release metadata.",
        )


def validate_manifest(root: Path, report: Report) -> ManifestResult:
    path = root / "plugin.json"
    relative = "plugin.json"
    if not path.exists() and not path.is_symlink():
        _error(
            report, "MANIFEST_MISSING", relative, "required root plugin.json is missing"
        )
        return ManifestResult(None, None, True)
    if not path.is_file():
        _error(
            report,
            "MANIFEST_KIND",
            relative,
            "plugin.json does not resolve to a regular file",
        )
        return ManifestResult(None, None, True)
    contained, resolved, problem = resolve_within(root, path, strict=True)
    if not contained:
        detail = f": {problem}" if problem else f" to {resolved}"
        _error(
            report,
            "MANIFEST_ESCAPE",
            relative,
            f"plugin.json does not resolve within the plugin root{detail}",
        )
        return ManifestResult(None, None, True)
    data = load_json(
        path,
        report,
        "manifest",
        "Reject plugin; do not discover or execute components.",
    )
    if data is None:
        return ManifestResult(None, None, True)
    if not isinstance(data, dict):
        _error(
            report,
            "MANIFEST_OBJECT",
            relative,
            "plugin.json top level must be an object",
        )
        return ManifestResult(None, None, True)

    fatal = False
    unknown = sorted(set(data) - ALLOWED_FIELDS)
    for field in unknown:
        _error(
            report,
            "MANIFEST_UNKNOWN_FIELD",
            f"plugin.json#/{field}",
            f"unknown top-level field {field!r}; core discovery cannot be redirected or extended here",
            fatal=False,
        )

    schema = data.get("$schema")
    version = schema_version(schema, "plugin")
    if schema != PLUGIN_SCHEMA:
        fatal |= _error(
            report,
            "MANIFEST_SCHEMA",
            "plugin.json#/$schema",
            f"$schema must be the canonical supported identifier {PLUGIN_SCHEMA!r}; found {schema!r}",
        )
    if version is not None and version != SUPPORTED_VERSION:
        fatal |= _error(
            report,
            "MANIFEST_VERSION_UNSUPPORTED",
            "plugin.json#/$schema",
            f"validator supports Agent Plugins {SUPPORTED_VERSION}, not {version}",
        )

    name = data.get("name")
    if not isinstance(name, str):
        fatal |= _error(
            report, "MANIFEST_NAME_TYPE", "plugin.json#/name", "name must be a string"
        )
    elif not (1 <= len(name) <= 64) or not PLUGIN_NAME_RE.fullmatch(name):
        fatal |= _error(
            report,
            "MANIFEST_NAME",
            "plugin.json#/name",
            "name must be 1-64 lowercase ASCII letters/digits/hyphens/periods, begin and end alphanumeric, and contain no '--' or '..'",
        )
    elif root.name != name:
        report.warn(
            "MANIFEST_DIRECTORY_NAME",
            "manifest",
            "plugin.json#/name",
            f"manifest name {name!r} differs from package directory {root.name!r}",
            "No core failure; distribution/install behavior may be less predictable.",
            "Prefer matching the package directory to the manifest name.",
        )

    for field in ("version", "description", "homepage", "repository", "license"):
        if field in data and not isinstance(data[field], str):
            fatal |= _error(
                report,
                "MANIFEST_FIELD_TYPE",
                f"plugin.json#/{field}",
                f"{field} must be a string",
            )

    version_value = data.get("version")
    if (
        isinstance(version_value, str)
        and version_value
        and not SEMVER_RE.fullmatch(version_value)
    ):
        report.warn(
            "MANIFEST_VERSION_ADVISORY",
            "manifest",
            "plugin.json#/version",
            f"version {version_value!r} is not canonical Semantic Versioning",
            "No required client failure; SemVer is recommended, not mandatory.",
        )
    for field in ("homepage", "repository"):
        value = data.get(field)
        if isinstance(value, str):
            _url_advisory(report, field, value)

    author = data.get("author")
    if "author" in data:
        if not isinstance(author, dict):
            fatal |= _error(
                report,
                "MANIFEST_AUTHOR_TYPE",
                "plugin.json#/author",
                "author must be an object",
            )
        else:
            for field in sorted(set(author) - AUTHOR_FIELDS):
                fatal |= _error(
                    report,
                    "MANIFEST_AUTHOR_FIELD",
                    f"plugin.json#/author/{field}",
                    f"author field {field!r} is not permitted",
                )
            for field, value in author.items():
                if field in AUTHOR_FIELDS and not isinstance(value, str):
                    fatal |= _error(
                        report,
                        "MANIFEST_AUTHOR_VALUE",
                        f"plugin.json#/author/{field}",
                        f"author.{field} must be a string",
                    )
            email = author.get("email")
            if (
                isinstance(email, str)
                and email
                and not re.fullmatch(r"[^\s@]+@[^\s@]+", email)
            ):
                report.warn(
                    "MANIFEST_EMAIL_ADVISORY",
                    "manifest",
                    "plugin.json#/author/email",
                    "author.email is not shaped like an email address",
                    "No required client failure; core validates it only as a string.",
                )
            url = author.get("url")
            if isinstance(url, str):
                _url_advisory(report, "author/url", url)

    keywords = data.get("keywords")
    if "keywords" in data:
        if not isinstance(keywords, list) or not all(
            isinstance(item, str) for item in keywords
        ):
            fatal |= _error(
                report,
                "MANIFEST_KEYWORDS",
                "plugin.json#/keywords",
                "keywords must be an array of strings",
            )
        elif len(keywords) != len(set(keywords)):
            report.warn(
                "MANIFEST_KEYWORDS_DUPLICATE",
                "manifest",
                "plugin.json#/keywords",
                "keywords contains duplicates",
                "No required client failure; metadata quality advisory.",
            )

    extensions = data.get("extensions")
    if "extensions" in data and not isinstance(extensions, dict):
        _error(
            report,
            "MANIFEST_EXTENSIONS_TYPE",
            "plugin.json#/extensions",
            "extensions must be an object",
            fatal=False,
        )
    elif isinstance(extensions, dict):
        for namespace, value in extensions.items():
            pointer = f"plugin.json#/extensions/{namespace}"
            if not NAMESPACE_RE.fullmatch(namespace):
                report.warn(
                    "EXTENSION_NAMESPACE_SHAPE",
                    f"extension:{namespace}",
                    pointer,
                    f"namespace {namespace!r} is not in the conventional lowercase reverse-domain form",
                    "Unsupported namespaces are ignored; implemented namespace behavior is client-defined.",
                    "Use the stable namespace documented by the domain-owning client.",
                )
            if not isinstance(value, dict):
                fatal |= _error(
                    report,
                    "EXTENSION_VALUE_TYPE",
                    pointer,
                    "extension namespace value must be an object",
                )

    return ManifestResult(data, version, fatal)
