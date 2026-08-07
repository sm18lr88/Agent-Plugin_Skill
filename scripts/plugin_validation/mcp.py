"""Validate root MCP configuration and isolate invalid server entries."""

from __future__ import annotations

import ipaddress
import os
import posixpath
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .core import (
    MCP_SCHEMA,
    SUPPORTED_VERSION,
    Report,
    load_json,
    resolve_within,
    schema_version,
)

TOP_FIELDS = {"$schema", "mcpServers"}
STDIO_FIELDS = {"type", "command", "args", "env", "cwd"}
REMOTE_FIELDS = {"type", "url", "headers"}
HEADER_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
SHELLISH_RE = re.compile(r"(?:&&|\|\||[;|<>`\r\n])")
SECRET_NAME_RE = re.compile(
    r"(?:^|_)(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE_?KEY|CREDENTIAL)(?:_|$)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}\b)"
)
SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}
PLACEHOLDERS = ("${PLUGIN_ROOT}", "${PLUGIN_DATA}")


def _server_error(
    report: Report,
    server: str,
    code: str,
    field: str,
    message: str,
    recommendation: str = "",
) -> None:
    report.error(
        code,
        f"server:{server}",
        f"mcp.json#/mcpServers/{server}{field}",
        message,
        "Skip this MCP server entry; continue other servers and component types.",
        recommendation,
    )


def _server_warn(
    report: Report,
    server: str,
    code: str,
    field: str,
    message: str,
    recommendation: str = "",
) -> None:
    report.warn(
        code,
        f"server:{server}",
        f"mcp.json#/mcpServers/{server}{field}",
        message,
        "No required conformance failure for this advisory; runtime or portability may be affected.",
        recommendation,
    )


def _has_lexical_escape(suffix: str) -> bool:
    depth = 0
    for part in suffix.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        else:
            depth += 1
    return False


def _validate_rooted_path(
    root: Path, server: str, field: str, value: str, report: Report
) -> None:
    if "\\" in value:
        _server_error(
            report,
            server,
            "MCP_PATH_SEPARATOR",
            field,
            "portable configured paths use forward slashes, not backslashes",
        )
        return
    base = ""
    suffix = ""
    if value.startswith("./"):
        base, suffix = "plugin", value[2:]
    elif value == "${PLUGIN_ROOT}" or value.startswith("${PLUGIN_ROOT}/"):
        base, suffix = "plugin", value[len("${PLUGIN_ROOT}") :].lstrip("/")
    elif value == "${PLUGIN_DATA}" or value.startswith("${PLUGIN_DATA}/"):
        base, suffix = "data", value[len("${PLUGIN_DATA}") :].lstrip("/")
    else:
        _server_error(
            report,
            server,
            "MCP_CWD_FORM",
            field,
            "cwd must begin './', '${PLUGIN_ROOT}', or '${PLUGIN_DATA}'",
        )
        return
    if _has_lexical_escape(suffix):
        _server_error(
            report,
            server,
            "MCP_CWD_ESCAPE",
            field,
            f"path escapes its {base} root after normalization",
        )
        return
    if base == "plugin":
        candidate = root / posixpath.normpath(suffix or ".")
        contained, resolved, problem = resolve_within(root, candidate, strict=False)
        if not contained:
            _server_error(
                report,
                server,
                "MCP_CWD_ESCAPE",
                field,
                f"path resolves outside plugin root: {problem or resolved}",
            )


def _validate_command(root: Path, server: str, value: Any, report: Report) -> None:
    field = "/command"
    if not isinstance(value, str) or not value:
        _server_error(
            report,
            server,
            "MCP_COMMAND",
            field,
            "stdio command must be a non-empty string",
        )
        return
    if value.startswith("./"):
        if "\\" in value or _has_lexical_escape(value[2:]):
            _server_error(
                report,
                server,
                "MCP_COMMAND_ESCAPE",
                field,
                "plugin-relative command must remain inside plugin root and use forward slashes",
            )
            return
        candidate = root / posixpath.normpath(value[2:] or ".")
        contained, resolved, problem = resolve_within(root, candidate, strict=False)
        if not contained:
            _server_error(
                report,
                server,
                "MCP_COMMAND_ESCAPE",
                field,
                f"command resolves outside plugin root: {problem or resolved}",
            )
        elif candidate.exists() and not candidate.is_file():
            _server_error(
                report,
                server,
                "MCP_COMMAND_KIND",
                field,
                "bundled command exists but is not a regular file",
            )
        elif not candidate.exists():
            _server_warn(
                report,
                server,
                "MCP_COMMAND_MISSING",
                field,
                f"bundled command path does not currently exist: {value}",
                "Bundle the executable before release and test it on every platform.",
            )
        elif os.name != "nt" and not os.access(candidate, os.X_OK):
            _server_warn(
                report,
                server,
                "MCP_COMMAND_NOT_EXECUTABLE",
                field,
                f"bundled command is not executable on this filesystem: {value}",
            )
    else:
        if "/" in value or "\\" in value or re.match(r"^[A-Za-z]:", value):
            _server_error(
                report,
                server,
                "MCP_COMMAND_FORM",
                field,
                "command must be a bare executable name or a plugin-relative path beginning './'",
            )
        else:
            _server_warn(
                report,
                server,
                "MCP_COMMAND_EXTERNAL",
                field,
                f"bare command {value!r} depends on the client platform's executable search",
                "Document the runtime dependency and do not depend on configured PATH resolution.",
            )
    if any(token in value for token in PLACEHOLDERS):
        _server_warn(
            report,
            server,
            "MCP_COMMAND_NO_EXPANSION",
            field,
            "command contains a plugin placeholder, but command never receives placeholder expansion",
        )
    if SHELLISH_RE.search(value):
        _server_warn(
            report,
            server,
            "MCP_COMMAND_SHELLISH",
            field,
            "command resembles a shell command or multi-token command; clients launch one executable token",
            "Move arguments into the args array and avoid shell operators.",
        )


def _validate_env(server: str, value: Any, report: Report) -> None:
    if not isinstance(value, dict):
        _server_error(
            report,
            server,
            "MCP_ENV_TYPE",
            "/env",
            "env must be an object mapping names to strings",
        )
        return
    for key, item in value.items():
        field = f"/env/{key}"
        if key in {"PLUGIN_ROOT", "PLUGIN_DATA"}:
            _server_error(
                report,
                server,
                "MCP_ENV_RESERVED",
                field,
                f"{key!r} conflicts with a client-owned reserved environment variable",
            )
        elif key.upper() in {"PLUGIN_ROOT", "PLUGIN_DATA"}:
            _server_warn(
                report,
                server,
                "MCP_ENV_PLATFORM_COLLISION",
                field,
                f"{key!r} conflicts with a reserved environment variable on case-insensitive platforms",
                "Rename this environment entry for cross-platform use.",
            )
        if not isinstance(item, str):
            _server_error(
                report,
                server,
                "MCP_ENV_VALUE",
                field,
                "environment value must be a string",
            )
            continue
        if SECRET_VALUE_RE.search(item):
            _server_warn(
                report,
                server,
                "MCP_ENV_SECRET",
                field,
                "environment value appears to contain embedded credential or private-key material",
                "Remove real credentials from the package. Use the client's secret or authentication system.",
            )
        elif SECRET_NAME_RE.search(key) and item:
            _server_warn(
                report,
                server,
                "MCP_ENV_SECRET_RISK",
                field,
                "credential-like environment name has a visible package value",
                "Agent Plugins v1 has no portable secret reference; redesign client-managed secret injection.",
            )


def _is_loopback(host: str | None) -> bool:
    if host is None:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _validate_headers(server: str, value: Any, report: Report) -> None:
    if not isinstance(value, dict):
        _server_error(
            report,
            server,
            "MCP_HEADERS_TYPE",
            "/headers",
            "headers must be an object mapping names to strings",
        )
        return
    seen: dict[str, str] = {}
    for name, item in value.items():
        field = f"/headers/{name}"
        folded = name.casefold()
        if not HEADER_NAME_RE.fullmatch(name):
            _server_error(
                report,
                server,
                "MCP_HEADER_NAME",
                field,
                "header name is not a valid HTTP field name",
            )
        if folded in seen:
            _server_error(
                report,
                server,
                "MCP_HEADER_DUPLICATE",
                field,
                f"header duplicates {seen[folded]!r} under case-insensitive comparison",
            )
        else:
            seen[folded] = name
        if not isinstance(item, str):
            _server_error(
                report,
                server,
                "MCP_HEADER_VALUE",
                field,
                "header value must be a string",
            )
            continue
        if any((ord(char) < 32 and char != "\t") or ord(char) == 127 for char in item):
            _server_error(
                report,
                server,
                "MCP_HEADER_CONTROL",
                field,
                "header value contains a prohibited control character",
            )
        if folded in SENSITIVE_HEADERS or SECRET_VALUE_RE.search(item):
            _server_warn(
                report,
                server,
                "MCP_HEADER_SECRET",
                field,
                "credential-bearing or secret-looking header is visible package data",
                "Remove real credentials. Use client-managed authorization.",
            )
        if any(token in item for token in PLACEHOLDERS) or re.search(
            r"\$\{[^}]+\}", item
        ):
            _server_warn(
                report,
                server,
                "MCP_HEADER_NO_EXPANSION",
                field,
                "headers do not receive placeholder or environment expansion; this value remains literal",
            )


def _validate_remote(server: str, data: dict[str, Any], report: Report) -> None:
    value = data.get("url")
    if not isinstance(value, str) or not value:
        _server_error(
            report,
            server,
            "MCP_URL",
            "/url",
            "remote MCP url must be a non-empty string",
        )
    else:
        if any(ord(character) <= 32 or ord(character) == 127 for character in value):
            _server_error(
                report,
                server,
                "MCP_URL_CONTROL",
                "/url",
                "url contains a raw space or control character",
            )
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError as exc:
            _server_error(
                report, server, "MCP_URL_PARSE", "/url", f"invalid URL: {exc}"
            )
        else:
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.hostname is None
            ):
                _server_error(
                    report,
                    server,
                    "MCP_URL_ABSOLUTE",
                    "/url",
                    "url must be an absolute HTTP or HTTPS URL with a host",
                )
            if parsed.username is not None or parsed.password is not None:
                _server_error(
                    report,
                    server,
                    "MCP_URL_USERINFO",
                    "/url",
                    "URL user information is visible package data",
                    "Remove credentials from the URL. Use client-managed authorization.",
                )
            if parsed.fragment:
                _server_error(
                    report,
                    server,
                    "MCP_URL_FRAGMENT",
                    "/url",
                    "URL fragments are not sent to an MCP server",
                    "Remove the fragment unless a target client documents different behavior.",
                )
            if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
                _server_error(
                    report,
                    server,
                    "MCP_URL_TLS",
                    "/url",
                    "non-loopback MCP endpoint uses unencrypted HTTP",
                    "Use HTTPS. Clients must warn or block before connecting to non-loopback HTTP endpoints.",
                )
            if re.search(r"\$\{[^}]+\}", value):
                _server_warn(
                    report,
                    server,
                    "MCP_URL_NO_EXPANSION",
                    "/url",
                    "URL does not receive placeholder or environment expansion; this value remains literal",
                )
    if "headers" in data:
        _validate_headers(server, data["headers"], report)


def _validate_server(root: Path, server: str, data: Any, report: Report) -> None:
    if not isinstance(data, dict):
        _server_error(
            report, server, "MCP_SERVER_OBJECT", "", "server entry must be an object"
        )
        return
    server_type = data.get("type")
    if server_type == "stdio":
        allowed = STDIO_FIELDS
    elif server_type in {"streamable-http", "sse"}:
        allowed = REMOTE_FIELDS
    else:
        _server_error(
            report,
            server,
            "MCP_SERVER_TYPE",
            "/type",
            f"type must be 'stdio', 'streamable-http', or 'sse'; found {server_type!r}",
        )
        return
    for field in sorted(set(data) - allowed):
        _server_error(
            report,
            server,
            "MCP_SERVER_FIELD",
            f"/{field}",
            f"field {field!r} is not allowed for {server_type}",
        )

    if server_type == "stdio":
        _validate_command(root, server, data.get("command"), report)
        args = data.get("args")
        if args is not None and (
            not isinstance(args, list)
            or not all(isinstance(item, str) for item in args)
        ):
            _server_error(
                report, server, "MCP_ARGS", "/args", "args must be an array of strings"
            )
        if "env" in data:
            _validate_env(server, data["env"], report)
        if "cwd" in data:
            cwd = data["cwd"]
            if not isinstance(cwd, str):
                _server_error(
                    report, server, "MCP_CWD_TYPE", "/cwd", "cwd must be a string"
                )
            else:
                _validate_rooted_path(root, server, "/cwd", cwd, report)
    else:
        _validate_remote(server, data, report)
        if server_type == "sse":
            _server_warn(
                report,
                server,
                "MCP_SSE_DEPRECATED",
                "/type",
                "legacy HTTP+SSE is deprecated and client support is optional",
                "Prefer Streamable HTTP when the endpoint supports it.",
            )


def validate_mcp(root: Path, manifest_version: str | None, report: Report) -> list[str]:
    path = root / "mcp.json"
    if not path.exists() and not path.is_symlink():
        return []
    if not path.is_file():
        report.error(
            "MCP_ROOT_KIND",
            "mcp",
            "mcp.json",
            "present fixed MCP location does not resolve to a regular file",
            "Disable MCP for this plugin; continue other component types.",
        )
        return []
    contained, resolved, problem = resolve_within(root, path, strict=True)
    if not contained:
        report.error(
            "MCP_ROOT_ESCAPE",
            "mcp",
            "mcp.json",
            f"mcp.json resolves outside plugin root: {problem or resolved}",
            "Disable MCP for this plugin; continue other component types.",
        )
        return []
    data = load_json(
        path,
        report,
        "mcp",
        "Disable MCP for this plugin; continue other component types.",
    )
    if data is None:
        return []
    if not isinstance(data, dict):
        report.error(
            "MCP_OBJECT",
            "mcp",
            "mcp.json",
            "mcp.json top level must be an object",
            "Disable MCP for this plugin; continue other component types.",
        )
        return []
    fatal = False
    for field in sorted(set(data) - TOP_FIELDS):
        fatal = True
        report.error(
            "MCP_TOP_FIELD",
            "mcp",
            f"mcp.json#/{field}",
            f"unknown top-level field {field!r}",
            "Disable MCP for this plugin; continue other component types.",
        )
    schema = data.get("$schema")
    version = schema_version(schema, "mcp")
    if schema != MCP_SCHEMA:
        fatal = True
        report.error(
            "MCP_SCHEMA",
            "mcp",
            "mcp.json#/$schema",
            f"$schema must be {MCP_SCHEMA!r}; found {schema!r}",
            "Disable MCP for this plugin; continue other component types.",
        )
    if version is not None and version != SUPPORTED_VERSION:
        fatal = True
        report.error(
            "MCP_VERSION_UNSUPPORTED",
            "mcp",
            "mcp.json#/$schema",
            f"validator supports Agent Plugins {SUPPORTED_VERSION}, not {version}",
            "Disable MCP for this plugin; continue other component types.",
        )
    if (
        manifest_version is not None
        and version is not None
        and version != manifest_version
    ):
        fatal = True
        report.error(
            "MCP_VERSION_MISMATCH",
            "mcp",
            "mcp.json#/$schema",
            f"MCP version {version} does not match plugin manifest version {manifest_version}",
            "Disable MCP for this plugin; continue other component types.",
        )
    if fatal:
        return []
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        report.error(
            "MCP_SERVERS_OBJECT",
            "mcp",
            "mcp.json#/mcpServers",
            "mcpServers must be an object",
            "Disable MCP for this plugin; continue other component types.",
        )
        return []
    valid_servers: list[str] = []
    for server, config in servers.items():
        prior_errors = len(report.errors)
        _validate_server(root, server, config, report)
        if len(report.errors) == prior_errors:
            valid_servers.append(server)
    return sorted(valid_servers)
