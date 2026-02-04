"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Development entrypoint for exercising the ciphercache client SDK.
- Connects to a local daemon, fetches one secret, and reports status.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from ciphercache.client import Client, ClientConfig


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the client tester."""
    parser = argparse.ArgumentParser(description="Run a simple client SDK test.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / "Library" / "Application Support" / "ciphercache",
        help="Data directory for socket and tickets.",
    )
    parser.add_argument(
        "--secret",
        default="service/api",
        help="Secret name to request.",
    )
    return parser.parse_args(argv)

def main(argv: Sequence[str] | None = None) -> None:
    """Run a basic client flow against the daemon."""
    args = _parse_args(argv)
    secret_name = str(args.secret)

    client = Client(config=ClientConfig(data_dir=args.data_dir))
    print("Ping:", client.ping())
    print("Status:", client.status())
    print("Secret:", client.get_secret(secret_name))


if __name__ == "__main__":
    main()
