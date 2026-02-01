"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Exposes top-level SDK and daemon helpers for convenience imports.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from ciphercache.client import Client, ClientConfig, Status
from ciphercache.daemon import DaemonConfig, DaemonState, UnixSocketServer
from ciphercache.yubikey import detect_yubikey, is_ykman_available

__all__ = [
    "Client",
    "ClientConfig",
    "Status",
    "DaemonConfig",
    "DaemonState",
    "UnixSocketServer",
    "detect_yubikey",
    "is_ykman_available",
]
