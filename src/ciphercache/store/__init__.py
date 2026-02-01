"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Store integration layer for ciphercache.
- Exposes KeePassXC helpers for reading secrets via keepassxc-cli.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from ciphercache.store.keepassxc import KeePassXCClient, KeePassXCConfig, KeePassXCParser, load_secrets

__all__ = ["KeePassXCClient", "KeePassXCConfig", "KeePassXCParser", "load_secrets"]
