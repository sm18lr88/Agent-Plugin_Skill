# Agent Plugins Client Conformance Review

## Identity

- Client/version/commit:
- Supported Agent Plugins versions:
- Supported components/transports:
- Extension namespaces owned:
- Platforms tested:

## Loader phases

- [ ] Resolved root and exact `plugin.json`
- [ ] Local schema/version selection, no network schema fetch
- [ ] Unknown-field and malformed-extensions recovery
- [ ] Fixed component discovery
- [ ] Independent skill validation
- [ ] Top-level and per-server MCP validation
- [ ] Namespace-owned extension handling
- [ ] Structured diagnostics and narrow failure isolation

## Path containment fixtures

| Scope | Fixture | Expected boundary | Result |
|---|---|---|---|
| manifest | escape/wrong kind | reject plugin | |
| skills root | escape/wrong kind | disable skills | |
| skill | escaping `SKILL.md` | skip one skill | |
| MCP server | command/cwd escape | skip one server | |
| other file | escape | deny access | |

## MCP runtime

- [ ] command and args remain tokenized
- [ ] placeholder expansion is exact, single-pass, and field-limited
- [ ] reserved environment variables are client-owned
- [ ] `PLUGIN_DATA` is writable, isolated, and update-persistent
- [ ] URL, loopback, header, origin, and redirect rules enforced
- [ ] unsupported transport and connection failure isolate one server

## Negative sibling-isolation fixtures

- [ ] one invalid skill plus one valid skill
- [ ] invalid MCP top level plus valid skill
- [ ] one invalid server plus one valid server
- [ ] unsupported namespace plus valid core
- [ ] implemented extension failure plus valid core

## Security controls outside v1

- Extraction hardening:
- Permission/sandbox model:
- Secret/auth system:
- Provenance/signature policy:
- Resource/network limits:
- Logging/redaction:

## Verdict and evidence

- 
