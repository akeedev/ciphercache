# ciphercache Architecture (010)

## Overview
`ciphercache` consists of a local daemon (`ciphercached`), a CLI command (`ccache`), and a Python client SDK. The daemon is the only component that reads from the external secret store and the only component that holds cached secret material. Clients fetch secrets on demand over local IPC.

The architecture is designed to:
- minimize developer friction (unlock once per session)
- reduce secret leakage surfaces
- remain simple and robust (OS primitives + minimal moving parts)
- allow later extension (mTLS listener, stronger client identity) without refactoring core logic


## Components
### 1) Daemon: `ciphercached`
Responsibilities:
- Serve an IPC API over a Unix domain socket.
- Manage sessions and TTL.
- Validate access control layers (0–2 in MVP).
- Integrate with the external store (KeePassXC initially).
- Maintain an in-memory secret cache encrypted with an ephemeral session master key.
- Provide status and operational introspection without exposing secret values.

Internal submodules (conceptual):
- `ipc_server`: accept connections, read/write messages, route requests
- `auth`: peer-credential validation + ticket validation
- `session`: TTL handling, session state machine
- `store`: abstraction and KeePassXC implementation
- `cache`: encrypted-in-memory cache, keyed by secret name
- `policy`: optional allowlist mapping (client -> secret names), MVP may start with “allow all” but the interface should exist


### 2) CLI: `ccache`
Responsibilities:
- Control daemon functionality via the same IPC API used by clients:
  - unlock, lock, status
  - initialize client ticket files
- Provide a stable UX surface for operators/developers.
- Avoid printing secret values by default (debug-only commands may exist and should be gated).

### 3) Client SDK
Responsibilities:
- Discover the daemon endpoint (standard socket path; optional `agent.json`).
- Load per-client session ticket (0600 ticket file).
- Provide simple API helpers (e.g., `get_secret(name) -> dict`).
- Avoid persistence of secrets on disk.

Scope:
- MVP provides a Python SDK only.

## Process Model and Lifecycle (macOS-first)
- `ciphercached` runs as a single instance in the logged-in user context.
- Recommended deployment: `launchd` user agent for stability and auto-restart.
- Single-instance is enforced by binding the Unix domain socket path and/or launchd constraints.

(Implementation details for launchd are specified later; this document defines the intention.)

## IPC Transport
- Primary transport: Unix domain socket (local IPC).
- Socket location: stable, documented path under user-controlled directories.
- The IPC protocol must be:
  - simple to implement in Python
  - robust against framing issues
  - safe by default (no secrets in logs, no secrets in CLI args)

Protocol framing decision (MVP):
- The architecture permits either newline-delimited JSON or length-prefixed JSON.
- Final choice and schema are defined in `spec/020-ipc-protocol.md`.

## Discovery
- Primary discovery: a fixed socket path known to both daemon and clients.
- Secondary discovery: daemon writes `agent.json` (0600) with metadata (socket path, PID, version)
  to support debugging and future multi-profile scenarios. No secrets are stored in this file.

Exact paths are defined in a follow-up spec to keep this doc stable.

## Session Model
Two related concepts:
- **Daemon unlocked state**: whether the store has been unlocked and the cache is populated.
- **Client session ticket**: a per-client bearer token used to authorize requests while the daemon remains unlocked.

MVP semantics:
- Unlocking via `ccache unlock --ttl <duration> --secrets <names>` sets the daemon to an unlocked
  state for the TTL duration and populates the cache with the requested secrets only.
- During unlocked state, clients can repeatedly connect (including after restarts), present valid tickets, and request secrets.
- On TTL expiry, the session ends and requests must be rejected. The daemon may
  transition to locked state lazily (on the next request) and then wipe cache.
  `lock` transitions immediately and wipes cache.

TTL format:
- TTL is a human-readable duration expressed in seconds, minutes, hours, days, or infinity.
- Examples: `5s` (5 seconds), `1h` (1 hour), `3d` (3 days), `infinity` (no expiry).
- Combined durations are allowed (e.g., `1h 30m`).
- Internal representation is an implementation detail, but behavior must be accurate to the specified duration.

Ticket lifetime:
- For MVP simplicity, tickets are valid only while the daemon is in an unlocked state (or equivalently, ticket TTL is bounded by unlock TTL).
- A separate ticket TTL is an allowed extension but not required for MVP.

Ticket generation:
- Tickets are created explicitly via `ccache client init <client_name>`.
- Tickets are stored as 0600 files in a per-client location.

Ticket format and storage details belong in `spec/030-session-tickets.md`.

Default data directory (macOS):
- `~/Library/Application Support/ciphercache` (tickets, `agent.json`, socket metadata)

## Access Control Layers (MVP)
MVP implements layers 0–2:

### Layer 0: Socket filesystem permissions
- Place socket in a directory with strict owner permissions (e.g., 0700).
- This prevents other local users from connecting.

### Layer 1: OS peer credentials
- Validate peer UID/GID from the OS for each connection.
- Reject peers not matching the expected local user.

### Layer 2: Per-client session ticket
- Require a valid per-client ticket for request authorization.

Rationale:
- Avoid custom crypto protocols for IPC.
- Enable “restart-friendly” dev flow by separating store unlock from client connection.

Layer 3 (Keychain-backed client credentials) is explicitly deferred to a future spec.

## Store Integration
- The store is external; `ciphercache` does not attempt to replace KeePassXC.
- `ciphercached` reads from the store only during `unlock`, then closes the store.
- The store integration must avoid leaking secrets via process arguments and logs.
- The KeePassXC database path is supplied to the daemon via command-line argument; details are
  specified in `spec/040-store-keepassxc.md`.
- Store identity is represented by a stable alias (not a filesystem path). The CLI maps aliases
  to store paths and passes the active store to the daemon. IPC requests may reference a store
  alias; in MVP a single active store is supported and acts as the default.
- Rationale: aliases keep IPC and client code stable while allowing multiple stores later without
  exposing filesystem paths to clients.

The mapping from store entries to secret names and JSON payloads is specified in `spec/040-store-keepassxc.md`.

## Cache and Crypto (In-Memory)
- `ciphercached` caches only the secrets requested at `unlock` to avoid repeated store access during a session.
- Cache is protected with a per-unlock ephemeral **Session Master Key**.
- Cache entries are stored as ciphertext blobs; decrypted only briefly per request.
- Assumption: secrets are small (passwords, API keys, tokens) and few in typical developer use,
  so cache size is expected to be modest.

Warning: In-memory encryption primarily reduces accidental exposure (e.g., crash dumps).
It is not designed to defend against active, same-user code execution while unlocked.

Cryptographic primitives (AEAD choice, key derivation, wipe strategy) are specified in `spec/050-cache-and-crypto.md`.

## Policy and Authorization Model (Hook for MVP)
- Architecture includes a `policy` abstraction:
  - input: `client_name`, `secret_name`
  - output: allow/deny
- MVP can start with permissive policy but should keep the interface to enable:
  - per-client allowlists
  - future “high value secret requires extra presence” rules

Policy definition is specified in `spec/070-policy.md`.

## Observability
- `ccache status` provides:
  - daemon locked/unlocked state
  - TTL remaining
  - high-level session info (no secret values)
- Logging must:
  - never include secret values
  - avoid logging full request payloads when they may contain sensitive data

## Extension Boundary: Optional mTLS Listener
The architecture anticipates a future TCP listener secured by mTLS:
- Add a separate listener module that authenticates clients by client certificates.
- Reuse the same internal service interfaces:
  - session management
  - policy enforcement
  - store and cache logic
- Keep IPC as the default local path.

mTLS details are specified in a future spec (placeholder).

## Architectural Decisions Deferred (by design)
- Exact IPC schema and framing.
- Ticket encoding and rotation strategy.
- Exact filesystem paths and discovery file schema.
- KeePassXC integration mechanics (CLI vs library) and mapping conventions.
- AEAD primitive choice and memory wipe strategy.
- launchd plist details for daemon lifecycle.

## Invariants
- `ciphercache` must be secure by default (no secrets in logs).
- CLI never passes secrets via command-line arguments.
- Ticket files are created with 0600 permissions.
- Socket directory permissions prevent other local users from connecting.
- Only `ciphercached` reads from the secret store.
- Client restarts do not require a new store unlock while TTL is valid.
- On `lock`, cached secrets are wiped immediately. After TTL expiry, cached
  secrets must become inaccessible and may be wiped lazily on the next request.
- Tickets are valid only while the daemon is unlocked (MVP).
- MVP supports a single active store; store aliases enable future multi-store support.
