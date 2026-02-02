# SESSION.md

## Session date
- 2026-02-02

## Current status
- Working branch: `main` (local ahead of origin by 2 commits)
- IPC protocol + daemon + SDK implemented and tested.
- KeePassXC integration (export XML parsing) implemented and wired to daemon unlock.
- YubiKey autodetect via `ykman list` added (spec 060).
- Client ticket auto-init + retry on invalid tickets.
- Client name validation and safe ticket file names enforced.
- Unlock timeout extended (client-side) for password/YubiKey prompts.
- Peer UID/GID validation is best-effort with optional strict flag.
- Demo notebooks updated for direct CLI export vs daemon unlock flows.
- Documentation under `doc/` updated including user guide and MVP checklist.
- Consistency and readiness pass completed with added tests and doc updates.

## Key decisions (specs)
- IPC framing: length-prefixed JSON.
- Message envelope v0 with request/response/error.
- Tickets are per client; soft identity only.
- Unlock requires explicit secret list; `get_secret` never triggers unlock.
- Unlock-all on daemon startup is optional (caches all entries).
- KeePassXC integration via `keepassxc-cli export` (XML in memory).
- TTL format supports `s|m|h|d`, combined tokens, and `infinity`.
- Client does not select database paths (daemon config fixed at startup).
- `close_store` clears cached secrets while preserving tickets.
- Peer credential validation is best-effort; strict enforcement is opt-in.

## Files changed (high level)
- Specs: `spec/000-overview.md`, `spec/010-architecture.md`, `spec/020-ipc-protocol.md`,
  `spec/030-daemon.md`, `spec/040-client-sdk.md`, `spec/050-store-keepassxc.md`,
  `spec/060-yubikey-autodetect.md`
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
  - `## main...origin/main [ahead 2]`

## TODO next session
- Decide on release/versioning cadence if needed.
