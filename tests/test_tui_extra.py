from __future__ import annotations

import asyncio
import os

from lexhint import DictionaryEntry, Sense

from dictterm.tui import DictionaryViewerApp, _temporary_no_color


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


def test_help_overlay_uses_current_bindings_and_closes() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("love", _entries("noun"))
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("?")
            help_content = app.screen.query_one("#help-content")
            assert "n / v / a / r" in help_content.render().plain
            assert "PageUp / PageDown" in help_content.render().plain
            await pilot.press("escape")
            assert not app.screen.query("#help-content")

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
