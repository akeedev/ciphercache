# ciphercache AI Agent Notes

This document is a brief, agent-oriented summary of how to use `ciphercache` safely.
It focuses on the running daemon (`ciphercached`) and the Python client SDK.

## Roles (short)
- **Daemon (`ciphercached`)**: the only process that reads from the secret store.
  It unlocks the store at startup and caches secrets in memory for a TTL.
- **Client SDK**: connects over a local Unix socket, presents a ticket, and
  fetches secrets by name.

## What agents should and should not do
- Do **not** print or log secret values.
- Do **not** store secrets on disk or in long-lived environment variables.
- Do **not** pass secret values via CLI arguments.
- Do use the SDK to fetch secrets only when needed and keep them in memory.
- Do use `SecretEnvelope` helpers (`reveal`, `use`) when a raw value is required.

## Prerequisites
- `ciphercached` must be running locally for the current user.
- A per-client ticket file must exist (0600 permissions).

## Client discovery
- Primary: fixed Unix socket path used by the daemon and client.
- Secondary (optional): `agent.json` at
  `~/Library/Application Support/ciphercache/agent.json` (0600), which can
  override the socket path.

The SDK handles discovery automatically when `CipherClientConfig` is default.

## Ticket lifecycle
- Create a ticket once per client app:
  - `client_init(client_name)` returns a ticket path and writes a 0600 file.
- `client_name` must be ASCII alnum plus `._-`, start with alnum, max 64 chars.
- Tickets are valid only while the daemon is unlocked (MVP semantics).

## Minimal SDK usage
```python
from ciphercache import CipherClient, CipherClientConfig

client = CipherClient(config=CipherClientConfig())

# One-time ticket creation (do this once per client app):
# ticket_path = client.client_init("my_app")
# client.config.ticket_path = ticket_path
# client.load_ticket()

secret = client.get_secret("service/api")
api_key = secret["api_key"].reveal()

client.shutdown()  # clears cached secrets and exits the daemon
```

## Daemon start (if needed)
Start the daemon in a terminal:
```bash
uv run python scripts/run_daemon.py --db-path testdata/demopasswords.kdbx
```
If the store requires a password or YubiKey, the prompt appears in the daemon
terminal, not in the client process.

## Security model (MVP)
- Protects against other local users via socket permissions, peer UID/GID checks,
  and ticket validation.
- Does **not** protect against malicious code running as the same user while the
  daemon is unlocked.

## Failure modes (common)
- Startup appears to hang: check the daemon terminal for KeePassXC prompts.
- `get_secret` fails: ensure the entry exists in the database and the TTL has not expired.
