# Client Compatibility Snapshot

Reviewed: **2026-08-06**

The Agent Plugins project listed the following support for the portable format on the review date:

| Client             | Agent Skills | MCP stdio | Streamable HTTP | Legacy SSE |
| ------------------ | -----------: | --------: | --------------: | ---------: |
| Visual Studio Code |          yes |       yes |             yes |        yes |
| Cursor             |          yes |       yes |             yes |        yes |
| GitHub Copilot     |          yes |       yes |             yes |        yes |
| ChatGPT & Codex    |          yes |       yes |             yes | not listed |
| Kiro               |          yes |       yes |             yes |        yes |

Source: `https://agent-plugins.org/compatible-clients`

## How to use this table

This is discovery evidence, not a permanent guarantee and not package-specific proof. Before release:

1. Recheck the official compatibility page and the setup documentation for each target client.
2. Record exact client product/version, install path, feature flags, operating system, and transport.
3. Test the package itself.
4. Treat client extensions separately. Core support does not imply that a client implements any namespace.
5. Do not claim legacy SSE support for ChatGPT/Codex from this snapshot because it was not listed.

Clients can adopt component types incrementally. A client can support skills without MCP, one MCP transport without another, or core without a particular distribution flow. Installation UX, update behavior, authorization, extension namespaces, and sandboxing are client-specific.
