# Plugin Manifest

`plugin.json` is required at the plugin root and is loaded before components or client-specific behavior.

## Minimal v1.0.0 manifest

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "example-plugin"
}
```

## Closed top-level fields

Only these fields are permitted:

| Field         | Required | Type         | Notes                                                   |
| ------------- | -------: | ------------ | ------------------------------------------------------- |
| `$schema`     |      yes | string       | canonical supported schema identifier                   |
| `name`        |      yes | string       | v1 naming constraints below                             |
| `version`     |       no | string       | SemVer recommended, not required by conformance         |
| `description` |       no | string       | concise package purpose                                 |
| `author`      |       no | object       | only optional string `name`, `email`, `url`             |
| `homepage`    |       no | string       | URL syntax recommended, not required by core validation |
| `repository`  |       no | string       | source URL recommended                                  |
| `license`     |       no | string       | SPDX identifier recommended                             |
| `keywords`    |       no | string array | search/discovery metadata                               |
| `extensions`  |       no | object       | namespace keys, object values                           |

Do not add `skills`, `mcpServers`, `hooks`, `agents`, `commands`, component paths, permissions, or marketplace fields at the root. Core discovery uses fixed locations. Client data belongs under `extensions`.

## Plugin name

The name must:

- contain 1–64 characters,
- use only lowercase ASCII `a-z`, digits, `-`, and `.`,
- begin and end with an alphanumeric character,
- contain neither `--` nor `..`.

Periods are valid in plugin names. Agent Skill names have a narrower grammar and cannot contain periods.

## Validation and runtime handling

The schema is closed. For authoring, every unknown field is a conformance error. A conforming client nevertheless handles two categories non-fatally:

- Unknown top-level field: report and ignore each unknown field, then continue if the rest of the manifest is valid.
- Non-object `extensions`: report and ignore the field, then continue loading components.

Every other manifest schema/type/name failure is fatal to the plugin: reject it and do not discover or execute components.

This distinction matters in reports. “Client can continue after ignoring this field” does not mean the package conforms.

## Schema and version selection

For v1.0.0, `$schema` must be exactly:

```text
https://agent-plugins.org/schemas/1.0.0/plugin.schema.json
```

Clients recognize supported identifiers locally and must not fetch a schema while loading. An unsupported declared version rejects the plugin. A client can explicitly map recognized versions as compatible, but must not guess compatibility from similar field shapes.

When `mcp.json` exists, its schema version must match the Agent Plugins version in the manifest. A mismatch disables MCP for this plugin but does not invalidate valid skills.

## Metadata quality advisories

The specification only requires JSON types for most optional metadata. For release quality:

- use canonical SemVer for released package versions,
- use a standard SPDX expression or clearly bundled license terms,
- publish stable HTTPS homepage/repository URLs,
- avoid duplicate or vague keywords,
- keep the package directory name equal to the manifest name unless the distribution system requires otherwise.

These are advisories unless a client or marketplace adds its own documented requirements.
