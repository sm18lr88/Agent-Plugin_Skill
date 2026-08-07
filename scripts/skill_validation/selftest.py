"""Exercise project validation with isolated source and package fixtures."""

from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from .package import GitResult, GitRunner, validate_root

SOURCE = Path(__file__).resolve().parents[2]
IGNORE = shutil.ignore_patterns(
    ".*",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


def fixture(temporary: str, label: str = "base") -> Path:
    root = Path(temporary) / label / "agent-plugin"
    shutil.copytree(SOURCE, root, ignore=IGNORE)
    return root


def errors(
    root: Path, mode: str = "package", git: GitRunner | None = None
) -> list[str]:
    if git is None:
        _, report = validate_root(root, mode, run_script_tests=False)
    else:
        _, report = validate_root(root, mode, run_script_tests=False, git=git)
    return [finding.message for finding in report.errors]


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SOURCE / "scripts/validate_skill.py"), *args],
        cwd=SOURCE,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def assert_cli_contract() -> None:
    invalid = (
        (),
        ("--source-checkout", "--package"),
        ("--self-test", "--source-checkout"),
        ("--self-test", "--package"),
        ("other", "--self-test"),
        ("--self-test", "--skip-script-tests"),
    )
    for arguments in invalid:
        result = cli(*arguments)
        assert result.returncode == 2, (arguments, result.stdout, result.stderr)
        assert result.stderr.startswith("validate_skill:")


def assert_metadata(root: Path) -> None:
    metadata = root / "agents/openai.yaml"
    original = metadata.read_text(encoding="utf-8")
    metadata.write_text("interface:\n  display_name: bad\n", encoding="utf-8")
    assert any("exact OpenAI" in item for item in errors(root))
    metadata.write_text(original.replace("\n", "\r\n"), encoding="utf-8", newline="")
    assert not errors(root), errors(root)
    metadata.write_text(original, encoding="utf-8")

    ledger_path = root / "maintenance/upstreams.lock.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger_path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    assert any("duplicate key" in item for item in errors(root))
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

    ledger["sources"]["agent-plugins-spec"]["reviewed_commit"] = "a" * 40
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    assert any("reviewed_commit" in item for item in errors(root))


def assert_schema_tamper(root: Path) -> None:
    schema = root / "references/schemas/1.0.0/plugin.schema.json"
    schema.write_text(schema.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert any("vendored schema hash changed" in item for item in errors(root))


def assert_filesystem_and_safety(root: Path) -> None:
    fake_link = os.stat_result((stat.S_IFLNK, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    with patch.object(Path, "lstat", lambda _self: fake_link):
        _, report = validate_root(root, "package", run_script_tests=False)
    assert any(
        "skill root must not be a symlink" in item.message for item in report.errors
    )

    link = root / "linked-file"
    try:
        link.symlink_to(root / "README.md")
    except OSError as exc:
        if exc.errno not in {errno.EACCES, errno.EPERM, errno.ENOTSUP}:
            raise
    else:
        assert any("symlinks are not allowed" in item for item in errors(root))
        link.unlink()

    if os.name == "nt":
        import _winapi

        junction_target = root / "junction-target"
        junction_target.mkdir()
        junction = root / "junction"
        _winapi.CreateJunction(str(junction_target), str(junction))
        assert any("reparse points are not allowed" in item for item in errors(root))
        junction.rmdir()
        junction_target.rmdir()

    unsafe = root / "scripts/unsafe.py"
    unsafe.write_text(
        "import subprocess\nsubprocess.run([], shell=True)\n", encoding="utf-8"
    )
    assert any("shell enabled" in item for item in errors(root))
    unsafe.unlink()

    headerless = root / "scripts/headerless.py"
    headerless.write_text("pass\n", encoding="utf-8")
    assert any("description docstring" in item for item in errors(root))
    headerless.unlink()

    transient = root / "__pycache__"
    transient.mkdir()
    assert any("transient state" in item for item in errors(root))
    transient.rmdir()

    unexpected = root / "notes.txt"
    unexpected.write_text("not declared\n", encoding="utf-8")
    assert any("undeclared root entry" in item for item in errors(root))
    unexpected.unlink()

    changelog = root / "CHANGELOG.md"
    changelog.unlink()
    assert any("required path is missing" in item for item in errors(root))


def assert_source_mode(root: Path) -> None:
    def missing_git(_args: tuple[str, ...], _root: Path) -> GitResult:
        return GitResult(127, b"", b"git unavailable")

    assert any(
        "git is required" in item
        for item in errors(root, "source-checkout", missing_git)
    )

    def clean(args: tuple[str, ...], checkout: Path) -> GitResult:
        if args[0] == "rev-parse":
            return GitResult(0, f"{checkout}\n".encode(), b"")
        return GitResult(0, b"", b"")

    source_control = root / ".git"
    source_control.mkdir()
    assert not errors(root, "source-checkout", clean), errors(
        root, "source-checkout", clean
    )
    assert any("source-control state" in item for item in errors(root, "package"))

    source_control.rmdir()

    def dirty(args: tuple[str, ...], checkout: Path) -> GitResult:
        if args[0] == "rev-parse":
            return GitResult(0, f"{checkout}\n".encode(), b"")
        return GitResult(0, b" M README.md\0", b"")

    assert any(
        "source checkout is not clean" in item
        for item in errors(root, "source-checkout", dirty)
    )


def assert_no_bytecode() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = fixture(temporary, "bytecode")
        result = subprocess.run(
            [sys.executable, str(root / "scripts/validate_plugin.py"), "--self-test"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert not [
            path for path in (root / "scripts").rglob("__pycache__") if path.is_dir()
        ]


def self_test() -> None:
    assert_cli_contract()
    with tempfile.TemporaryDirectory() as temporary:
        root = fixture(temporary)
        baseline = errors(root)
        assert not baseline, baseline

        readme = root / "README.md"
        original = readme.read_text(encoding="utf-8")
        readme.write_text("[Broken](missing.md)\n", encoding="utf-8")
        assert any("broken local link" in item for item in errors(root))
        readme.write_text(original, encoding="utf-8")

        assert_metadata(root)
        root = fixture(temporary, "schema")
        assert_schema_tamper(root)
        root = fixture(temporary, "filesystem")
        assert_filesystem_and_safety(root)
        root = fixture(temporary, "git")
        assert_source_mode(root)
    assert_no_bytecode()
    print("validate_skill self-test: PASS")
