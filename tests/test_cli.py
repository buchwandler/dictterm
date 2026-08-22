from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from lexhint import (
    DictionaryEntry,
    LexiconCapabilityError,
    LexiconCoverageError,
    LexiconNotInstalled,
    Sense,
)

from dictterm import cli


def _entry(word: str, pos: str) -> DictionaryEntry:
    return DictionaryEntry(
        word=word,
        pos=pos,
        senses=(Sense(glosses=(f"A {pos} definition.",)),),
    )


class FakeLexicon:
    created: list[tuple[str, dict[str, object]]] = []
    path_created: list[tuple[object, dict[str, object]]] = []
    results: tuple[DictionaryEntry, ...] = (_entry("word", "noun"),)

    def __init__(self, language: str, **kwargs: object) -> None:
        self.language = language
        self.kwargs = kwargs
        type(self).created.append((language, kwargs))

    @classmethod
    def from_path(cls, path: object, **kwargs: object) -> FakeLexicon:
        instance = cls.__new__(cls)
        instance.language = kwargs.get("language")
        instance.kwargs = kwargs
        cls.path_created.append((path, kwargs))
        return instance

    def entries(self, word: str, *, all_case_variants: bool = False):
        if word == "missing":
            return ()
        return self.results


@pytest.fixture(autouse=True)
def reset_fake() -> None:
    FakeLexicon.created.clear()
    FakeLexicon.path_created.clear()
    FakeLexicon.results = (_entry("word", "noun"),)


def test_cli_lookup_uses_managed_english_rich_dataset(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--no-color"]) == 0
    assert "A noun definition." in capsys.readouterr().out
    assert FakeLexicon.created == [
        ("en", {"variant": "rich", "dataset_version": None, "locale": None})
    ]


def test_explicit_language_and_locale_are_forwarded(monkeypatch) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "-l", "de", "--locale", "de-DE", "--plain"]) == 0
    assert FakeLexicon.created[0] == (
        "de",
        {"variant": "rich", "dataset_version": None, "locale": "de-DE"},
    )


def test_path_without_language_uses_artifact_metadata(monkeypatch) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--path", "lexicon.sqlite3", "--locale", "de-DE"]) == 0
    assert FakeLexicon.path_created == [
        (Path("lexicon.sqlite3"), {"language": None, "locale": "de-DE"})
    ]


def test_path_with_language_is_forwarded_for_validation(monkeypatch) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--path", "lexicon.sqlite3", "-l", "de"]) == 0
    assert FakeLexicon.path_created == [
        (Path("lexicon.sqlite3"), {"language": "de", "locale": None})
    ]


def test_path_and_dataset_version_is_controlled_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--path", "x.sqlite3", "--dataset-version", "1"]) == 2
    error = capsys.readouterr().err
    assert "--path cannot be combined with --dataset-version" in error
    assert "dataset download" not in error


def test_all_case_variants_reaches_entries(monkeypatch) -> None:
    seen: list[bool] = []

    class CaseLexicon(FakeLexicon):
        def entries(self, word: str, *, all_case_variants: bool = False):
            seen.append(all_case_variants)
            return super().entries(word, all_case_variants=all_case_variants)

    monkeypatch.setattr(cli, "Lexicon", CaseLexicon)
    assert cli.main(["word", "--all-case-variants", "--plain"]) == 0
    assert seen == [True]


def test_pos_filter_normalizes_and_excludes(monkeypatch, capsys) -> None:
    FakeLexicon.results = (
        _entry("love", "noun"),
        _entry("love", "proper_noun"),
        _entry("love", "verb"),
    )
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["love", "--pos", "proper-noun", "--plain"]) == 0
    output = capsys.readouterr().out
    assert "PROPER_NOUN" in output
    assert " NOUN   " not in output


def test_filtering_all_entries_has_distinct_message(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["word", "--pos", "verb", "--plain"]) == 1
    assert "No verb entry found for 'word'." in capsys.readouterr().out


def test_missing_word_exit_one(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    assert cli.main(["missing", "--no-color"]) == 1
    assert "No dictionary entry found" in capsys.readouterr().out


def test_plain_mode_never_starts_textual(monkeypatch) -> None:
    monkeypatch.setattr(cli, "Lexicon", FakeLexicon)
    import dictterm.tui

    monkeypatch.setattr(
        dictterm.tui, "run_viewer", lambda *args, **kwargs: pytest.fail("TUI started")
    )
    assert cli.main(["word", "--plain"]) == 0


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


def test_width_below_minimum_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["word", "--width", "39"])
    assert exc_info.value.code == 2


def test_missing_managed_dataset_hint_uses_resolved_language(monkeypatch, capsys) -> None:
    class MissingLexicon:
        def __init__(self, *args, **kwargs):
            raise LexiconNotInstalled("no local artifact")

    monkeypatch.setattr(cli, "Lexicon", MissingLexicon)
    assert cli.main(["word"]) == 2
    assert "lexhint dataset download en --variant rich" in capsys.readouterr().err


def test_bare_tui_missing_dataset_prints_install_hint(monkeypatch, capsys) -> None:
    class TTY:
        def isatty(self) -> bool:
            return True

    class MissingLexicon:
        def __init__(self, *args, **kwargs):
            raise LexiconNotInstalled("no local artifact")

    monkeypatch.setattr(cli.sys, "stdin", TTY())
    monkeypatch.setattr(cli.sys, "stdout", TTY())
    monkeypatch.setattr(cli, "Lexicon", MissingLexicon)

    assert cli.main([]) == 2
    assert "lexhint dataset download en --variant rich" in capsys.readouterr().err


def test_managed_capability_error_prints_install_hint(monkeypatch, capsys) -> None:
    class MissingCapabilityLexicon:
        def __init__(self, *args, **kwargs):
            raise LexiconCapabilityError("rich capability missing")

    monkeypatch.setattr(cli, "Lexicon", MissingCapabilityLexicon)

    assert cli.main(["word"]) == 2
    assert "lexhint dataset download en --variant rich" in capsys.readouterr().err


def test_unrelated_managed_error_does_not_print_install_hint(monkeypatch, capsys) -> None:
    class BrokenLexicon:
        def __init__(self, *args, **kwargs):
            raise LexiconCoverageError("incomplete artifact")

    monkeypatch.setattr(cli, "Lexicon", BrokenLexicon)

    assert cli.main(["word"]) == 2
    assert "dataset download" not in capsys.readouterr().err


def test_custom_dataset_error_does_not_print_install_hint(monkeypatch, capsys) -> None:
    class MissingCustomLexicon:
        @classmethod
        def from_path(cls, path, **kwargs):
            raise LexiconNotInstalled("custom artifact missing")

    monkeypatch.setattr(cli, "Lexicon", MissingCustomLexicon)

    assert cli.main(["word", "--path", "custom.sqlite3"]) == 2
    assert "dataset download" not in capsys.readouterr().err


def test_config_path_prints_override(tmp_path: Path, capsys) -> None:
    path = tmp_path / "config.toml"
    assert cli.main(["--config", str(path), "--config-path"]) == 0
    assert capsys.readouterr().out.strip() == str(path)


def test_init_config_reports_path_and_refuses_overwrite(tmp_path: Path, capsys) -> None:
    path = tmp_path / "config.toml"
    assert cli.main(["--config", str(path), "--init-config"]) == 0
    assert capsys.readouterr().out.strip() == str(path)
    assert cli.main(["--config", str(path), "--init-config"]) == 2
    assert "already exists" in capsys.readouterr().err


def test_invalid_config_is_controlled_error(tmp_path: Path, capsys) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[tts]\nspeed = 0\n")
    assert cli.main(["--config", str(path), "word"]) == 2
    assert "greater than 0" in capsys.readouterr().err
