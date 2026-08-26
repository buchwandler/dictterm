from __future__ import annotations

from collections.abc import Sequence

from lexhint import (
    DictionaryEntry,
    Example,
    Form,
    HeadwordRelation,
    Pronunciation,
    RelatedTerm,
    Sense,
)
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .backend import LookupResult

WORD_STYLE = Style(bold=True)
POS_STYLE = Style(bold=True, color="black", bgcolor="bright_cyan")
HEADING_STYLE = Style(bold=True, color="cyan")
DEFINITION_STYLE = Style(bold=True)
META_STYLE = Style(dim=True)
EXAMPLE_STYLE = Style(italic=True, dim=True)
RELATION_STYLE = Style(color="magenta")

THEME = Theme(
    {
        "dictterm.word": "bold",
        "dictterm.pos": "bold black on bright_cyan",
        "dictterm.heading": "bold cyan",
        "dictterm.definition": "bold",
        "dictterm.meta": "dim",
        "dictterm.example": "italic dim",
        "dictterm.relation": "magenta",
    }
)


def _heading(title: str) -> Text:
    return Text(title, style=HEADING_STYLE)


def _tagged_value(value: str, tags: Sequence[str]) -> Text:
    text = Text(value)
    if tags:
        text.append("  ")
        text.append(", ".join(tags), style=META_STYLE)
    return text


def _form_renderable(form: Form) -> RenderableType:
    parts: list[RenderableType] = [Text(form.form)]
    if form.tags:
        parts.append(
            Padding(
                Text(", ".join(form.tags), style=META_STYLE),
                (0, 0, 0, 2),
            )
        )
    return Group(*parts)


def _forms(forms: Sequence[Form]) -> RenderableType | None:
    if not forms:
        return None
    body = Group(*(_form_renderable(form) for form in forms))
    return Group(_heading("Forms"), Padding(body, (1, 0, 0, 2)))


def _pronunciations(values: Sequence[Pronunciation]) -> RenderableType | None:
    if not values:
        return None
    body = Group(*[_tagged_value(item.ipa, item.tags) for item in values])
    return Group(_heading("Pronunciation"), Padding(body, (1, 0, 0, 2)))


def _example(example: Example) -> Text:
    text = Text("“", style=EXAMPLE_STYLE)
    text.append(example.text, style=EXAMPLE_STYLE)
    text.append("”", style=EXAMPLE_STYLE)
    if example.translation:
        text.append(" — ", style=META_STYLE)
        text.append(example.translation, style=META_STYLE)
    return text


def _relations(label: str, values: Sequence[str | RelatedTerm]) -> Text:
    text = Text(f"{label}: ", style=RELATION_STYLE)
    for index, value in enumerate(values):
        if index:
            text.append(", ")
        if isinstance(value, RelatedTerm):
            if value.tags:
                text.append(", ".join(value.tags) + ": ", style=META_STYLE)
            text.append(value.word)
        else:
            text.append(value)
    return text


def _sense(index: int, sense: Sense) -> RenderableType:
    parts: list[RenderableType] = []
    glosses = sense.glosses or ("(no definition)",)

    first = Text()
    first.append(f"{index}. ", style=META_STYLE)
    first.append(glosses[0], style=DEFINITION_STYLE)
    parts.append(first)

    for gloss in glosses[1:]:
        parts.append(Padding(Text(gloss), (0, 0, 0, 3)))

    if sense.tags:
        parts.append(Padding(Text(", ".join(sense.tags), style=META_STYLE), (0, 0, 0, 3)))
    if sense.topics:
        topics = Text("topics: ", style=META_STYLE)
        topics.append(", ".join(sense.topics))
        parts.append(Padding(topics, (0, 0, 0, 3)))

    for example in sense.examples:
        parts.append(Padding(_example(example), (0, 0, 0, 3)))

    if sense.synonyms:
        parts.append(Padding(_relations("synonyms", sense.synonyms), (0, 0, 0, 3)))
    if sense.antonyms:
        parts.append(Padding(_relations("antonyms", sense.antonyms), (0, 0, 0, 3)))

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
    pos = Text(f" {entry.pos.upper()} ", style=POS_STYLE)
    word = Text(entry.word, style=WORD_STYLE)
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


def render_entries(
    console: Console,
    word: str,
    entries: Sequence[DictionaryEntry],
    *,
    empty_message: str | None = None,
) -> None:
    """Render dictionary entries without owning any dictionary-data policy."""
    if not entries:
        message = Text(empty_message or "No dictionary entry found for ")
        if empty_message is None:
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


RELATION_LABELS = {
    "redirect": "Redirect",
    "alternative": "Alternative",
    "form_of": "Form of",
    "synonym": "Synonyms",
    "antonym": "Antonyms",
    "hypernym": "Broader terms",
    "hyponym": "Narrower terms",
    "related": "Related",
}


def _relation_label(relation: str) -> str:
    return RELATION_LABELS.get(relation, relation.replace("_", " ").title())


def _headword_relation(relation: HeadwordRelation) -> Text:
    text = Text("  ")
    text.append(_relation_label(relation.relation), style=RELATION_STYLE)
    text.append("  ")
    text.append(relation.target)
    if relation.tags:
        text.append("  ")
        text.append(", ".join(relation.tags), style=META_STYLE)
    return text


def _headword_relations(relations: Sequence[HeadwordRelation]) -> RenderableType | None:
    if not relations:
        return None
    rows = Group(*(_headword_relation(relation) for relation in relations))
    return Group(_heading("Relations"), Padding(rows, (1, 0, 0, 0)))


def render_lookup(
    console: Console,
    result: LookupResult,
    *,
    empty_message: str | None = None,
) -> None:
    """Render entries and query-level headword relations for one lookup."""
    if not result.entries:
        if empty_message is not None:
            message = Text(empty_message)
        elif result.relations:
            message = Text("No direct dictionary entry found for ")
            message.append(repr(result.word), style="bold")
            message.append(".")
        else:
            message = Text("No dictionary entry found for ")
            message.append(repr(result.word), style="bold")
            message.append(".")
        console.print(message)
    else:
        for index, entry in enumerate(result.entries):
            if index:
                console.print()
                console.print(Rule(style="dim"))
                console.print()
            console.print(Group(*entry_renderables(entry)))
    relations = _headword_relations(result.relations)
    if relations is not None:
        console.print()
        console.print(relations)
