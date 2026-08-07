# Security and Supply Chain

Separate normative Agent Plugins rules from additional hardening. Conformance is not a trust decision.

## Normative v1 security-relevant rules

- Every package-supplied resolved path stays within the resolved plugin root.
- Plugin-relative paths begin `./` and remain contained.
- stdio `command` is one executable token, not a shell command string.
- `cwd` remains within plugin root or within the dedicated `PLUGIN_DATA` root.
- Clients control `PLUGIN_ROOT` and `PLUGIN_DATA`. Configuration cannot override them.
- Package `env` values and remote headers are visible data and cannot embed secrets.
- Remote non-loopback MCP endpoints use HTTPS.
- Remote URLs contain no user information or fragments.
- Header names are case-insensitive and duplicates by casing are invalid.
- Configured headers are not forwarded to another origin without explicit authorization.
- Client-generated authorization/HTTP/MCP headers take precedence.

## Not defined by v1

The standard does not define a trust registry, signatures, provenance attestations, installer permissions, or a process sandbox. It does not define resource limits, network policy, dependency resolution, a secret store, an OAuth block, an enterprise allowlist, telemetry, or an audit-log schema. A client or distribution system must supply these controls.

## Threat model

Review at least:

| Surface             | Representative risk                                                 | Control                                                                              |
| ------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Archive/install     | traversal, link escape, case collision, overwrite                   | hardened extraction into isolated staging root                                       |
| Manifest/JSON       | duplicate keys, parser differential, unsupported version            | duplicate-key rejection, local version rules, closed fields                          |
| Skills/instructions | prompt injection, unsafe commands, data exfiltration                | treat package instructions as untrusted code-like content. Use host policy and approvals |
| Scripts/binaries    | arbitrary code, architecture mismatch, persistence                  | provenance, review, sandbox, least privilege, hashes/signing outside core            |
| stdio command       | shell injection, PATH hijack, argument confusion                    | tokenized spawn, contained bundled paths, controlled environment                     |
| Dependencies        | install scripts, typosquatting, drift                               | lockfiles, verified registries, offline/cache policy, SBOM and scanning              |
| `PLUGIN_DATA`       | poisoned cache, stale generated code, cross-version incompatibility | per-instance isolation, migration/versioning, safe cleanup                           |
| Remote MCP          | malicious origin, TLS/auth failure, redirect leakage                | HTTPS, origin pinning/policy, client-managed auth, redirect controls                 |
| Logs/diagnostics    | secret or patient/customer data leakage                             | structured redaction and minimal logging                                             |
| Updates             | source replacement, rollback attack, incompatible state             | immutable release identity, signature/provenance system, rollback plan               |
| Extensions          | client-specific privilege escalation                                | namespace-owner validation and host permission policy                                |

## Package secret review

Scan all text and metadata for:

- bearer/API tokens, passwords, cookies, private keys, cloud credentials,
- `.env` files and credential config,
- live authorization headers,
- secret-looking MCP environment values,
- private repository URLs containing credentials,
- logs, fixtures, or examples with real data.

Placeholders other than the two plugin path placeholders are not a portable secret mechanism. `${API_TOKEN}` in a header remains literal. It does not defer secret lookup.

## Subprocess policy recommendations

Beyond conformance, a production client is recommended to consider:

- per-plugin identity and least filesystem access,
- network egress controls,
- CPU/memory/process/time quotas,
- explicit user/admin approvals by capability,
- executable allowlists or provenance policy,
- sanitized base environment and working directory,
- no implicit shell,
- stdout/stderr size limits and redaction,
- lifecycle cleanup and child-process termination,
- secure `PLUGIN_DATA` permissions and tenant separation.

## Release evidence

For a distributable plugin, record:

- source commit and clean build procedure,
- dependency lock and SBOM where relevant,
- generated/bundled binary hashes and target platforms,
- archive hash and signing/provenance evidence supplied by the distribution system,
- validator and client test results,
- vulnerability review and accepted risks,
- update/rollback behavior and `PLUGIN_DATA` migration expectations.

Use [the threat-model asset](../assets/threat-model.md) for consequential packages.
