"""Validate the agent-plugin skill source tree or exported package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_validation import Report, validate_root
from skill_validation.selftest import self_test


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", nargs="?", default=".", help="skill folder; default: current directory"
    )
    parser.add_argument(
        "--skip-script-tests",
        action="store_true",
        help="skip bundled script self-tests in source mode",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run validator regression tests"
    )
    parser.add_argument(
        "--source-checkout",
        action="store_true",
        help="validate a clean Git repository root",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="validate a clean exported package without Git",
    )
    return parser.parse_args(argv)


def print_report(root: Path, report: Report) -> None:
    for finding in sorted(report.errors, key=lambda item: (item.path, item.message)):
        print(f"ERROR {finding.path}: {finding.message}")
    for finding in sorted(report.warnings, key=lambda item: (item.path, item.message)):
        print(f"WARN  {finding.path}: {finding.message}")
    if report.errors:
        print(
            f"\nagent-plugin validation: FAILED ({len(report.errors)} error(s), {len(report.warnings)} warning(s))"
        )
    else:
        print(
            f"agent-plugin validation: PASS ({len(report.warnings)} warning(s)) - {root}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    mode_count = int(args.source_checkout) + int(args.package)
    if args.self_test and (mode_count or args.root != "." or args.skip_script_tests):
        print(
            "validate_skill: --self-test cannot be combined with a root, validation mode, or script-test option",
            file=sys.stderr,
        )
        return 2
    if not args.self_test and mode_count != 1:
        print(
            "validate_skill: exactly one of --source-checkout or --package is required for normal validation",
            file=sys.stderr,
        )
        return 2
    if args.self_test:
        try:
            self_test()
        except (AssertionError, OSError, ValueError) as exc:
            print(f"validate_skill self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    mode = "source-checkout" if args.source_checkout else "package"
    root, report = validate_root(
        Path(args.root), mode, run_script_tests=not args.skip_script_tests
    )
    print_report(root or Path(args.root), report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
