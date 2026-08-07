# Failure Boundaries

Agent Plugins deliberately isolates many faults. A client implementation reports precisely and continues at the narrowest valid boundary.

| Failure                                                                                                             | Required client effect                               | Unrelated behavior                      |
| ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | --------------------------------------- |
| `plugin.json` missing, wrong kind, outside root, invalid JSON, unsupported schema, invalid required/type/name field | reject plugin                                        | discover/execute nothing                |
| unknown top-level manifest field                                                                                    | report and ignore field, then continue if otherwise valid | components can load                  |
| non-object `extensions`                                                                                             | report and ignore extensions field                   | core components can load                |
| absent `skills/`                                                                                                    | no error                                             | MCP/extensions can load                 |
| present `skills/` wrong kind or escaping root                                                                       | invalidate skills component type                     | MCP/extensions can load                 |
| one discovered `SKILL.md` invalid or escaping root                                                                  | skip that skill                                      | other skills/MCP can load               |
| absent `mcp.json`                                                                                                   | no error                                             | skills/extensions can load              |
| `mcp.json` wrong kind, invalid JSON, unsupported/mismatched schema, or invalid top level                            | disable MCP for plugin                               | skills/extensions can load              |
| one MCP server invalid or command/cwd escaping its allowed root                                                     | skip that server                                     | other servers/components can load       |
| declared MCP transport unsupported                                                                                  | skip that server                                     | other servers/components can load       |
| MCP start/connect/auth/handshake failure                                                                            | report connection failure for that server            | other servers/components can load       |
| unsupported extension namespace                                                                                     | ignore without validating its contents               | portable core can load                  |
| failure inside an implemented extension namespace                                                                   | rules of the owning client                            | core semantics remain unchanged         |
| another package path escapes root                                                                                   | deny that access                                     | apply no broader failure than necessary |

## Authoring versus runtime recovery

A validator can correctly emit an error for a nonconforming package even where a client is required to recover and load other components. Include both facts:

```text
ERROR MCP_SERVER_CWD_ESCAPE [server:local]
The server entry is nonconforming and must be skipped. Other MCP servers and valid skills remain eligible to load.
```

Do not flatten all errors into “plugin rejected,” and do not downgrade nonconformance to a warning merely because runtime recovery is defined.

## Implementation pattern

Represent findings with at least:

- specification version,
- scope (`plugin`, `manifest`, `skills`, `skill:<name>`, `mcp`, `server:<name>`, `extension:<namespace>`),
- code and message,
- severity for authoring/conformance,
- required runtime effect,
- evidence path and, when available, line/field,
- whether execution was attempted.

Keep parse/validation data separate per component so one exception cannot prevent the client from evaluating independent siblings.
