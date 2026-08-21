from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Sequence
from contextlib import contextmanager

from lexhint import DictionaryEntry
from rich.console import Group
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from .render import entry_renderables
from .selection import normalize_pos

_normalize_pos = normalize_pos

NAV_LABEL_STYLE = Style(bold=True)
NAV_ACTIVE_STYLE = Style(bold=True, reverse=True)
NAV_DIM_STYLE = Style(dim=True)

VIEWER_BINDINGS = [
    ("q", "quit", "Quit"),
    ("up", "scroll_up", "Up"),
    ("down", "scroll_down", "Down"),
    ("j", "scroll_down", "Down"),
    ("k", "scroll_up", "Up"),
    ("pageup", "page_up", "Page Up"),
    ("pagedown", "page_down", "Page Down"),
    ("space", "page_down", "Page Down"),
    ("b", "page_up", "Page Up"),
    ("home", "scroll_home", "Top"),
    ("end", "scroll_end", "Bottom"),
    ("g", "scroll_home", "Top"),
    ("G", "scroll_end", "Bottom"),
    ("[", "previous_entry", "Previous"),
    ("]", "next_entry", "Next"),
    ("n", "jump_noun", "Noun"),
    ("v", "jump_verb", "Verb"),
    ("a", "jump_adjective", "Adjective"),
    ("r", "jump_adverb", "Adverb"),
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

HELP_GROUPS = (
    (
        "Navigation",
        (
            ("↑ / ↓ / j / k", "scroll"),
            ("PageUp / PageDown", "page"),
            ("Home / End", "top / bottom"),
            ("[ / ]", "previous / next entry"),
            ("n / v / a / r", "cycle noun / verb / adjective / adverb"),
            ("1..9", "entry shortcut"),
        ),
    ),
    (
        "Application",
        (("?", "help"), ("q", "quit")),
    ),
)


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

HelpScreen {
    align: center middle;
    background: $background 80%;
}

#help-content {
    width: 70%;
    max-width: 80;
    height: auto;
    padding: 1 2;
    border: round $accent;
    background: $surface;
}
"""


def _help_text() -> Text:
    text = Text("dictterm help\n", style="bold")
    for heading, bindings in HELP_GROUPS:
        text.append(f"\n{heading}\n", style="bold cyan")
        for key, description in bindings:
            text.append(f"  {key:<22} {description}\n")
    text.append("\nEsc or q closes help.", style="dim")
    return text


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


class HelpScreen(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Close")]

    def compose(self) -> ComposeResult:
        yield Static(_help_text(), id="help-content", markup=False)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key in {"escape", "q"}:
            event.stop()
            self.dismiss(None)


class EntryScroll(VerticalScroll):
    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        if self.app.is_mounted:
            self.app.call_after_refresh(self.app._sync_active_index)


class DictionaryViewerApp(App[None]):
    """Full-screen viewer for a sequence of Lexhint dictionary entries."""

    CSS = CSS
    BINDINGS = VIEWER_BINDINGS

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
        self._entry_offsets: tuple[float, ...] = ()
        self._entry_heights: tuple[int, ...] = ()
        pos_to_indices: defaultdict[str, list[int]] = defaultdict(list)
        for index, entry in enumerate(self.entries):
            pos_to_indices[normalize_pos(entry.pos)].append(index)
        self._pos_to_indices = {pos: tuple(indices) for pos, indices in pos_to_indices.items()}

    def compose(self) -> ComposeResult:
        yield Static(self._navigation_text(), id="entry-nav", markup=False)
        with EntryScroll(id="entry-scroll"):
            for index, entry in enumerate(self.entries):
                yield DictionaryEntryView(entry, index)
        yield Footer()

    def on_mount(self) -> None:
        scroll = self.query_one("#entry-scroll", VerticalScroll)
        if self.width is not None:
            scroll.styles.width = self.width
        scroll.scroll_home(animate=False, immediate=True)
        self._capture_entry_geometry(scroll)
        self._sync_active_index()
        self._update_navigation()

    def _navigation_text(self) -> Text:
        if not self.entries:
            return Text(f"dictterm  {self.word}    no entries")
        entry = self.entries[self._active_index]
        text = Text(
            f"dictterm  {self.word}    entry {self._active_index + 1}/{len(self.entries)}    "
        )
        text.append(entry.pos.upper(), style=NAV_ACTIVE_STYLE)
        counts: defaultdict[str, int] = defaultdict(int)
        for item in self.entries:
            counts[item.pos.upper()] += 1
        text.append("\n", style=NAV_DIM_STYLE)
        text.append(
            "   ".join(f"{pos} ×{count}" for pos, count in counts.items()),
            style=NAV_DIM_STYLE,
        )
        return text

    def _update_navigation(self) -> None:
        self.query_one("#entry-nav", Static).update(self._navigation_text())

    def _current_entry_index(self) -> int:
        scroll = self.query_one("#entry-scroll", VerticalScroll)
        if not self._entry_heights or not all(self._entry_heights):
            self._capture_entry_geometry(scroll)
        if len(self._entry_offsets) == len(self.entries):
            scroll_top = scroll.scroll_y
            visible = [
                index
                for index, (offset, height) in enumerate(
                    zip(self._entry_offsets, self._entry_heights, strict=True)
                )
                if offset + height > scroll_top
            ]
            if visible:
                return min(visible, key=lambda index: abs(self._entry_offsets[index] - scroll_top))
        viewport_top = scroll.region.y
        views = list(self.query(DictionaryEntryView))
        visible = [view for view in views if view.region.bottom > viewport_top]
        if visible:
            return min(visible, key=lambda view: abs(view.region.y - viewport_top)).index
        return self._active_index

    def _capture_entry_geometry(self, scroll: VerticalScroll) -> None:
        views = list(self.query(DictionaryEntryView))
        if len(views) != len(self.entries) or not all(view.region.height for view in views):
            return
        self._entry_offsets = tuple(
            view.region.y - scroll.region.y + scroll.scroll_y for view in views
        )
        self._entry_heights = tuple(view.region.height for view in views)

    def _sync_active_index(self) -> None:
        if not self.entries:
            return
        index = self._current_entry_index()
        if index != self._active_index:
            self._active_index = index
            self._update_navigation()

    def _jump_to_entry(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        target = self.query_one(f"#entry-{index}", DictionaryEntryView)
        scroll = self.query_one("#entry-scroll", VerticalScroll)
        scroll.scroll_to_widget(target, animate=False, top=True, immediate=True)
        self._active_index = index
        self._update_navigation()

    def _jump_to_pos(self, pos: str) -> None:
        indices = self._pos_to_indices.get(normalize_pos(pos))
        if not indices:
            self.notify(f"No {pos} entry")
            return
        current = self._active_index
        target = next((index for index in indices if index > current), indices[0])
        self._jump_to_entry(target)

    def action_scroll_down(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_down()
        self._sync_active_index()

    def action_scroll_up(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_up()
        self._sync_active_index()

    def action_page_down(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_page_down()
        self._sync_active_index()

    def action_page_up(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_page_up()
        self._sync_active_index()

    def action_scroll_home(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_home()
        self._sync_active_index()

    def action_scroll_end(self) -> None:
        self.query_one("#entry-scroll", VerticalScroll).scroll_end()
        self._sync_active_index()

    def action_previous_entry(self) -> None:
        self._jump_to_entry(self._active_index - 1)

    def action_next_entry(self) -> None:
        self._jump_to_entry(self._active_index + 1)

    def action_jump_noun(self) -> None:
        self._jump_to_pos("noun")

    def action_jump_verb(self) -> None:
        self._jump_to_pos("verb")

    def action_jump_adjective(self) -> None:
        self._jump_to_pos("adjective")

    def action_jump_adverb(self) -> None:
        self._jump_to_pos("adverb")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def _jump_from_digit(self, digit: int) -> None:
        self._jump_to_entry(digit - 1)

    def action_jump_1(self) -> None:
        self._jump_from_digit(1)

    def action_jump_2(self) -> None:
        self._jump_from_digit(2)

    def action_jump_3(self) -> None:
        self._jump_from_digit(3)

    def action_jump_4(self) -> None:
        self._jump_from_digit(4)

    def action_jump_5(self) -> None:
        self._jump_from_digit(5)

    def action_jump_6(self) -> None:
        self._jump_from_digit(6)

    def action_jump_7(self) -> None:
        self._jump_from_digit(7)

    def action_jump_8(self) -> None:
        self._jump_from_digit(8)

    def action_jump_9(self) -> None:
        self._jump_from_digit(9)


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
