from __future__ import annotations

import asyncio

from lexhint import DictionaryEntry, Sense
from textual.widgets import Input, OptionList

from dictterm.tui import DictionaryEntryView, DictionaryViewerApp, LookupScreen


def _entry(word: str, pos: str = "noun", long: bool = False) -> DictionaryEntry:
    gloss = " ".join(["A long definition."] * 100) if long else f"A {word} definition."
    return DictionaryEntry(
        word=word,
        pos=pos,
        senses=(Sense(glosses=(gloss,)),),
    )


class FakeBackend:
    def __init__(self) -> None:
        self.lookup_calls: list[str] = []
        self.suggest_calls: list[str] = []
        self._entries = {
            "love": (_entry("love"),),
            "lover": (_entry("lover", "verb"),),
            "lovely": (_entry("lovely", "adjective"),),
            "loving": (_entry("loving"),),
            "long": (_entry("long", long=True),),
        }
        self._suggestions = {
            "lov": ("love", "lover", "lovely"),
            "love": ("love", "lover"),
            "lover": ("lover", "lovely"),
            "lovely": ("lovely",),
        }

    def entries(self, word: str) -> tuple[DictionaryEntry, ...]:
        self.lookup_calls.append(word)
        return self._entries.get(word, ())

    def suggest(self, query: str, *, limit: int = 20) -> tuple[str, ...]:
        self.suggest_calls.append(query)
        return self._suggestions.get(query, ())[:limit]


async def _open_lookup(pilot) -> LookupScreen:
    await pilot.press("/")
    await pilot.pause()
    assert isinstance(pilot.app.screen, LookupScreen)
    return pilot.app.screen


async def _replace_input(screen: LookupScreen, pilot, value: str) -> Input:
    input_widget = screen.query_one("#lookup-input", Input)
    input_widget.value = ""
    await pilot.pause()
    for character in value:
        await pilot.press(character)
    await pilot.pause(0.15)
    return input_widget


def test_lookup_modal_focuses_input_and_filters_viewer_bindings() -> None:
    async def scenario() -> None:
        backend = FakeBackend()
        app = DictionaryViewerApp(backend, (_entry("love"),), word="love")
        async with app.run_test(size=(80, 20)) as pilot:
            screen = await _open_lookup(pilot)
            input_widget = await _replace_input(screen, pilot, "queryjavelinvariant")
            assert input_widget.has_focus
            assert input_widget.value == "queryjavelinvariant"
            assert app.is_running
            assert app.word == "love"

    asyncio.run(scenario())


def test_live_suggestions_navigation_and_enter_replace_result() -> None:
    async def scenario() -> None:
        backend = FakeBackend()
        app = DictionaryViewerApp(backend, (_entry("love"),), word="love")
        async with app.run_test(size=(80, 20)) as pilot:
            screen = await _open_lookup(pilot)
            await _replace_input(screen, pilot, "lov")
            options = screen.query_one("#lookup-options", OptionList)
            assert options.option_count == 3
            assert options.highlighted == 0
            await pilot.press("down")
            assert options.highlighted == 1
            await pilot.press("enter")
            await pilot.pause()
            assert app.word == "lover"
            assert backend.lookup_calls[-1] == "lover"
            assert len(app.query(DictionaryEntryView)) == 1
            assert app.query_one("#entry-0", DictionaryEntryView).entry.word == "lover"

    asyncio.run(scenario())


def test_escape_preserves_current_result_and_missing_exact_reopens_lookup() -> None:
    async def scenario() -> None:
        backend = FakeBackend()
        app = DictionaryViewerApp(backend, (_entry("love", long=True),), word="love")
        async with app.run_test(size=(80, 12)) as pilot:
            scroll = app.query_one("#entry-scroll")
            await pilot.press("pagedown")
            before = scroll.scroll_y
            await _open_lookup(pilot)
            await pilot.press("escape")
            await pilot.pause()
            assert app.word == "love"
            assert scroll.scroll_y == before

            screen = await _open_lookup(pilot)
            await _replace_input(screen, pilot, "missing")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, LookupScreen)
            assert app.word == "love"
            status = app.screen.query_one("#lookup-status").render().plain
            assert "No dictionary entry found" in status

    asyncio.run(scenario())


def test_repeated_lookup_replaces_widgets_and_resets_scroll() -> None:
    async def scenario() -> None:
        backend = FakeBackend()
        app = DictionaryViewerApp(backend, (_entry("love"),), word="love")
        async with app.run_test(size=(80, 12)) as pilot:
            for word in ("lover", "lovely", "love"):
                screen = await _open_lookup(pilot)
                await _replace_input(screen, pilot, word)
                await pilot.press("enter")
                await pilot.pause()
                assert app.word == word
                assert app._active_index == 0
                assert app.query_one("#entry-scroll").scroll_y == 0
                assert len(app.query(DictionaryEntryView)) == 1

    asyncio.run(scenario())


def test_post_lookup_long_result_can_scroll() -> None:
    async def scenario() -> None:
        backend = FakeBackend()
        app = DictionaryViewerApp(backend, (_entry("love"),), word="love")
        async with app.run_test(size=(60, 12)) as pilot:
            screen = await _open_lookup(pilot)
            await _replace_input(screen, pilot, "long")
            await pilot.press("enter")
            await pilot.pause()
            scroll = app.query_one("#entry-scroll")
            await pilot.press("down")
            assert app.word == "long"
            assert scroll.scroll_y > 0
            await pilot.press("home")
            assert scroll.scroll_y == 0
            await pilot.press("j")
            assert scroll.scroll_y > 0
            await pilot.press("end")
            assert scroll.scroll_y == scroll.max_scroll_y
            assert len(app.query(DictionaryEntryView)) == 1

    asyncio.run(scenario())


def test_bare_cli_launches_lookup_in_tty(monkeypatch) -> None:
    from dictterm import cli

    class TTY:
        def isatty(self) -> bool:
            return True

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(cli.sys, "stdin", TTY())
    monkeypatch.setattr(cli.sys, "stdout", TTY())
    monkeypatch.setattr(cli, "Lexicon", lambda *args, **kwargs: object())

    import dictterm.tui

    monkeypatch.setattr(
        dictterm.tui,
        "run_viewer",
        lambda *args, **kwargs: calls.append({"args": args, "kwargs": kwargs}),
    )
    assert cli.main([]) == 0
    assert calls[0]["kwargs"]["open_lookup_on_mount"] is True
    assert calls[0]["kwargs"]["word"] is None


def test_bare_plain_cli_fails_without_opening_dataset(monkeypatch, capsys) -> None:
    from dictterm import cli

    monkeypatch.setattr(
        cli,
        "Lexicon",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dataset should not open")),
    )
    assert cli.main(["--plain"]) == 2
    assert "word is required" in capsys.readouterr().err
