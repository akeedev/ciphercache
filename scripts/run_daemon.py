"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Development entrypoint for running the ciphercached Unix socket server.
- Supports an optional demo mode that seeds requested secrets after unlock.
- Uses `UnixSocketServer` and `DaemonState` from the core daemon module.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import logging

from ciphercache.daemon import DaemonConfig, DaemonState, UnixSocketServer


class DemoDaemonState(DaemonState):
    """DaemonState that seeds demo secrets on unlock (development only)."""

    def unlock(self, ttl_seconds: int | None, secrets: list[str], store_alias: str | None = None) -> None:
        """Unlock and seed demo secrets for the requested names."""
        super().unlock(ttl_seconds, secrets, store_alias)
        store = self.secrets.setdefault(self.active_store_alias or self.config.store_alias_default, {})
        for name in secrets:
            store[name] = {"demo": True, "value": f"demo:{name}"}


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the daemon runner."""
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
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO).",
    )
    return parser.parse_args()


def _run_server(config: DaemonConfig, state: DaemonState) -> None:
    """Create and run the Unix socket server forever."""
    server = UnixSocketServer(config=config, state=state)
    server.serve_forever()


def main(argv: Iterable[str] | None = None) -> None:
    """Run the daemon with optional demo behavior."""
    _ = argv
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    config = DaemonConfig(
        data_dir=args.data_dir,
        write_agent_metadata=not args.no_agent_metadata,
    )
    state: DaemonState
    if args.demo:
        state = DemoDaemonState(config=config)
    else:
        state = DaemonState(config=config)
    _run_server(config, state)


if __name__ == "__main__":
    main()
