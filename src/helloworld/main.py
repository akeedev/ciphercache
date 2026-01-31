"""CLI entrypoint for the hello example."""

from __future__ import annotations

from helloworld.greeting import get_full_name, greeting_for_user


def main() -> None:
    full_name = get_full_name()
    print(greeting_for_user(full_name))
