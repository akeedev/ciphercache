# ciphercache MVP Checklist

## Core functionality
- [x] IPC protocol framing and handler
- [x] Daemon server loop (Unix socket)
- [x] Tickets (file-based, 0600)
- [x] TTL parsing and enforcement
- [x] Client SDK
- [x] KeePassXC XML export parsing
- [x] KeePassXC integration wired to unlock

## Security & safety
- [x] Socket directory permissions (0700)
- [x] Socket file permissions (0600)
- [x] Peer UID/GID validation
- [x] No secrets in logs

## Docs & demos
- [x] README with usage
- [x] User guide in `doc/`
- [x] Demo notebooks per spec
