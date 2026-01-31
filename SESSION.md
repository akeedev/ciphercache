# SESSION.md

## Session date
- 2026-01-31

## Current status
- Working branch: `feat/020-ipc-protocol`
- IPC protocol MVP implemented with framing, handler, daemon state skeleton, and specs updated.
- Additional unit tests and invariant tests added.
- Notebook demo updated to use secure temp dir.
- AGENTS.md updated with testing/docstring/doctest rules.

## Key decisions (specs)
- IPC framing: length-prefixed JSON.
- Message envelope v0 with request/response/error.
- Tickets inline per `get_secret`.
- Store identity is via alias; MVP supports a single active store; alias enables future multi-store.
- TTL format supports `s|m|h|d`, combined tokens, and `infinity`.

## Files changed (high level)
- Specs: `spec/000-overview.md`, `spec/010-architecture.md`, `spec/020-ipc-protocol.md`
- IPC code: `src/ciphercache/ipc/*`, `src/ciphercache/daemon/state.py`, `src/ciphercache/ttl.py`
- Tests: `tests/test_020_ipc_protocol.py`, `tests/test_ttl.py`, `tests/test_ipc_framing.py`,
  `tests/test_ipc_handler.py`, `tests/test_010_arch_invariants.py`
- Notebook: `notebooks/demo_020_ipc_protocol.ipynb`
- Guidelines: `AGENTS.md`

## Tests run (all passing)
- `uv run pytest -q`
- `uv run mypy src tests`
- `uv run ruff check src tests`

## Git status snapshot
- `git status -sb`:
  - `## feat/020-ipc-protocol...origin/feat/020-ipc-protocol`
  - ` M SESSION.md`

## Recent commits
- `567edf3` Specified IPC feature, coded and tested it, working version. Now in review.
- `e3ea64e` Merge pull request #2 from akeedev/chore-template-cleanup
- `545e63d` Clean project based on the AI code template. Will now begin with spec.
- `7bcec5b` Merge pull request #1 from akeedev/chore-template-cleanup
- `e9bf8ca` Clean project based on the AI code template. Will now begin with spec.

## TODO next session
- Ensure code review of current changes.
- Decide on commit strategy and push/merge workflow.
- Implement Unix domain socket server loop for `ciphercached` (next milestone).

