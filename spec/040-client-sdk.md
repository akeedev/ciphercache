# ciphercache Client SDK (040)

## Purpose
Define the Python client SDK that connects to `ciphercached` over the local Unix
domain socket and provides a simple, safe API for client applications.

This SDK is the only supported client SDK in MVP.

## Scope (MVP)
- Python SDK only.
- Local Unix domain socket transport using the IPC protocol defined in `spec/020-ipc-protocol.md`.
- Client discovery via fixed socket path and optional `agent.json`.
- Ticket loading from a 0600 ticket file.
- Convenience helpers for `ping`, `status`, `get_secret`, and `client_init`.
- The SDK also exposes `unlock`/`lock` to keep the CLI thin.
- Minimal retry strategy for transient connection errors.

## Non-Goals (MVP)
- Remote transports (TCP/mTLS).
- Advanced policy management.
- Ticket rotation or renewal.
- Encrypted IPC channel.
- CLI UX decisions (CLI should remain a thin wrapper over the SDK).

## Responsibilities
- Discover the daemon endpoint.
- Load the client ticket from disk (0600).
- Build and send IPC requests (length-prefixed JSON).
- Parse and return IPC responses.
- Surface errors with clear exceptions.
- Keep `unlock` explicit to avoid unexpected KeePassXC prompts.

## Ticket Loading
Ticket loading is required before `get_secret` requests. The SDK reads the ticket
from the ticket file (0600) and includes the token in request payloads.

Notes:
- The daemon reads secrets immediately at unlock (KeePassXC prompt happens then).
- The client still must present a valid ticket on each request.

## Rationale: Explicit Unlock
Unlocking can trigger user interaction (password and hardware key prompt) via
KeePassXC. To avoid surprising prompts during ordinary requests, the SDK keeps
unlock explicit and separate from `get_secret`. Clients should call `unlock`
with an explicit list of secrets to cache, then use `get_secret` for fast
retrieval. If a new secret is needed, a new `unlock` is required.

## Discovery
Primary: fixed socket path at:
`~/Library/Application Support/ciphercache/ciphercached.sock`

Secondary (optional): `agent.json` (0600) at:
`~/Library/Application Support/ciphercache/agent.json`

If `agent.json` exists and is readable, the SDK should use its socket path.

## Request Flow
1. Build request envelope (`version`, `id`, `type`, `op`, `payload`).
2. Encode with length-prefixed JSON.
3. Connect to Unix socket.
4. Send request.
5. Read response frame.
6. Decode and validate response.
7. Map errors to exceptions.

## Errors and Exceptions
- `invalid_request` → `ValueError`
- `unauthorized` → `PermissionError`
- `locked` → `RuntimeError`
- `not_found` → `LookupError`
- `internal_error` → `RuntimeError`

## Retry Strategy
- For connection failures (`FileNotFoundError`, `ConnectionRefusedError`,
  `ConnectionResetError`, `BrokenPipeError`), retry a small number of times
  with short backoff (e.g., 3 attempts, 50–200ms).
- Do not retry if a response is received with an error code.

## Classes and Functions (planned)
- `ciphercache.client.ClientConfig`
  - `data_dir: Path` (defaults to `~/Library/Application Support/ciphercache`)
  - `socket_path: Path | None`
  - `ticket_path: Path | None`
  - `store_alias: str | None`
  - `max_frame_bytes: int` (default `1_000_000`)
  - `read_timeout_seconds: float` (default `5.0`)
  - `write_timeout_seconds: float` (default `5.0`)
  - `retries: int` (default `3`)
  - `retry_backoff_seconds: float` (default `0.1`)
- `ciphercache.client.Status`
  - `locked: bool`
  - `ttl_remaining_seconds: int`
- `ciphercache.client.Client`
  - `ping() -> bool`
  - `status() -> Status`
  - `unlock(ttl: str, secrets: list[str]) -> bool` (secrets must be non-empty)
  - `lock() -> bool`
  - `get_secret(name: str) -> dict[str, object]`
  - `client_init(client_name: str) -> Path`
  - `load_ticket() -> str`
  - `request(op: str, payload: dict[str, object]) -> dict[str, object]`

## Lifecycle Overview
- Instantiate `ClientConfig`.
- Instantiate `Client`.
- Load ticket at initialization (or explicitly via `load_ticket`) before requests.
- Each request uses a new socket connection (one request per connection).
- Responses are decoded, typed, and returned or raised as exceptions.
- `unlock` is called explicitly before `get_secret` to avoid unexpected store prompts.
- `unlock` specifies a non-empty list of secret names to fetch and cache; new secrets require a new unlock.

## Acceptance Criteria (MVP)
- SDK can connect to the daemon socket and perform `ping`.
- SDK can read `agent.json` and override socket path when present.
- SDK can load a ticket file and use it in `get_secret`.
- `get_secret` returns secret dict on success.
- `status()` returns a typed `Status`.
- `unlock` and `lock` are exposed in the SDK and used by the CLI as a thin wrapper.
- Errors from the daemon are mapped to the correct Python exception types.
- Connection failures are retried with a small backoff.
- `unlock` accepts a list of secret names to fetch and cache.

## Decisions
1. Ticket loading: eager by default (load during `Client` init) with explicit `load_ticket()`.
2. `client_init` lives in the SDK so the CLI can stay thin.
3. `status()` returns a typed dataclass (`Status`).
4. Expose low-level `request(op, payload)` for advanced usage.
5. Client identity remains a soft boundary (ticket-based).
