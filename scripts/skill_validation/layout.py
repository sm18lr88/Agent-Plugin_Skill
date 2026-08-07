"""Define the visible root entries in this project's distribution package."""

from __future__ import annotations

DISTRIBUTION_ENTRIES = frozenset({
    "agents",
    "assets",
    "evals",
    "licenses",
    "maintenance",
    "references",
    "scripts",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "SKILL.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
})


def is_local_root_entry(name: str) -> bool:
    return name.startswith(".") or name == "dist"
