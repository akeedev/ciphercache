# ciphercache User Guide

## Prerequisites
- Python 3.12+
- `uv` installed
- KeePassXC installed (CLI available)

## Quickstart (SDK)
```python
from ciphercache import Client, ClientConfig

client = Client(config=ClientConfig())
secret = client.get_secret("service/api")
print(secret["api_key"].reveal())
client.shutdown()
```
Note: KeePassXC prompts appear in the daemon terminal on startup. TTL expiry is
enforced on each request and locks the daemon, clearing cached secrets. Use `--ttl`
to configure the session TTL (default: infinity).
Secrets are wrapped in a `SecretEnvelope` that redacts their string/repr output.

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

## Running the daemon
Start the daemon in a terminal:
```bash
uv run python scripts/run_daemon.py --db-path testdata/demopasswords.kdbx
```
Use `--require-peer-credentials` to fail if the OS cannot provide UID/GID for the client.
Use `--ttl 1h` to set a session TTL (default: infinity).

### KeePassXC integration (startup unlock)
```bash
uv run python scripts/run_daemon.py \
  --db-path testdata/demopasswords.kdbx \
  --yubikey 1:12345678 \
  --keepassxc-cli-path /Applications/KeePassXC_2.7.6.app/Contents/MacOS/keepassxc-cli
```

KeePassXC will prompt in the daemon terminal during startup.

## Tickets
Tickets are per-client bearer tokens stored as `0600` files. Use the SDK:
```python
from ciphercache import Client, ClientConfig

client = Client(config=ClientConfig())
ticket_path = client.client_init("my_client")
client.config.ticket_path = ticket_path
client.load_ticket()
```
Note: `client_name` must be ASCII alnum plus `._-`, start with alnum, and be <= 64 characters.

## Troubleshooting
- If startup appears to hang, check the daemon terminal for KeePassXC prompts.
- If `keepassxc-cli` is not found, set `--keepassxc-cli-path` explicitly.
- If a secret is not found, ensure the entry exists in the KeePassXC database.
