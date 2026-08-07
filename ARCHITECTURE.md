# Architecture

## Purpose

This repository contains an Agent Skill and its local engineering tools. It does not implement an Agent Plugins client.

## Boundaries

The project has four main boundaries:

1. `SKILL.md` routes an agent to focused reference documents.
2. `scripts/plugin_validation/` validates one Agent Plugin package.
3. `scripts/skill_validation/` validates this repository and its distribution package.
4. Entry scripts provide command-line interfaces for authoring, validation, and packaging.

Entry scripts can import validation packages. Validation packages must not import entry scripts.

`plugin_validation.agent_skills` is the Agent Skills adapter. It supplies UTF-8 text to the pinned official StrictYAML parser and metadata validator.

## Authority

Use this authority order:

1. Official Agent Plugins specification text.
2. Official Agent Plugins schemas.
3. Official Agent Skills specification and pinned reference validator.
4. Local security and release policy.
5. Authoring recommendations.

Local policy must not change a warning into an Agent Plugins conformance error.

## Failure isolation

A fatal `plugin.json` error stops all component discovery.

An invalid root `mcp.json` disables the complete MCP component. One invalid server entry does not disable valid sibling entries.

An invalid skill does not disable sibling skills or MCP servers.

Client extension failures do not change portable-core validity unless the manifest schema itself fails.

## Trust boundaries

Plugin input paths are untrusted data. Validators inspect them without starting plugin processes.

The source validator executes self-tests only for its own project root. It does not execute scripts from another selected checkout.

Packagers reject symlinks and snapshot regular-file bytes before archive creation. These are local safety policies.

## Distribution

`scripts/skill_validation/layout.py` owns the visible root entries in the skill distribution.

The exporter ignores hidden root state without naming local tools. It rejects undeclared visible entries.

Archives use sorted names, fixed timestamps, and normalized modes. Identical inputs produce identical bytes.
