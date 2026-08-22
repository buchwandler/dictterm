from __future__ import annotations

import asyncio

from lexhint import DictionaryEntry, Example, Pronunciation, Sense

from dictterm.config import TTSConfig
from dictterm.tui import DictionaryEntryView, DictionaryViewerApp, ReadControl


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
