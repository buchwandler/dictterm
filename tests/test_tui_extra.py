from __future__ import annotations

import asyncio
import os

from lexhint import DictionaryEntry, Sense
from textual.widgets import Footer

from dictterm.tui import DictionaryViewerApp, EntryScroll, _temporary_no_color


def _entries(*parts_of_speech: str) -> tuple[DictionaryEntry, ...]:
    return tuple(
        DictionaryEntry(
            word="love",
            pos=pos,
            senses=(Sense(glosses=(f"A {pos} definition.",)),),
        )
        for pos in parts_of_speech
    )


def test_pos_jumps_cycle_and_support_adjective_adverb() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp(
            "love",
            _entries("noun", "noun", "verb", "verb", "adjective", "adverb"),
        )
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("v")
            assert app._active_index == 2
            await pilot.press("v")
            assert app._active_index == 3
            await pilot.press("v")
            assert app._active_index == 2
            await pilot.press("n")
            assert app._active_index == 0
            await pilot.press("n")
            assert app._active_index == 1
            await pilot.press("a")
            assert app._active_index == 4
            await pilot.press("r")
            assert app._active_index == 5

    asyncio.run(scenario())


def test_native_home_end_and_page_keys() -> None:
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
            page_position = scroll.scroll_y
            await pilot.press("space")
            assert scroll.scroll_y >= page_position
            await pilot.press("pageup")
            assert scroll.scroll_y < scroll.max_scroll_y
            await pilot.press("b")
            assert scroll.scroll_y >= 0

            await pilot.press("home")
            assert scroll.scroll_y == 0
            await pilot.press("g")
            assert scroll.scroll_y == 0
            await pilot.press("end")
            assert scroll.scroll_y == scroll.max_scroll_y
            await pilot.press("G")
            assert scroll.scroll_y == scroll.max_scroll_y
            await pilot.press("k")
            assert scroll.scroll_y < scroll.max_scroll_y
            await pilot.press("j")
            assert scroll.scroll_y > 0

    asyncio.run(scenario())



def test_scrolling_remains_available_when_footer_has_focus() -> None:
    long_text = " ".join(["A long definition."] * 240)
    entries = (DictionaryEntry("love", "noun", (Sense(glosses=(long_text,)),)),)

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(40, 10)) as pilot:
            scroll = app.query_one("#entry-scroll", EntryScroll)
            footer = app.query_one(Footer)
            app.screen.set_focus(footer)
            assert app.screen.focused is footer

            before = scroll.scroll_y
            await pilot.press("down")
            assert scroll.scroll_y > before
            before = scroll.scroll_y
            await pilot.press("j")
            assert scroll.scroll_y > before

            before = scroll.scroll_y
            await pilot.press("pagedown")
            assert scroll.scroll_y > before
            before = scroll.scroll_y
            await pilot.press("pageup")
            assert scroll.scroll_y < before

            await pilot.press("home")
            assert scroll.scroll_y == 0
            await pilot.press("end")
            assert scroll.scroll_y == scroll.max_scroll_y

    asyncio.run(scenario())


def test_line_scroll_stays_within_first_entry_before_boundary() -> None:
    first_text = " ".join(["First entry definition."] * 220)
    entries = (
        DictionaryEntry("love", "noun", (Sense(glosses=(first_text,)),)),
        DictionaryEntry("love", "verb", (Sense(glosses=("Second entry.",)),)),
    )

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(40, 10)) as pilot:
            scroll = app.query_one("#entry-scroll", EntryScroll)
            await pilot.pause()
            app._capture_entry_geometry(scroll)
            second_entry_offset = app._entry_offsets[1]
            assert second_entry_offset > 3

            await pilot.press("home")
            positions = []
            for _ in range(3):
                await pilot.press("down")
                positions.append(scroll.scroll_y)
            assert 0 < positions[0] < positions[1] < positions[2] < second_entry_offset
            assert app._active_index == 0

            attempts = 0
            while app._active_index == 0 and attempts < int(scroll.max_scroll_y) + 5:
                await pilot.press("down")
                attempts += 1
            assert app._active_index == 1
            assert scroll.scroll_y >= second_entry_offset

    asyncio.run(scenario())

def test_manual_scrolling_updates_header_active_entry() -> None:
    long_text = " ".join(["A long definition."] * 120)
    entries = (
        DictionaryEntry("love", "noun", (Sense(glosses=(long_text,)),)),
        DictionaryEntry("love", "verb", (Sense(glosses=("To cherish.",)),)),
    )

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(60, 12)) as pilot:
            for _ in range(20):
                await pilot.press("pagedown")
            assert app._active_index == 1
            header = app.query_one("#entry-nav").render()
            assert "entry 2/2" in header.plain
            assert "VERB" in header.plain

    asyncio.run(scenario())


def test_help_overlay_isolates_background_scrolling() -> None:
    long_text = " ".join(["A long definition."] * 180)
    entries = (DictionaryEntry("love", "noun", (Sense(glosses=(long_text,)),)),)

    async def scenario() -> None:
        app = DictionaryViewerApp("love", entries)
        async with app.run_test(size=(40, 10)) as pilot:
            scroll = app.query_one("#entry-scroll", EntryScroll)
            await pilot.press("pagedown")
            before = scroll.scroll_y
            await pilot.press("?")
            help_content = app.screen.query_one("#help-content")
            assert "n / v / a / r" in help_content.render().plain
            assert "PageUp / PageDown" in help_content.render().plain

            scroll_keys = (
                "up", "down", "pageup", "pagedown", "home", "end",
                "j", "k", "space", "b", "g", "G",
            )
            for key in scroll_keys:
                await pilot.press(key)
            assert scroll.scroll_y == before

            await pilot.press("escape")
            assert not app.screen.query("#help-content")
            await pilot.press("home")
            await pilot.press("down")
            assert scroll.scroll_y > 0

    asyncio.run(scenario())


def test_many_entry_header_is_compact_and_stable() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries(*(["noun"] * 12)))
        async with app.run_test(size=(60, 12)):
            header = app.query_one("#entry-nav").render()
            assert "entry 1/12" in header.plain
            assert "NOUN" in header.plain

    asyncio.run(scenario())


def test_existing_no_color_environment_is_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "existing")
    with _temporary_no_color(True):
        assert os.environ["NO_COLOR"] == "existing"
    assert os.environ["NO_COLOR"] == "existing"
