# Agent Plugin Skill

Author, review, migrate, validate, and package portable Agent Plugins 1.0.0.

## Install

```bash
npx skills add sm18lr88/Agent-Plugin_Skill
```

The bundled tools require Python 3.11 or later and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --frozen
```

## Common commands

Preview a new plugin. Add `--write` when the preview is correct.

```bash
uv run python scripts/new_plugin.py example-plugin --skill-name release-notes
```

Validate or package a plugin:

```bash
uv run python scripts/validate_plugin.py /path/to/plugin
uv run python scripts/package_plugin.py /path/to/plugin
```

Validate or package this skill:

```bash
uv run python scripts/validate_skill.py . --source-checkout
uv run python scripts/package_skill.py . --output ../agent-plugin.zip
```

## Scope

Portable Agent Plugins 1.0.0 contain Agent Skills and optional MCP server configuration. Client-specific behavior belongs in documented client namespaces or compatibility packages.

The validator checks manifests, skill metadata, MCP configuration, package containment, duplicate keys, visible secret risks, and independent component failure.

The packager rejects links, reparse points, source-control state, build state, credential-like files, and secret-looking content. It creates a deterministic ZIP from the bytes that passed validation.

The tools do not start plugin processes, connect to MCP servers, test skill activation, or prove client support.

## Project layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Skill instructions and reference router |
| `references/` | Agent Plugins rules and source records |
| `assets/` | Templates and an example plugin |
| `scripts/` | Validation, scaffolding, and packaging tools |
| `evals/` | Activation and behavior cases |
| `maintenance/` | Pinned upstream review process |

The official specifications remain authoritative. Read [Research Notes](references/research-notes.md) before you make a current-version claim.
