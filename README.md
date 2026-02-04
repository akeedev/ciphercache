# ciphercache

**ciphercache** is a locally running **secret agent daemon** that unlocks a secure
store (initially: a KeePassXC database) at startup and then serves secrets from an
**in-memory cache** for the configured TTL.

Client software can be restarted frequently during development and still retrieve secrets as long as a **session ticket** and **TTL (Time To Live)** remain valid. TTL expiry is enforced on each request; expired sessions lock the daemon and clear cached secrets. The primary transport is **IPC (Inter-Process Communication)** via **Unix domain sockets**. 

The objective for creating this software was to protect secrets from accidental exposure in source control which is especially important when 
working with AI agents. A secondary objective was to explore a spec-driven
development approach with AI (OpenAI codex was used in Jetbrains Pycharm)

Optionally, we might later add a **TCP listener with mTLS (mutual TLS, i.e., TLS with client certificate authentication)**.

## Example quickstart

```bash
uv run python scripts/run_daemon.py --demo --db-path testdata/demopasswords.kdbx
```

## Getting started

See the full user guide in `doc/user_guide.md`.

## Installing

Editable install for development:

```bash
pip install -e .
```

Or using uv:

```bash
uv pip install -e .
```

Install from a built wheel:

```bash
uv build
pip install dist/ciphercache-*.whl
```

## SDK usage

```python
from ciphercache import Client, ClientConfig

config = ClientConfig()
client = Client(config=config)

# Fetch a cached secret (daemon unlocks on startup).
secret = client.get_secret("service/api")
print(secret)
print(secret["api_key"].reveal())

# Shutdown the daemon (clears cached secrets and exits).
client.shutdown()
```

## KeePassXC integration (daemon)

Start the daemon with KeePassXC CLI config:

```bash
uv run python scripts/run_daemon.py \
  --db-path testdata/demopasswords.kdbx \
  --yubikey 1:12345678 \
  --keepassxc-cli-path /Applications/KeePassXC_2.7.6.app/Contents/MacOS/keepassxc-cli
```
Use `--ttl 1h` to set a session TTL, or omit it for infinity. Use
`--require-peer-credentials` to fail if the OS cannot provide UID/GID for the client.

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

## Documentation

- `doc/overview.md`
- `doc/user_guide.md`
- `doc/mvp_checklist.md`
- `DELIVERABLES.md` (project build artifacts and regeneration rules)

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
