# Architecture

# ciphercache Overview (000)

## Purpose
`ciphercache` provides a local secret agent which enables client software to retrieve
secrets on demand from a local daemon, with minimal repeated user interaction during 
active development. It is especially tailored for use in software development
and automation workflows where source code and repositories must not contain secrets 
(API keys, passwords, tokens, etc.). The local daemon is designed to be lightweight 
and access a single secret store (KeePassXC) for obtaining secrets.

## Naming
- Project / repository: `ciphercache`
- Daemon: `ciphercached`
- CLI command: `ccache`

## Problem Statement
Common secret handling patterns (e.g., environment variables, dotfiles, ad-hoc encrypted 
blobs) are convenient but often leak via logs, crash dumps, shell history, child processes,
CI output, or accidental commits. `ciphercache` reduces these leak paths by centralizing
secret access in a local agent and keeping secrets out of repositories and out of 
long-lived process environments.

## Goals
- Keep plaintext secrets separated from client programs and out of Git repos and source code.
- Allow programs to retrieve secrets on demand while requiring little user interaction.
- Provide a local daemon (`ciphercached`) that can be unlocked once per session and then serve 
  secrets without reopening the secret store again by keeping them cached in memory.
- Support frequent client restarts (typical during development) without forcing repeated store unlocks.
- Use local IPC (Unix domain sockets) as the primary transport.
- Store secrets as structured key-value objects addressable by name (conceptually JSON; in Python this is a dict).
- Keep the design simple and robust by relying on OS primitives rather than custom crypto 
  protocols.
- Assume secrets are small (passwords, API keys, tokens) and low in count per developer, so cache
  size is modest in typical workflows.


## Non-Goals
- Not a general-purpose remote secret management server (MVP is local-only).
- Not an HSM replacement and not intended to withstand a fully compromised logged-in user session.
- Not a full PKI system; no bespoke key agreement protocols for IPC.
- Not a password manager UI; the secure store remains external (initially KeePassXC).


## Scope (MVP)
- macOS-first, single-user, local daemon.
- Access control layers 0–2:
  - Layer 0: Unix socket filesystem permissions
  - Layer 1: OS peer credentials (UID/GID validation)
  - Layer 2: per-client session tickets (opaque bearer tokens) stored as 0600 files
- One external secret store integration: KeePassXC (exact integration details specified separately).
  MVP supports a single active store, but the design allows adding multiple stores later.
- In-memory caching in the daemon, protected by encryption via an ephemeral session master key.
- CLI commands to unlock/lock/status and to initialize client tickets.


## Threat Model (MVP)
### In scope
- Prevent accidental leakage of secrets into:
  - repositories, code, config committed to VCS
  - logs and debug output
  - process environments propagated to child processes
  - common “oops” surfaces (shell history, command line args)
- Prevent access by other local users on the same machine.

### Out of scope
- A determined attacker with code execution as the same logged-in user while 
  the agent is unlocked can often access secrets indirectly. `ciphercache` 
  does not claim to fully prevent this scenario.
- In-memory encryption primarily reduces accidental exposure (e.g., crash dumps). It is not
  designed to defend against active, same-user code execution while unlocked.


## Conceptual Workflow
1. **Client software onboarding (one-time):**
   - Create a per-client-software ticket file (file mode 0600) via `ccache client init <client_name>`.
2. **Session start (once per dev session/day):**
   - Unlock the store via `ccache unlock --ttl <duration>`.
   - `ciphercached` reads secrets from the store and populates an in-memory cache.
3. **Normal operation (frequent):**
   - Clients connect via Unix domain socket, present ticket, and request secrets by name.
   - Clients may restart repeatedly without additional store unlocking, until TTL expires.
4. **Session end:**
   - TTL expiry or `ccache lock` ends the session. The daemon may invalidate tickets lazily
     (on the next request) and then wipe cached secrets.


## Extensions (Future)
- Optional TCP listener with mTLS (mutual TLS) for LAN scenarios.
- Optional Layer 3 client credentials (Keychain-backed keypairs, challenge-response).
- Policy engine for per-client secret allowlists.
- Multiple store support (selectable by alias).
- Alternative stores (age/GPG/SOPS-based file stores).
- MCP adapter layer that fetches secrets via the agent API.


## Spec Map
This repository uses `spec/NNN-*.md` documents.
- `spec/000-overview.md` (this file; high-level goals and constraints)
- `spec/010-architecture.md` (system architecture and component boundaries)
- `spec/020-ipc-protocol.md` (IPC framing, envelope, and request/response schema)
- `spec/030-daemon.md` (daemon process, Unix socket server loop, and lifecycle)
- `spec/040-client-sdk.md` (client SDK connection, ticket loading, request helpers)
- `spec/050-cli.md` (CLI commands built on the SDK)

Note: The feature specs listed above are not complete; they evolve as the project matures.
