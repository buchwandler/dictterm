from __future__ import annotations

from io import StringIO

from lexhint import DictionaryEntry, Example, Form, Pronunciation, RelatedTerm, Sense
from rich.console import Console, Group

from dictshow.render import THEME, entry_renderables, render_entries


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


def test_entry_renderables_do_not_require_dictshow_theme() -> None:
    entry = DictionaryEntry(
        word="word",
        pos="noun",
        senses=(Sense(glosses=("A definition.",)),),
    )
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, no_color=True, width=80)

    console.print(Group(*entry_renderables(entry)))

    assert "A definition." in stream.getvalue()


def test_render_structured_related_terms() -> None:
    entry = DictionaryEntry(
        word="love",
        pos="noun",
        senses=(
            Sense(
                glosses=("A strong feeling of affection.",),
                synonyms=(RelatedTerm("affection", "synonym", ("formal",)),),
                antonyms=(RelatedTerm("hate", "antonym"),),
            ),
        ),
    )
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, no_color=True, width=80)

    render_entries(console, "love", (entry,))

    output = stream.getvalue()
    assert "synonyms: formal: affection" in output
    assert "antonyms: hate" in output
