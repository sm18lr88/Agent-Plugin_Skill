"""Build a validated deterministic ZIP of this Agent Plugin skill project."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from plugin_validation.core import (
    PackageContainmentError,
    is_link_or_reparse,
    opened_file_path,
    resolve_within,
)
from plugin_validation.security import SECRET_FILE_RE, SECRET_TEXT_RE
from skill_validation import validate_root
from skill_validation.layout import DISTRIBUTION_ENTRIES, is_local_root_entry

EXCLUDED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "dist",
}
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".swp", ".tmp"}
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    output: Path
    sha256: str
    file_count: int


@dataclass(frozen=True, slots=True)
class FileEntry:
    path: Path
    data: bytes


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="skill project root; default: current directory",
    )
    parser.add_argument(
        "--output", help="archive path; default: agent-plugin.zip beside the project"
    )
    parser.add_argument(
        "--replace", action="store_true", help="explicitly replace an existing archive"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run deterministic export tests"
    )
    return parser.parse_args(argv)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except (OSError, ValueError):
        return False


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _stable_bytes(path: Path, root: Path) -> bytes:
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"skill export source is not a regular file: {path}")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        opened_path = opened_file_path(stream, path)
        contained, resolved, problem = resolve_within(
            root, opened_path, strict=True
        )
        if not contained:
            raise PackageContainmentError(
                "opened skill export file resolves outside the project root: "
                f"{path.relative_to(root).as_posix()} ({problem or resolved})"
            )
        data = stream.read()
    after = path.stat(follow_symlinks=False)
    if (
        _stat_identity(before) != _stat_identity(opened)
        or _stat_identity(opened) != _stat_identity(after)
    ):
        raise ValueError(f"skill export source changed while it was read: {path}")
    return data


def _files(root: Path) -> list[FileEntry]:
    files: list[FileEntry] = []
    for child in root.iterdir():
        if is_local_root_entry(child.name):
            continue
        if is_link_or_reparse(child):
            raise ValueError(
                f"skill export rejects symlink or reparse point: {child.name}"
            )
        if child.name not in DISTRIBUTION_ENTRIES:
            raise ValueError(
                f"skill export source has an undeclared root entry: {child.name}"
            )
    for current, dirs, names in os.walk(str(root), followlinks=False):
        current_path = Path(current)
        retained: list[str] = []
        for name in sorted(dirs):
            path = current_path / name
            relative = path.relative_to(root)
            if is_link_or_reparse(path):
                raise ValueError(
                    "skill export rejects symlink or reparse point directory: "
                    f"{relative.as_posix()}"
                )
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                raise PackageContainmentError(
                    "skill export directory resolves outside the project root: "
                    f"{relative.as_posix()} ({problem or resolved})"
                )
            if is_local_root_entry(relative.parts[0]) or any(
                part in EXCLUDED_PARTS for part in relative.parts
            ):
                continue
            retained.append(name)
        dirs[:] = retained
        for name in sorted(names):
            path = current_path / name
            relative = path.relative_to(root)
            if is_link_or_reparse(path):
                raise ValueError(
                    "skill export rejects symlink or reparse point file: "
                    f"{relative.as_posix()}"
                )
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                raise PackageContainmentError(
                    "skill export file resolves outside the project root: "
                    f"{relative.as_posix()} ({problem or resolved})"
                )
            if is_local_root_entry(relative.parts[0]) or any(
                part in EXCLUDED_PARTS for part in relative.parts
            ):
                continue
            if (
                name in EXCLUDED_NAMES
                or path.suffix in EXCLUDED_SUFFIXES
                or name.endswith("~")
            ):
                continue
            relative_text = relative.as_posix()
            if SECRET_FILE_RE.search(relative_text):
                raise ValueError(
                    f"security policy rejects credential-like filename: {relative_text}"
                )
            data = _stable_bytes(path, root)
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                raise PackageContainmentError(
                    "skill export file changed containment while it was read: "
                    f"{relative.as_posix()} ({problem or resolved})"
                )
            if len(data) <= 2 * 1024 * 1024 and SECRET_TEXT_RE.search(data):
                raise ValueError(
                    f"security policy rejects secret-looking content: {relative_text}"
                )
            files.append(FileEntry(path, data))
    return sorted(files, key=lambda item: item.path)


def _zip_info(name: str, mode: int, *, directory: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name if not directory else name.rstrip("/") + "/", ZIP_TIME)
    info.create_system = 3
    file_type = stat.S_IFDIR if directory else stat.S_IFREG
    info.external_attr = (file_type | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    info.flag_bits |= 0x800
    return info


def build_archive(
    root: Path, output: Path | None = None, *, replace: bool = False
) -> ArchiveResult:
    root = root.expanduser().absolute()
    if root.exists() and is_link_or_reparse(root):
        raise ValueError("skill export rejects a symlink or reparse point root")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"skill project root is not a directory: {root}")
    output = (output or root.parent / "agent-plugin.zip").expanduser().absolute()
    if _inside(output, root):
        raise ValueError("output archive must be outside the skill project")
    if output.exists() and not replace:
        raise FileExistsError(
            f"output already exists; use --replace explicitly: {output}"
        )
    files = _files(root)

    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / "agent-plugin"
        for entry in files:
            target = stage / entry.path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(entry.data)
        _, report = validate_root(stage, "package", run_script_tests=False)
        if report.errors:
            details = "; ".join(
                f"{item.path}: {item.message}" for item in report.errors
            )
            raise ValueError(f"skill package validation failed: {details}")

        output.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        os.close(handle)
        temporary_output = Path(temporary_name)
        try:
            with zipfile.ZipFile(
                temporary_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                entries: list[tuple[str, Path | None, bool]] = [
                    ("agent-plugin/", None, True)
                ]
                for staged_path in stage.rglob("*"):
                    name = f"agent-plugin/{staged_path.relative_to(stage).as_posix()}"
                    entries.append((name, staged_path, staged_path.is_dir()))
                for name, entry_path, is_directory in sorted(
                    entries, key=lambda item: item[0]
                ):
                    if is_directory:
                        archive.writestr(_zip_info(name, 0o755, directory=True), b"")
                        continue
                    assert entry_path is not None
                    data = entry_path.read_bytes()
                    mode = 0o755 if data.startswith(b"#!") else 0o644
                    archive.writestr(_zip_info(name, mode, directory=False), data)
            digest = hashlib.sha256(temporary_output.read_bytes()).hexdigest()
            os.replace(temporary_output, output)
        finally:
            temporary_output.unlink(missing_ok=True)
    return ArchiveResult(output, digest, len(files))


def self_test() -> None:
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        first = build_archive(source, base / "one.zip")
        second = build_archive(source, base / "two.zip")
        assert first.sha256 == second.sha256
        with zipfile.ZipFile(first.output) as archive:
            names = archive.namelist()
            assert names == sorted(names)
            assert "agent-plugin/SKILL.md" in names
            assert not any(
                part.startswith(".") for name in names for part in name.split("/")[1:]
            )
            extracted = base / "extracted"
            archive.extractall(extracted)
        _, report = validate_root(
            extracted / "agent-plugin", "package", run_script_tests=False
        )
        assert not report.errors, report.errors
        probe = base / "probe"
        probe.mkdir()
        (probe / "SKILL.md").write_text("probe\n", encoding="utf-8")
        (probe / "notes.txt").write_text("not declared\n", encoding="utf-8")
        try:
            _files(probe)
        except ValueError as exc:
            assert "undeclared root entry" in str(exc)
        else:
            raise AssertionError("undeclared root entry was exported")
        if os.name == "nt":
            import _winapi

            junction_target = source / "junction-target"
            junction = source / "junction"
            junction_target.mkdir()
            try:
                _winapi.CreateJunction(str(junction_target), str(junction))
                try:
                    _files(source)
                except ValueError as exc:
                    assert "reparse point" in str(exc)
                else:
                    raise AssertionError("junction was exported")
            finally:
                junction.rmdir()
                junction_target.rmdir()
    print("package_skill self-test: PASS")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        if args.root != "." or args.output or args.replace:
            print(
                "package_skill: --self-test cannot be combined with packaging options",
                file=sys.stderr,
            )
            return 2
        try:
            self_test()
        except (
            AssertionError,
            FileExistsError,
            OSError,
            ValueError,
            zipfile.BadZipFile,
        ) as exc:
            print(f"package_skill self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        result = build_archive(
            Path(args.root),
            Path(args.output) if args.output else None,
            replace=args.replace,
        )
    except (FileExistsError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"package_skill: {exc}", file=sys.stderr)
        return 1
    print(f"Archive: {result.output}")
    print(f"SHA-256: {result.sha256}")
    print(f"Inventory: {result.file_count} file(s), root agent-plugin/")
    print(
        "Boundary: this is a validated source artifact; no client load or runtime execution was performed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
