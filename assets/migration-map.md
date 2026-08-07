# Agent Plugin Migration Map

## Source and targets

- Source plugin format/client(s):
- Target Agent Plugins version:
- Target clients/versions/platforms:
- Baseline tests captured:
- Canonical source after migration:

## Artifact map

| Source path/artifact | Current consumer | Behavior | Destination class | Target path/system | Compatibility action | Validation | Rollback | Removal gate |
|---|---|---|---|---|---|---|---|---|
| | | | portable core / extension / adapter / distribution / remove | | | | | |

## Portable core

### `plugin.json`

### Skills

### MCP servers

## Preserved non-core behavior

### Client extension namespaces

### Compatibility packages

### Distribution metadata

## Execution sequence

1. Add portable root without removing legacy behavior.
2. Normalize and validate one component at a time.
3. Test each target client.
4. Generate adapters from canonical sources where possible.
5. Prove update and rollback.
6. Remove legacy artifacts only after their gates pass.

## Open gaps and decisions

- 
