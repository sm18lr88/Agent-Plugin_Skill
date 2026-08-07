# MCP Servers

Agent Plugins defines the root `mcp.json` configuration used to locate and connect to MCP servers. The Model Context Protocol specification governs wire behavior, capabilities, authorization behavior, and lifecycle semantics.

## Root configuration

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {}
}
```

Only `$schema` and `mcpServers` are allowed at the top level. An empty server map is valid. The MCP schema version must match the Agent Plugins version selected by `plugin.json`.

Each server is validated independently and must match exactly one closed variant.

## stdio

```json
{
  "type": "stdio",
  "command": "python",
  "args": ["${PLUGIN_ROOT}/server/main.py"],
  "env": {
    "CACHE_DIR": "${PLUGIN_DATA}/cache"
  },
  "cwd": "${PLUGIN_ROOT}"
}
```

Fields:

- `type`: exact `stdio`, required.
- `command`: one executable token, required. It is either a bare executable name or a plugin-relative path beginning `./`.
- `args`: optional string array passed separately from the executable.
- `env`: optional string-to-string map.
- `cwd`: optional working directory.

Do not place a shell command line in `command`. A package-bundled executable must use `./path`. A bare name uses platform executable search. Placeholder expansion never occurs in `command`. Plugins must not depend on a configured `PATH` participating in command resolution because that behavior is client-defined.

When `cwd` is absent, use the plugin root. When present, it must be:

- `./...`, resolved inside plugin root,
- `${PLUGIN_ROOT}` or `${PLUGIN_ROOT}/...`, resolved inside plugin root,
- `${PLUGIN_DATA}` or `${PLUGIN_DATA}/...`, resolved inside the dedicated data root.

A post-normalization escape invalidates only that server entry.

## Placeholders and process environment

Clients launching stdio servers provide:

- `PLUGIN_ROOT`: absolute filesystem-resolved plugin root,
- `PLUGIN_DATA`: absolute, writable, per-installed-plugin data directory preserved across updates.

Use `PLUGIN_ROOT` for bundled immutable scripts, binaries, and configuration. Use `PLUGIN_DATA` for installed dependencies, virtual environments, caches, generated code, indexes, and other persistent mutable state.

Clients expand every exact `${PLUGIN_ROOT}` and `${PLUGIN_DATA}` occurrence in:

- each `args` string,
- each `env` value,
- `cwd`.

Expansion is single-pass, textual, and non-recursive. It does not apply to `command`, environment keys, URLs, headers, or fixed component paths. Unrecognized placeholder-like text remains literal. No other environment interpolation is portable.

`env` cannot define `PLUGIN_ROOT` or `PLUGIN_DATA`. Package environment values are visible data and must not contain secrets.

## Streamable HTTP

```json
{
  "type": "streamable-http",
  "url": "https://tools.example.com/mcp",
  "headers": {
    "X-Tenant": "public-tenant"
  }
}
```

The URL must:

- be absolute HTTP or HTTPS,
- contain no user information,
- contain no fragment,
- use HTTPS unless the host is exactly `localhost` or an IP literal in a loopback range.

Headers are fixed visible package data. Names and values must be valid HTTP fields. Names are case-insensitive, so `X-Foo` plus `x-foo` is an invalid duplicate. Clients do not expand placeholders in URLs or headers. Client-generated HTTP, MCP, or authorization headers take precedence. A client must not forward configured headers to another origin through redirects or legacy SSE endpoint events without explicit user authorization.

Agent Plugins v1 defines no portable OAuth block or credential-reference field. Authorization discovery, interaction, and storage are client-managed. Do not place API keys, bearer tokens, cookies, passwords, or private material in `headers`.

## Legacy SSE

`type: "sse"` selects the deprecated HTTP+SSE transport from MCP 2024-11-05. It does not mean SSE responses used inside Streamable HTTP. Client support is optional. Use it only for a real legacy endpoint and document the compatibility requirement.

## Support and failures

A client implementing Agent Plugins MCP must support at least one of stdio or Streamable HTTP. Support for both is recommended. SSE is optional. There is no portable automatic transport fallback.

Failure scope:

- invalid/unsupported/mismatched root `mcp.json`: disable MCP for this plugin, keep valid skills,
- invalid one server entry: skip it, keep other servers/components,
- unsupported declared transport: skip that server,
- start, connection, authentication, or handshake failure: report it and continue other components.

## Runtime review

Conformance validation cannot prove:

- the bare executable exists on every platform,
- a bundled binary matches architecture or execute permissions,
- dependencies are installed,
- the endpoint is reachable or trustworthy,
- TLS, authentication, MCP negotiation, or tools work,
- the subprocess is sandboxed.

Test representative start/connect, handshake, capability discovery, tool/resource/prompt operations, shutdown, restart, update persistence, and failure behavior on every promised client/platform.
