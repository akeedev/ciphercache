# SESSION.md

## Session date
- 2026-02-01

## Current status
- Working branch: `feat/050-store-keepassxc`
- IPC protocol + daemon + SDK implemented and tested.
- KeePassXC integration (export XML parsing) implemented and wired to daemon unlock.
- Demo notebooks added for IPC, daemon, SDK, and KeePassXC store.
- Documentation added under `doc/` including user guide and MVP checklist.
- Performed consistency and readiness pass; added missing tests and documentation updates.

## Key decisions (specs)
- IPC framing: length-prefixed JSON.
- Message envelope v0 with request/response/error.
- Tickets are per client; soft identity only.
- Unlock requires explicit secret list; `get_secret` never triggers unlock.
- Unlock-all on daemon startup is optional (caches all entries).
- KeePassXC integration via `keepassxc-cli export` (XML in memory).
- TTL format supports `s|m|h|d`, combined tokens, and `infinity`.

## Files changed (high level)
- Specs: `spec/000-overview.md`, `spec/010-architecture.md`, `spec/020-ipc-protocol.md`,
  `spec/030-daemon.md`, `spec/040-client-sdk.md`, `spec/050-store-keepassxc.md`
- Daemon: `src/ciphercache/daemon/*`, `scripts/run_daemon.py`
- SDK: `src/ciphercache/client.py`, `scripts/test_client.py`
- Store: `src/ciphercache/store/*`
- Tests: `tests/test_020_ipc_protocol.py`, `tests/test_ipc_handler.py`, `tests/test_030_daemon.py`,
  `tests/test_040_client_sdk.py`, `tests/test_050_store_keepassxc.py`
- Notebooks: `notebooks/demo_020_ipc_protocol.ipynb`, `notebooks/demo_030_daemon.ipynb`,
  `notebooks/demo_040_client_sdk.ipynb`, `notebooks/demo_050_store_keepassxc.ipynb`
- Docs: `doc/overview.md`, `doc/user_guide.md`, `doc/mvp_checklist.md`
- Guidelines: `AGENTS.md`, `CONTRIBUTING.md`, `README.md`

## Tests run (all passing)
- `uv run pytest -q`
- `uv run mypy src tests`
- `uv run ruff check src tests`

## Git status snapshot
- `git status -sb`:
  - `## feat/050-store-keepassxc`

## TODO next session
- Merge `feat/050-store-keepassxc` into `main`.
- Decide on release/versioning cadence.
