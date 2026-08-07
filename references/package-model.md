# Package Model and Discovery

## Minimal package

A plugin is one directory with an exact root manifest:

```text
example-plugin/
└── plugin.json
```

`skills/`, `mcp.json`, extension directories, licenses, changelogs, binaries, and other files are optional. Missing optional fixed locations are not errors.

## Standard layout

```text
example-plugin/
├── plugin.json
├── skills/
│   └── summarize/
│       ├── SKILL.md
│       ├── scripts/
│       ├── references/
│       └── assets/
├── mcp.json
├── com.example.client/
├── LICENSE
└── CHANGELOG.md
```

Core discovery is fixed:

| Component    | Location                                                    | Discovery                                                 |
| ------------ | ----------------------------------------------------------- | --------------------------------------------------------- |
| Manifest     | root `plugin.json`                                          | exact regular file, loaded first                          |
| Skills       | root `skills/`                                              | immediate child directories with exact regular `SKILL.md` |
| MCP servers  | root `mcp.json`                                             | one closed JSON configuration                             |
| Client files | root directory named exactly for a reverse-domain namespace | semantics only from the owning client                     |

`plugin.json` cannot redirect these locations or declare inline components. Clients do not recursively search for skills beneath grandchildren of `skills/`.

## Filesystem containment

Whenever a client reads or executes package-supplied content, the filesystem-resolved path must stay within the filesystem-resolved plugin root. This includes symlinks, junctions, reparse points, and equivalent mechanisms.

A field defined as a plugin-relative path must:

1. begin with `./`,
2. resolve against the plugin root,
3. remain inside the resolved plugin root.

Examples:

- `./bin/server`: structurally valid if resolution stays inside.
- `./data/../bin/server`: can be valid after normalization if it stays inside.
- `../bin/server`: invalid.
- `/opt/server`: invalid as a plugin-relative command.
- a symlink `./bin/server -> ../../outside`: invalid.

Arguments and environment values are opaque strings except for the two defined MCP placeholders. Do not reinterpret every string that resembles a path as a package path.

## Narrow failure scope

A containment problem applies at the narrowest owner:

- escaping root manifest: reject plugin,
- escaping fixed `skills/` or `mcp.json`: invalidate that component type,
- escaping discovered `SKILL.md`: skip that skill,
- escaping one MCP server command or working directory: skip that server,
- other package path: deny that access.

See [Failure Boundaries](failure-boundaries.md).

## Filesystem kind

When present:

- `plugin.json` must resolve to a regular file,
- `skills/` must resolve to a directory,
- a discovered `SKILL.md` must resolve to a regular file,
- `mcp.json` must resolve to a regular file.

A wrong kind at an optional fixed location invalidates that component type but does not automatically reject unrelated types.

## Containment is not sandboxing

Package containment prevents a package path from escaping while the client discovers or resolves it. It does not prevent a launched subprocess from later reading the filesystem, opening a network connection, spawning a child, modifying user files, or consuming resources. Sandboxing, permissions, and trust policy are outside Agent Plugins v1 and require client/platform controls.

## Packaging policy in this skill

The bundled packager rejects all symlinks rather than attempting to preserve internal links. This is stricter than the specification because ZIP extraction and link semantics differ across operating systems and clients. A repository that intentionally relies on internal symlinks must use a reviewed distribution process and test every target extractor/client.
