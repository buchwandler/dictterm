from __future__ import annotations

from io import StringIO

from lexhint import DictionaryEntry, Example, Form, Pronunciation, Sense
from rich.console import Console

from dictshow.render import THEME, render_entries


def test_render_rich_entry() -> None:
    entry = DictionaryEntry(
        word="lavish",
        pos="adj",
        pronunciations=(Pronunciation("/ˈlævɪʃ/", ("UK",)),),
        etymology="From Middle English laves.",
        forms=(Form("more lavish", ("comparative",)),),
        senses=(
            Sense(
                glosses=("Expending or bestowing profusely; prodigal.",),
                examples=(Example("lavish praise"),),
                synonyms=("profuse", "extravagant"),
            ),
        ),
    )
    stream = StringIO()
    console = Console(theme=THEME, file=stream, force_terminal=False, no_color=True, width=80)

    render_entries(console, "lavish", (entry,))

    output = stream.getvalue()
    assert "LAVISH" not in output
    assert "lavish" in output
    assert "ADJ" in output
    assert "Pronunciation" in output
    assert "/ˈlævɪʃ/" in output
    assert "Etymology" in output
    assert "Definitions" in output
    assert "lavish praise" in output
    assert "synonyms:" in output
