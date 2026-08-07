"""Exercise Agent Plugin validation with isolated package fixtures."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .core import MCP_SCHEMA, PLUGIN_SCHEMA
from .package import validate_plugin


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _plugin(root: Path, *, name: str = "test-plugin") -> None:
    root.mkdir(parents=True, exist_ok=True)
    _json(root / "plugin.json", {"$schema": PLUGIN_SCHEMA, "name": name})


def _codes(root: Path) -> set[str]:
    return {item.code for item in validate_plugin(root).report.findings}


def _errors(root: Path) -> set[str]:
    return {item.code for item in validate_plugin(root).report.errors}


def self_test() -> None:
    cases = 0
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)

        root = base / "minimal"
        _plugin(root)
        assert not validate_plugin(root).report.errors
        cases += 1

        root = base / "skill"
        _plugin(root)
        skill = root / "skills" / "release-notes"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: release-notes\ndescription: "Create notes. Use when releasing."\nmetadata:\n  version: "1.0"\n---\n\n# Release Notes\n',
            encoding="utf-8",
        )
        result = validate_plugin(root)
        assert not result.report.errors, result.report.errors
        assert result.skills == ("release-notes",)
        cases += 1

        root = base / "unicode-skill"
        _plugin(root)
        skill = root / "skills" / "résumé-review"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: résumé-review\ndescription: "Review résumés. Use when assessing a CV."\n---\n\n# Review\n',
            encoding="utf-8",
        )
        result = validate_plugin(root)
        assert not result.report.errors, result.report.errors
        assert result.skills == ("résumé-review",)
        cases += 1

        root = base / "unknown-skill-field"
        _plugin(root)
        skill = root / "skills" / "test"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: test\ndescription: "Use when testing."\ncustom-field: true\n---\nbody\n',
            encoding="utf-8",
        )
        assert "AGENT_SKILLS_REFERENCE" in _errors(root)
        cases += 1

        root = base / "duplicate-json"
        root.mkdir()
        (root / "plugin.json").write_text(
            f'{{"$schema":"{PLUGIN_SCHEMA}","name":"a","name":"b"}}', encoding="utf-8"
        )
        assert "JSON_DUPLICATE_KEY" in _errors(root)
        cases += 1

        root = base / "unknown-field"
        _plugin(root)
        data = json.loads((root / "plugin.json").read_text())
        data["skills"] = ["x"]
        _json(root / "plugin.json", data)
        result = validate_plugin(root)
        finding = next(
            item
            for item in result.report.errors
            if item.code == "MANIFEST_UNKNOWN_FIELD"
        )
        assert "ignore" in finding.runtime_effect.lower()
        cases += 1

        root = base / "recoverable-extensions"
        _plugin(root)
        skill = root / "skills" / "still-valid"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: still-valid\ndescription: "Use when testing recovery."\n---\nbody\n',
            encoding="utf-8",
        )
        data = json.loads((root / "plugin.json").read_text())
        data["extensions"] = []
        _json(root / "plugin.json", data)
        result = validate_plugin(root)
        assert "MANIFEST_EXTENSIONS_TYPE" in {
            item.code for item in result.report.errors
        }
        assert result.skills == ("still-valid",)
        cases += 1

        root = base / "fatal-extension-value"
        _plugin(root)
        skill = root / "skills" / "still-valid"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: still-valid\ndescription: "Use when testing recovery."\n---\nbody\n',
            encoding="utf-8",
        )
        data = json.loads((root / "plugin.json").read_text())
        data["extensions"] = {"com.example.client": []}
        _json(root / "plugin.json", data)
        result = validate_plugin(root)
        assert "EXTENSION_VALUE_TYPE" in {item.code for item in result.report.errors}
        assert result.skills == ()
        assert result.mcp_servers == ()
        cases += 1

        root = base / "bad-name"
        _plugin(root, name="Bad--Name")
        assert "MANIFEST_NAME" in _errors(root)
        cases += 1

        root = base / "nested-skill"
        _plugin(root)
        nested = root / "skills" / "group" / "task"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text(
            "---\nname: task\ndescription: Use when testing.\n---\nbody\n",
            encoding="utf-8",
        )
        assert "SKILL_NESTED_NOT_DISCOVERED" in _codes(root)
        cases += 1

        root = base / "stdio"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "local": {
                        "type": "stdio",
                        "command": "python",
                        "args": ["${PLUGIN_ROOT}/server.py"],
                        "cwd": "${PLUGIN_DATA}/runtime",
                    }
                },
            },
        )
        assert not validate_plugin(root).report.errors
        cases += 1

        root = base / "command-escape"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {"bad": {"type": "stdio", "command": "../server"}},
            },
        )
        assert "MCP_COMMAND_FORM" in _errors(root)
        cases += 1

        root = base / "cwd-escape"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "stdio",
                        "command": "python",
                        "cwd": "${PLUGIN_ROOT}/../outside",
                    }
                },
            },
        )
        assert "MCP_CWD_ESCAPE" in _errors(root)
        cases += 1

        root = base / "reserved-env"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "stdio",
                        "command": "python",
                        "env": {"PLUGIN_ROOT": "x"},
                    }
                },
            },
        )
        assert "MCP_ENV_RESERVED" in _errors(root)
        cases += 1

        root = base / "platform-env-collision"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "portable-risk": {
                        "type": "stdio",
                        "command": "python",
                        "env": {"plugin_root": "x"},
                    }
                },
            },
        )
        result = validate_plugin(root)
        assert not result.report.errors
        assert "MCP_ENV_PLATFORM_COLLISION" in {
            item.code for item in result.report.warnings
        }
        cases += 1

        root = base / "insecure-url"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {"type": "streamable-http", "url": "http://example.com/mcp"}
                },
            },
        )
        result = validate_plugin(root)
        assert "MCP_URL_TLS" in {item.code for item in result.report.errors}
        assert result.mcp_servers == ()
        cases += 1

        root = base / "invalid-remote-urls"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "fragment": {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp#private",
                    },
                    "relative": {"type": "streamable-http", "url": "/mcp"},
                    "valid": {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp",
                    },
                },
            },
        )
        result = validate_plugin(root)
        assert {"MCP_URL_ABSOLUTE", "MCP_URL_FRAGMENT"} <= {
            item.code for item in result.report.errors
        }
        assert result.mcp_servers == ("valid",)
        cases += 1

        root = base / "loopback-url"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "ok": {
                        "type": "streamable-http",
                        "url": "http://127.0.0.1:3000/mcp",
                    }
                },
            },
        )
        assert not validate_plugin(root).report.errors
        cases += 1

        root = base / "duplicate-header"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp",
                        "headers": {"X-Test": "a", "x-test": "b"},
                    }
                },
            },
        )
        assert "MCP_HEADER_DUPLICATE" in _errors(root)
        cases += 1

        root = base / "secret-header"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp",
                        "headers": {
                            "Authorization": "Bearer example-not-a-real-secret"
                        },
                    }
                },
            },
        )
        result = validate_plugin(root)
        assert not result.report.errors
        assert "MCP_HEADER_SECRET" in {item.code for item in result.report.warnings}
        cases += 1

        root = base / "fatal-manifest"
        _plugin(root, name="Bad--Name")
        skill = root / "skills" / "hidden"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: hidden\ndescription: Use when testing.\n---\nbody\n",
            encoding="utf-8",
        )
        result = validate_plugin(root)
        assert "MANIFEST_NAME" in {item.code for item in result.report.errors}
        assert result.skills == ()
        cases += 1

        root = base / "fatal-mcp-root"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "unknown": True,
                "mcpServers": {"hidden": {"type": "stdio", "command": "python"}},
            },
        )
        result = validate_plugin(root)
        assert "MCP_TOP_FIELD" in {item.code for item in result.report.errors}
        assert result.mcp_servers == ()
        cases += 1

        root = base / "command-with-space"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "space": {"type": "stdio", "command": "named executable"}
                },
            },
        )
        result = validate_plugin(root)
        assert "MCP_COMMAND_SHELLISH" not in {
            item.code for item in result.report.warnings
        }
        assert not result.report.errors
        cases += 1

        root = base / "mcp-version"
        _plugin(root)
        _json(
            root / "mcp.json",
            {
                "$schema": "https://agent-plugins.org/schemas/2.0.0/mcp.schema.json",
                "mcpServers": {},
            },
        )
        codes = _errors(root)
        assert {
            "MCP_SCHEMA",
            "MCP_VERSION_UNSUPPORTED",
            "MCP_VERSION_MISMATCH",
        } <= codes
        cases += 1

        root = base / "complex-yaml"
        _plugin(root)
        skill = root / "skills" / "test"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: test\ndescription: Use when testing.\nmetadata: {version: '1'}\n---\nbody\n",
            encoding="utf-8",
        )
        assert "AGENT_SKILLS_REFERENCE" in _errors(root)
        cases += 1

        root = base / "broken-skill-link"
        _plugin(root)
        skill = root / "skills" / "test"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: test\ndescription: "Use when testing."\n---\n[missing](references/missing.md)\n',
            encoding="utf-8",
        )
        result = validate_plugin(root)
        assert "SKILL_LINK_MISSING" in {item.code for item in result.report.warnings}
        assert not result.report.errors
        cases += 1

        root = base / "secret-file"
        _plugin(root)
        (root / ".env").write_text("TOKEN=not-real\n", encoding="utf-8")
        result = validate_plugin(root)
        assert "PACKAGE_SECRET_FILE" in {item.code for item in result.report.warnings}
        assert "PACKAGE_SECRET_FILE" not in {item.code for item in result.report.errors}
        cases += 1

        root = base / "link-escape"
        outside = base / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        _plugin(root)
        try:
            (root / "linked.txt").symlink_to(outside)
        except OSError as exc:
            if os.name != "nt":
                raise
            print(f"validate_plugin self-test: symlink case skipped: {exc}")
        else:
            assert "PACKAGE_LINK_ESCAPE" in _errors(root)
        cases += 1

    print(f"validate_plugin self-test: PASS ({cases} cases)")
