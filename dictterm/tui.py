from __future__ import annotations

import os
import threading
from collections import defaultdict
from collections.abc import Sequence
from contextlib import contextmanager

from lexhint import DictionaryEntry, Sense
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from .backend import DictionaryBackend
from .config import TTSConfig
from .render import _entry_header
from .selection import normalize_pos
from .speech import (
    PyKokoroSpeechService,
    SpeechError,
    SpeechPlaybackError,
    SpeechRequest,
    SpeechSynthesisError,
    SpeechUnavailable,
    spoken_definition,
    spoken_definitions,
    spoken_forms,
)

_normalize_pos = normalize_pos

NAV_ACTIVE_STYLE = Style(bold=True, reverse=True)
NAV_DIM_STYLE = Style(dim=True)

VIEWER_BINDINGS = [
    Binding("q", "quit", "Quit", priority=True),
    Binding("up,k", "scroll_line_up", "", show=False, priority=True),
    Binding("down,j", "scroll_line_down", "", show=False, priority=True),
    Binding("pageup,b", "scroll_page_up", "", show=False, priority=True),
    Binding("pagedown,space", "scroll_page_down", "", show=False, priority=True),
    Binding("home,g", "scroll_document_home", "", show=False, priority=True),
    Binding("end,G", "scroll_document_end", "", show=False, priority=True),
    Binding("[", "previous_entry", "Previous", priority=True),
    Binding("]", "next_entry", "Next", priority=True),
    Binding("n", "jump_noun", "Noun", priority=True),
    Binding("v", "jump_verb", "Verb", priority=True),
    Binding("a", "jump_adjective", "Adjective", priority=True),
    Binding("r", "jump_adverb", "Adverb", priority=True),
    Binding("/", "lookup", "Lookup", priority=True),
    Binding("?", "help", "Help", priority=True),
    Binding("1", "jump_1", "", priority=True),
    Binding("2", "jump_2", "", priority=True),
    Binding("3", "jump_3", "", priority=True),
    Binding("4", "jump_4", "", priority=True),
    Binding("5", "jump_5", "", priority=True),
    Binding("6", "jump_6", "", priority=True),
    Binding("7", "jump_7", "", priority=True),
    Binding("8", "jump_8", "", priority=True),
    Binding("9", "jump_9", "", priority=True),
]

_VIEWER_ACTIONS = frozenset(binding.action for binding in VIEWER_BINDINGS)

HELP_GROUPS = (
    (
        "Navigation",
        (
            ("up / down / j / k", "scroll"),
            ("PageUp / PageDown / Space / b", "page"),
            ("Home / End / g / G", "top / bottom"),
            ("[ / ]", "previous / next entry"),
            ("n / v / a / r", "cycle noun / verb / adjective / adverb"),
            ("1..9", "entry shortcut"),
            ("/", "look up another word"),
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
    padding: 1 1 3 1;
}


.semantic-section, .definitions-section, .sense-view {
    width: 1fr;
    height: auto;
}


.semantic-row {
    width: 100%;
    height: auto;
    overflow-x: hidden;
}



.semantic-content {
    width: 1fr;
    height: auto;
}



.semantic-row-content {
    width: 1fr;
    min-width: 0;
    height: auto;
    overflow-x: hidden;
}


.read-control {
    width: 3;
    min-width: 3;
    max-width: 3;
    height: 1;
    margin-left: 1;
    padding: 0;
    content-align: center middle;
}




.read-control:focus {
    text-style: reverse;
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

LookupScreen {
    align: center middle;
    background: $background 70%;
}

#lookup-dialog {
    width: 80%;
    max-width: 80;
    height: auto;
    max-height: 80%;
    padding: 1 2;
    border: round $accent;
    background: $surface;
}

#lookup-title {
    height: auto;
    padding-bottom: 1;
}

#lookup-options {
    height: auto;
    max-height: 12;
    min-height: 1;
    margin-top: 1;
}

#lookup-status {
    height: auto;
    padding-top: 1;
    color: $text-muted;
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


class ReadRequested(Message):
    def __init__(self, request: SpeechRequest) -> None:
        super().__init__()
        self.request = request


class ReadControl(Static):
    can_focus = True
    BINDINGS = [Binding("enter", "activate", "Read", show=False)]

    def __init__(self, request: SpeechRequest, **kwargs: object) -> None:
        super().__init__("▶", classes="read-control", markup=False, **kwargs)
        self.request = request

    def action_activate(self) -> None:
        self.post_message(ReadRequested(self.request))

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.action_activate()


def _request(
    config: TTSConfig,
    entry: DictionaryEntry,
    entry_index: int,
    kind: str,
    text: str,
    *,
    sense_index: int | None = None,
    example_index: int | None = None,
) -> SpeechRequest | None:
    if not config.enabled:
        return None
    return SpeechRequest(
        id=f"entry-{entry_index}-{kind}-{sense_index}-{example_index}",
        text=text,
        language=config.language,
        kind=kind,
        entry_index=entry_index,
        sense_index=sense_index,
        example_index=example_index,
    )


class SemanticSection(Vertical):
    def __init__(
        self,
        title: str,
        body: Text,
        request: SpeechRequest | None = None,
    ) -> None:
        super().__init__(classes="semantic-section")
        self.title = title
        self.body = body
        self.request = request

    def compose(self) -> ComposeResult:
        with Horizontal(classes="semantic-row"):
            yield Static(Text(self.title, style="bold cyan"), classes="semantic-row-content")
            if self.request is not None:
                yield ReadControl(self.request)
        yield Static(self.body, classes="semantic-content")


class SenseView(Vertical):
    def __init__(
        self,
        sense: Sense,
        entry: DictionaryEntry,
        entry_index: int,
        sense_index: int,
        config: TTSConfig,
    ) -> None:
        super().__init__(classes="sense-view")
        self.sense = sense
        self.entry = entry
        self.entry_index = entry_index
        self.sense_index = sense_index
        self.config = config

    def compose(self) -> ComposeResult:
        definition = Text(f"{self.sense_index + 1}. {spoken_definition(self.sense)}")
        definition_request = _request(
            self.config,
            self.entry,
            self.entry_index,
            "definition",
            spoken_definition(self.sense),
            sense_index=self.sense_index,
        )
        with Horizontal(classes="semantic-row"):
            yield Static(definition, classes="semantic-row-content")
            if definition_request is not None:
                yield ReadControl(definition_request)
        for example_index, example in enumerate(self.sense.examples):
            example_request = _request(
                self.config,
                self.entry,
                self.entry_index,
                "example",
                example.text,
                sense_index=self.sense_index,
                example_index=example_index,
            )
            with Horizontal(classes="semantic-row"):
                # Italic glyphs may overhang their terminal cell and be erased when
                # Textual paints the adjacent control gutter. Dim text remains portable.
                yield Static(
                    Text(f"“{example.text}”", style="dim"),
                    classes="semantic-row-content",
                )
                if example_request is not None:
                    yield ReadControl(example_request)
        if self.sense.tags:
            yield Static(Text(", ".join(self.sense.tags), style="dim"), classes="semantic-content")
        if self.sense.topics:
            yield Static(
                Text(f"topics: {', '.join(self.sense.topics)}", style="dim"),
                classes="semantic-content",
            )


class DefinitionsSection(Vertical):
    def __init__(self, entry: DictionaryEntry, entry_index: int, config: TTSConfig) -> None:
        super().__init__(classes="definitions-section")
        self.entry = entry
        self.entry_index = entry_index
        self.config = config

    def compose(self) -> ComposeResult:
        definitions_request = _request(
            self.config,
            self.entry,
            self.entry_index,
            "definitions",
            spoken_definitions(self.entry),
        )
        with Horizontal(classes="semantic-row"):
            yield Static(Text("Definitions", style="bold cyan"), classes="semantic-row-content")
            if definitions_request is not None:
                yield ReadControl(definitions_request)
        for sense_index, sense in enumerate(self.entry.senses):
            yield SenseView(sense, self.entry, self.entry_index, sense_index, self.config)


class DictionaryEntryView(Vertical):
    """One complete Lexhint dictionary entry made from semantic child widgets."""

    def __init__(
        self, entry: DictionaryEntry, index: int, tts_config: TTSConfig | None = None
    ) -> None:
        super().__init__(id=f"entry-{index}", classes="dictionary-entry")
        self.entry = entry
        self.index = index
        self.tts_config = tts_config or TTSConfig()

    def compose(self) -> ComposeResult:
        yield Static(_entry_header(self.entry), markup=False, classes="entry-header")
        if self.entry.pronunciations:
            yield SemanticSection(
                "Pronunciation",
                Text("\n".join(item.ipa for item in self.entry.pronunciations), style="dim"),
                _request(self.tts_config, self.entry, self.index, "headword", self.entry.word),
            )
        if self.entry.etymology:
            yield SemanticSection(
                "Etymology",
                Text(self.entry.etymology),
                _request(
                    self.tts_config, self.entry, self.index, "etymology", self.entry.etymology
                ),
            )
        if self.entry.forms:
            yield SemanticSection(
                "Forms",
                Text(spoken_forms(self.entry)),
                _request(
                    self.tts_config, self.entry, self.index, "forms", spoken_forms(self.entry)
                ),
            )
        yield DefinitionsSection(self.entry, self.index, self.tts_config)


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


class LookupScreen(ModalScreen[str | None]):
    """Modal, hotkey-isolated headword lookup screen."""

    BINDINGS = [
        Binding("up", "candidate_up", "", priority=True),
        Binding("down", "candidate_down", "", priority=True),
        Binding("pageup", "candidate_page_up", "", priority=True),
        Binding("pagedown", "candidate_page_down", "", priority=True),
    ]

    def __init__(
        self,
        backend: DictionaryBackend,
        *,
        seed: str = "",
        error: str | None = None,
    ) -> None:
        super().__init__()
        self.backend = backend
        self.seed = seed
        self.initial_error = error
        self._initial_error_active = error is not None
        self._refresh_timer: Timer | None = None
        self._generation = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="lookup-dialog"):
            yield Static("Look up a word", id="lookup-title")
            yield Input(value=self.seed, placeholder="Type a word", id="lookup-input")
            yield OptionList(id="lookup-options")
            yield Static("", id="lookup-status")

    def on_mount(self) -> None:
        input_widget = self.query_one("#lookup-input", Input)
        input_widget.cursor_position = len(input_widget.value)
        input_widget.focus()
        if self.initial_error:
            self._set_status(self.initial_error, error=True)
        elif input_widget.value.strip():
            self._schedule_refresh(input_widget.value.strip())
        else:
            self._set_status("Type a word to search.")

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#lookup-status", Static)
        status.update(Text(message, style="red" if error else "dim"))

    def _schedule_refresh(self, query: str) -> None:
        self._generation += 1
        generation = self._generation
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_timer(
            0.1,
            lambda: self._refresh_completions(query, generation),
        )

    def _refresh_completions(self, query: str, generation: int) -> None:
        current_query = self.query_one("#lookup-input", Input).value.strip()
        if generation != self._generation or query != current_query:
            return
        try:
            completions = tuple(self.backend.complete(query, limit=20))
        except Exception as exc:
            self.query_one("#lookup-options", OptionList).clear_options()
            self._set_status(f"Lookup error: {exc}", error=True)
            return
        options = self.query_one("#lookup-options", OptionList)
        options.clear_options()
        if completions:
            options.add_options(Option(word, id=word) for word in completions)
            options.highlighted = 0
            self._set_status("up/down choose   Enter open   Esc cancel")
        else:
            self._set_status(f'No completions. Press Enter to try an exact lookup for "{query}".')

    def _selected_word(self) -> str | None:
        options = self.query_one("#lookup-options", OptionList)
        if options.highlighted is None:
            return None
        option = options.get_option_at_index(options.highlighted)
        return option.id or str(option.prompt)

    def _submit(self) -> None:
        input_widget = self.query_one("#lookup-input", Input)
        typed = input_widget.value.strip()
        selected = self._selected_word()
        if selected:
            self.dismiss(selected)
            return
        if typed:
            self.dismiss(typed)
            return
        self._set_status("Type a word to search.")

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()
        if self._initial_error_active and query == self.seed.strip():
            if self.initial_error:
                self._set_status(self.initial_error, error=True)
            return
        self._initial_error_active = False
        options = self.query_one("#lookup-options", OptionList)
        options.clear_options()
        if not query:
            self._generation += 1
            if self._refresh_timer is not None:
                self._refresh_timer.stop()
            self._set_status("Type a word to search.")
            return
        self._set_status("Searching...")
        self._schedule_refresh(query)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._submit()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id or str(event.option.prompt))

    def action_candidate_up(self) -> None:
        self.query_one("#lookup-options", OptionList).action_cursor_up()

    def action_candidate_down(self) -> None:
        self.query_one("#lookup-options", OptionList).action_cursor_down()

    def action_candidate_page_up(self) -> None:
        self.query_one("#lookup-options", OptionList).action_page_up()

    def action_candidate_page_down(self) -> None:
        self.query_one("#lookup-options", OptionList).action_page_down()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)


class ViewerFooter(Footer):
    can_focus = True


class EntryScroll(VerticalScroll):
    can_focus = True

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        if self.app.is_mounted:
            self.app.call_after_refresh(self.app._sync_active_index)


class _StaticBackend:
    def __init__(self, word: str, entries: Sequence[DictionaryEntry]) -> None:
        self.word = word
        self._entries = tuple(entries)

    def entries(self, word: str) -> tuple[DictionaryEntry, ...]:
        return self._entries if word == self.word else ()

    def complete(self, prefix: str, *, limit: int = 20) -> tuple[str, ...]:
        return ()


class DictionaryViewerApp(App[None]):
    """Full-screen viewer and reusable interactive dictionary session."""

    CSS = CSS
    BINDINGS = VIEWER_BINDINGS

    def __init__(
        self,
        backend_or_word: DictionaryBackend | str,
        entries: Sequence[DictionaryEntry] = (),
        *,
        word: str | None = None,
        width: int | None = None,
        no_color: bool = False,
        tts_config: TTSConfig | None = None,
        open_lookup_on_mount: bool = False,
    ) -> None:
        super().__init__()
        if isinstance(backend_or_word, str):
            self.backend: DictionaryBackend = _StaticBackend(backend_or_word, entries)
            self.word = backend_or_word
        else:
            self.backend = backend_or_word
            self.word = word
        self.entries = tuple(entries)
        self.width = width
        self.no_color = no_color
        self.tts_config = tts_config or TTSConfig()
        self.open_lookup_on_mount = open_lookup_on_mount
        self._speech_service: PyKokoroSpeechService | None = None
        self._speech_generation = 0
        self._speech_lock = threading.Lock()
        self._speech_workers: dict[object, int] = {}
        self._active_index = 0
        self._entry_offsets: tuple[float, ...] = ()
        self._entry_heights: tuple[int, ...] = ()
        self._programmatic_scroll_y: float | None = None
        self._pos_to_indices: dict[str, tuple[int, ...]] = {}
        self._reindex_entries()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if isinstance(self.screen, (LookupScreen, HelpScreen)) and action in _VIEWER_ACTIONS:
            return False
        return super().check_action(action, parameters)

    def _get_speech_service(self) -> PyKokoroSpeechService:
        if self._speech_service is None:
            self._speech_service = PyKokoroSpeechService(self.tts_config)
        return self._speech_service

    def on_read_requested(self, message: ReadRequested) -> None:
        message.stop()
        if not self.tts_config.enabled or isinstance(self.screen, (LookupScreen, HelpScreen)):
            return
        self._speech_generation += 1
        generation = self._speech_generation
        self.notify("Loading TTS model…", timeout=2)
        worker = self.run_worker(
            lambda: self._speak_in_worker(message.request, generation),
            name=f"speech-{generation}",
            group="speech",
            exit_on_error=False,
            thread=True,
        )
        self._speech_workers[worker] = generation

    def _speak_in_worker(self, request: SpeechRequest, generation: int) -> None:
        with self._speech_lock:
            if generation != self._speech_generation:
                return
            self._get_speech_service().speak(request)

    def on_worker_state_changed(self, event) -> None:
        worker = event.worker
        if worker not in self._speech_workers:
            return
        generation = (
            self._speech_workers.pop(worker)
            if event.state.name in {"SUCCESS", "ERROR", "CANCELLED"}
            else self._speech_workers[worker]
        )
        if event.state.name != "ERROR" or generation != self._speech_generation:
            return
        error = worker.error
        if isinstance(
            error,
            (SpeechUnavailable, SpeechSynthesisError, SpeechPlaybackError, SpeechError),
        ):
            self.notify(str(error), severity="error")
        elif error is not None:
            self.notify(f"TTS failed: {error}", severity="error")

    def on_unmount(self) -> None:
        if self._speech_service is not None:
            self._speech_service.close()
            self._speech_service = None

    def _reindex_entries(self) -> None:
        pos_to_indices: defaultdict[str, list[int]] = defaultdict(list)
        for index, entry in enumerate(self.entries):
            pos_to_indices[normalize_pos(entry.pos)].append(index)
        self._pos_to_indices = {pos: tuple(indices) for pos, indices in pos_to_indices.items()}

    def _entry_scroll(self) -> EntryScroll:
        return self.query_one("#entry-scroll", EntryScroll)

    def action_scroll_line_down(self) -> None:
        self._entry_scroll().scroll_down(animate=False, immediate=True)

    def action_scroll_line_up(self) -> None:
        self._entry_scroll().scroll_up(animate=False, immediate=True)

    def action_scroll_page_down(self) -> None:
        self._entry_scroll().scroll_page_down(animate=False)

    def action_scroll_page_up(self) -> None:
        self._entry_scroll().scroll_page_up(animate=False)

    def action_scroll_document_home(self) -> None:
        self._entry_scroll().scroll_home(animate=False, immediate=True)

    def action_scroll_document_end(self) -> None:
        self._entry_scroll().scroll_end(animate=False, immediate=True)

    def compose(self) -> ComposeResult:
        yield Static(self._navigation_text(), id="entry-nav", markup=False)
        with EntryScroll(id="entry-scroll"):
            for index, entry in enumerate(self.entries):
                yield DictionaryEntryView(entry, index, self.tts_config)
        yield ViewerFooter()

    def on_mount(self) -> None:
        scroll = self.query_one("#entry-scroll", EntryScroll)
        if self.width is not None:
            scroll.styles.width = self.width
        scroll.scroll_home(animate=False, immediate=True)
        scroll.focus(scroll_visible=False)
        self._capture_entry_geometry(scroll)
        self._sync_active_index()
        self._update_navigation()
        if self.open_lookup_on_mount:
            self.call_after_refresh(self.action_lookup)

    def _navigation_text(self) -> Text:
        if not self.word:
            return Text("dictterm  lookup mode")
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
            "   ".join(f"{pos} x{count}" for pos, count in counts.items()),
            style=NAV_DIM_STYLE,
        )
        return text

    def _update_navigation(self) -> None:
        self.query_one("#entry-nav", Static).update(self._navigation_text())

    def _current_entry_index(self) -> int:
        scroll = self.query_one("#entry-scroll", EntryScroll)
        if not self._entry_heights or not all(self._entry_heights):
            self._capture_entry_geometry(scroll)
        if len(self._entry_offsets) == len(self.entries):
            scroll_top = scroll.scroll_y
            if scroll_top >= scroll.max_scroll_y:
                viewport_bottom = scroll_top + scroll.region.height
                visible_at_bottom = [
                    index
                    for index, offset in enumerate(self._entry_offsets)
                    if offset < viewport_bottom
                ]
                if visible_at_bottom:
                    return max(visible_at_bottom)
            for index, (offset, height) in enumerate(
                zip(self._entry_offsets, self._entry_heights, strict=True)
            ):
                if scroll_top < offset + height:
                    return index
            return len(self._entry_offsets) - 1
        viewport_top = scroll.region.y
        views = list(self.query(DictionaryEntryView))
        visible = [view for view in views if view.region.bottom > viewport_top]
        if visible:
            return min(visible, key=lambda view: abs(view.region.y - viewport_top)).index
        return self._active_index

    def _capture_entry_geometry(self, scroll: EntryScroll) -> None:
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
        scroll = self.query_one("#entry-scroll", EntryScroll)
        if self._programmatic_scroll_y is not None:
            if scroll.scroll_y == self._programmatic_scroll_y:
                self._programmatic_scroll_y = None
                return
            self._programmatic_scroll_y = None
        index = self._current_entry_index()
        if index != self._active_index:
            self._active_index = index
            self._update_navigation()

    def _jump_to_entry(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        target = self.query_one(f"#entry-{index}", DictionaryEntryView)
        scroll = self.query_one("#entry-scroll", EntryScroll)
        scroll.scroll_to_widget(target, animate=False, top=True, immediate=True)
        self._programmatic_scroll_y = scroll.scroll_y
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

    def _mount_replacement(self, entries: tuple[DictionaryEntry, ...]) -> None:
        scroll = self.query_one("#entry-scroll", EntryScroll)
        scroll.mount(
            *(
                DictionaryEntryView(entry, index, self.tts_config)
                for index, entry in enumerate(entries)
            )
        )
        scroll.scroll_home(animate=False, immediate=True)
        self._entry_offsets = ()
        self._entry_heights = ()
        self.call_after_refresh(self._finish_replacement)

    def _finish_replacement(self) -> None:
        scroll = self.query_one("#entry-scroll", EntryScroll)
        scroll.scroll_home(animate=False, immediate=True)
        self._capture_entry_geometry(scroll)
        self._update_navigation()
        self._sync_active_index()
        scroll.focus(scroll_visible=False)

    def _set_result(self, word: str, entries: Sequence[DictionaryEntry]) -> None:
        self.word = word
        self.entries = tuple(entries)
        self._active_index = 0
        self._reindex_entries()
        self._entry_offsets = ()
        self._entry_heights = ()
        self._update_navigation()
        scroll = self.query_one("#entry-scroll", EntryScroll)
        old_views = list(self.query(DictionaryEntryView))
        scroll.remove_children(old_views)
        self.call_after_refresh(lambda: self._mount_replacement(self.entries))

    def _reopen_lookup(self, seed: str, error: str) -> None:
        self.push_screen(
            LookupScreen(self.backend, seed=seed, error=error),
            self._on_lookup_selected,
        )

    def _on_lookup_selected(self, selected: str | None) -> None:
        if selected is None:
            return
        try:
            entries = self.backend.entries(selected)
        except Exception as exc:
            self._reopen_lookup(selected, f"Lookup error: {exc}")
            return
        if not entries:
            self._reopen_lookup(selected, f'No dictionary entry found for "{selected}".')
            return
        self._set_result(selected, entries)

    def action_lookup(self) -> None:
        self.push_screen(
            LookupScreen(self.backend, seed=self.word or ""),
            self._on_lookup_selected,
        )

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
    backend: DictionaryBackend,
    *,
    word: str | None = None,
    entries: Sequence[DictionaryEntry] = (),
    width: int | None = None,
    no_color: bool = False,
    tts_config: TTSConfig | None = None,
    open_lookup_on_mount: bool = False,
) -> None:
    app = DictionaryViewerApp(
        backend,
        entries,
        word=word,
        width=width,
        no_color=no_color,
        tts_config=tts_config,
        open_lookup_on_mount=open_lookup_on_mount,
    )
    with _temporary_no_color(no_color):
        app.run()
