"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Daemon runtime state, configuration, and server helpers.
- Re-exports `DaemonConfig`, `DaemonState`, and `UnixSocketServer` for convenience.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from ciphercache.daemon.server import UnixSocketServer
from ciphercache.daemon.state import DaemonConfig, DaemonState

__all__ = ["DaemonConfig", "DaemonState", "UnixSocketServer"]
