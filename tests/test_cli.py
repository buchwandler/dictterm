from __future__ import annotations

import argparse

from lexhint import DictionaryEntry, Sense

from dictshow import cli


class FakeLexicon:
    def __init__(self, language: str, **kwargs: object) -> None:
        self.language = language
        self.kwargs = kwargs

    def entries(self, word: str):
        if word == "missing":
            return ()
        return (
            DictionaryEntry(
                word=word,
                pos="noun",
                senses=(Sense(glosses=("A test definition.",)),),
            ),
        )


def test_cli_lookup(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--no-color"]) == 0
    assert "A test definition." in capsys.readouterr().out


def test_cli_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["missing", "--no-color"]) == 1
    assert "No dictionary entry found" in capsys.readouterr().out


def test_use_tui_requires_two_ttys(monkeypatch) -> None:
    class TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(cli.sys, "stdin", TTY())
    monkeypatch.setattr(cli.sys, "stdout", TTY())
    assert cli._use_tui(argparse.Namespace(plain=False, tui=True)) is True
    assert cli._use_tui(argparse.Namespace(plain=True, tui=False)) is False


def test_forced_tui_on_non_tty_is_controlled_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--tui", "--no-color"]) == 2
    assert "--tui requires an interactive terminal" in capsys.readouterr().err
