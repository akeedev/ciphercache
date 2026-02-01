# Contributing

Thanks for your interest in contributing!

## Scope and reading guide

Before coding, read:
- `spec/000-overview.md`
- `spec/010-architecture.md`
- The active feature spec(s) under `spec/NNN-*.md`
- `SESSION.md` for current status

## Development setup

1. Install `uv`.
2. Create/update the environment:
   ```bash
   uv sync
   ```
3. Run the tests:
   ```bash
   uv run pytest
   ```

## Code style

- Python >= 3.12
- Follow repo formatting/linting settings (ruff).
- Keep changes small and focused.
- Prefer clarity and explicitness.

## Tests and checks

Always run:
```bash
uv run pytest -q
uv run mypy src tests
uv run ruff check src tests
```

## Branching and commits

- Create a new branch per feature/bugfix.
- Commit often with clear messages.
- Do not push to `main` directly unless you are the sole maintainer.

## Documentation

Update documentation in `doc/` and README for user-facing changes.
Specs in `spec/` must be updated for behavior changes.

## Pull requests

- Explain the motivation and what changed.
- Add or update tests when behavior changes.

## Development note

AI tools may be used to assist development. All changes are reviewed by maintainers.
