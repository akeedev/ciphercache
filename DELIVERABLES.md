# Project Deliverables

This document defines the project artifacts that should exist after changes are
implemented. It is the authoritative project-specific deliverables guide and is
intended for both human contributors and coding agents.

## Required deliverables
- Source code under `src/`.
- Tests under `tests/` (including spec-aligned tests).
- Demo notebooks under `notebooks/` (one per spec when applicable).
- User-facing documentation under `doc/`.
- Build artifacts in `dist/` (wheel and sdist).

## When to regenerate deliverables
- **Specs or user-facing behavior changed**:
  - Update `doc/ai_agent_notes.md` if the agent workflow or usage changed.
  - Update `doc/overview.md` or `doc/user_guide.md` if the user-facing behavior changed.
- **New feature spec added or updated**:
  - Add or update the matching `tests/test_NNN_*.py`.
  - Add or update the matching `notebooks/demo_NNN_*.ipynb`.
- **Preparing a reviewable build or handoff**:
  - Produce wheel and sdist via `uv build`.

## Build commands
- Build artifacts:
  - `uv build`
- Install wheel elsewhere:
  - `uv pip install /path/to/dist/ciphercache-<version>-py3-none-any.whl`

## Output locations
- Wheels and sdists: `dist/`
- Docs: `doc/`
- Notebooks: `notebooks/`
- Tests: `tests/`
