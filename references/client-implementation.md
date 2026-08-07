# Client Implementation

This reference is for hosts that discover, install, load, or execute Agent Plugins. It summarizes the v1 contract. The published specification remains authoritative.

## Loader phases

Implement explicit phases. One component must not accidentally broaden the failure boundary of another component:

1. Resolve one plugin root.
2. Resolve and validate exact root `plugin.json`.
3. Select locally supported rules from its canonical `$schema` identifier. Never fetch schemas during loading.
4. Apply manifest handling, including the two non-fatal cases for unknown fields and non-object `extensions`.
5. Discover each supported fixed component location independently.
6. Validate every skill independently.
7. Validate root MCP configuration, then every server independently.
8. Apply only implemented extension namespaces under owner-defined rules.
9. Start/connect eligible MCP servers independently.
10. Expose valid skills/components and structured diagnostics.

Pseudo-code:

```text
root = resolve_plugin_root(input)
manifest = load_manifest(root/plugin.json) or reject_plugin
rules = select_supported_version(manifest.$schema) or reject_plugin
manifest = validate_manifest_with_recoverable_fields(manifest) or reject_plugin

skills = discover_fixed_skills(root)
for skill in skills:
    validate_or_skip(skill)

mcp = load_fixed_mcp(root)
if top_level_mcp_valid_and_version_matches(mcp, manifest):
    for server in mcp.servers:
        validate_or_skip(server)

for namespace in implemented_extensions:
    load_under_namespace_rules(namespace)
```

## Path handling

- Establish a filesystem-resolved root once and use canonical containment checks.
- Check containment after symlink/junction/reparse resolution, not by string prefix.
- Apply plugin-relative `./` semantics only to fields the specification defines as paths.
- Keep component-type and item scopes so a path failure maps to the required narrow boundary.
- Defend archive extraction itself against `..`, absolute paths, link escapes, case collisions, and platform-reserved names before loading.

Archive extraction safety is an installer responsibility even though the package model is expressed as a directory.

## Manifest handling

Keep an allowlist for the selected spec version. Unknown top-level fields are reported and ignored, while other type/name/schema failures reject the plugin. Ignore a non-object `extensions` field but do not treat malformed extension values as portable core data.

Do not infer support for a newer schema from successful JSON parsing. Compatibility mappings must be explicit client decisions.

## Skill handling

- Check only immediate children of `skills/`.
- Require exact `SKILL.md` regular files contained in root.
- Validate with the Agent Skills source of truth.
- Skip invalid skills individually.
- Make activation/exposure behavior a client concern without rewriting skill semantics.

## MCP runtime

For stdio:

- resolve bare executable names with platform rules,
- resolve `./` commands against plugin root and verify containment,
- expand only the two defined placeholders in args/env values/cwd,
- provide client-owned absolute `PLUGIN_ROOT` and writable persistent `PLUGIN_DATA`,
- apply configured env over the chosen base, then force the reserved variables,
- preserve argument boundaries. Do not concatenate a shell line,
- isolate process start, handshake, shutdown, logs, and failures per server.

For remote transports:

- enforce URL and loopback rules,
- validate header names/values and case-insensitive duplicates,
- keep client-generated HTTP/MCP/auth headers authoritative,
- do not forward configured headers cross-origin without explicit authorization,
- manage authorization outside package-visible fields.

## Diagnostics

Emit stable machine-readable diagnostics with:

- plugin identity and selected version,
- component/item scope,
- code, severity, path/field,
- required runtime action,
- parse/schema/semantic/runtime stage,
- cause chain without leaking secrets,
- whether other components remain available.

Do not log configured secrets. Conforming packages are expected not to contain them, but clients must still assume hostile input.

## Client conformance testing

Test at least:

- missing/wrong-kind fixed locations,
- unknown manifest field recovery versus fatal field errors,
- symlink and traversal escapes at every scope,
- multiple skills with one invalid sibling,
- bad top-level MCP versus one bad server,
- unsupported transport and connection failure isolation,
- single-pass placeholder expansion and unrecognized literal placeholders,
- reserved environment override attempts,
- URL loopback, userinfo, fragment, TLS, duplicate header, and redirect cases,
- ignored unknown extensions and the failure rules of one implemented extension,
- upgrades preserving `PLUGIN_DATA`, uninstall cleanup policy, and concurrent versions where supported.

See [the client-conformance-review asset](../assets/client-conformance-review.md).
