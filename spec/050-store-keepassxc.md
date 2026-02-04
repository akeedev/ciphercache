# ciphercache KeePassXC Store Integration (050)

## Purpose
Define how `ciphercached` fetches secrets from a local KeePassXC database using
`keepassxc-cli`, with a single unlock prompt and in-memory parsing.

## Scope (MVP)
- Use `keepassxc-cli export --format xml` to read the database once per daemon startup.
- Capture export output in memory (stdout), never write plaintext to disk.
- Parse XML in memory, then cache only the requested secrets.
- Support YubiKey challenge-response unlocking.
- Support `--no-password` when configured (YubiKey-only mode).

## Non-Goals (MVP)
- Direct integration with KeePassXC GUI or IPC/DBus.
- Incremental refresh or live sync.
- Encrypted IPC between client and daemon.
- Client-driven database selection or per-request store configuration.

## Rationale
`keepassxc-cli show` requires a prompt per entry. `export` allows a single unlock
followed by an in-memory parse of all entries, minimizing exposure and latency after unlock.

## Startup Unlock Flow (MVP)
1. Daemon executes at startup:
   ```
   keepassxc-cli export --format xml [--key-file <path>] [--yubikey <slot[:serial]>] [--no-password] <db_path>
   ```
2. Daemon captures stdout (XML) in memory, parses entries, and caches all entries.
3. Daemon closes the process and wipes in-memory XML.

Parsing note:
- The CLI may emit localized prompts before the XML. The parser must locate the first `<?xml`
  and ignore any preceding text to keep parsing language-independent.
- KeePassXC prompts (password / YubiKey) are emitted on stderr; the daemon should
  allow them to surface in its terminal.

## Security Requirements
- No plaintext export is written to disk.
- No secrets are logged.
- `keepassxc-cli` is executed without leaking secrets via arguments or logs.
- Secrets are cached only for the current TTL.

## Configuration
Store configuration is provided via `DaemonConfig` or a dedicated store config and
is fixed at daemon startup (clients do not select database paths in MVP):
- `database_path: Path`
- `key_file_path: Path | None`
- `yubikey_slot: str | None` (e.g., `"1"` or `"1:12345678"`)
- `yubikey_slot` may be `"auto"` to use YubiKey autodetect (see `spec/060-yubikey-autodetect.md`).
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
  - `load_all_secrets(config) -> dict[str, dict[str, object]]`: used for startup cache.

## Error Handling
- Invalid DB path or CLI failure → log error and exit daemon with non-zero status.
- Unlock failure (wrong key/YubiKey) → log error and exit daemon with non-zero status.
- Malformed XML export (parse error) → log error and exit daemon with non-zero status.
- Empty or incomplete XML export → log error and exit daemon with non-zero status.
- Requested secret not found (during `get_secret` request) → return `not_found` error to client.

Rationale: Startup errors prevent the daemon from entering a valid unlocked state, so the daemon
must exit rather than serve requests. Parse failures indicate a corrupted database or incompatible
KeePassXC version.

## Acceptance Criteria (MVP)
- Startup unlock triggers a single KeePassXC prompt and caches all secrets.
- No plaintext export files are written to disk.
- `keepassxc-cli export` output is handled in memory and discarded after parsing.
- Malformed or empty XML exports cause the daemon to log an error and exit with non-zero status.
- Parsing locates the first `<?xml` tag and ignores any preceding localized prompts.

## Test Data and Demos
- `testdata/demopasswords.export.xml` is a plaintext export used for parser unit tests.
- `testdata/demopasswords.kdbx` is an encrypted demo database used only in notebooks
  (manual unlock with YubiKey/password).

## Decisions
1. Mapping uses entry title (assumed unique) with no custom attribute.
2. Cached secret fields: title, username, password, url, tags.
