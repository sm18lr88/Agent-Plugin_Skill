# Testing and Evaluation

No single check proves an Agent Plugin is correct. Use layered evidence.

## Validation layers

1. **Bytes and syntax:** UTF-8, JSON parsing with duplicate-key detection, frontmatter delimiters.
2. **Schema/field semantics:** closed fields, required types, names, variant selection, matching schema versions.
3. **Filesystem semantics:** fixed locations, regular-file/directory kinds, immediate-child discovery, resolved containment.
4. **Security advisories:** visible secrets, remote origin/header risks, executable and dependency hazards.
5. **Packaging:** clean inventory, no accidental state, deterministic archive, hash, safe extraction.
6. **Client discovery:** install/load and component exposure in each promised client.
7. **Skill behavior:** positive/negative activation and task-output quality.
8. **MCP runtime:** process/connection, handshake, capabilities, operations, errors, shutdown, restart.
9. **Lifecycle:** update, `PLUGIN_DATA` persistence/migration, rollback, uninstall.

The bundled validator covers mainly layers 1–4 and part of 5. The packager covers a stricter distribution subset of 5. Target clients own 6–9.

## Plugin test matrix

Record one row per client/platform combination:

| Client/version | OS/arch | Install   | Manifest | Skills | stdio | HTTP | SSE | Extension | Update | Rollback |
| -------------- | ------- | --------- | -------- | ------ | ----- | ---- | --- | --------- | ------ | -------- |
| ...            | ...     | pass/fail | ...      | ...    | ...   | ...  | n/a | ...       | ...    | ...      |

Do not infer one client from another. A transport shown on a compatibility page still needs package-specific testing.

## Skill evals

For each included Agent Skill, build realistic cases with:

- positive activation prompts,
- negative prompts with no activation,
- ambiguous or terse phrasing,
- malformed inputs and missing prerequisites,
- expected output properties,
- anti-expectations for common unsafe or nonportable behavior.

Run cases with the skill and against a no-skill or prior-version baseline. Grade objective assertions with scripts where possible. Use blind human/model comparison for organization and usability. Record tokens/time if the host exposes them. Remove assertions that pass equally without the skill and investigate inconsistent runs.

## MCP tests

For every server and supported client:

- resolve command/URL as the client actually does,
- verify environment and `cwd`, without exposing secrets,
- complete MCP initialization/handshake,
- list and invoke representative tools/resources/prompts,
- test invalid arguments and server errors,
- terminate and restart cleanly,
- test unavailable executable/endpoint/auth and confirm sibling isolation,
- verify data persists across update only where intended,
- verify old state can migrate or roll back safely.

For remote endpoints, test redirect behavior, origin changes, TLS validation, authorization renewal, and client-generated header precedence.

## Client conformance fixtures

A client implementation is recommended to include negative fixtures for every boundary in [Failure Boundaries](failure-boundaries.md), especially sibling isolation. Assertions are recommended to verify both the finding and what remains loaded.

## Release gate

A release is ready only when:

- declared specification/version is supported,
- offline validator has no unresolved conformance errors,
- archive inventory and hash are recorded,
- no package secrets or unreviewed executable/dependency changes remain,
- every promised client/component/transport has evidence or is explicitly marked untested/unsupported,
- upgrade and rollback are proven for stateful plugins,
- documentation distinguishes portable core, extensions, adapters, and distribution metadata.

Use the exact command output, client/version, and artifact hash. “Works everywhere” is not test evidence.
