# Client Extensions and Compatibility Layers

## Portable core boundary

Agent Plugins v1 standardizes only:

- root `plugin.json`,
- Agent Skills under root `skills/`,
- MCP servers in root `mcp.json`.

Hooks, custom agents, commands, prompts, LSP servers, UI/app resources, permission declarations, authentication configuration, marketplaces, signing, and install policy have no portable v1 core location.

## Client-owned namespace

Client-specific manifest data belongs under `plugin.json.extensions`:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "example-plugin",
  "extensions": {
    "com.example.client": {
      "setting": true
    }
  }
}
```

Client-specific files belong in a top-level directory named exactly for that namespace:

```text
example-plugin/
└── com.example.client/
    └── hooks/
```

A stable namespace based on a domain controlled by its owner is recommended. The Agent Plugins core assigns no discovery, validation, loading, or failure semantics to extension content.

Use a namespace only when the owning client documents it. Do not invent `com.vendor.client`, place arbitrary files there, and claim that client will load them. A client ignores namespaces it does not implement without validating their contents.

## Extension versus compatibility package

Use an extension when:

- the client supports Agent Plugins core,
- the client publishes a namespace,
- the extra behavior is defined inside that namespace.

Use a compatibility package or adapter when:

- the client requires a different root manifest or discovery layout,
- the client has no Agent Plugins support,
- legacy hooks/agents/commands cannot yet be represented by an implemented namespace,
- marketplace or signing infrastructure requires separate metadata.

Keep adapters outside the portable package unless the client explicitly loads them as a namespace. Label canonical versus generated files and avoid hand-maintained divergent metadata.

## Converting client-native concepts

Do not mechanically rename components:

| Existing behavior    | Portable only when                                    | Otherwise                        |
| -------------------- | ----------------------------------------------------- | -------------------------------- |
| prompt/command       | it is genuinely reusable on-demand skill instructions | retain client behavior           |
| custom agent/persona | skill semantics preserve the behavior and lifecycle   | retain extension/adapter         |
| hook                 | no portable v1 equivalent                             | extension/adapter                |
| MCP server           | it fits `mcp.json` without losing required semantics  | adapter or documented limitation |
| UI/LSP/app           | no portable v1 equivalent                             | extension/adapter                |
| auth declaration     | no portable v1 core field                             | client-managed system            |
| marketplace metadata | never part of core package conformance                | distribution repository/process  |

## Review questions

- Who owns and documents the namespace?
- Which client/version loads it?
- Is extension validation isolated from core loading?
- Are extension secrets or permissions managed outside visible package data?
- Is there a single source of truth for metadata shared with legacy packages?
- Can the extension be removed without breaking portable components?
- Are installation, update, rollback, and failure tests client-specific and recorded?
