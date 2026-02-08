# ciphercache Architecture (010)

## Overview
`ciphercache` consists of a local daemon (`ciphercached`) and a Python client SDK. The daemon is the only component that reads from the external secret store and the only component that holds cached secret material. Clients fetch secrets on demand over local IPC and return them to the caller in a Secret envelope (see feature 070-secret-envelope).


The architecture is designed to:
- minimize developer friction (startup unlock; cache for TTL)
- reduce secret leakage risks
- remain simple and robust (OS primitives + minimal moving parts)
- allow later extension (e.g. mTLS listener, stronger client identity) without refactoring core logic


## Components
### 1) Daemon: `ciphercached`
Responsibilities:
- Integrate with the external store (KeePassXC initially) by opening a KeePassXC database at startup, reading secrets, and caching them in memory.
- Serve an IPC API to clients over a Unix domain socket.
- Enforce TTL by refusing requests and shutting down after TTL expiry.
- Validate access control layers (0–2 in MVP).
- Maintain an in-memory secret cache (plaintext in MVP).
- Provide status and operational introspection without exposing secret values.
- For now, any client may access any secret, this might be extended to stricter control in a later version.

Internal submodules (conceptual):
- `ipc_server`: accept connections, read/write messages, route requests
- `auth`: peer-credential validation + ticket validation
- `session`: TTL handling, session state machine
- `store`: abstraction and KeePassXC implementation
- `cache`: encrypted-in-memory cache, keyed by secret name

### 2) Client API SDK:
Responsibilities:
- Discover the daemon endpoint (standard socket path; optional `agent.json`).
- Load per-client session ticket (0600 ticket file)
- Provide simple API helpers (e.g., `get_secret(name) -> SecretEnvelope`).
- Avoid persistence of secrets on disk.

Scope:
- MVP provides a Python SDK only.

## Process Model and Lifecycle (macOS-first)
- `ciphercached` runs as a single instance in the logged-in user context.
- Upon start of daemon, the KeepassXC database is opened and secrets are read and cached for TTL.
- Single-instance is enforced by binding the Unix domain socket path and/or launchd constraints.


## IPC Transport
- Primary transport: Unix domain socket (local IPC).
- The IPC protocol must be:
  - simple to implement in Python
  - robust against framing issues
  - safe by default (no secrets in logs, no secrets in CLI args)

Protocol framing decision (MVP):
- The architecture permits either newline-delimited JSON or length-prefixed JSON.
- Final choice and schema are defined in `spec/020-ipc-protocol.md`.

## Discovery
- Primary discovery: a fixed socket path known to both daemon and clients.
- Secondary discovery: daemon writes `agent.json` (0600) with metadata (socket path, PID, version) to support debugging and future multi-profile scenarios. No secrets are stored in this file.

Exact paths and `agent.json` schema are defined in `spec/030-daemon.md`.

## Session Model
Two related concepts:
- **Daemon unlocked state**: whether the store has been opened and the cache is populated.
- **Client session ticket**: a per-client bearer token used to authorize requests while the daemon remains unlocked.

MVP semantics:
- While daemon is unlocked, clients can repeatedly connect (including after restarts) by presenting valid tickets, and request secrets.
- On TTL expiry, the daemon will refuse secret requests, clear the cache, and shut down.
- `shutdown` request transitions immediately and wipes cache, then exits.

TTL format and parsing are defined in `spec/020-ipc-protocol.md`.

Ticket generation:
- Tickets are created explicitly via the SDK `client_init(client_name)`
- Tickets are stored as 0600 files in a per-client location to restrict access to user running the daemon.
- `client_name` validation: ASCII alphanumeric plus `._-`, must start with alphanumeric, maximum 64 characters, no path separators or `.` / `..`.
- Rationale: Tickets might be the basis for differentiating access between clients, but for now this is out of scope.
- Ticket format and storage details are deferred to a future spec (TBD).

Default data directory (macOS):
- `~/Library/Application Support/ciphercache` (tickets, `agent.json`, socket metadata)


## Access Control Layers (MVP)
MVP implements layers 0–2:

### Layer 0: Socket filesystem permissions
- Place socket in a directory with strict owner permissions (e.g., 0700).
- This prevents other local users from connecting.

### Layer 1: OS peer credentials (best-effort on macOS)
- Attempt to validate peer UID/GID from the OS for each connection.
- On macOS, peer credential retrieval via `SO_PEERCRED` or `LOCAL_PEERCRED` is unreliable or unavailable.
- If peer credentials can be retrieved and do not match the expected user, reject the connection.
- If peer credentials are unavailable from the OS, log a debug message and continue (relying on Layer 0 socket permissions and Layer 2 ticket file permissions).
- The `require_peer_credentials` config flag (default `False`) makes credential validation mandatory; if enabled and credentials are unavailable, the daemon rejects the connection.

### Layer 2: Per-client session ticket
- Require a valid per-client ticket for request authorization.

Rationale:
- Enable “restart-friendly” dev flow by separating store unlock from client connection.

Layer 3 (Keychain-backed client credentials) is explicitly deferred to a future spec.

## Store Integration
- The store is external; `ciphercache` does not attempt to replace KeePassXC.
- `ciphercached` reads from the store during startup, then closes the store.
- The store integration must avoid leaking secrets via process arguments and logs.
- The KeePassXC database path is supplied to the daemon via command-line argument; details are specified in `spec/050-store-keepassxc.md`.
- MVP supports exactly one KeePassXC database per daemon instance.

The mapping from store entries to secret names and JSON payloads is specified in `spec/050-store-keepassxc.md`.

## Cache (In-Memory)
- `ciphercached` caches secrets read at startup to avoid repeated store access during a session.
- Assumption: secrets are small (passwords, API keys, tokens) and few in typical developer use, so cache size is expected to be modest.
- MVP stores cached secrets as plaintext dicts in daemon memory.

## Policy and Authorization Model (Hook for MVP)
- Architecture includes a `policy` abstraction:
  - input: `client_name`, `secret_name`
  - output: allow/deny
- MVP can start with permissive policy but should keep the interface to enable:
  - per-client allowlists
  - future “high value secret requires extra presence” rules

Policy definition is deferred to a future spec (TBD).

## Observability
- `status` request from client API provides:
  - daemon locked/unlocked state
  - TTL remaining
  - high-level session info (no secret values)
- Logging must:
  - never include secret values
  - avoid logging full request payloads when they may contain sensitive data


## Architectural Decisions Deferred (by design)
- Exact IPC schema and framing.
- Ticket encoding and rotation strategy.
- KeePassXC integration mechanics (CLI vs library) and mapping conventions.
- launchd plist details for daemon lifecycle.

## Invariants
- `ciphercache` must be secure by default (no secrets in logs).
- CLI never passes secrets via command-line arguments.
- Ticket files are created with 0600 permissions.
- Socket directory permissions prevent other local users from connecting.
- Only `ciphercached` reads from the secret store.
- Client restarts do not require a new store unlock while TTL is valid.
- On `shutdown`, cached secrets are wiped immediately.
- Tickets are valid only while the daemon is unlocked (MVP).
- MVP supports exactly one KeePassXC database per daemon instance.
