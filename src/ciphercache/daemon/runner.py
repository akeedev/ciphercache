"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Package entrypoint for running the ciphercached daemon.
- Wraps the Unix socket server and optional KeePassXC configuration.
- Intended for use via the `ciphercached` console script.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from ciphercache.daemon import DaemonConfig, DaemonState, UnixSocketServer
from ciphercache.store.keepassxc import KeePassXCConfig, load_all_secrets


class DemoDaemonState(DaemonState):
    """DaemonState that seeds demo secrets on unlock (development only)."""

    def unlock(self, ttl_seconds: int | None, secrets: list[str], store_alias: str | None = None) -> None:
        """Unlock and seed demo secrets for the requested names."""
        super().unlock(ttl_seconds, secrets, store_alias)
        store = self.secrets.setdefault(self.active_store_alias or self.config.store_alias_default, {})
        for name in secrets:
            store[name] = {"demo": True, "value": f"demo:{name}"}


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the daemon runner."""
    parser = argparse.ArgumentParser(description="Run the ciphercached daemon.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "Library" / "Application Support" / "ciphercache",
        help="Data directory for socket and tickets.",
    )
    parser.add_argument(
        "--no-agent-metadata",
        action="store_true",
        help="Disable writing agent.json metadata.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed requested secrets with demo values after unlock.",
    )
    parser.add_argument(
        "--unlock-all-on-start",
        action="store_true",
        help="Unlock and cache all secrets on startup (requires store config).",
    )
    parser.add_argument(
        "--unlock-ttl",
        default=None,
        help="TTL for unlock-all-on-start (e.g., 1h, 30m). Default: infinity.",
    )
    parser.add_argument(
        "--unlock-ttl-default",
        default=None,
        help="Default TTL for unlock requests when omitted (e.g., 1h, 30m). Default: infinity.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="KeePassXC database path.",
    )
    parser.add_argument(
        "--key-file",
        type=Path,
        help="KeePassXC key file path.",
    )
    parser.add_argument(
        "--yubikey",
        type=str,
        help="YubiKey slot[:serial] (e.g., 1:12345678) or 'auto'/'autodetect' to autodetect.",
    )
    parser.add_argument(
        "--no-password",
        action="store_true",
        help="Use YubiKey-only mode (no password).",
    )
    parser.add_argument(
        "--keepassxc-cli-path",
        type=Path,
        help="Path to keepassxc-cli executable.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO).",
    )
    parser.add_argument(
        "--require-peer-credentials",
        action="store_true",
        help="Require peer UID/GID validation and fail if unavailable.",
    )
    return parser


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the daemon runner."""
    return _build_parser().parse_args(argv)


def _run_server(config: DaemonConfig, state: DaemonState, unlock_all_on_start: bool) -> None:
    """Create and run the Unix socket server forever."""
    server = UnixSocketServer(config=config, state=state)
    if unlock_all_on_start:
        _unlock_all_on_start(state)
    server.serve_forever()


def _build_store_config(args: argparse.Namespace) -> KeePassXCConfig | None:
    """Build KeePassXCConfig from CLI args."""
    if args.db_path is None:
        return None
    return KeePassXCConfig(
        database_path=args.db_path,
        key_file_path=args.key_file,
        yubikey_slot=args.yubikey,
        no_password=args.no_password,
        keepassxc_cli_path=args.keepassxc_cli_path,
    )


def _unlock_all_on_start(state: DaemonState) -> None:
    """Unlock the store and cache all entries (startup mode)."""
    config = state.config.store_config
    if config is None:
        raise ValueError("store_config is required for unlock-all-on-start")
    secrets = load_all_secrets(config)
    names = list(secrets.keys())
    ttl_seconds = None
    if state.config.unlock_all_ttl is not None:
        ttl_seconds = state.config.unlock_all_ttl
    state.unlock(ttl_seconds, names)
    for name, payload in secrets.items():
        state.secrets.setdefault(state.active_store_alias or state.config.store_alias_default, {})[name] = payload


def main(argv: Sequence[str] | None = None) -> None:
    """Run the daemon with optional demo behavior."""
    args = _parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    store_config = _build_store_config(args)
    if args.unlock_all_on_start and store_config is None:
        raise ValueError("--unlock-all-on-start requires --db-path")
    unlock_all_ttl = None
    if args.unlock_ttl:
        from ciphercache.ttl import parse_ttl

        unlock_all_ttl = parse_ttl(args.unlock_ttl)
    unlock_ttl_default = None
    if args.unlock_ttl_default:
        from ciphercache.ttl import parse_ttl

        unlock_ttl_default = parse_ttl(args.unlock_ttl_default)
    config = DaemonConfig(
        data_dir=args.data_dir,
        write_agent_metadata=not args.no_agent_metadata,
        store_config=store_config,
        unlock_all_ttl=unlock_all_ttl,
        unlock_ttl_default=unlock_ttl_default,
        require_peer_credentials=args.require_peer_credentials,
    )
    state: DaemonState
    if args.demo:
        state = DemoDaemonState(config=config)
    else:
        state = DaemonState(config=config)
    _run_server(config, state, args.unlock_all_on_start)


if __name__ == "__main__":
    main()
