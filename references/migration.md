# Migration Method

Migrate additively. Do not delete or move client-specific behavior until its consumer and tested replacement are known.

## 1. Inventory

Locate and record:

- every root or hidden manifest,
- all skill/prompt/command/agent directories,
- MCP configuration and inline MCP fields,
- hooks, LSP, UI/app, auth, permissions, and settings,
- scripts, binaries, dependencies, data/state locations, and secret requirements,
- client install/discovery rules,
- marketplace, signing, update, and release configuration,
- existing validation, smoke, upgrade, and rollback tests.

Capture a working baseline before conversion.

## 2. Build a migration map

Use [the migration-map asset](../assets/migration-map.md). Every artifact receives:

- source path and consumer,
- behavior/purpose,
- destination class,
- canonical source after migration,
- compatibility action,
- validation and smoke test,
- rollback path,
- removal gate.

Destination classes:

1. portable core,
2. client extension,
3. compatibility layer,
4. distribution metadata,
5. remove after evidence.

## 3. Add the portable root

Create the smallest conforming `plugin.json`. Use only core fields. Do not copy legacy `hooks`, `commands`, `agents`, component paths, or MCP configuration into unknown top-level fields.

## 4. Normalize reusable skills

For each genuine skill:

- place it at `skills/<name>/SKILL.md`,
- make frontmatter name match its directory,
- rewrite local references after moves,
- keep dependencies inside the skill where practical,
- separate detailed material for progressive disclosure,
- add positive and negative activation cases.

A prompt, command, or persona is not automatically a skill. Preserve semantics, not labels.

## 5. Normalize MCP

Move portable server configuration to root `mcp.json`, select an explicit transport, split executable and arguments, and use only the defined placeholders. Move writable dependencies/state to `PLUGIN_DATA`. Keep packaged immutable resources under `PLUGIN_ROOT`. Remove embedded secrets and design client-managed authorization.

If required fields or behavior cannot fit the portable schema, retain a client adapter and document the gap rather than inventing a core field.

## 6. Preserve non-core behavior

- Use only documented client-owned namespaces.
- Keep legacy packages for clients that still need them.
- Generate duplicated metadata/files from one canonical source where practical.
- Keep portable package and adapters as siblings when their roots conflict.
- Clearly distinguish portable conformance from adapter support.

## 7. Validate incrementally

At each stage:

1. run portable validation,
2. load the package in one target client,
3. test changed skills or MCP servers,
4. retest retained client-specific behavior,
5. verify upgrade and rollback paths.

Do not wait until all files have moved before checking discovery.

## 8. Remove only after replacement proof

A legacy artifact can be removed only when:

- every known consumer has migrated or is intentionally unsupported,
- the replacement passes equivalent behavior tests,
- install/update/rollback are proven,
- documentation and release automation point to the canonical package,
- recovery remains possible for the release window.

## Required migration report

Report source format, target clients, complete artifact map, files added/moved/generated/retained/removed, validation and client evidence, compatibility gaps, release steps, and removal gates. Never state that non-core features “became portable” unless the v1 core actually defines them.
