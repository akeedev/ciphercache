# ciphercache Daemon (030)

## Purpose
Define the daemon (`ciphercached`) process that serves the local IPC protocol over
Unix domain sockets, owns session state, and enforces access control layers 0–2.

This spec focuses on the runtime behavior and server loop, not store integration
or crypto internals.

## Scope (MVP)
- Single-user, macOS-first daemon process.
- Local Unix domain socket server using the `020` IPC protocol.
- In-memory session state (locked/unlocked, TTL, tickets, cached secrets).
- Lazy TTL expiry: on request, expired sessions are rejected and the daemon
  transitions to locked state and wipes cache/tickets.
- Minimal operational observability (status via IPC, safe logs).

## Non-Goals (MVP)
- External store integration details (KeePassXC mapping is defined later).
- Long-running background reaping or scheduler.
- Multi-user support.
- TCP listener or mTLS.
- Full policy engine beyond allow-all (hook only).

## Responsibilities
- Listen on a Unix domain socket and accept connections.
- Decode length-prefixed JSON frames and dispatch to the IPC handler.
- Enforce access control layers:
  - Layer 0: socket directory permissions.
  - Layer 1: peer UID/GID validation (OS-level).
  - Layer 2: ticket validation (handled in IPC logic).
- Manage daemon lifecycle: startup, graceful shutdown, lock on exit.
- Only `unlock` initiates store access and user interaction; `get_secret` never triggers unlock.
- `close_store` clears cached secrets while preserving tickets.
- Unlock requests include an explicit list of secret names to fetch and cache.

## Process Model
- Single process with a single socket listener.
- Concurrency: single-threaded, blocking accept loop.
- Handle one request per connection, then close.
- Clients should retry with brief backoff if the daemon is busy or unreachable.

## Socket and Paths
- Base data directory: `~/Library/Application Support/ciphercache`.
- Socket path: `${data_dir}/ciphercached.sock`.
- Socket directory must be `0700` (owner-only).
- Ticket directory is under `data_dir/tickets` (0600 ticket files).
- Ticket file names are derived from `client_name` after validation (ASCII alnum plus `._-`, start with alnum, max 64 chars; no path separators or `.` / `..`).
- Agent metadata (`agent.json`) is written to `data_dir/agent.json` (0600).
  It is intended for debugging and discovery.

## Lifecycle
1. **Startup**:
   - Ensure data directory exists (0700).
   - Ensure socket directory exists (0700).
   - Remove stale socket file if present.
   - Bind and listen on socket.
2. **Serve**:
   - Accept connection.
   - Validate peer credentials (UID/GID).
   - Read and decode frames; dispatch to handler.
   - Write response frame.
3. **Shutdown**:
   - On SIGINT/SIGTERM, lock the daemon and close socket.
   - Remove socket file.

## Request Handling
- Decode frames using `ipc.framing`.
- Dispatch using `ipc.handler.handle_request`.
- Respond with a single frame per request.
- Malformed frames result in `invalid_request` errors.
- TTL expiry is enforced lazily (on request).
- Requests larger than the maximum frame size are rejected.
- Connections that exceed read/write timeouts are closed.
- `get_secret` returns `locked` if the daemon is locked; it does not initiate unlock.
- `unlock` requests must include a non-empty list of secrets to cache; otherwise `invalid_request`.
- `close_store` clears cached secrets and resets store alias while preserving tickets.

## Access Control (MVP)
- **Layer 0:** socket path is in an owner-only directory.
- **Layer 1:** validate peer credentials (UID/GID match expected user).
- **Layer 2:** ticket validation in `get_secret` handler.

## Logging
- Log start/stop, socket bind failures, and protocol errors.
- Never log secrets or full payloads.
- Ticket values must not be logged.
- Log a brief summary per request (op + payload keys). When present, log client_name.
- Default log level for the daemon runner is INFO and should be configurable.
- If peer credential lookup fails, log the failure at DEBUG with the OS error.

## Optional Unlock on Startup
The daemon runner may support an option to unlock on startup, prompting for
KeePassXC credentials immediately. This can improve UX when prompts must be
entered in the daemon terminal.

Unlock-all mode:
- When enabled at startup, the daemon exports and caches all entries from the store.
- In this mode, clients with valid tickets may request any cached secret.
- The startup unlock may accept an optional TTL; default is infinity.

## Agent Metadata (`agent.json`)
Written at startup and removed on shutdown. Intended for debugging and discovery.

Schema (JSON):
```
{
  "version": "v0",
  "pid": 12345,
  "socket_path": "/Users/you/Library/Application Support/ciphercache/ciphercached.sock",
  "data_dir": "/Users/you/Library/Application Support/ciphercache",
  "started_at": "2026-02-01T12:00:00Z",
  "uid": 501,
  "gid": 20
}
```

Notes:
- No secrets or ticket values are written.
- `started_at` is UTC in RFC 3339 format.

## Configuration
Configuration is provided via a `DaemonConfig` structure:
- `data_dir: Path`
- `store_alias_default: str`
- `socket_path: Path` (defaults to `${data_dir}/ciphercached.sock`)
- `expected_uid: int` (derived from current user)
- `expected_gid: int` (optional)
- `max_frame_bytes: int` (default `1_000_000`)
- `read_timeout_seconds: float` (default `5.0`)
- `write_timeout_seconds: float` (default `5.0`)
- `write_agent_metadata: bool` (default `True`)
- `require_peer_credentials: bool` (default `False`)

## Modules and Classes (planned)
- `ciphercache.daemon.server`
  - `UnixSocketServer`: binds socket, accepts connections, dispatches requests.
- `ciphercache.daemon.state`
  - `DaemonState`: session state (existing).
- `ciphercache.ipc.handler`
  - `handle_request`: request validation/dispatch (existing).
- `ciphercache.ipc.framing`
  - `encode_message`, `decode_frames` (existing).

## Acceptance Criteria (MVP)
- Daemon binds a Unix socket at the configured path and accepts connections.
- Socket directory permissions are `0700`; socket file permissions are owner-only.
- Peer UID/GID validation rejects non-owner clients.
- If peer credentials are unavailable from the OS, the daemon logs a warning and
  skips UID/GID validation (still relying on socket permissions and tickets), unless
  `require_peer_credentials` is enabled.
- A valid `ping` request yields `{"ok": true}` response.
- Invalid frames yield `invalid_request`.
- Requests larger than the max frame size are rejected.
- When TTL has expired, any request (including `get_secret`) is rejected with `locked`,
  and the daemon transitions to locked state (secrets/tickets cleared).
- `status` reflects locked/unlocked and TTL remaining accurately.
- On SIGTERM/SIGINT, daemon locks and removes socket file.
- `agent.json` is written on startup (when enabled) and removed on shutdown.

## Decisions
1. **Socket path**: `~/Library/Application Support/ciphercache` with
   socket at `${data_dir}/ciphercached.sock`.
2. **Concurrency model**: blocking single-thread, one request per connection.
3. **Max frame size**: cap at `1_000_000` bytes.
4. **Timeouts**: read/write timeouts enabled; client retries with backoff.
5. **Agent metadata**: write `agent.json`, include debug info, but no secrets
6. **Lifecycle management**: no launchd plist in MVP (later).
