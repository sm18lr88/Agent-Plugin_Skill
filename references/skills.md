# Agent Skills in a Plugin

Agent Plugins defines where skills are discovered. The Agent Skills specification defines the format for each skill and is the source of truth.

## Discovery

A discoverable skill is an immediate child of root `skills/` whose exact `SKILL.md` path resolves to a regular file:

```text
skills/
└── release-notes/
    ├── SKILL.md
    ├── scripts/
    ├── references/
    └── assets/
```

Clients must not recursively discover deeper skill directories. A nested `skills/group/task/SKILL.md` is not a portable discovered skill. One invalid skill is skipped without hiding other valid skills or MCP servers.

## Required frontmatter

```yaml
---
name: release-notes
description: Create release notes from repository changes. Use when preparing a release or changelog.
---
```

Rules:

- `name`: 1–64 characters. Use normalized lowercase Unicode alphanumeric characters and hyphens. Do not use a leading/trailing hyphen or `--`. Exactly match the parent directory.
- `description`: 1–1024 characters. It is recommended to state both capability and activation context with concrete keywords.

Optional fields:

- `license`: short license name or bundled license reference,
- `compatibility`: 1–500 characters when environment constraints genuinely matter,
- `metadata`: mapping from string keys to string values,
- `allowed-tools`: experimental space-separated string. Support varies by host.

## Body and resources

The Markdown body has no fixed section grammar. Make it a focused, reusable procedure rather than a one-off answer. Agent Skills recommends progressive disclosure:

1. concise name/description available for discovery,
2. compact `SKILL.md` loaded on activation,
3. scripts/references/assets loaded only when needed.

Use references for detailed rules, assets for optional templates, and scripts for deterministic repeated work. Scripts are recommended to be self-contained or document dependencies, give actionable errors, and handle edge cases.

## Skill engineering checklist

- Describe exactly when the skill is recommended to activate and not activate.
- Put high-value gotchas in `SKILL.md` when the agent can fail to recognize the trigger.
- Give one safe default rather than a large menu of equivalent approaches.
- Separate reusable method from task-specific output.
- Keep local links within the skill directory and test them after moves.
- Make writes explicit. Prefer dry-run or preview behavior for scaffolding and destructive operations.
- Add positive activation, negative activation, behavior, malformed-input, and migration evals.
- Compare with-skill results to no-skill or prior-skill baselines rather than assuming added instructions help.

## Validator boundary

The validator supplies UTF-8 text to the pinned official `skills-ref` StrictYAML parser and metadata validator. It reports the official parser and metadata errors. Use the target client before release to test client-specific loading and behavior.
