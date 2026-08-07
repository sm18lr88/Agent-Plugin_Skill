# Core Method

This is the operating method for Agent Plugin work. Use the focused references for field-level rules.

## Authority and evidence

Apply sources in this order when they conflict:

1. The explicit goal of the user and the governing instructions of the repository.
2. The published Agent Plugins specification version declared by `plugin.json`.
3. The Agent Skills specification for each `SKILL.md` and MCP for wire and lifecycle behavior.
4. The documentation of the owning client for its namespace, installation, and supported components.
5. Official examples and migration guidance.
6. The references, assets, and scripts in this skill.

The Agent Plugins textual specification is authoritative over its JSON schemas. Do not retrieve schemas during client loading. Clients select locally supported rules from the canonical `$schema` identifier. For authoring, the vendored schemas are a reviewed offline snapshot, not proof that upstream has not changed.

## Classify the request

### Author

Create or extend a portable plugin. Determine:

- plugin identity and targeted Agent Plugins version,
- target clients and promised transports,
- whether any reusable behavior is a skill,
- whether an MCP server is actually required,
- whether client-only behavior has an owner-defined namespace,
- runtime, data, secret, and distribution requirements.

Start with only `plugin.json`. Add `skills/` and `mcp.json` only when they provide real behavior. Do not create placeholder components that cannot run.

### Review

Report four independent conclusions:

1. **Conformance:** does the package satisfy the declared specification?
2. **Portability:** does it rely on undeclared client-native behavior or host assumptions?
3. **Runtime viability:** do referenced files, executables, endpoints, and permissions plausibly work?
4. **Security/release readiness:** are secrets, subprocesses, dependencies, origins, update behavior, and provenance controlled?

A conforming package can still fail at runtime or be unsafe. A client can recover from a nonconforming local component without making the package authoring defect disappear.

### Migrate

Inventory first. Map every artifact to exactly one primary owner:

- portable core,
- client extension,
- compatibility layer,
- distribution metadata,
- removal with evidence.

Prefer additive and reversible conversion. Keep working legacy files until the portable or namespaced replacement passes the same client behaviors.

### Implement a client

Implement version recognition, fixed discovery, resolved-path containment, independent component validation, placeholder expansion, transport mapping, and narrow failure isolation. Do not turn a convenience implementation into new portable semantics.

## Evidence-first workflow

1. **Inspect without mutation.** Locate manifests, skills, MCP files, extension directories, legacy layouts, scripts, binaries, dependency files, tests, release jobs, and marketplace entries.
2. **Declare targets.** Record Agent Plugins version, operating systems, architectures, clients, transports, install modes, and offline/network expectations.
3. **Build a component map.** Name the consumer and source of truth for every artifact.
4. **Design the smallest core.** Use fixed locations. Keep metadata closed. Avoid optional mechanisms without a real consumer.
5. **Apply path and secret rules early.** Resolve paths, choose `PLUGIN_ROOT` or `PLUGIN_DATA`, and remove credentials from package data before implementation grows around them.
6. **Validate in layers.** Parse, schema/field semantics, filesystem semantics, component independence, packaging, then client behavior.
7. **Test promised behavior.** Install and load on every promised client. Start/connect each MCP transport and exercise representative tools. Trigger each skill with positive and negative prompts.
8. **Package and record evidence.** Produce a deterministic artifact where practical. Record hash, version, source commit, tests, unsupported clients, and residual risks.

## Decision rules

- Treat a skill as reusable instructions/resources, not as a disguised continuously running agent.
- Use MCP when the plugin needs callable external capabilities or data access. Do not add it merely to execute static guidance.
- Use a client extension only when the client publishes and owns the namespace and behavior.
- Use a compatibility package when a target client still requires a legacy layout or has no portable equivalent.
- Keep one canonical metadata/component source where multiple client packages must be generated.
- Prefer `PLUGIN_ROOT` for immutable packaged resources and `PLUGIN_DATA` for dependencies, caches, generated code, and persistent writable state.
- Never use package headers or environment values as a secret-injection scheme.
- Do not infer sandboxing, signing, permission prompts, dependency resolution, or enterprise policy from v1 conformance.

## Required handoff

For substantial work, report:

- declared specification and schema versions,
- target clients, platforms, and transports,
- original-to-final artifact map when migrating,
- portable files added or changed,
- extension/compatibility/distribution files retained and why,
- validator commands and exact results,
- client installation, discovery, activation, MCP handshake/tool, upgrade, and rollback evidence actually run,
- findings grouped by conformance, advisory, runtime, security, and compatibility,
- failure boundary for each nonconforming component,
- remaining assumptions, untested paths, and release blockers.

Use explicit language: “schema-valid,” “passes this validator,” “loaded in client X,” and “MCP handshake completed” are different claims.
