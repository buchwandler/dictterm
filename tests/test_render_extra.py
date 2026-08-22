from __future__ import annotations

from io import StringIO

import pytest
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


def _render_defer_forms(width: int) -> str:
    entry = DictionaryEntry(
        word="defer",
        pos="verb",
        forms=(
            Form("defers", ("present", "singular", "third-person")),
            Form("deferring", ("participle", "present")),
            Form("deferred", ("participle", "past")),
            Form("deferred", ("past",)),
        ),
        senses=(Sense(glosses=("Put off until later.",)),),
    )
    stream = StringIO()
    console = Console(theme=THEME, file=stream, force_terminal=False, no_color=True, width=width)
    render_entries(console, "defer", (entry,))
    return stream.getvalue()


@pytest.mark.parametrize("width", (40, 48, 60, 80))
def test_render_forms_keep_values_and_tags_at_small_widths(width: int) -> None:
    output = _render_defer_forms(width)

    for expected in (
        "defers",
        "deferring",
        "deferred",
        "present",
        "singular",
        "third-person",
        "participle",
        "past",
    ):
        assert expected in output

    assert "defer…" not in output
    assert "defer..." not in output
    lines = output.splitlines()
    assert sum(line.strip() == "deferred" for line in lines) == 2
    assert not any("defers" in line and "deferring" in line for line in lines)
    assert not any("deferring" in line and "deferred" in line for line in lines)


def test_render_form_without_tags_keeps_value_visible() -> None:
    entry = DictionaryEntry(
        word="walk",
        pos="verb",
        forms=(Form("walked"),),
        senses=(Sense(glosses=("Move on foot.",)),),
    )
    stream = StringIO()
    console = Console(theme=THEME, file=stream, force_terminal=False, no_color=True, width=40)

    render_entries(console, "walk", (entry,))

    assert "walked" in stream.getvalue()


def test_render_custom_empty_message() -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, no_color=True, width=40)
    render_entries(console, "love", (), empty_message="No verb entry found for 'love'.")
    assert stream.getvalue().strip() == "No verb entry found for 'love'."
