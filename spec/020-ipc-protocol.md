# ciphercache IPC Protocol (020)

## Purpose
Define the local IPC protocol between clients and `ciphercached`.
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
- Socket path is stable and defined in `spec/030-daemon.md`.

## Framing
Length-prefixed JSON
- Each frame: 4-byte big-endian length prefix + UTF-8 JSON payload.
- Robust against embedded newlines and easier to stream safely.
- Slightly more code but explicit boundaries.

## Message Envelope (v0)
All messages are JSON objects with a stable envelope. The API surface in Python should
use dicts; dicts are serialized to JSON for IPC transport.

```
{
  "version": "v0",
  "id": "uuid",
  "type": "request|response|error",
  "op": "shutdown|status|client_init|get_secret|ping",
  "payload": { ... }
}
```

Notes:
- `id` correlates requests and responses. MVP uses millisecond timestamps; collisions
  are benign because the daemon processes one request per connection and does not
  deduplicate by ID. Stronger IDs (e.g., UUID) may be used in a future version.
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
Removed in current design. The daemon unlocks the store at startup only.

### `shutdown`
Request payload: empty object.
Notes:
- Wipes cached secrets and exits the daemon.

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
Notes:
- `client_name` validation is defined in `spec/010-architecture.md` (Ticket generation).
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
  "secret_name": "service/api"
}
```
Notes:
- MVP supports exactly one KeePassXC database per daemon instance.
- `get_secret` must not trigger store unlock; if the daemon is locked, it returns `locked`.
- TTL expiry is enforced on each request; expired sessions return `locked`, clear cache/tickets, and exit.
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
- `get_secret` with an unknown secret name returns `code: "not_found"`.
- Unknown `op` returns `code: "invalid_request"`.
- `shutdown` wipes cached secrets and exits the daemon.

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
    "secret_name": "service/api"
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
## TTL Semantics
- TTL is configured on the daemon command line at startup.
- TTL is a human-readable duration expressed in seconds, minutes, hours, days, or infinity.
- Examples: `5s`, `1h`, `3d`, `1h 30m`, `infinity`.
- TTL expiry is checked on-demand: when a request arrives after expiry, the daemon rejects the
  request, clears cache/tickets, and exits.
