"""Report visible secret risks and non-core compatibility artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from .core import Report, iter_files, safe_relative

SECRET_FILE_RE = re.compile(
    r"(?:^|/)(?:\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|.*\.(?:pem|p12|pfx|key)|credentials(?:\.json)?|secrets?\.(?:json|ya?ml|toml))$",
    re.IGNORECASE,
)
SECRET_TEXT_RE = re.compile(
    rb"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}\b|(?i:authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~-]{12,}))"
)
LEGACY_TOP_LEVEL = {
    ".claude-plugin",
    ".codex-plugin",
    ".cursor",
    ".github",
    ".kiro",
    ".mcp.json",
    "agents",
    "commands",
    "hooks",
    "prompts",
}


def validate_package_security(root: Path, report: Report) -> None:
    for path in iter_files(root):
        relative = safe_relative(path, root)
        if SECRET_FILE_RE.search(relative):
            report.warn(
                "PACKAGE_SECRET_FILE",
                "package",
                relative,
                "package contains a filename commonly used for credentials or private key material",
                "Not a general core-format failure; package data remains visible and is unsafe to distribute.",
                "Remove secrets and use client-managed authorization/secret storage. The bundled packager refuses this package.",
            )
        try:
            if path.stat().st_size <= 2 * 1024 * 1024:
                data = path.read_bytes()
            else:
                continue
        except OSError:
            continue
        if SECRET_TEXT_RE.search(data):
            report.warn(
                "PACKAGE_SECRET_CONTENT",
                "package",
                relative,
                "file contains high-confidence credential or private-key material",
                "Not a general core-format failure; package data remains visible and is unsafe to distribute.",
                "Revoke real credentials, remove them from history/artifacts, and use client-managed secret storage. The bundled packager refuses this package.",
            )

    for name in sorted(LEGACY_TOP_LEVEL):
        path = root / name
        if path.exists() or path.is_symlink():
            report.warn(
                "CLIENT_COMPATIBILITY_ARTIFACT",
                "compatibility",
                name,
                f"top-level {name!r} is not a portable Agent Plugins v1 core component",
                "Portable clients ignore it unless an owning client explicitly treats it as compatibility behavior.",
                "Classify it as a documented client extension, separate compatibility package, or distribution metadata.",
            )
