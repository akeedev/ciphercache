"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Development entrypoint for running the ciphercached Unix socket server.
- Thin wrapper around `ciphercache.daemon.runner`.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

from ciphercache.daemon.runner import main


if __name__ == "__main__":
    main()
