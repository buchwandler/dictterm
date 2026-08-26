from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from lexhint import HeadwordRelation, Lexicon
from lexhint.builder import build_dictionary
from rich.console import Console

from dictterm.backend import LexhintBackend
from dictterm.render import THEME, render_lookup


def test_dictterm_consumes_generated_schema10_artifact(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {
                    "word": "love",
                    "lang_code": "en",
                    "pos": "verb",
                    "redirects": ["loving"],
                    "senses": [
                        {
                            "senseid": ["en:care"],
                            "wikidata": ["Q1"],
                            "glosses": ["To care deeply."],
                            "topics": ["emotion"],
                        }
                    ],
                },
                {
                    "word": "lover",
                    "lang_code": "en",
                    "pos": "noun",
                    "senses": [{"glosses": ["One who loves."]}],
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    database, _ = build_dictionary(
        "en",
        source,
        output=tmp_path / "schema10.sqlite3",
        profile="dictionary",
        no_frequency=True,
    )

    lexicon = Lexicon.from_path(database)
    assert lexicon.schema_version == "10"

    backend = LexhintBackend(lexicon)
    result = backend.lookup("love")

    assert result.word == "love"
    assert result.entries[0].senses[0].sense_id
    assert result.entries[0].senses[0].source_ids[0].namespace == "wiktionary-senseid"
    assert result.entries[0].senses[0].source_ids[1].namespace == "wikidata"
    assert result.relations == (HeadwordRelation("love", "loving", "redirect"),)
    assert "love" in backend.complete("lov")
    assert "lover" in backend.complete("lov")

    stream = StringIO()
    console = Console(theme=THEME, file=stream, force_terminal=False, no_color=True, width=80)
    render_lookup(console, result)
    output = stream.getvalue()
    assert "To care deeply." in output
    assert "Redirect" in output
    assert "loving" in output
    assert result.entries[0].senses[0].sense_id not in output
