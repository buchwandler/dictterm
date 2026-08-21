from __future__ import annotations

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
