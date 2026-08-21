from __future__ import annotations

import os
import re
from collections import defaultdict
from collections.abc import Sequence
from contextlib import contextmanager

from lexhint import DictionaryEntry
from rich.console import Group
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Static

from .render import entry_renderables

NAV_LABEL_STYLE = Style(bold=True)
NAV_ACTIVE_STYLE = Style(bold=True, reverse=True)
NAV_DIM_STYLE = Style(dim=True)


CSS = """
Screen {
    layout: vertical;
}

#entry-nav {
    height: auto;
    padding: 0 1;
}

#entry-scroll {
    height: 1fr;
    overflow-x: hidden;
}

.dictionary-entry {
    width: 1fr;
    height: auto;
    padding: 1 1;
}
"""


def _normalize_pos(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", value.strip().lower())


class DictionaryEntryView(Static):
    """One complete Lexhint dictionary entry rendered with Rich."""

    def __init__(self, entry: DictionaryEntry, index: int) -> None:
        super().__init__(
            Group(*entry_renderables(entry)),
            markup=False,
            id=f"entry-{index}",
            classes="dictionary-entry",
        )
        self.entry = entry
        self.index = index


class DictionaryViewerApp(App[None]):
    """Full-screen viewer for a sequence of Lexhint dictionary entries."""

    CSS = CSS
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("j", "scroll_down", "Down"),
        ("k", "scroll_up", "Up"),
        ("space", "page_down", "Page Down"),
        ("b", "page_up", "Page Up"),
        ("g", "scroll_home", "Top"),
        ("G", "scroll_end", "Bottom"),
        ("[", "previous_entry", "Previous"),
        ("]", "next_entry", "Next"),
        ("n", "jump_noun", "Noun"),
        ("v", "jump_verb", "Verb"),
        ("?", "help", "Help"),
        ("1", "jump_1", ""),
        ("2", "jump_2", ""),
        ("3", "jump_3", ""),
        ("4", "jump_4", ""),
        ("5", "jump_5", ""),
        ("6", "jump_6", ""),
        ("7", "jump_7", ""),
        ("8", "jump_8", ""),
        ("9", "jump_9", ""),
    ]

    def __init__(
        self,
        word: str,
        entries: Sequence[DictionaryEntry],
        *,
        width: int | None = None,
    ) -> None:
        super().__init__()
        self.word = word
        self.entries = tuple(entries)
        self.width = width
        self._active_index = 0
        pos_to_indices: defaultdict[str, list[int]] = defaultdict(list)
        for index, entry in enumerate(self.entries):
            pos_to_indices[_normalize_pos(entry.pos)].append(index)
        self._pos_to_indices = {
            pos: tuple(indices) for pos, indices in pos_to_indices.items()
        }

    def compose(self) -> ComposeResult:
        yield Static(self._navigation_text(), id="entry-nav", markup=False)
        with VerticalScroll(id="entry-scroll"):
            for index, entry in enumerate(self.entries):
                yield DictionaryEntryView(entry, index)
        yield Footer()

    def on_mount(self) -> None:
        scroll = self.query_one("#entry-scroll", VerticalScroll)
        if self.width is not None:
            scroll.styles.width = self.width
        scroll.scroll_home(animate=False, immediate=True)
        self._update_navigation()

    def _navigation_text(self) -> Text:
        text = Text(f"dictshow  {self.word}    ")
        for index, entry in enumerate(self.entries):
            if index:
                text.append("   ", style=NAV_DIM_STYLE)
            style = NAV_ACTIVE_STYLE if index == self._active_index else NAV_LABEL_STYLE
            text.append(f"{index + 1} {entry.pos.upper()}", style=style)
        return text

    def _update_navigation(self) -> None:
        self.query_one("#entry-nav", Static).update(self._navigation_text())

    def _jump_to_entry(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        target = self.query_one(f"#entry-{index}", DictionaryEntryView)
        scroll = self.query_one("#entry-scroll", VerticalScroll)
        scroll.scroll_to_widget(target, animate=False, top=True, immediate=True)
        self._active_index = index
        self._update_navigation()

    def _jump_to_pos(self, pos: str) -> None:
        indices = self._pos_to_indices.get(_normalize_pos(pos))
        if not indices:
            self.notify(f"No {pos} entry")
            return
        self._jump_to_entry(indices[0])

    def _current_entry_index(self) -> int:
        scroll = self.query_one("#entry-scroll", VerticalScroll)
        scroll_top = scroll.region.y
        visible = [
            entry.index
            for entry in self.query(DictionaryEntryView)
            if entry.region.y >= scroll_top
        ]
        return visible[0] if visible else self._active_index

    def action_scroll_down(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_up()

    def action_page_down(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_page_down()

    def action_page_up(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_page_up()

    def action_scroll_home(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_end()

    def action_previous_entry(self) -> None:
        self._jump_to_entry(self._current_entry_index() - 1)

    def action_next_entry(self) -> None:
        self._jump_to_entry(self._current_entry_index() + 1)

    def action_jump_noun(self) -> None:
        self._jump_to_pos("noun")

    def action_jump_verb(self) -> None:
        self._jump_to_pos("verb")

    def action_help(self) -> None:
        self.notify(
            "Keys: arrows/jk scroll, PgUp/PgDn, Home/End, [/] entries, n noun, "
            "v verb, 1-9 jump, q quit"
        )

    def action_jump_1(self) -> None:
        self._jump_to_entry(0)

    def action_jump_2(self) -> None:
        self._jump_to_entry(1)

    def action_jump_3(self) -> None:
        self._jump_to_entry(2)

    def action_jump_4(self) -> None:
        self._jump_to_entry(3)

    def action_jump_5(self) -> None:
        self._jump_to_entry(4)

    def action_jump_6(self) -> None:
        self._jump_to_entry(5)

    def action_jump_7(self) -> None:
        self._jump_to_entry(6)

    def action_jump_8(self) -> None:
        self._jump_to_entry(7)

    def action_jump_9(self) -> None:
        self._jump_to_entry(8)


@contextmanager
def _temporary_no_color(enabled: bool):
    if not enabled or "NO_COLOR" in os.environ:
        yield
        return

    os.environ["NO_COLOR"] = "1"
    try:
        yield
    finally:
        del os.environ["NO_COLOR"]


def run_viewer(
    word: str,
    entries: Sequence[DictionaryEntry],
    *,
    width: int | None = None,
    no_color: bool = False,
) -> None:
    app = DictionaryViewerApp(word, entries, width=width)
    with _temporary_no_color(no_color):
        app.run()
