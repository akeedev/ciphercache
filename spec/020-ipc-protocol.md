# ciphercache IPC Protocol (020)

## Purpose
Define the local IPC protocol between clients, `ccache`, and `ciphercached`.
This spec focuses on message framing, envelope shape, and a minimal request/response
schema. It does not define the full secret store mapping or crypto choices.

## Scope (MVP)
- Local Unix domain socket only.
- Single user context (UID/GID checks are handled separately).
- Python SDK is the only supported client SDK for MVP.

## Versioning
- Protocol version: `v0` (MVP).
- Version is included in every request and response envelope.
- Compatibility rule: `ciphercached` may reject unknown versions with a clear error.

## Transport
- Unix domain socket.
- Socket path is stable and defined in a later spec.

## Framing
Length-prefixed JSON
- Each frame: 4-byte big-endian length prefix + UTF-8 JSON payload.
- Robust against embedded newlines and easier to stream safely.
- Slightly more code but explicit boundaries.

## Message Envelope (v0)
All messages are JSON objects with a stable envelope. The API surface in Python should
use dicts; dicts are serialized to JSON for IPC transport and to a byte stream for in-memory
encryption.

```
{
  "version": "v0",
  "id": "uuid",
  "type": "request|response|error",
  "op": "unlock|lock|status|client_init|get_secret|ping",
  "payload": { ... }
}
```

Notes:
- `id` correlates requests and responses.
- `type` is explicit even for errors.
- `payload` is op-specific.

## Operations (v0)
### `ping`
Request:
```
{ "version": "v0", "id": "...", "type": "request", "op": "ping", "payload": {} }
```
Response:
```
{ "version": "v0", "id": "...", "type": "response", "op": "ping", "payload": {"ok": true} }
```

### `unlock`
Request payload:
```
{
  "ttl": "5s | 1h | 3d | 1h 30m | infinity",
  "secrets": ["service/api", "service/db"]
}
```
Notes:
- Store selection is out-of-band to IPC (CLI/daemon configuration) and uses a store alias.
- TTL expiry is enforced lazily: after expiry, the next request must be rejected (typically
  with `locked`), and the daemon may transition to locked state at that time.
- `secrets` is the explicit allowlist to fetch and cache during unlock. If omitted,
  the daemon may use a default policy (MVP: reject or treat as empty).

### `lock`
Request payload: empty object.

### `status`
Response payload:
```
{
  "locked": true|false,
  "ttl_remaining_seconds": 0
}
```

### `client_init`
Request payload:
```
{
  "client_name": "my_client"
}
```
Response payload:
```
{
  "ticket_path": "/path/to/ticket"
}
```

### `get_secret`
Request payload:
```
{
  "ticket": "opaque-token",
  "secret_name": "service/api",
  "store": "default"
}
```
Notes:
- `store` is a store alias (not a filesystem path).
- If omitted, the daemon uses the single active store (MVP default).
- Rationale: aliases keep the IPC and SDK stable while enabling multiple stores later without
  exposing filesystem paths to clients.
- `get_secret` must not trigger store unlock; if the daemon is locked, it returns `locked`.
Response payload:
```
{
  "secret": { "key": "value" }
}
```

## Errors (v0)
Errors are responses with `type: "error"`:
```
{
  "version": "v0",
  "id": "...",
  "type": "error",
  "op": "get_secret",
  "payload": {
    "code": "unauthorized|locked|not_found|invalid_request|internal_error",
    "message": "short human-readable summary"
  }
}
```

## Logging and Safety
- Never log full payloads.
- Avoid logging secret values or ticket contents.

## Acceptance Criteria (MVP)
- Daemon accepts a length-prefixed JSON frame and responds with a well-formed envelope matching the request `id`.
- Invalid JSON or missing required fields returns `type: "error"` with `code: "invalid_request"`.
- `ping` returns `{"ok": true}`.
- `status` returns `locked` (boolean) and `ttl_remaining_seconds` (integer).
- `get_secret` with an invalid ticket returns `code: "unauthorized"`.
- `get_secret` with an unknown store alias returns `code: "not_found"`.
- Unknown `op` returns `code: "invalid_request"`.

## Example Exchange (v0)
Request (`get_secret`):
```
{
  "version": "v0",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "request",
  "op": "get_secret",
  "payload": {
    "ticket": "opaque-token",
    "secret_name": "service/api",
    "store": "default"
  }
}
```

Response (`get_secret`):
```
{
  "version": "v0",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "response",
  "op": "get_secret",
  "payload": {
    "secret": { "api_key": "redacted" }
  }
}
```

Request (`status`):
```
{
  "version": "v0",
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "request",
  "op": "status",
  "payload": {}
}
```

Response (`status`):
```
{
  "version": "v0",
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "response",
  "op": "status",
  "payload": {
    "locked": false,
    "ttl_remaining_seconds": 1800
  }
}
```
