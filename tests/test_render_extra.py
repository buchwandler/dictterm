from __future__ import annotations

from io import StringIO

from lexhint import DictionaryEntry, Example, Form, Pronunciation, Sense
from rich.console import Console

from dictterm.render import THEME, render_entries


def test_render_all_optional_fields_at_narrow_width() -> None:
    entry = DictionaryEntry(
        word="Straße",
        pos="noun",
        pronunciations=(
            Pronunciation("/ˈʃtʁaːsə/", ("Germany",)),
            Pronunciation("[ˈʃtʁaːsə]", ("Austria",)),
        ),
        forms=(Form("Straßen", ("plural",)),),
        senses=(
            Sense(
                glosses=("A road.", "A street."),
                tags=("countable",),
                topics=("transport",),
                examples=(Example("Die Straße ist lang.", "The street is long."),),
                synonyms=("road",),
                antonyms=("dead end",),
            ),
        ),
    )
    stream = StringIO()
    console = Console(theme=THEME, file=stream, force_terminal=False, no_color=True, width=40)

    render_entries(console, "Straße", (entry,))

    output = stream.getvalue()
    for expected in (
        "Straße",
        "/ˈʃtʁaːsə/",
        "[ˈʃtʁaːsə]",
        "Straßen",
        "A road.",
        "A street.",
        "countable",
        "topics: transport",
        "Die Straße ist lang.",
        "The street",
        "long.",
        "synonyms: road",
        "antonyms: dead end",
    ):
        assert expected in output


def test_render_custom_empty_message() -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, no_color=True, width=40)
    render_entries(console, "love", (), empty_message="No verb entry found for 'love'.")
    assert stream.getvalue().strip() == "No verb entry found for 'love'."
