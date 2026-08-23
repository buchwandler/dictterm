from __future__ import annotations

import pytest

from dictterm.config import TTSConfig
from dictterm.speech import (
    PyKokoroSpeechService,
    SpeechError,
    SpeechRequest,
    SpeechUnavailable,
)


class FakeGeneration:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class FakePipelineConfig:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class FakePipeline:
    created: list[FakePipeline] = []
    stream_calls: list[dict[str, object]] = []
    stream_error: Exception | None = None

    def __init__(self, config: FakePipelineConfig) -> None:
        self.config = config
        self.closed = False
        type(self).created.append(self)

    def play_streaming(
        self,
        text: str,
        *,
        unit: str = "sentence",
        queue_size: int = 2,
    ) -> None:
        type(self).stream_calls.append({"text": text, "unit": unit, "queue_size": queue_size})
        if self.stream_error is not None:
            raise self.stream_error

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakePipeline.created.clear()
    FakePipeline.stream_calls.clear()
    FakePipeline.stream_error = None


def request(text: str = "defer") -> SpeechRequest:
    return SpeechRequest("request-1", text, "en-us", "headword", 0)


def install_fake(monkeypatch) -> None:
    from dictterm import speech

    monkeypatch.setattr(
        speech,
        "_load_pykokoro",
        lambda: (FakePipeline, FakePipelineConfig, FakeGeneration),
    )


def test_disabled_service_does_not_load_pykokoro(monkeypatch) -> None:
    from dictterm import speech

    monkeypatch.setattr(speech, "_load_pykokoro", lambda: pytest.fail("must stay lazy"))
    PyKokoroSpeechService(TTSConfig()).speak(request())


def test_pipeline_is_lazy_reused_and_streamed(monkeypatch) -> None:
    install_fake(monkeypatch)
    service = PyKokoroSpeechService(TTSConfig(enabled=True, voice="af_voice", speed=1.25))
    assert not FakePipeline.created
    service.speak(request("first"))
    service.speak(request("second"))
    assert len(FakePipeline.created) == 1
    assert FakePipeline.stream_calls == [
        {"text": "first", "unit": "sentence", "queue_size": 2},
        {"text": "second", "unit": "sentence", "queue_size": 2},
    ]
    config = FakePipeline.created[0].config.kwargs
    assert config["voice"] == "af_voice"
    assert config["generation"].kwargs == {"lang": "en-us", "speed": 1.25}
    service.close()
    assert FakePipeline.created[0].closed


def test_optional_pipeline_settings_only_forward_when_set(monkeypatch) -> None:
    install_fake(monkeypatch)
    service = PyKokoroSpeechService(
        TTSConfig(enabled=True, provider="CPUExecutionProvider", model_quality="fp32")
    )
    service.speak(request())
    kwargs = FakePipeline.created[0].config.kwargs
    assert kwargs["provider"] == "CPUExecutionProvider"
    assert kwargs["model_quality"] == "fp32"
    assert "model_source" not in kwargs
    assert "model_variant" not in kwargs


def test_import_failure_stays_unavailable(monkeypatch) -> None:
    from dictterm import speech

    monkeypatch.setattr(
        speech, "_load_pykokoro", lambda: (_ for _ in ()).throw(ImportError("missing"))
    )
    with pytest.raises(SpeechUnavailable):
        PyKokoroSpeechService(TTSConfig(enabled=True)).speak(request())


def test_playback_extra_failure_has_install_hint(monkeypatch) -> None:
    install_fake(monkeypatch)
    FakePipeline.stream_error = ImportError("No module named sounddevice")
    with pytest.raises(SpeechUnavailable, match=r"dictterm\[tts\]"):
        PyKokoroSpeechService(TTSConfig(enabled=True)).speak(request())


def test_streaming_failure_is_generic_speech_error(monkeypatch) -> None:
    install_fake(monkeypatch)
    FakePipeline.stream_error = RuntimeError("stream failed")
    with pytest.raises(SpeechError, match="TTS streaming failed"):
        PyKokoroSpeechService(TTSConfig(enabled=True)).speak(request())


def test_structured_speech_text_omits_visual_metadata() -> None:
    from lexhint import DictionaryEntry, Example, Form, Sense

    from dictterm.speech import spoken_definition, spoken_definitions, spoken_forms

    entry = DictionaryEntry(
        "defer",
        "verb",
        (
            Sense(
                glosses=("To postpone or delay.",),
                tags=("transitive",),
                topics=("time",),
                examples=(Example("Wait until Monday.", "Attendre lundi."),),
            ),
        ),
        forms=(Form("defers", ("present", "singular")),),
    )
    assert spoken_definition(entry.senses[0]) == "To postpone or delay."
    assert spoken_forms(entry) == "defers. present, singular."
    assert spoken_definitions(entry) == "To postpone or delay. Example: Wait until Monday."
    assert "/" not in spoken_definitions(entry)
    assert "Attendre" not in spoken_definitions(entry)
