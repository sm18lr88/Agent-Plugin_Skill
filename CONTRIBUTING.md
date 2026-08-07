# Contributing

## Prepare the checkout

Install Python 3.11 or later and uv.

Run:

```bash
uv sync --frozen
```

## Make a focused change

1. Read `SKILL.md` and the reference for your subject.
2. Preserve the official requirement strength.
3. Label local security or release policy as local policy.
4. Add a regression case for a subtle validation boundary.
5. Keep generated files and local state out of the change.

## Validate the change

Run:

```bash
uv run python scripts/validate_plugin.py --self-test
uv run python scripts/new_plugin.py --self-test
uv run python scripts/package_plugin.py --self-test
uv run python scripts/package_skill.py --self-test
uv run python scripts/portability_check.py --self-test
uv run python scripts/validate_skill.py --self-test
uv run python scripts/validate_skill.py . --source-checkout
```

The last command requires a clean Git checkout.

## Submit the change

Describe the official source or local policy behind each changed rule. Include commands and observed results.

Do not include credentials, private paths, generated indexes, virtual environments, or editor state.
