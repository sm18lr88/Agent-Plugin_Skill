"""Coordinate validation for source checkouts and distribution packages."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from plugin_validation import validate_plugin
from plugin_validation.core import is_link_or_reparse, resolve_within

from .core import (
    Report,
    validate_eval_jsonl,
    validate_json_files,
    validate_links,
    validate_required,
    validate_skill_file,
)
from .layout import DISTRIBUTION_ENTRIES
from .metadata import (
    validate_notice,
    validate_openai_metadata,
    validate_schema_snapshots,
    validate_upstream_ledger,
)
from .python_safety import validate_python_safety
from .simple_english import validate_simple_english

SOURCE_CONTROL = {".git", ".hg", ".svn"}
TRANSIENT = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    ".DS_Store",
}
SCRIPT_TESTS = (
    ("scripts/validate_plugin.py", "--self-test"),
    ("scripts/new_plugin.py", "--self-test"),
    ("scripts/package_plugin.py", "--self-test"),
    ("scripts/portability_check.py", "--self-test"),
    ("scripts/package_skill.py", "--self-test"),
    ("scripts/validate_skill.py", "--self-test"),
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class GitResult:
    returncode: int
    stdout: bytes
    stderr: bytes


GitRunner = Callable[[tuple[str, ...], Path], GitResult]


def _git(args: tuple[str, ...], root: Path) -> GitResult:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GitResult(127, b"", str(exc).encode())
    return GitResult(result.returncode, result.stdout, result.stderr)


def _filesystem(root: Path, mode: str, report: Report) -> list[Path]:
    try:
        lstat = root.lstat()
    except OSError as exc:
        report.error(root, f"cannot inspect skill root: {exc}")
        return []
    if stat.S_ISLNK(lstat.st_mode) or is_link_or_reparse(root):
        report.error(root, "skill root must not be a symlink or reparse point")
        return []
    if not stat.S_ISDIR(lstat.st_mode):
        report.error(root, "skill root must be a directory")
        return []
    if mode == "package":
        try:
            root_entries = list(root.iterdir())
        except OSError as exc:
            report.error(root, f"cannot inspect package root entries: {exc}")
            return []
        for entry in root_entries:
            if entry.name not in DISTRIBUTION_ENTRIES:
                report.error(
                    entry.name,
                    "this project's distribution package contains an undeclared root entry",
                )
    files: list[Path] = []
    for current, dirs, names in os.walk(str(root), followlinks=False):
        current_path = Path(current)
        retained_dirs: list[str] = []
        for name in sorted(dirs):
            path = current_path / name
            relative = path.relative_to(root)
            if is_link_or_reparse(path):
                report.error(
                    relative,
                    "symlinks are not allowed; reparse points are not allowed in the skill package",
                )
                continue
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                report.error(
                    relative,
                    f"directory resolves outside the skill root: {problem or resolved}",
                )
                continue
            if name in SOURCE_CONTROL:
                if mode == "package":
                    report.error(relative, "package contains source-control state")
                continue
            if any(part in TRANSIENT for part in relative.parts):
                if mode == "package":
                    report.error(relative, "package contains transient state")
                continue
            retained_dirs.append(name)
        dirs[:] = retained_dirs
        for name in sorted(names):
            path = current_path / name
            relative = path.relative_to(root)
            if is_link_or_reparse(path):
                report.error(
                    relative,
                    "symlinks are not allowed; reparse points are not allowed in the skill package",
                )
                continue
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                report.error(
                    relative,
                    f"file resolves outside the skill root: {problem or resolved}",
                )
                continue
            if any(part in SOURCE_CONTROL for part in relative.parts):
                if mode == "package":
                    report.error(relative, "package contains source-control state")
                continue
            if any(part in TRANSIENT for part in relative.parts):
                if mode == "package":
                    report.error(relative, "package contains transient state")
                continue
            if path.is_file():
                files.append(path)
    return sorted(files)


def _source_checkout(root: Path, report: Report, git: GitRunner) -> None:
    top = git(("rev-parse", "--show-toplevel"), root)
    if top.returncode != 0:
        report.error(
            root,
            f"git is required for --source-checkout: {top.stderr.decode(errors='replace').strip()}",
        )
        return
    try:
        git_root = Path(top.stdout.decode().strip()).resolve(strict=True)
        source_root = root.resolve(strict=True)
    except (UnicodeDecodeError, OSError) as exc:
        report.error(root, f"cannot decode or resolve Git and skill roots: {exc}")
        return
    if git_root != source_root:
        report.error(
            root, f"skill root must be the Git repository root; Git reports {git_root}"
        )
    status = git(("status", "--porcelain=v1", "--untracked-files=all", "-z"), root)
    if status.returncode != 0:
        report.error(
            root,
            f"cannot inspect Git status: {status.stderr.decode(errors='replace').strip()}",
        )
    elif status.stdout:
        records = [record for record in status.stdout.split(b"\0") if record]
        report.error(root, f"source checkout is not clean: {records!r}")


def _run_script_tests(root: Path, report: Report) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    for script, flag in SCRIPT_TESTS:
        try:
            result = subprocess.run(
                [sys.executable, "-E", "-B", str(root / script), flag],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            report.error(script, f"self-test could not run: {exc}")
            continue
        if result.returncode != 0:
            report.error(
                script,
                f"self-test failed ({result.returncode}): {result.stdout}{result.stderr}",
            )


def _validate_assets(root: Path, report: Report) -> None:
    example = validate_plugin(root / "assets/example-plugin")
    for finding in example.report.errors:
        report.error(
            "assets/example-plugin", f"example plugin {finding.code}: {finding.message}"
        )
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        for name in ("minimal", "full"):
            target = base / "example-plugin"
            target.mkdir(exist_ok=True)
            shutil.copy2(root / f"assets/plugin-{name}.json", target / "plugin.json")
            result = validate_plugin(target)
            for finding in result.report.errors:
                report.error(
                    f"assets/plugin-{name}.json",
                    f"template {finding.code}: {finding.message}",
                )
            shutil.rmtree(target)
        for name in ("stdio", "http", "mixed"):
            target = base / "example-plugin"
            target.mkdir(exist_ok=True)
            shutil.copy2(root / "assets/plugin-minimal.json", target / "plugin.json")
            shutil.copy2(root / f"assets/mcp-{name}.json", target / "mcp.json")
            result = validate_plugin(target)
            for finding in result.report.errors:
                report.error(
                    f"assets/mcp-{name}.json",
                    f"template {finding.code}: {finding.message}",
                )
            shutil.rmtree(target)


def validate_root(
    root: Path,
    mode: str,
    *,
    run_script_tests: bool,
    git: GitRunner = _git,
) -> tuple[Path | None, Report]:
    report = Report()
    try:
        root = root.expanduser().absolute()
    except OSError as exc:
        report.error(root, f"cannot normalize root: {exc}")
        return None, report
    files = _filesystem(root, mode, report)
    if not root.is_dir():
        return None, report
    validate_required(root, report)
    validate_skill_file(root, report)
    validate_links(root, files, report)
    validate_simple_english(root, files, report)
    validate_json_files(root, files, report)
    validate_eval_jsonl(root, report)
    validate_openai_metadata(root, report)
    validate_schema_snapshots(root, report)
    validate_upstream_ledger(root, report)
    validate_notice(root, report)
    validate_python_safety(root, files, report)
    _validate_assets(root, report)
    if mode == "source-checkout":
        _source_checkout(root, report, git)
        if run_script_tests:
            if root != PROJECT_ROOT:
                report.warn(
                    root,
                    "script self-tests were not executed because the selected source tree is not this validator's trusted project root",
                )
            elif not report.errors:
                _run_script_tests(root, report)
    return root, report
