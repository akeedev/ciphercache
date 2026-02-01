# ciphercache

**ciphercache** is a locally running **secret agent daemon** that unlocks
requested secrets from a secure store (initially: a KeePassXC database) and then serves those secrets from an **in-memory cache** for the configured TTL. New secrets require a new unlock request.

Client software can be restarted frequently during development and still retrieve secrets as long as a **session ticket** and **TTL (Time To Live)** remain valid. The primary transport is **IPC (Inter-Process Communication)** via **Unix domain sockets**. 

Optionally, we might later add a **TCP listener with mTLS (mutual TLS, i.e., TLS with client certificate authentication)**.

## Example quickstart

```bash
uv run python scripts/run_daemon.py --demo
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

# Unlock the daemon and cache the required secrets.
# Requires the daemon to run in demo mode or with KeePassXC configuration.
client.unlock("1h", ["service/api"])

# Fetch a cached secret.
secret = client.get_secret("service/api")
print(secret["api_key"])
```

## KeePassXC integration (daemon)

Start the daemon with KeePassXC CLI config:

```bash
uv run python scripts/run_daemon.py \
  --db-path testdata/demopasswords.kdbx \
  --yubikey 1:23753626 \
  --keepassxc-cli-path /Applications/KeePassXC_2.7.6.app/Contents/MacOS/keepassxc-cli
```

Unlock-all on startup (caches all entries at start):

```bash
uv run python scripts/run_daemon.py \
  --unlock-all-on-start \
  --unlock-ttl 1h \
  --db-path testdata/demopasswords.kdbx \
  --yubikey 1:23753626 \
  --keepassxc-cli-path /Applications/KeePassXC_2.7.6.app/Contents/MacOS/keepassxc-cli
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

## Documentation

- `doc/overview.md`
- `doc/user_guide.md`
- `doc/mvp_checklist.md`

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
