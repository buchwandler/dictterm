from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from lexhint import DictionaryEntry, Sense

from .config import TTSConfig

SpeechKind = Literal[
    "headword",
    "etymology",
    "forms",
    "definition",
    "definitions",
    "example",
    "translation",
]


@dataclass(frozen=True)
class SpeechRequest:
    id: str
    text: str
    language: str
    kind: SpeechKind
    entry_index: int
    sense_index: int | None = None
    example_index: int | None = None


def spoken_forms(entry: DictionaryEntry) -> str:
    parts: list[str] = []
    for form in entry.forms:
        if form.tags:
            parts.append(f"{form.form}. {', '.join(form.tags)}.")
        else:
            parts.append(form.form)
    return " ".join(parts)


def spoken_definition(sense: Sense) -> str:
    return " ".join(sense.glosses)


def spoken_definitions(entry: DictionaryEntry) -> str:
    parts: list[str] = []
    for sense in entry.senses:
        definition = spoken_definition(sense)
        if definition:
            parts.append(definition)
        parts.extend(f"Example: {example.text}" for example in sense.examples)
    return " ".join(parts)


class SpeechError(RuntimeError):
    """Base class for errors raised by the speech service."""


class SpeechUnavailable(SpeechError):
    """PyKokoro is not installed or could not initialize."""


class SpeechSynthesisError(SpeechError):
    """PyKokoro could not synthesize the requested text."""


class SpeechPlaybackError(SpeechError):
    """The synthesized audio could not be played."""


class SpeechService(Protocol):
    def speak(self, request: SpeechRequest) -> None: ...

    def close(self) -> None: ...


def _load_pykokoro():
    try:
        from pykokoro import KokoroPipeline, PipelineConfig
        from pykokoro.generation_config import GenerationConfig
    except ImportError as exc:
        raise SpeechUnavailable(
            'PyKokoro playback is not installed. Install dictterm with: pip install "dictterm[tts]"'
        ) from exc
    return KokoroPipeline, PipelineConfig, GenerationConfig


class PyKokoroSpeechService:
    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            KokoroPipeline, PipelineConfig, GenerationConfig = _load_pykokoro()
            generation = GenerationConfig(lang=self.config.language, speed=self.config.speed)
            kwargs: dict[str, object] = {
                "voice": self.config.voice,
                "generation": generation,
            }
            for name in ("provider", "model_source", "model_variant", "model_quality"):
                value = getattr(self.config, name)
                if value is not None:
                    kwargs[name] = value
            self._pipeline = KokoroPipeline(PipelineConfig(**kwargs))
        except SpeechUnavailable:
            raise
        except Exception as exc:
            raise SpeechUnavailable(f"PyKokoro could not initialize: {exc}") from exc
        return self._pipeline

    def speak(self, request: SpeechRequest) -> None:
        if not self.config.enabled:
            return
        pipeline = self._get_pipeline()
        try:
            pipeline.play_streaming(
                request.text,
                unit="sentence",
                queue_size=2,
            )
        except ImportError as exc:
            raise SpeechUnavailable(
                "PyKokoro playback is not installed. Install dictterm with: "
                'pip install "dictterm[tts]"'
            ) from exc
        except Exception as exc:
            raise SpeechError(f"TTS streaming failed: {exc}") from exc

    def close(self) -> None:
        if self._pipeline is None:
            return
        pipeline = self._pipeline
        self._pipeline = None
        pipeline.close()
