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
        help="Replace loaded secrets with demo placeholders after startup unlock.",
    )
    parser.add_argument(
        "--ttl",
        default=None,
        help="Session TTL for the daemon (e.g., 1h, 30m). Default: infinity.",
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


def _run_server(config: DaemonConfig, state: DaemonState, demo: bool) -> None:
    """Create and run the Unix socket server forever."""
    server = UnixSocketServer(config=config, state=state)
    _unlock_on_start(state, demo)
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


def _unlock_on_start(state: DaemonState, demo: bool) -> None:
    """Unlock the store and cache all entries (startup mode)."""
    config = state.config.store_config
    if config is None:
        raise ValueError("store_config is required for startup unlock")
    secrets = load_all_secrets(config)
    if demo:
        secrets = {name: {"demo": True, "value": f"demo:{name}"} for name in secrets.keys()}
    state.unlock(state.config.ttl_seconds)
    state.secrets = secrets


def main(argv: Sequence[str] | None = None) -> None:
    """Run the daemon with optional demo behavior."""
    args = _parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    store_config = _build_store_config(args)
    if store_config is None:
        raise ValueError("--db-path is required")
    ttl_seconds = None
    if args.ttl:
        from ciphercache.ttl import parse_ttl

        ttl_seconds = parse_ttl(args.ttl)
    config = DaemonConfig(
        data_dir=args.data_dir,
        write_agent_metadata=not args.no_agent_metadata,
        store_config=store_config,
        ttl_seconds=ttl_seconds,
        require_peer_credentials=args.require_peer_credentials,
    )
    state = DaemonState(config=config)
    _run_server(config, state, args.demo)


if __name__ == "__main__":
    main()
