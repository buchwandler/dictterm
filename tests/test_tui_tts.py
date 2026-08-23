from __future__ import annotations

import asyncio

import pytest
from lexhint import DictionaryEntry, Example, Form, Pronunciation, Sense

from dictterm.config import TTSConfig
from dictterm.tui import DictionaryEntryView, DictionaryViewerApp, EntryScroll, ReadControl


def _entry() -> DictionaryEntry:
    return DictionaryEntry(
        "defer",
        "verb",
        (Sense(glosses=("To postpone or delay.",), examples=(Example("Wait until Monday."),)),),
        pronunciations=(Pronunciation("/dɪˈfɜː/"),),
        etymology="From Latin.",
    )


class FakeSpeechService:
    instances: list[FakeSpeechService] = []

    def __init__(self, config) -> None:
        self.config = config
        self.requests = []
        self.closed = False
        type(self).instances.append(self)

    def speak(self, request) -> None:
        self.requests.append(request)

    def close(self) -> None:
        self.closed = True


def test_disabled_tts_has_no_read_controls() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("defer", (_entry(),))
        async with app.run_test(size=(80, 20)):
            assert not app.query(ReadControl)

    asyncio.run(scenario())


def test_enabled_tts_controls_target_structured_text(monkeypatch) -> None:
    from dictterm import tui

    FakeSpeechService.instances.clear()
    monkeypatch.setattr(tui, "PyKokoroSpeechService", FakeSpeechService)

    async def scenario() -> None:
        app = DictionaryViewerApp("defer", (_entry(),), tts_config=TTSConfig(enabled=True))
        async with app.run_test(size=(80, 20)) as pilot:
            controls = list(app.query(ReadControl))
            assert len(controls) == 5
            assert {control.request.kind for control in controls} == {
                "headword",
                "etymology",
                "definitions",
                "definition",
                "example",
            }
            app.screen.set_focus(controls[-1])
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            service = FakeSpeechService.instances[0]
            assert service.requests[0].text == "Wait until Monday."
            assert app.query_one("#entry-0", DictionaryEntryView).entry.word == "defer"
        assert service.closed

    asyncio.run(scenario())


_LONG_DEFINITION = (
    "A definition with enough prose to wrap across many narrow terminal lines while "
    "remaining fully present in the Textual content widget, final-Z."
)
_LONG_EXAMPLE_ONE = (
    "The first example contains enough prose to wrap before the play control gutter, final-Q."
)
_LONG_EXAMPLE_TWO = (
    "The second example also contains enough prose to wrap across several lines, final-X."
)


def _long_entry() -> DictionaryEntry:
    return DictionaryEntry(
        "compiler",
        "noun",
        (
            Sense(
                glosses=(_LONG_DEFINITION,),
                examples=(Example(_LONG_EXAMPLE_ONE), Example(_LONG_EXAMPLE_TWO)),
            ),
        ),
        pronunciations=(Pronunciation("/kəmˈpaɪlər/"),),
        etymology="From compile and the suffix -er.",
        forms=(Form("compilers"),),
    )


def test_semantic_rows_without_tts_keep_full_content_width() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("compiler", (_long_entry(),))
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            rows = list(app.query(".semantic-row"))
            assert rows
            for row in rows:
                content = row.query_one(".semantic-row-content")
                assert content.content_region.right == content.region.right

    asyncio.run(scenario())


def test_example_text_avoids_terminal_dependent_italic_clipping() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp("compiler", (_long_entry(),))
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            examples = [
                content.render()
                for content in app.query(".semantic-row-content")
                if content.render().plain.startswith("“")
            ]
            assert examples
            assert all(
                "italic" not in str(span.style) for example in examples for span in example.spans
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("width", (40, 41, 42, 44, 46, 50))
def test_tts_read_controls_reserve_gutter_at_wrap_boundaries(width: int) -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp(
            "compiler",
            (_long_entry(),),
            tts_config=TTSConfig(enabled=True),
        )
        async with app.run_test(size=(width, 12)) as pilot:
            await pilot.pause()
            controls = list(app.query(ReadControl))
            assert controls
            app.screen.set_focus(controls[-1])
            await pilot.pause()
            scroll = app.query_one("#entry-scroll", EntryScroll)
            rendered_rows = []
            for row in app.query(".semantic-row"):
                row_controls = list(row.query(ReadControl))
                if not row_controls:
                    continue
                content = row.query_one(".semantic-row-content")
                control = row_controls[0]
                assert content.region.right + 1 <= control.region.x
                assert control.region.right <= row.region.right
                assert row.region.right <= scroll.region.right
                assert control.region.width == 3
                rendered_rows.append(content.render().plain)

            rendered = "\n".join(rendered_rows)
            assert _LONG_DEFINITION in rendered
            assert _LONG_EXAMPLE_ONE in rendered
            assert _LONG_EXAMPLE_TWO in rendered
            assert "final-Z" in rendered
            assert "final-Q" in rendered
            assert "final-X" in rendered
            assert scroll.max_scroll_x == 0

    asyncio.run(scenario())
