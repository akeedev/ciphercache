"""Greeting helpers for the CLI example."""

from __future__ import annotations

import os
import pwd


def get_full_name() -> str:
    """Return the full name from macOS user account info."""
    gecos = pwd.getpwuid(os.getuid()).pw_gecos
    full_name = gecos.split(",")[0].strip()
    if not full_name:
        raise ValueError("Full name not available from macOS user info.")
    return full_name


def greeting_for_user(full_name: str) -> str:
    return f"Hello, {full_name}!"
