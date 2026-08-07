"""Detect private-environment coupling and unsafe primitives in this skill package."""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TEXT_PATTERNS = {
    "PRIVATE_CONTAINER_PATH": re.compile(
        r"(?:/home/oai(?:/|\b)|/mnt/data(?:/|\b)|sandbox:/mnt/data)",
        re.IGNORECASE,
    ),
    "PRIVATE_USER_PATH": re.compile(
        r"(?:[A-Za-z]:\\Users\\[^\\\s]+|/Users/[^/\s]+|/home/(?!user\b)[^/\s]+/)",
        re.IGNORECASE,
    ),
}
NETWORK_IMPORTS = {
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "ftplib",
    "urllib.request",
    "http.client",
}


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    path: str
    line: int
    message: str


def _text_issues(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    paths = [root / "SKILL.md", root / "README.md"]
    paths += (
        sorted((root / "references").rglob("*.md"))
        if (root / "references").is_dir()
        else []
    )
    paths += (
        sorted((root / "maintenance").rglob("*.md"))
        if (root / "maintenance").is_dir()
        else []
    )
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        for code, pattern in TEXT_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                issues.append(
                    Issue(
                        code,
                        relative,
                        line,
                        f"environment-coupled text: {match.group(0)!r}",
                    )
                )
    return issues


def _python_issues(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    scripts = root / "scripts"
    if not scripts.is_dir():
        return issues
    for path in sorted(scripts.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            issues.append(
                Issue(
                    "PYTHON_PARSE", relative, getattr(exc, "lineno", 1) or 1, str(exc)
                )
            )
            continue
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = alias.name
                    if alias.name in NETWORK_IMPORTS:
                        issues.append(
                            Issue(
                                "NETWORK_IMPORT",
                                relative,
                                node.lineno,
                                f"network-capable import {alias.name!r}",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in NETWORK_IMPORTS:
                    issues.append(
                        Issue(
                            "NETWORK_IMPORT",
                            relative,
                            node.lineno,
                            f"network-capable import from {module!r}",
                        )
                    )
            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr
                    in {"run", "Popen", "call", "check_call", "check_output"}
                    and any(
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in node.keywords
                    )
                ):
                    issues.append(
                        Issue(
                            "SHELL_TRUE",
                            relative,
                            node.lineno,
                            "subprocess call enables shell=True",
                        )
                    )
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "system"
                ):
                    issues.append(
                        Issue(
                            "OS_SYSTEM",
                            relative,
                            node.lineno,
                            "os.system invokes a shell",
                        )
                    )
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    issues.append(
                        Issue(
                            "DYNAMIC_EXECUTION",
                            relative,
                            node.lineno,
                            f"use of {node.func.id}()",
                        )
                    )
    return issues


def check(root: Path) -> list[Issue]:
    root = root.expanduser().resolve()
    return sorted(
        _text_issues(root) + _python_issues(root),
        key=lambda item: (item.path, item.line, item.code),
    )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "references").mkdir()
        (root / "scripts").mkdir()
        (root / "SKILL.md").write_text(
            "Use /mnt/data/private here.\n", encoding="utf-8"
        )
        (root / "README.md").write_text("portable\n", encoding="utf-8")
        (root / "scripts" / "bad.py").write_text(
            "import requests\nimport subprocess\nsubprocess.run('x', shell=True)\n",
            encoding="utf-8",
        )
        codes = {item.code for item in check(root)}
        assert {"PRIVATE_CONTAINER_PATH", "NETWORK_IMPORT", "SHELL_TRUE"} <= codes
        (root / "SKILL.md").write_text(
            "Use /path/to/plugin as documentation.\n", encoding="utf-8"
        )
        (root / "scripts" / "bad.py").write_text(
            "from urllib.parse import urlsplit\n", encoding="utf-8"
        )
        assert not check(root)
    print("portability_check self-test: PASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv or sys.argv[1:])
    if args.self_test:
        if args.root != ".":
            print(
                "portability_check: --self-test cannot be combined with a root",
                file=sys.stderr,
            )
            return 2
        try:
            self_test()
        except (AssertionError, OSError, ValueError) as exc:
            print(f"portability_check self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    issues = check(Path(args.root))
    for item in issues:
        print(f"ERROR {item.code} {item.path}:{item.line}: {item.message}")
    if issues:
        print(f"portability check: FAILED ({len(issues)} issue(s))")
        return 1
    print("portability check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
