"""Safely scaffold an Agent Plugins 1.0.0 package; dry-run unless --write is supplied."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from plugin_validation import validate_plugin
from plugin_validation.core import (
    MCP_SCHEMA,
    NAMESPACE_RE,
    PLUGIN_NAME_RE,
    PLUGIN_SCHEMA,
    SEMVER_RE,
    valid_skill_name,
)


@dataclass(frozen=True, slots=True)
class Plan:
    name: str
    parent: Path
    files: dict[str, str]

    @property
    def target(self) -> Path:
        return self.parent / self.name


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", help="plugin name and output directory name")
    parser.add_argument(
        "--parent", default=".", help="parent directory; default: current directory"
    )
    parser.add_argument("--description", default="", help="plugin description")
    parser.add_argument(
        "--version", default="0.1.0", help="plugin version; default: 0.1.0"
    )
    parser.add_argument(
        "--license",
        default="Apache-2.0",
        help="license identifier; default: Apache-2.0",
    )
    parser.add_argument("--author-name")
    parser.add_argument("--author-email")
    parser.add_argument("--author-url")
    parser.add_argument(
        "--skill-name", help="create one Agent Skill under skills/<name>"
    )
    parser.add_argument(
        "--skill-description", help="skill capability and activation description"
    )
    parser.add_argument("--mcp-name", help="create one MCP server entry")
    parser.add_argument("--mcp-type", choices=("stdio", "streamable-http", "sse"))
    parser.add_argument("--command", help="stdio executable token")
    parser.add_argument(
        "--arg", action="append", default=[], help="stdio argument; repeatable"
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="stdio environment entry; repeatable",
    )
    parser.add_argument("--cwd", help="stdio working directory")
    parser.add_argument("--url", help="remote MCP URL")
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="remote header; repeatable; never put secrets here",
    )
    parser.add_argument(
        "--extension",
        action="append",
        default=[],
        metavar="NAMESPACE",
        help="add an empty client-owned extension object; repeatable",
    )
    parser.add_argument(
        "--show-content",
        action="store_true",
        help="include full planned file contents in dry-run output",
    )
    parser.add_argument(
        "--write", action="store_true", help="atomically create the new package"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run isolated scaffold tests"
    )
    return parser.parse_args(argv)


def _pairs(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"{label} entry must use KEY=VALUE: {raw!r}")
        key, value = raw.split("=", 1)
        if not key:
            raise ValueError(f"{label} key cannot be empty")
        if key in result:
            raise ValueError(f"duplicate {label} key {key!r}")
        result[key] = value
    return result


def _skill_text(name: str, description: str, license_name: str) -> str:
    title = " ".join(part.capitalize() for part in name.split("-"))
    description_yaml = json.dumps(description, ensure_ascii=False)
    license_yaml = json.dumps(license_name, ensure_ascii=False)
    return f"""---
name: {name}
description: {description_yaml}
license: {license_yaml}
metadata:
  version: "1.0.0"
---

# {title}

Inspect the relevant inputs before acting. Apply the reusable procedure for this skill, validate deterministic requirements, and report exact evidence and limitations.

## Workflow

1. Establish the requested scope and source of truth.
2. Perform the task without inventing inputs, execution, or validation.
3. Run applicable checks and correct failures.
4. Return the smallest complete result with remaining risks.
"""


def build_plan(args: argparse.Namespace) -> Plan:
    if (
        not args.name
        or not PLUGIN_NAME_RE.fullmatch(args.name)
        or not (1 <= len(args.name) <= 64)
    ):
        raise ValueError(
            "name must satisfy the Agent Plugins v1 1-64 character lowercase name grammar"
        )
    if args.version and not SEMVER_RE.fullmatch(args.version):
        raise ValueError(
            "--version must be canonical Semantic Versioning for this scaffold"
        )
    if args.skill_description and not args.skill_name:
        raise ValueError("--skill-description requires --skill-name")
    if args.skill_name and not valid_skill_name(args.skill_name):
        raise ValueError(
            "--skill-name must satisfy the Agent Skills normalized lowercase Unicode alphanumeric-and-hyphen grammar"
        )
    if len(args.extension) != len(set(args.extension)):
        raise ValueError("duplicate extension namespace")
    for namespace in args.extension:
        if not NAMESPACE_RE.fullmatch(namespace):
            raise ValueError(
                f"extension namespace must be conventional lowercase reverse-domain form: {namespace!r}"
            )

    mcp_requested = any((
        args.mcp_name,
        args.mcp_type,
        args.command,
        args.arg,
        args.env,
        args.cwd,
        args.url,
        args.header,
    ))
    if mcp_requested and (not args.mcp_name or not args.mcp_type):
        raise ValueError("MCP scaffolding requires both --mcp-name and --mcp-type")
    if args.mcp_type == "stdio" and not args.command:
        raise ValueError("stdio MCP scaffolding requires --command")
    if args.mcp_type == "stdio" and (args.url or args.header):
        raise ValueError("stdio MCP entries do not accept --url or --header")
    if args.mcp_type in {"streamable-http", "sse"} and not args.url:
        raise ValueError("remote MCP scaffolding requires --url")
    if args.mcp_type in {"streamable-http", "sse"} and (
        args.command or args.arg or args.env or args.cwd
    ):
        raise ValueError(
            "remote MCP entries do not accept stdio command/arg/env/cwd options"
        )

    manifest: dict[str, object] = {"$schema": PLUGIN_SCHEMA, "name": args.name}
    if args.version:
        manifest["version"] = args.version
    if args.description:
        manifest["description"] = args.description
    author = {
        key: value
        for key, value in (
            ("name", args.author_name),
            ("email", args.author_email),
            ("url", args.author_url),
        )
        if value
    }
    if author:
        manifest["author"] = author
    if args.license:
        manifest["license"] = args.license
    if args.extension:
        manifest["extensions"] = {namespace: {} for namespace in args.extension}
    files = {"plugin.json": json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"}

    if args.skill_name:
        description = (
            args.skill_description
            or f"Perform {args.skill_name.replace('-', ' ')} tasks. Use when the user requests this workflow."
        )
        files[f"skills/{args.skill_name}/SKILL.md"] = _skill_text(
            args.skill_name, description, args.license
        )

    if mcp_requested:
        if args.mcp_type == "stdio":
            server: dict[str, object] = {"type": "stdio", "command": args.command}
            if args.arg:
                server["args"] = args.arg
            env = _pairs(args.env, "environment")
            if env:
                server["env"] = env
            if args.cwd:
                server["cwd"] = args.cwd
        else:
            server = {"type": args.mcp_type, "url": args.url}
            headers = _pairs(args.header, "header")
            if headers:
                server["headers"] = headers
        mcp = {"$schema": MCP_SCHEMA, "mcpServers": {args.mcp_name: server}}
        files["mcp.json"] = json.dumps(mcp, indent=2, ensure_ascii=False) + "\n"
    return Plan(args.name, Path(args.parent).expanduser().absolute(), files)


def _materialize(plan: Plan, target: Path) -> None:
    for relative, content in plan.files.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def _verify_plan(plan: Plan) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / plan.name
        _materialize(plan, target)
        result = validate_plugin(target)
        findings = result.report.errors
        if findings:
            messages = "; ".join(f"{item.code}: {item.message}" for item in findings)
            raise ValueError(f"generated plan is not conforming: {messages}")


def write_plan(plan: Plan) -> Path:
    if plan.target.exists() or plan.target.is_symlink():
        raise FileExistsError(f"destination already exists: {plan.target}")
    plan.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=f".{plan.name}.stage-", dir=plan.parent)
    )
    staging_target = staging_parent / plan.name
    try:
        _materialize(plan, staging_target)
        result = validate_plugin(staging_target)
        findings = result.report.errors
        if findings:
            messages = "; ".join(f"{item.code}: {item.message}" for item in findings)
            raise ValueError(f"generated package failed validation: {messages}")
        os.replace(staging_target, plan.target)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)
    return plan.target


def preview(plan: Plan, show_content: bool) -> None:
    print(f"Planned plugin root: {plan.target}")
    for relative in sorted(plan.files):
        print(f"CREATE {relative}")
        if show_content:
            print("-----")
            print(
                plan.files[relative],
                end="" if plan.files[relative].endswith("\n") else "\n",
            )
            print("-----")
    print("Dry run only; no files written. Add --write to create the package.")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        args = parse_args([
            "sample-plugin",
            "--parent",
            temporary,
            "--skill-name",
            "release-notes",
        ])
        plan = build_plan(args)
        _verify_plan(plan)
        assert not plan.target.exists()
        target = write_plan(plan)
        assert target.is_dir() and not validate_plugin(target).report.errors
        unicode_args = parse_args([
            "unicode-plugin",
            "--parent",
            temporary,
            "--skill-name",
            "résumé-review",
            "--skill-description",
            "Review résumés. Use when assessing a CV.\nPreserve nuance.",
            "--license",
            "Apache-2.0 # reviewed",
        ])
        unicode_plan = build_plan(unicode_args)
        _verify_plan(unicode_plan)
        skill_text = unicode_plan.files["skills/résumé-review/SKILL.md"]
        assert (
            'description: "Review résumés. Use when assessing a CV.\\nPreserve nuance."'
            in skill_text
        )
        assert 'license: "Apache-2.0 # reviewed"' in skill_text
        duplicate_extension = parse_args([
            "dupe-plugin",
            "--extension",
            "com.example.client",
            "--extension",
            "com.example.client",
        ])
        try:
            build_plan(duplicate_extension)
        except ValueError as exc:
            assert "duplicate extension" in str(exc)
        else:
            raise AssertionError("duplicate extension namespace was accepted")
        try:
            write_plan(plan)
        except FileExistsError:
            pass
        else:
            raise AssertionError("existing target was overwritten")
        bad = parse_args([
            "bad-plugin",
            "--parent",
            temporary,
            "--mcp-name",
            "x",
            "--mcp-type",
            "streamable-http",
            "--url",
            "http://example.com/mcp",
        ])
        try:
            _verify_plan(build_plan(bad))
        except ValueError as exc:
            assert "MCP_URL_TLS" in str(exc)
        else:
            raise AssertionError("insecure remote scaffold passed")
    print("new_plugin self-test: PASS")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        if args.name or args.write:
            print(
                "new_plugin: --self-test cannot be combined with a name or --write",
                file=sys.stderr,
            )
            return 2
        try:
            self_test()
        except (AssertionError, OSError, ValueError) as exc:
            print(f"new_plugin self-test: FAIL: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        plan = build_plan(args)
        _verify_plan(plan)
        if args.write:
            target = write_plan(plan)
            print(f"Created conforming Agent Plugin scaffold: {target}")
            print(f"Validate: python scripts/validate_plugin.py {target}")
        else:
            preview(plan, args.show_content)
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"new_plugin: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
