# Changelog

This file records user-visible project changes.

## Unreleased

### Changed

- Replaced the handwritten Agent Skills parser with the pinned official `skills-ref` StrictYAML parser and metadata validator.
- Removed computer-specific state names and unsupported file-size limits from validation policy.
- Corrected manifest, MCP, skill, and extension failure isolation.
- Added a deterministic skill distribution contract and extracted-package validation.
- Added repository governance, architecture, CI, and release guidance.

### Security

- Stopped source validation from executing scripts in another selected checkout.
- Added stable regular-file snapshots before archive creation.

## 1.0.0

- Added the initial Agent Plugins 1.0.0 authoring, review, validation, migration, and packaging skill.
