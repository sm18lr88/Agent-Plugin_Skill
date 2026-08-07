# Agent Plugin Threat Model

## Scope

- Plugin/version/hash:
- Distribution channel:
- Target clients/platforms:
- Skills/MCP/extensions/adapters:
- Trust assumptions:

## Assets and actors

| Asset | Owner | Sensitivity | Required protection |
|---|---|---|---|
| | | | |

| Actor | Trust level | Capabilities | Goal |
|---|---|---|---|
| | | | |

## Trust boundaries and data flows

- Package acquisition and extraction:
- Manifest/skill parsing:
- Subprocess execution:
- `PLUGIN_DATA`:
- Remote MCP origins:
- Authorization/secret store:
- Extensions and client APIs:
- Update/rollback:

## Threats

| ID | Surface | Attack path | Impact | Existing control | Gap | Verification |
|---|---|---|---|---|---|---|
| T-01 | | | | | | |

## Normative Agent Plugins controls

- [ ] resolved package containment
- [ ] tokenized stdio command
- [ ] contained working directory
- [ ] reserved client-owned path variables
- [ ] no secrets in package env/headers
- [ ] HTTPS for non-loopback remote MCP
- [ ] no userinfo/fragments and safe header/origin behavior

## Additional host/distribution controls

- [ ] hardened archive extraction
- [ ] source/release provenance and hashes
- [ ] dependency lock/SBOM/scanning
- [ ] least privilege and sandboxing
- [ ] network/resource/process limits
- [ ] client-managed secrets and authorization
- [ ] redacted diagnostics
- [ ] state migration, rollback, and uninstall policy

## Residual risks and acceptance

- 
