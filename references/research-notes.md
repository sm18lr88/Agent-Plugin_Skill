# Research Notes and Provenance

Reviewed: **2026-08-06**

## Normative sources

### Agent Plugins Specification 1.0.0

- Published specification: `https://agent-plugins.org/specification`
- Schemas: `https://agent-plugins.org/schemas`
- Repository: `https://github.com/agentplugins/agent-plugins-spec`
- Pinned branch/commit: `main` / `bd383552095128f6effe895b9257cfd580a6d179`
- Pinned spec path: `spec/1.0.0.md`
- License statement: documentation/examples CC BY 4.0. Schemas/code/scripts Apache-2.0.

The pinned `spec/1.0.0.md` source labels v1.0.0 as Published. Recheck the current site before you report a later status.

Vendored schema snapshots:

| Schema | Canonical ID                                                 | Upstream blob SHA                          |
| ------ | ------------------------------------------------------------ | ------------------------------------------ |
| plugin | `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` | `8fed0e1fe45d0464aee880d3fbab228b71ecfc1e` |
| MCP    | `https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`    | `a9139a4259b932c60b5351c8d9da6a5c60c97646` |

### Agent Skills

- Specification: `https://agentskills.io/specification`
- Best practices: `https://agentskills.io/skill-creation/best-practices`
- Evaluating skills: `https://agentskills.io/skill-creation/evaluating-skills`
- Repository: `https://github.com/agentskills/agentskills`
- Pinned branch/commit: `main` / `217be548739f21d6008915c29aefe320ea1a90af`
- Reference parser reviewed: `skills-ref/src/skills_ref/parser.py`
- Reference validator reviewed: `skills-ref/src/skills_ref/validator.py`
- Installed package: `skills-ref==0.1.1` from PyPI
- Wheel SHA-256: `d35db5bb8de71ae301daf5ca9cb71f8a555e8c6f83a6d40e46a5bc09f8f461b5`
- Source distribution SHA-256: `6b400ca6e0049be62dca0167ff943ba2745fd67efb37fbba4d0ee341fccd2695`

Agent Plugins defers the `SKILL.md` format to Agent Skills. This project pins reviewed `skills-ref` artifacts by version and hash. The package was uploaded without Trusted Publishing, so the hashes prove artifact identity but not source-build provenance. Local validation uses its StrictYAML parser and metadata validator.

### Model Context Protocol

- Current published specification reviewed: `https://modelcontextprotocol.io/specification/2026-07-28`
- Repository: `https://github.com/modelcontextprotocol/modelcontextprotocol`
- Pinned branch/commit: `main` / `2de0727d3c2d6f2f32b3fefbba0bf8395b2e7324`

MCP governs wire/lifecycle behavior. Agent Plugins governs how a plugin declares server connection configuration in `mcp.json`.

## Official implementation and migration sources

- Build guidance: `https://agent-plugins.org/plugin-authors`
- Manifest: `https://agent-plugins.org/plugin-authors/manifest`
- Skills: `https://agent-plugins.org/plugin-authors/skills`
- MCP servers: `https://agent-plugins.org/plugin-authors/mcp-servers`
- Client extensions: `https://agent-plugins.org/plugin-authors/client-extensions`
- Compatible clients: `https://agent-plugins.org/compatible-clients`
- Official example repository: `https://github.com/agentplugins/agent-plugins-example`
- Pinned example commit: `5f3f5084a821aefa792e79500dd8f0462ab83473`

The migration skill in the official example informed the inventory-first, additive, consumer-preserving approach. Local guidance expands it with failure-scope diagnostics, deterministic packaging, security review, and regression tooling.

## Non-normative gaps deliberately exposed

The Agent Plugins future-considerations material identifies major areas outside v1. These areas include trust/permissions/sandboxing, provenance/signatures, secrets, enterprise policy, audit, dependencies, and a standard validator/test harness. This skill treats those as separate engineering layers. It never labels its local recommendations as v1 requirements.

## Update triggers

Review upstream before modifying current-version claims when:

- `plugin.json` or `mcp.json` schema identifiers change,
- a new Agent Plugins spec release appears,
- Agent Skills frontmatter or discovery rules change,
- MCP deprecates or adds a transport relevant to plugin configuration,
- the compatible-client matrix changes,
- a client publishes or removes an extension namespace,
- path, placeholder, header, authorization, or failure-boundary text changes.

Use [the maintenance protocol](../maintenance/UPSTREAM_REVIEW.md) and update the immutable baseline only after classifying every relevant upstream change.
