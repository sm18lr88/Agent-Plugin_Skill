"""Validate and build a deterministic ZIP for an Agent Plugins 1.0.0 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from plugin_validation import validate_plugin
from plugin_validation.core import (
    PLUGIN_SCHEMA,
    PackageContainmentError,
    Report,
    is_link_or_reparse,
    opened_file_path,
    resolve_within,
    validate_package_root,
)
from plugin_validation.security import SECRET_FILE_RE, SECRET_TEXT_RE

FORBIDDEN_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
}
FORBIDDEN_NAMES = {".DS_Store", "Thumbs.db"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".swp", ".tmp"}
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    output: Path
    sha256: str
    file_count: int
    directory_count: int
    prefix: str


@dataclass(frozen=True, slots=True)
class FileEntry:
    path: Path
    data: bytes


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", nargs="?", default=".", help="plugin root; default: current directory"
    )
    parser.add_argument(
        "--output", help="archive path; default: <name>-<version>.zip beside the plugin"
    )
    parser.add_argument(
        "--inventory-json", help="optional path for a JSON archive inventory and hash"
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="refuse packaging when validator warnings remain",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="explicitly replace an existing output archive",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run isolated deterministic-packaging tests",
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
        raise ValueError(f"package source is not a regular file: {path}")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        opened_path = opened_file_path(stream, path)
        contained, resolved, problem = resolve_within(
            root, opened_path, strict=True
        )
        if not contained:
            raise PackageContainmentError(
                "opened package file resolves outside the plugin root: "
                f"{path.relative_to(root).as_posix()} ({problem or resolved})"
            )
        data = stream.read()
    after = path.stat(follow_symlinks=False)
    if (
        _stat_identity(before) != _stat_identity(opened)
        or _stat_identity(opened) != _stat_identity(after)
    ):
        raise ValueError(f"package source changed while it was read: {path}")
    return data


def _inventory(root: Path) -> tuple[list[Path], list[FileEntry]]:
    directories: list[Path] = []
    files: list[FileEntry] = []
    for current, dirs, names in os.walk(str(root), followlinks=False):
        current_path = Path(current)
        for name in sorted(dirs):
            path = current_path / name
            relative = path.relative_to(root)
            if is_link_or_reparse(path):
                raise ValueError(
                    "packaging policy rejects symlink or reparse point directory: "
                    f"{relative.as_posix()}"
                )
            if is_link_or_reparse(path):
                raise ValueError(
                    "packaging policy rejects a directory replaced by a symlink or reparse point: "
                    f"{relative.as_posix()}"
                )
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                raise PackageContainmentError(
                    "package directory resolves outside the plugin root: "
                    f"{relative.as_posix()} ({problem or resolved})"
                )
            if any(part in FORBIDDEN_PARTS for part in relative.parts):
                raise ValueError(
                    f"transient/source-control directory is not packageable: {relative.as_posix()}"
                )
            directories.append(path)
        for name in sorted(names):
            path = current_path / name
            relative = path.relative_to(root)
            if is_link_or_reparse(path):
                raise ValueError(
                    "packaging policy rejects symlink or reparse point file: "
                    f"{relative.as_posix()}"
                )
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                raise PackageContainmentError(
                    "package file resolves outside the plugin root: "
                    f"{relative.as_posix()} ({problem or resolved})"
                )
            if (
                any(part in FORBIDDEN_PARTS for part in relative.parts)
                or name in FORBIDDEN_NAMES
                or path.suffix in FORBIDDEN_SUFFIXES
                or name.endswith("~")
            ):
                raise ValueError(
                    f"transient/source-control file is not packageable: {relative.as_posix()}"
                )
            relative_text = relative.as_posix()
            if SECRET_FILE_RE.search(relative_text):
                raise ValueError(
                    f"security policy rejects credential-like filename: {relative_text}"
                )
            data = _stable_bytes(path, root)
            contained, resolved, problem = resolve_within(root, path, strict=True)
            if not contained:
                raise PackageContainmentError(
                    "package file changed containment while it was read: "
                    f"{relative.as_posix()} ({problem or resolved})"
                )
            if len(data) <= 2 * 1024 * 1024 and SECRET_TEXT_RE.search(data):
                raise ValueError(
                    f"security policy rejects secret-looking content: {relative_text}"
                )
            files.append(FileEntry(path, data))
    return sorted(directories), sorted(files, key=lambda item: item.path)


def _zip_info(name: str, mode: int, *, directory: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name if not directory else name.rstrip("/") + "/", ZIP_TIME)
    info.create_system = 3
    file_type = stat.S_IFDIR if directory else stat.S_IFREG
    info.external_attr = (file_type | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    info.flag_bits |= 0x800
    return info


def _default_output(root: Path, manifest: dict[str, object]) -> Path:
    name = str(manifest["name"])
    version = manifest.get("version")
    suffix = f"-{version}" if isinstance(version, str) and version else ""
    return root.parent / f"{name}{suffix}.zip"


def build_archive(
    root: Path,
    output: Path | None = None,
    *,
    fail_on_warnings: bool = False,
    replace: bool = False,
) -> ArchiveResult:
    root = root.expanduser().absolute()
    if root.exists() and is_link_or_reparse(root):
        raise ValueError("packaging policy rejects a symlink or reparse point root")
    root_report = Report()
    normalized = validate_package_root(root, root_report)
    if normalized is None:
        details = "; ".join(
            f"{item.code}: {item.message}" for item in root_report.errors
        )
        raise ValueError(f"plugin validation failed: {details}")
    directories, files = _inventory(normalized)
    with tempfile.TemporaryDirectory(
        prefix="agent-plugin-package-"
    ) as snapshot_parent:
        snapshot = Path(snapshot_parent) / normalized.name
        snapshot.mkdir()
        for directory in directories:
            (snapshot / directory.relative_to(normalized)).mkdir(
                parents=True, exist_ok=True
            )
        for entry in files:
            target = snapshot / entry.path.relative_to(normalized)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(entry.data)
        validation = validate_plugin(snapshot)
    if validation.root is None or validation.report.errors:
        details = "; ".join(
            f"{item.code}: {item.message}" for item in validation.report.errors
        )
        raise ValueError(f"plugin validation failed: {details}")
    if fail_on_warnings and validation.report.warnings:
        details = "; ".join(
            f"{item.code}: {item.message}" for item in validation.report.warnings
        )
        raise ValueError(f"plugin validation has warnings: {details}")
    if validation.manifest is None or not isinstance(
        validation.manifest.get("name"), str
    ):
        raise ValueError("validated manifest name is unavailable")
    root = normalized
    output = (
        (output or _default_output(root, validation.manifest)).expanduser().absolute()
    )
    if _inside(output, root):
        raise ValueError("output archive must be outside the plugin root")
    if output.exists() and not replace:
        raise FileExistsError(
            f"output already exists; use --replace explicitly: {output}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = str(validation.manifest["name"])

    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(handle)
    temporary_archive = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            entries: list[tuple[str, bytes | None, bool]] = [(f"{prefix}/", None, True)]
            entries.extend(
                (f"{prefix}/{directory.relative_to(root).as_posix()}/", None, True)
                for directory in directories
            )
            entries.extend(
                (
                    f"{prefix}/{entry.path.relative_to(root).as_posix()}",
                    entry.data,
                    False,
                )
                for entry in files
            )
            for archive_name, source, is_directory in sorted(
                entries, key=lambda item: item[0]
            ):
                if is_directory:
                    archive.writestr(
                        _zip_info(archive_name, 0o755, directory=True), b""
                    )
                else:
                    assert isinstance(source, bytes)
                    data = source
                    mode = 0o755 if data.startswith(b"#!") else 0o644
                    archive.writestr(
                        _zip_info(archive_name, mode, directory=False), data
                    )
        digest = hashlib.sha256(temporary_archive.read_bytes()).hexdigest()
        os.replace(temporary_archive, output)
    finally:
        temporary_archive.unlink(missing_ok=True)
    return ArchiveResult(output, digest, len(files), len(directories) + 1, prefix)


def _write_inventory(path: Path, result: ArchiveResult) -> None:
    payload = {
        "archive": str(result.output),
        "sha256": result.sha256,
        "prefix": result.prefix,
        "files": result.file_count,
        "directories": result.directory_count,
        "deterministic_timestamp": "1980-01-01T00:00:00Z",
    }
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base / "test-plugin"
        root.mkdir()
        (root / "plugin.json").write_text(
            json.dumps({
                "$schema": PLUGIN_SCHEMA,
                "name": "test-plugin",
                "version": "1.0.0",
            })
            + "\n",
            encoding="utf-8",
        )
        (root / "data").mkdir()
        (root / "data" / "sample.txt").write_text("sample\n", encoding="utf-8")
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        (root / "z-dir").mkdir()
        first = build_archive(root, base / "one.zip")
        second = build_archive(root, base / "two.zip")
        assert first.sha256 == second.sha256
        with zipfile.ZipFile(first.output) as archive:
            names = archive.namelist()
            assert names == sorted(names)
            assert all(
                name == "test-plugin/" or name.startswith("test-plugin/")
                for name in names
            )
            assert archive.read("test-plugin/plugin.json")
        try:
            build_archive(root, first.output)
        except FileExistsError:
            pass
        else:
            raise AssertionError("existing archive was replaced without --replace")
        secret = root / ".env"
        secret.write_text("TOKEN=not-a-real-token\n", encoding="utf-8")
        try:
            build_archive(root, base / "secret.zip")
        except ValueError as exc:
            assert "credential-like filename" in str(exc)
        else:
            raise AssertionError("credential-like file was packaged")
        secret.unlink()
        race = root / "race.txt"
        race.write_bytes(b"validated bytes\n")
        validator = validate_plugin

        def mutate_source_after_validation(candidate: Path):
            result = validator(candidate)
            race.write_bytes(b"unvalidated bytes\n")
            return result

        with patch(
            f"{__name__}.validate_plugin", side_effect=mutate_source_after_validation
        ):
            raced = build_archive(root, base / "race.zip")
        with zipfile.ZipFile(raced.output) as archive:
            archived = archive.read("test-plugin/race.txt")
            assert archived == b"validated bytes\n", archived
        race.unlink()
        try:
            (root / "link").symlink_to(root / "data" / "sample.txt")
        except OSError as exc:
            if os.name != "nt":
                raise
            print(f"package_plugin self-test: symlink case skipped: {exc}")
        else:
            try:
                build_archive(root, base / "link.zip")
            except ValueError as exc:
                assert "symlink" in str(exc)
            else:
                raise AssertionError("symlink package was accepted")
            (root / "link").unlink()
        if os.name == "nt":
            import _winapi

            junction_target = root / "junction-target"
            junction_target.mkdir()
            junction = root / "junction"
            try:
                _winapi.CreateJunction(str(junction_target), str(junction))
                try:
                    build_archive(root, base / "junction.zip")
                except ValueError as exc:
                    assert "reparse point" in str(exc)
                else:
                    raise AssertionError("junction package was accepted")
            finally:
                junction.rmdir()
                junction_target.rmdir()
            outside = base / "outside"
            outside.mkdir()
            (outside / "outside.txt").write_text("outside\n", encoding="utf-8")
            swap = root / "swap"
            swap.mkdir()
            inventory_swap = swap.resolve(strict=True)
            detector = is_link_or_reparse
            swapped = False

            def swap_after_directory_check(path: Path) -> bool:
                nonlocal swapped
                linked = detector(path)
                if path == inventory_swap and not swapped:
                    swap.rmdir()
                    _winapi.CreateJunction(str(outside), str(swap))
                    swapped = True
                return linked

            try:
                with patch(
                    f"{__name__}.is_link_or_reparse",
                    side_effect=swap_after_directory_check,
                ):
                    try:
                        build_archive(root, base / "swapped-junction.zip")
                    except ValueError as exc:
                        assert "reparse point" in str(exc)
                    else:
                        raise AssertionError("swapped junction package was accepted")
                assert swapped, "junction swap hook did not inspect the inventory path"
            finally:
                swap.rmdir()
            inside = root / "reversible"
            inside.mkdir()
            inside_file = inside / "same.txt"
            inside_file.write_text("inside\n", encoding="utf-8")
            inventory_inside_file = inside_file.resolve(strict=True)
            outside_file = outside / "same.txt"
            outside_file.write_text("outside\n", encoding="utf-8")
            saved_inside = root / "reversible-saved"
            stable_reader = _stable_bytes
            junction_injected = False

            def read_through_reversible_junction(path: Path, trusted_root: Path) -> bytes:
                nonlocal junction_injected
                if path != inventory_inside_file:
                    return stable_reader(path, trusted_root)
                inside.rename(saved_inside)
                _winapi.CreateJunction(str(outside), str(inside))
                junction_injected = True
                try:
                    return stable_reader(path, trusted_root)
                finally:
                    inside.rmdir()
                    saved_inside.rename(inside)

            with patch(
                f"{__name__}._stable_bytes",
                side_effect=read_through_reversible_junction,
            ):
                try:
                    build_archive(root, base / "reversible-junction.zip")
                except ValueError as exc:
                    assert junction_injected, "reversible junction hook was not exercised"
                    assert "opened package file resolves outside" in str(exc)
                else:
                    raise AssertionError("reversible junction package was accepted")
    print("package_plugin self-test: PASS")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        if (
            args.root != "."
            or args.output
            or args.inventory_json
            or args.fail_on_warnings
            or args.replace
        ):
            print(
                "package_plugin: --self-test cannot be combined with packaging options",
                file=sys.stderr,
            )
            return 2
        try:
            self_test()
        except (AssertionError, OSError, ValueError) as exc:
            print(f"package_plugin self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        raw_root = Path(args.root).expanduser().absolute()
        inventory_path = (
            Path(args.inventory_json).expanduser().absolute()
            if args.inventory_json
            else None
        )
        if inventory_path is not None and _inside(inventory_path, raw_root):
            raise ValueError("inventory JSON must be outside the plugin root")
        result = build_archive(
            raw_root,
            Path(args.output) if args.output else None,
            fail_on_warnings=args.fail_on_warnings,
            replace=args.replace,
        )
        if inventory_path is not None:
            if inventory_path == result.output:
                raise ValueError("inventory JSON must not overwrite the archive")
            _write_inventory(inventory_path, result)
    except (FileExistsError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"package_plugin: {exc}", file=sys.stderr)
        return 1
    print(f"Archive: {result.output}")
    print(f"SHA-256: {result.sha256}")
    print(
        f"Inventory: {result.file_count} file(s), {result.directory_count} directories, root {result.prefix}/"
    )
    print(
        "Boundary: package was structurally validated and deterministically archived; no client load or runtime execution was performed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
