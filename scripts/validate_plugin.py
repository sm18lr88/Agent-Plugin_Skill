"""Validate an Agent Plugins 1.0.0 package without network access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plugin_validation import ValidationResult, validate_plugin
from plugin_validation.selftest import self_test


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", nargs="?", default=".", help="plugin root; default: current directory"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit one machine-readable JSON report"
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="return exit code 3 when only warnings remain",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run isolated validator regression tests",
    )
    parser.add_argument(
        "--version", action="version", version="agent-plugin validator 1.0.0"
    )
    return parser.parse_args(argv)


def print_human(result: ValidationResult) -> None:
    root = result.root or Path(".")
    for item in result.report.sorted():
        label = "ERROR" if item.severity == "error" else "WARN "
        print(f"{label} {item.code} [{item.scope}] {item.path}: {item.message}")
        print(f"      runtime: {item.runtime_effect}")
        if item.recommendation:
            print(f"      fix: {item.recommendation}")
    summary = f"{len(result.report.errors)} error(s), {len(result.report.warnings)} warning(s)"
    if result.report.errors:
        print(f"\nAgent Plugin validation: FAILED ({summary}) - {root}")
    else:
        print(f"\nAgent Plugin validation: PASS ({summary}) - {root}")
    print(
        f"Statically found skill candidates: {', '.join(result.skills) if result.skills else '(none)'}"
    )
    print(
        f"Statically found MCP entries: {', '.join(result.mcp_servers) if result.mcp_servers else '(none)'}"
    )
    print(
        "Boundary: structural/semantic validation only; no client load, skill activation, process start, network connection, or MCP handshake was performed."
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        if args.json or args.fail_on_warnings or args.root != ".":
            print(
                "validate_plugin: --self-test cannot be combined with a root or output policy flags",
                file=sys.stderr,
            )
            return 2
        try:
            self_test()
        except (AssertionError, OSError, ValueError) as exc:
            print(f"validate_plugin self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    result = validate_plugin(Path(args.root))
    if args.json:
        root = result.root or Path(args.root)
        payload = result.report.as_dict(root)
        payload["statically_found"] = {
            "skill_candidates": list(result.skills),
            "mcp_entries": list(result.mcp_servers),
        }
        payload["execution_performed"] = False
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(result)
    if result.report.errors:
        return 1
    if args.fail_on_warnings and result.report.warnings:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
