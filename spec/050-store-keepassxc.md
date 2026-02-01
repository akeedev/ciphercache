# ciphercache KeePassXC Store Integration (050)

## Purpose
Define how `ciphercached` fetches secrets from a local KeePassXC database using
`keepassxc-cli`, with a single unlock prompt and in-memory parsing.

## Scope (MVP)
- Use `keepassxc-cli export --format xml` to read the database once per unlock.
- Capture export output in memory (stdout), never write plaintext to disk.
- Parse XML in memory, then cache only the requested secrets.
- Support YubiKey challenge-response unlocking.
- Support `--no-password` when configured (YubiKey-only mode).

## Non-Goals (MVP)
- Direct integration with KeePassXC GUI or IPC/DBus.
- Incremental refresh or live sync.
- Encrypted IPC between client and daemon.

## Rationale
`keepassxc-cli show` requires a prompt per entry. `export` allows a single unlock
followed by an in-memory parse of all entries. We then filter to only the requested
secrets, minimizing exposure and latency after unlock.

## Unlock Flow (MVP)
1. Client requests `unlock` with a non-empty list of secret names.
2. Daemon executes:
   ```
   keepassxc-cli export --format xml [--key-file <path>] [--yubikey <slot[:serial]>] [--no-password] <db_path>
   ```
3. Daemon captures stdout (XML) in memory, parses entries, and extracts only the requested secrets.
4. Daemon closes the process, wipes in-memory XML, and caches the requested secrets only.

Unlock-all mode (daemon startup):
- When enabled at startup, the daemon exports the database once and caches all entries.
- `get_secret` may return any cached entry without a per-secret allowlist.

Parsing note:
- The CLI may emit localized prompts before the XML. The parser must locate the first `<?xml`
  and ignore any preceding text to keep parsing language-independent.
- KeePassXC prompts (password / YubiKey) are emitted on stderr; the daemon should
  allow them to surface in its terminal.

## Security Requirements
- No plaintext export is written to disk.
- No secrets are logged.
- `keepassxc-cli` is executed without leaking secrets via arguments or logs.
- Secrets are cached only for the current TTL and only for requested names.

## Configuration
Store configuration is provided via `DaemonConfig` or a dedicated store config:
- `database_path: Path`
- `key_file_path: Path | None`
- `yubikey_slot: str | None` (e.g., `"1"` or `"1:23753626"`)
- `no_password: bool` (default `False`)
- `keepassxc_cli_path: Path | None`
- `keepassxc_cli_search_roots: list[Path]` (default `[Path("/Applications")]`)

CLI discovery (MVP):
- If `keepassxc_cli_path` is set, use it.
- Otherwise, search `PATH` for `keepassxc-cli`.
- If not found in `PATH`, search for `KeePassXC*.app/Contents/MacOS/keepassxc-cli` under `/Applications`,
  preferring the highest version if multiple are found.

## Mapping: KeePassXC Entry → Secret Name
MVP mapping:
- Use the entry title as `secret_name` and ignore group path.
- Assumption: entry titles are unique within the database.

## Expected Data Shape
Each cached secret is stored as a dict with a minimal stable schema:
```
{
  "title": "...",
  "username": "...",
  "password": "...",
  "url": "...",
  "tags": ["..."]
}
```
Fields may be omitted if missing in the entry.

Notes on XML fields:
- Entry data appears under `<Entry>` with `<String><Key>...</Key><Value>...</Value></String>`.
- Tags appear in `<Tags>` as a single string; split on whitespace and commas.

## Modules and Classes (planned)
- `ciphercache.store.keepassxc`
  - `KeePassXCConfig`: paths and unlock parameters for `keepassxc-cli`.
  - `KeePassXCClient`: executes CLI export and returns parsed entries.
  - `KeePassXCParser`: parses XML and extracts requested entries by title.
  - `load_secrets(config, names) -> dict[str, dict[str, object]]`: main entrypoint used by daemon unlock.
  - `load_all_secrets(config) -> dict[str, dict[str, object]]`: used for unlock-all startup mode.

## Error Handling
- Invalid DB path or CLI failure → `internal_error` or `invalid_request` (with safe message).
- Unlock failure (wrong key/YubiKey) → `invalid_request` (do not expose details).
- Requested secret not found → `not_found` for that secret (daemon caches none).

## Acceptance Criteria (MVP)
- Unlock with a list of secrets triggers a single KeePassXC prompt and caches only those secrets.
- No plaintext export files are written to disk.
- `keepassxc-cli export` output is handled in memory and discarded after parsing.
- Requests for secrets not in the allowlist return `not_found`.

## Test Data and Demos
- `testdata/demopasswords.export.xml` is a plaintext export used for parser unit tests.
- `testdata/demopasswords.kdbx` is an encrypted demo database used only in notebooks
  (manual unlock with YubiKey/password).

## Decisions
1. Mapping uses entry title (assumed unique) with no custom attribute.
2. Cached secret fields: title, username, password, url, tags.
