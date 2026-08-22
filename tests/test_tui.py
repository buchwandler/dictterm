from __future__ import annotations

import asyncio
import os

from lexhint import DictionaryEntry, Sense
from textual.binding import Binding

from dictterm.tui import (
    VIEWER_BINDINGS,
    DictionaryEntryView,
    DictionaryViewerApp,
    EntryScroll,
    _normalize_pos,
    _temporary_no_color,
)


def _entries(*parts_of_speech: str) -> tuple[DictionaryEntry, ...]:
    return tuple(
        DictionaryEntry(
            word="love",
            pos=pos,
            senses=(Sense(glosses=(f"A {pos} definition.",)),),
        )
        for pos in parts_of_speech
    )


def test_normalize_pos() -> None:
    assert _normalize_pos(" Proper_Noun ") == "proper noun"
    assert _normalize_pos("proper-noun") == "proper noun"


def test_viewer_opens_at_first_entry() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries("noun", "verb"))
        async with app.run_test(size=(80, 12)):
            scroll = app.query_one("#entry-scroll", EntryScroll)
            first = app.query_one("#entry-0", DictionaryEntryView)
            assert app.screen.focused is scroll
            assert scroll.scroll_y == 0
            assert first.region.y == scroll.region.y
            assert app._active_index == 0

    asyncio.run(scenario())


def test_pos_and_index_jumps() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries("noun", "verb", "interjection"))
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("v")
            assert app._active_index == 1
            await pilot.press("n")
            assert app._active_index == 0
            await pilot.press("3")
            assert app._active_index == 2

    asyncio.run(scenario())


def test_previous_and_next_entry_boundaries() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries("noun", "verb", "interjection"))
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("]")
            assert app._active_index == 1
            await pilot.press("]")
            assert app._active_index == 2
            await pilot.press("]")
            assert app._active_index == 2
            await pilot.press("[")
            assert app._active_index == 1

    asyncio.run(scenario())


def test_missing_pos_is_harmless() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries("noun"))
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("v")
            assert app._active_index == 0
            assert app.query_one("#entry-0", DictionaryEntryView).entry.pos == "noun"

    asyncio.run(scenario())


def test_viewer_bindings_are_priority_binding_objects() -> None:
    assert all(isinstance(binding, Binding) for binding in VIEWER_BINDINGS)
    assert all(binding.priority for binding in VIEWER_BINDINGS)


def test_viewer_scroll_bindings_are_priority_and_focus_independent() -> None:
    bindings = {binding.action: binding for binding in VIEWER_BINDINGS}
    expected = {
        "scroll_line_up": "up,k",
        "scroll_line_down": "down,j",
        "scroll_page_up": "pageup,b",
        "scroll_page_down": "pagedown,space",
        "scroll_document_home": "home,g",
        "scroll_document_end": "end,G",
    }
    assert {action: bindings[action].key for action in expected} == expected
    assert all(bindings[action].priority for action in expected)
    assert not any(binding.action in expected for binding in EntryScroll.BINDINGS)


def test_line_scroll_keys_move_repeatedly_at_mobile_size() -> None:
    long_text = " ".join(["A long definition."] * 300)
    entries = (
        DictionaryEntry(
            word="love",
            pos="noun",
            senses=(Sense(glosses=(long_text,)),),
        ),
    )

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(40, 10)) as pilot:
            scroll = app.query_one("#entry-scroll", EntryScroll)
            assert app.screen.focused is scroll
            assert scroll.max_scroll_y > 0

            for _ in range(30):
                await pilot.press("down")
            assert 1 < scroll.scroll_y <= scroll.max_scroll_y
            assert scroll.vertical_scrollbar.position == scroll.scroll_y

            await pilot.press("home")
            assert scroll.scroll_y == 0
            for _ in range(30):
                await pilot.press("j")
            assert 1 < scroll.scroll_y <= scroll.max_scroll_y

            await pilot.press("end")
            assert scroll.scroll_y == scroll.max_scroll_y
            for _ in range(30):
                await pilot.press("k")
            assert 0 <= scroll.scroll_y < scroll.max_scroll_y

    asyncio.run(scenario())


def test_page_and_home_end_keys_work_at_mobile_size() -> None:
    long_text = " ".join(["A long definition."] * 150)
    entries = (
        DictionaryEntry(
            word="love",
            pos="noun",
            senses=(Sense(glosses=(long_text,)),),
        ),
    )

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(40, 10)) as pilot:
            scroll = app.query_one("#entry-scroll", EntryScroll)
            await pilot.press("pagedown")
            first = scroll.scroll_y
            assert first > 0
            await pilot.press("space")
            assert scroll.scroll_y >= first
            await pilot.press("pageup")
            assert scroll.scroll_y < scroll.max_scroll_y

            await pilot.press("end")
            assert scroll.scroll_y == scroll.max_scroll_y
            await pilot.press("g")
            assert scroll.scroll_y == 0
            await pilot.press("G")
            assert scroll.scroll_y == scroll.max_scroll_y
            await pilot.press("home")
            assert scroll.scroll_y == 0

    asyncio.run(scenario())


def test_scroll_keys_change_scroll_position() -> None:
    long_text = " ".join(["A long definition."] * 100)
    entries = (
        DictionaryEntry(
            word="love",
            pos="noun",
            senses=(Sense(glosses=(long_text,)),),
        ),
    )

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(60, 12)) as pilot:
            scroll = app.query_one("#entry-scroll")
            await pilot.press("pagedown")
            assert scroll.scroll_y > 0
            await pilot.press("home")
            assert scroll.scroll_y == 0
            await pilot.press("j")
            assert scroll.scroll_y > 0

    asyncio.run(scenario())


def test_q_quits() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries("noun"))
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("q")
            assert not app.is_running

    asyncio.run(scenario())


def test_no_color_environment_is_restored(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    with _temporary_no_color(True):
        assert os.environ["NO_COLOR"] == "1"
    assert "NO_COLOR" not in os.environ
