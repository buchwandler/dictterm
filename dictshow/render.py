from __future__ import annotations

from collections.abc import Sequence

from lexhint import DictionaryEntry, Example, Form, Pronunciation, Sense
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "dictshow.word": "bold",
        "dictshow.pos": "bold black on bright_cyan",
        "dictshow.heading": "bold cyan",
        "dictshow.definition": "bold",
        "dictshow.meta": "dim",
        "dictshow.example": "italic dim",
        "dictshow.relation": "magenta",
    }
)


def _heading(title: str) -> Text:
    return Text(title, style="dictshow.heading")


def _tagged_value(value: str, tags: Sequence[str]) -> Text:
    text = Text(value)
    if tags:
        text.append("  ")
        text.append(", ".join(tags), style="dictshow.meta")
    return text


def _forms(forms: Sequence[Form]) -> RenderableType | None:
    if not forms:
        return None
    rows = Table.grid(padding=(0, 1))
    rows.add_column(style="dictshow.meta", no_wrap=True)
    rows.add_column()
    for form in forms:
        label = ", ".join(form.tags) if form.tags else "form"
        rows.add_row(label, form.form)
    return Group(_heading("Forms"), Padding(rows, (1, 0, 0, 2)))


def _pronunciations(values: Sequence[Pronunciation]) -> RenderableType | None:
    if not values:
        return None
    body = Group(*[_tagged_value(item.ipa, item.tags) for item in values])
    return Group(_heading("Pronunciation"), Padding(body, (1, 0, 0, 2)))


def _example(example: Example) -> Text:
    text = Text("“", style="dictshow.example")
    text.append(example.text, style="dictshow.example")
    text.append("”", style="dictshow.example")
    if example.translation:
        text.append(" — ", style="dictshow.meta")
        text.append(example.translation, style="dictshow.meta")
    return text


def _sense(index: int, sense: Sense) -> RenderableType:
    parts: list[RenderableType] = []
    glosses = sense.glosses or ("(no definition)",)

    first = Text()
    first.append(f"{index}. ", style="dictshow.meta")
    first.append(glosses[0], style="dictshow.definition")
    parts.append(first)

    for gloss in glosses[1:]:
        parts.append(Padding(Text(gloss), (0, 0, 0, 3)))

    if sense.tags:
        parts.append(Padding(Text(", ".join(sense.tags), style="dictshow.meta"), (0, 0, 0, 3)))
    if sense.topics:
        topics = Text("topics: ", style="dictshow.meta")
        topics.append(", ".join(sense.topics))
        parts.append(Padding(topics, (0, 0, 0, 3)))

    for example in sense.examples:
        parts.append(Padding(_example(example), (0, 0, 0, 3)))

    if sense.synonyms:
        synonyms = Text("synonyms: ", style="dictshow.relation")
        synonyms.append(", ".join(sense.synonyms))
        parts.append(Padding(synonyms, (0, 0, 0, 3)))
    if sense.antonyms:
        antonyms = Text("antonyms: ", style="dictshow.relation")
        antonyms.append(", ".join(sense.antonyms))
        parts.append(Padding(antonyms, (0, 0, 0, 3)))

    return Group(*parts)


def _definitions(senses: Sequence[Sense]) -> RenderableType:
    body: list[RenderableType] = []
    for index, sense in enumerate(senses, start=1):
        if body:
            body.append(Text(""))
        body.append(_sense(index, sense))
    return Group(_heading("Definitions"), Padding(Group(*body), (1, 0, 0, 0)))


def _entry_header(entry: DictionaryEntry) -> Table:
    header = Table.grid(padding=(0, 2))
    header.add_column(no_wrap=True)
    header.add_column()
    pos = Text(f" {entry.pos.upper()} ", style="dictshow.pos")
    word = Text(entry.word, style="dictshow.word")
    header.add_row(pos, word)
    return header


def entry_renderables(entry: DictionaryEntry) -> list[RenderableType]:
    blocks: list[RenderableType] = [_entry_header(entry)]

    pronunciation = _pronunciations(entry.pronunciations)
    if pronunciation is not None:
        blocks.extend((Text(""), pronunciation))

    if entry.etymology:
        blocks.extend(
            (
                Text(""),
                _heading("Etymology"),
                Padding(Text(entry.etymology), (1, 0, 0, 2)),
            )
        )

    forms = _forms(entry.forms)
    if forms is not None:
        blocks.extend((Text(""), forms))

    blocks.extend((Text(""), _definitions(entry.senses)))
    return blocks


def render_entries(console: Console, word: str, entries: Sequence[DictionaryEntry]) -> None:
    """Render dictionary entries without owning any dictionary-data policy."""
    if not entries:
        message = Text("No dictionary entry found for ")
        message.append(repr(word), style="bold")
        message.append(".")
        console.print(message)
        return

    for index, entry in enumerate(entries):
        if index:
            console.print()
            console.print(Rule(style="dim"))
            console.print()
        console.print(Group(*entry_renderables(entry)))
