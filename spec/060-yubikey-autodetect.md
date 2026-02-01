# ciphercache YubiKey Autodetect (060)

## Purpose
Provide an optional YubiKey autodetection mechanism for KeePassXC unlocks, using
`ykman list` when the CLI is installed.

## Scope (MVP)
- Implement autodetect only if `ykman` is available in `PATH`.
- Use `ykman list` to enumerate connected YubiKeys. Parse the `Serial: <id>` field
  (or a line with a standalone numeric serial, if provided by `ykman`).
- If exactly one YubiKey is found, use its serial automatically.
- If none are found, error with a clear message.
- If more than one are found, list serials and require explicit selection.

## Non-Goals
- Adding `ykman` as a required dependency.
- USB device scanning without `ykman`.
- Automatic slot selection beyond default slot 1.

## Responsibilities
- Provide a small utility module for YubiKey autodetect.
- Expose an API for the daemon and SDK to request autodetection.
- Map `--yubikey auto` (or `autodetect`) to autodetection in the daemon runner.

## Interface (planned)
- `ciphercache.yubikey.detect_yubikey() -> str`
  - Returns a serial string when exactly one is found.
  - Raises `RuntimeError` when none or multiple devices are found.
- `ciphercache.yubikey.is_ykman_available() -> bool`

## Behavior
- Command invoked: `ykman list`
- Parse output lines as serials (one per line).
- If output is empty → error.
- If multiple serials → error with list of serials.
- If exactly one serial → return it.

## Acceptance Criteria
- `--yubikey auto` works only when `ykman` is installed.
- Autodetect fails with clear errors on 0 or >1 devices.
- Autodetect module is used by the daemon runner and SDK.
