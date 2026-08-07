# Releasing

## Prepare

1. Review `maintenance/upstreams.lock.json` and `maintenance/UPSTREAM_REVIEW.md`.
2. Update current claims only after the required upstream review.
3. Update `CHANGELOG.md` with the release version and date.
4. Update the project version in `pyproject.toml`, `SKILL.md`, and `agents/openai.yaml` when applicable.

## Validate

Run from a clean Git checkout:

```bash
uv sync --frozen
uv run skills-ref validate "$(pwd)"
uv run python scripts/validate_skill.py . --source-checkout
uv run python scripts/package_skill.py . --output ../agent-plugin.zip
uv run python scripts/validate_skill.py ../agent-plugin --package
```

Extract the archive before the last command. Keep the top-level `agent-plugin/` directory.

## Record evidence

Record:

- the release commit.
- the archive SHA-256.
- the official source pins.
- all validation commands and results.
- target-client smoke tests.
- unresolved security and compatibility risks.

## Publish

Create a signed Git tag if repository policy supports signing. Attach the archive and checksum to the GitHub release.

Do not claim client support without a current client test.
