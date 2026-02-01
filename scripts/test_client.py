"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Development entrypoint for exercising the ciphercache client SDK.
- Connects to a local daemon, optionally unlocks secrets, and fetches one secret.

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

from ciphercache.client import Client, ClientConfig


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the client tester."""
    parser = argparse.ArgumentParser(description="Run a simple client SDK test.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "Library" / "Application Support" / "ciphercache",
        help="Data directory for socket and tickets.",
    )
    parser.add_argument(
        "--ttl",
        default="1h",
        help="TTL for unlock (default: 1h).",
    )
    parser.add_argument(
        "--secrets",
        default="service/api",
        help="Comma-separated secret names to unlock.",
    )
    parser.add_argument(
        "--skip-unlock",
        action="store_true",
        help="Skip calling unlock before get_secret.",
    )
    parser.add_argument(
        "--unlock-all-on-start",
        action="store_true",
        help="Assume daemon was started with unlock-all-on-start.",
    )
    return parser.parse_args()


def _parse_secrets(raw: str) -> list[str]:
    """Parse comma-separated secret names into a list."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def main(argv: Iterable[str] | None = None) -> None:
    """Run a basic client flow against the daemon."""
    _ = argv
    args = _parse_args()
    secrets = _parse_secrets(args.secrets)
    if not secrets:
        raise ValueError("At least one secret name is required")

    client = Client(config=ClientConfig(data_dir=args.data_dir))
    print("Ping:", client.ping())
    print("Status:", client.status())

    if not args.skip_unlock:
        if args.unlock_all_on_start:
            print("Skipping unlock (daemon already unlocked all secrets)")
        else:
            print("Unlock:", client.unlock(args.ttl, secrets))

    print("Secret:", client.get_secret(secrets[0]))


if __name__ == "__main__":
    main()
