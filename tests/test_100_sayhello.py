from __future__ import annotations

from helloworld import greeting
from helloworld import main as hello_main


def test_greeting_for_user() -> None:
    assert greeting.greeting_for_user("Andreas") == "Hello, Andreas!"


def test_cli_outputs_full_name(monkeypatch, capsys) -> None:
    monkeypatch.setattr(greeting, "get_full_name", lambda: "Andreas")
    hello_main.main()
    captured = capsys.readouterr()
    assert captured.out.strip() == "Hello, Andreas!"
