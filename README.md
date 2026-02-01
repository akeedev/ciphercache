# ciphercache

**ciphercache** is a locally running **secret agent daemon** that unlocks
requested secrets from a secure store (initially: a KeePassXC database) and then serves those secrets from an **in-memory cache** for the configured TTL. New secrets require a new unlock request.

Client software can be restarted frequently during development and still retrieve secrets as long as a **session ticket** and **TTL (Time To Live)** remain valid. The primary transport is **IPC (Inter-Process Communication)** via **Unix domain sockets**. 

Optionally, we might later add a **TCP listener with mTLS (mutual TLS, i.e., TLS with client certificate authentication)**.

## Example quickstart

```bash
uv run python main.py
```

## Example tests

```bash
uv run pytest
```

## Project layout

- `src/` application sources
- `tests/` pytest tests
- `spec/` feature specifications
- `data/` data files
- `testdata/` test data
- `doc/` documentation

## PyCharm run configurations

If you use PyCharm, you can add shared run configurations under `.idea/runConfigurations/`.


## License
This project is licensed under the Apache License 2.0. See `LICENSE`.

The software is provided "AS IS", without warranties, guarantees, or conditions of any kind. Use is at your own risk.

## Threat model (read first)

Protected:
- Accidental leakage of secrets into source control, logs, CLI args, and environment variables.
- Access by other local users on the same machine (via socket permissions and UID/GID checks).

Not protected (by design, MVP):
- A determined attacker with code execution as the same logged-in user while the daemon is unlocked.
- Malware or injected code running under your user account can connect to the socket if it can read a valid ticket.
- Network attacks (there is no remote listener in MVP).

Important: IPC uses clear-text local Unix domain sockets. Protection relies on OS filesystem
permissions, peer credential checks, and tickets. If you need same-user isolation, stronger
client authentication or encrypted IPC would be required.

## Development note

AI tools were used to assist development.
