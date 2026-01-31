# 2026_ai_pycoding_template

A template repository for spec-first, Codex-assisted Python projects. 
It includes a small example CLI feature.

## Example quickstart

```bash
uv run python main.py
```

## Example tests

```bash
uv run pytest
```

## Using this template
- Update `pyproject.toml` project metadata.
- Rename the example package in `src/helloworld` if you want a clean slate.
- Add new feature specs under `spec/NNN-*.md` and corresponding tests under `tests/`.

## Project layout

- `src/` application sources
- `tests/` pytest tests
- `spec/` feature specifications
- `data/` data files
- `testdata/` test data
- `doc/` documentation

## PyCharm run configurations

If you use PyCharm, you can add shared run configurations under `.idea/runConfigurations/`.
