# ciphercache Overview

## What it is
`ciphercache` is a local secret agent that unlocks a KeePassXC database at startup,
caches secrets in memory for a TTL, and serves secrets over local IPC.

## Why it exists
It reduces accidental secret leakage into source control, logs, CLI arguments, or
environment variables by centralizing access in a local daemon.

## Current scope (MVP)
- Local daemon with Unix domain sockets.
- Python client SDK.
- Startup unlock with a single KeePassXC prompt.
- CLI: currently out of scope, might be added later.
 
## Quickstart
1. Start the daemon:
   ```bash
   uv run python scripts/run_daemon.py --demo --db-path testdata/demopasswords.kdbx
   ```
2. In another terminal or a Python session:
   ```python
   from ciphercache import Client, ClientConfig

   client = Client(config=ClientConfig())
   secret = client.get_secret("service/api")
   print(secret)
   ```
   Note: secrets are wrapped in a SecretEnvelope to prevent accidental logging.

## Security model (brief)
- Protects against other local users via socket permissions and UID/GID checks.
- Does not protect against malicious code running under the same user.
