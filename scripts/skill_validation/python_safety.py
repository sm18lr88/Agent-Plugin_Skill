"""Check Python modules for safe imports, calls, and execution settings."""

from __future__ import annotations

import ast
from pathlib import Path

from .core import Report

NETWORK_IMPORTS = {
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "ftplib",
    "urllib.request",
    "http.client",
}
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}


def validate_python_safety(root: Path, files: list[Path], report: Report) -> None:
    for path in files:
        if path.suffix != ".py":
            continue
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=relative)
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            report.error(relative, f"Python cannot be parsed: {exc}")
            continue
        if ast.get_docstring(tree, clean=False) is None:
            report.error(relative, "Python module must start with a description docstring")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in NETWORK_IMPORTS:
                        report.error(
                            relative,
                            f"network-capable import is not allowed: {alias.name}",
                        )
                continue
            if isinstance(node, ast.ImportFrom):
                if (node.module or "") in NETWORK_IMPORTS:
                    report.error(
                        relative,
                        f"network-capable import is not allowed: {node.module}",
                    )
                continue
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in SUBPROCESS_CALLS:
                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        report.error(relative, f"shell enabled at line {node.lineno}")
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "system"
            ):
                report.error(relative, f"os.system is not allowed at line {node.lineno}")
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                report.error(
                    relative,
                    f"dynamic {node.func.id} is not allowed at line {node.lineno}",
                )
