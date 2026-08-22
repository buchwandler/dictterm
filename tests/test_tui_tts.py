from __future__ import annotations

import asyncio

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
    "remaining fully present in the Textual content widget."
)
_LONG_EXAMPLE_ONE = (
    "The first example contains enough prose to wrap before the play control gutter."
)
_LONG_EXAMPLE_TWO = "The second example also contains enough prose to wrap across several lines."


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


def test_tts_read_controls_never_overlap_text_at_mobile_width() -> None:
    async def scenario() -> None:
        app = DictionaryViewerApp(
            "compiler",
            (_long_entry(),),
            tts_config=TTSConfig(enabled=True),
        )
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.pause()
            scroll = app.query_one("#entry-scroll", EntryScroll)
            rendered_rows = []
            for row in app.query(".semantic-row"):
                controls = list(row.query(ReadControl))
                if not controls:
                    continue
                content = row.query_one(".semantic-row-content")
                control = controls[0]
                assert content.region.right <= control.region.x
                assert control.region.right <= row.region.right
                assert row.region.right <= scroll.region.right
                assert control.region.width == 3
                rendered_rows.append(content.render().plain)

            rendered = "\n".join(rendered_rows)
            assert _LONG_DEFINITION in rendered
            assert _LONG_EXAMPLE_ONE in rendered
            assert _LONG_EXAMPLE_TWO in rendered
            assert scroll.max_scroll_x == 0

    asyncio.run(scenario())
