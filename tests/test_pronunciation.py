from __future__ import annotations

import json
from pathlib import Path

import pytest
from lexhint.builder import build_dictionary

from dictterm.cli import main


@pytest.fixture
def pronunciation_artifact(tmp_path: Path) -> Path:
    source = tmp_path / "pronunciations.jsonl"
    records = [
        {
            "word": "love",
            "lang_code": "en",
            "pos": "noun",
            "sounds": [
                {"ipa": "/canada/", "tags": ["Canada"]},
                {"ipa": "/american/", "tags": ["General-American"]},
                {"ipa": "/british/", "tags": ["Received-Pronunciation"]},
                {"ipa": "/neutral/", "tags": []},
                {"ipa": "/canada/", "tags": ["Canada"]},
            ],
            "senses": [{"glosses": ["not shown"]}],
        },
        {
            "word": "love",
            "lang_code": "en",
            "pos": "verb",
            "sounds": [{"ipa": "/canada/", "tags": ["Canada"]}],
            "senses": [{"glosses": ["also not shown"]}],
        },
    ]
    source.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    artifact, _ = build_dictionary(
        "en",
        source,
        output=tmp_path / "pronunciations.sqlite3",
        capabilities="lexical,dictionary",
        no_frequency=True,
    )
    return artifact


def args(path: Path, *extra: str) -> list[str]:
    return ["pronunciation", "love", "--path", str(path), "--no-color", *extra]


def test_region_output_is_grouped_and_focused(
    pronunciation_artifact: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(args(pronunciation_artifact, "--region", "canada")) == 0

    output = capsys.readouterr().out
    assert output.splitlines() == [
        "love",
        "  noun",
        "    /canada/  Canada",
        "  verb",
        "    /canada/  Canada",
    ]
    assert "not shown" not in output


def test_locale_and_neutral_options(pronunciation_artifact: Path, capsys) -> None:
    assert main(args(pronunciation_artifact, "--locale", "en_CA", "--include-neutral")) == 0
    output = capsys.readouterr().out
    assert "/canada/" in output
    assert "/neutral/" in output
    assert "/american/" not in output


def test_pos_filter_is_forwarded(pronunciation_artifact: Path, capsys) -> None:
    assert main(args(pronunciation_artifact, "--region", "Canada", "--pos", "verb")) == 0
    output = capsys.readouterr().out
    assert "  verb" in output
    assert "  noun" not in output


def test_invalid_pronunciation_option_combinations(capsys) -> None:
    assert main(["pronunciation", "love", "--include-neutral"]) == 2
    assert "requires --region or --locale" in capsys.readouterr().err


def test_region_and_locale_are_rejected(pronunciation_artifact: Path, capsys) -> None:
    assert main(args(pronunciation_artifact, "--region", "Canada", "--locale", "en_CA")) == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_empty_filtered_pronunciation_result_is_success(
    pronunciation_artifact: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(args(pronunciation_artifact, "--region", "Australia")) == 0
    output = capsys.readouterr().out
    assert "No pronunciations matched region 'Australia' for 'love'." in output
