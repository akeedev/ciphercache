# ciphercache User Guide

## Prerequisites
- Python 3.12+
- `uv` installed
- KeePassXC installed (CLI available)

## Quickstart (SDK)
```python
from ciphercache import Client, ClientConfig

client = Client(config=ClientConfig())
client.unlock("1h", ["service/api"])
secret = client.get_secret("service/api")
print(secret["api_key"])
client.close_store()
```
Note: unlock may take time due to password/YubiKey prompts; adjust
`unlock_timeout_seconds` if needed. TTL expiry is enforced on each request and
locks the daemon, clearing cached secrets.

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
uv run python scripts/run_daemon.py
```

### KeePassXC integration (unlock on request)
```bash
uv run python scripts/run_daemon.py \
  --db-path testdata/demopasswords.kdbx \
  --yubikey 1:12345678 \
  --keepassxc-cli-path /Applications/KeePassXC_2.7.6.app/Contents/MacOS/keepassxc-cli
```

When you call `unlock`, KeePassXC will prompt in the daemon terminal.

### Unlock-all on startup
```bash
uv run python scripts/run_daemon.py \
  --unlock-all-on-start \
  --unlock-ttl 1h \
  --db-path testdata/demopasswords.kdbx \
  --yubikey 1:12345678 \
  --keepassxc-cli-path /Applications/KeePassXC_2.7.6.app/Contents/MacOS/keepassxc-cli
```

In this mode, the daemon caches all entries at startup. Any client with a valid
ticket can request any cached secret.

## Tickets
Tickets are per-client bearer tokens stored as `0600` files. Use the SDK:
```python
from ciphercache import Client, ClientConfig

client = Client(config=ClientConfig())
ticket_path = client.client_init("my_client")
client.config.ticket_path = ticket_path
client.load_ticket()
```

## Troubleshooting
- If `unlock` appears to hang, check the daemon terminal for KeePassXC prompts.
- If `keepassxc-cli` is not found, set `--keepassxc-cli-path` explicitly.
- If a secret is not found, ensure it was included in the `unlock` secret list.
