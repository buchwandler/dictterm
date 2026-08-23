from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

from .dataset_policy import DEFAULT_VARIANT, MANAGED_VARIANTS, validate_managed_variant

ConfigMode = Literal["auto", "tui", "plain"]


class ConfigError(ValueError):
    """A user-facing configuration error."""


@dataclass(frozen=True)
class DictionaryConfig:
    language: str = "en"
    locale: str | None = None
    variant: str = DEFAULT_VARIANT
    all_case_variants: bool = False


@dataclass(frozen=True)
class DisplayConfig:
    mode: ConfigMode = "auto"
    width: int | None = None
    no_color: bool = False


@dataclass(frozen=True)
class TTSConfig:
    enabled: bool = False
    voice: str = "af_heart"
    language: str = "en-us"
    speed: float = 1.0
    provider: str | None = None
    model_source: str | None = None
    model_variant: str | None = None
    model_quality: str | None = None


@dataclass(frozen=True)
class AppConfig:
    version: int = 1
    dictionary: DictionaryConfig = field(default_factory=DictionaryConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)


@dataclass(frozen=True)
class SettingsOverrides:
    """Explicit command-line values used to resolve effective settings."""

    language: str | None = None
    locale: str | None = None
    variant: str | None = None
    all_case_variants: bool | None = None
    width: int | None = None
    no_color: bool | None = None
    plain: bool | None = None
    tui: bool | None = None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> SettingsOverrides:
        return cls(
            language=getattr(args, "language", None),
            locale=getattr(args, "locale", None),
            variant=getattr(args, "variant", None),
            all_case_variants=getattr(args, "all_case_variants", None),
            width=getattr(args, "width", None),
            no_color=getattr(args, "no_color", None),
            plain=getattr(args, "plain", None),
            tui=getattr(args, "tui", None),
        )


@dataclass(frozen=True)
class EffectiveSettings:
    language: str
    locale: str | None
    variant: str
    all_case_variants: bool
    mode: ConfigMode
    width: int | None
    no_color: bool
    tts: TTSConfig


_DEFAULT_CONFIG = """# dictterm user configuration
version = 1

[dictionary]
language = "en"
# locale = "en-US"
variant = "dictionary"   # dictionary | rich
all_case_variants = false

[display]
mode = "auto"        # auto | tui | plain
no_color = false
# width = 80

[tts]
enabled = false
voice = "af_heart"
language = "en-us"
speed = 1.0
"""

_TABLE_KEYS = {
    "dictionary": {"language", "locale", "variant", "all_case_variants"},
    "display": {"mode", "width", "no_color"},
    "tts": {
        "enabled",
        "voice",
        "language",
        "speed",
        "provider",
        "model_source",
        "model_variant",
        "model_quality",
    },
}


def default_config_path() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    if root:
        return Path(root).expanduser() / "dictterm" / "config.toml"
    return Path.home() / ".config" / "dictterm" / "config.toml"


def _config_path(path: Path | None) -> Path:
    return (path if path is not None else default_config_path()).expanduser()


def _fail(path: Path, message: str) -> ConfigError:
    return ConfigError(f"invalid dictterm config {path}: {message}")


def _require_table(data: dict[str, object], name: str, path: Path) -> dict[str, object]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise _fail(path, f"[{name}] must be a table")
    return value


def _validate_keys(table: dict[str, object], name: str, path: Path) -> None:
    unknown = sorted(set(table) - _TABLE_KEYS[name])
    if unknown:
        raise _fail(path, f"unknown key [{name}].{unknown[0]}")


def _string(value: object, label: str, path: Path, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    if not isinstance(value, str):
        raise _fail(path, f"[{label}] must be a string")
    return value


def _bool(value: object, label: str, path: Path) -> bool:
    if type(value) is not bool:
        raise _fail(path, f"[{label}] must be a boolean")
    return value


def _int(value: object, label: str, path: Path) -> int:
    if type(value) is not int:
        raise _fail(path, f"[{label}] must be an integer")
    return value


def _parse(data: dict[str, object], path: Path) -> AppConfig:
    unknown = sorted(set(data) - {"version", *_TABLE_KEYS})
    if unknown:
        raise _fail(path, f"unknown key {unknown[0]}")

    version = data.get("version", 1)
    if type(version) is not int:
        raise _fail(path, "version must be an integer")
    if version != 1:
        raise ConfigError(
            f"unsupported config version {version}; this version of dictterm supports version 1"
        )

    dictionary = _require_table(data, "dictionary", path)
    display = _require_table(data, "display", path)
    tts = _require_table(data, "tts", path)
    _validate_keys(dictionary, "dictionary", path)
    _validate_keys(display, "display", path)
    _validate_keys(tts, "tts", path)

    language = _string(dictionary.get("language", "en"), "dictionary.language", path)
    locale = _string(dictionary.get("locale"), "dictionary.locale", path, allow_none=True)
    variant_value = _string(dictionary.get("variant", DEFAULT_VARIANT), "dictionary.variant", path)
    try:
        variant = validate_managed_variant(variant_value or DEFAULT_VARIANT)
    except ValueError as exc:
        allowed = ", ".join(MANAGED_VARIANTS)
        raise _fail(path, f"[dictionary].variant must be one of: {allowed}") from exc
    all_case_variants = _bool(
        dictionary.get("all_case_variants", False), "dictionary.all_case_variants", path
    )

    mode = _string(display.get("mode", "auto"), "display.mode", path)
    if mode not in {"auto", "tui", "plain"}:
        raise _fail(path, "[display].mode must be one of: auto, tui, plain")
    width_value = display.get("width")
    width = None if width_value is None else _int(width_value, "display.width", path)
    if width is not None and width < 40:
        raise _fail(path, "[display].width must be at least 40")
    no_color = _bool(display.get("no_color", False), "display.no_color", path)

    enabled = _bool(tts.get("enabled", False), "tts.enabled", path)
    voice = _string(tts.get("voice", "af_heart"), "tts.voice", path)
    tts_language = _string(tts.get("language", "en-us"), "tts.language", path)
    speed_value = tts.get("speed", 1.0)
    if type(speed_value) not in {int, float}:
        raise _fail(path, "[tts].speed must be a number")
    speed = float(speed_value)
    if speed <= 0:
        raise _fail(path, "[tts].speed must be greater than 0")
    optional = {
        key: _string(tts.get(key), f"tts.{key}", path, allow_none=True)
        for key in ("provider", "model_source", "model_variant", "model_quality")
    }

    return AppConfig(
        version=version,
        dictionary=DictionaryConfig(
            language=language or "en",
            locale=locale,
            variant=variant,
            all_case_variants=all_case_variants,
        ),
        display=DisplayConfig(mode, width, no_color),
        tts=TTSConfig(enabled, voice or "af_heart", tts_language or "en-us", speed, **optional),
    )


def load_config(path: Path | None = None) -> AppConfig:
    config_path = _config_path(path)
    if not config_path.exists():
        return AppConfig()
    try:
        with config_path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise _fail(config_path, f"invalid TOML: {exc}") from exc
    except OSError as exc:
        raise _fail(config_path, str(exc)) from exc
    if not isinstance(data, dict):  # pragma: no cover - tomllib always returns a dict
        raise _fail(config_path, "top level must be a table")
    return _parse(data, config_path)


def _env_bool(name: str, value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"invalid {name}: expected a boolean")


def _env_int(name: str, value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ConfigError(f"invalid {name}: expected an integer") from exc
    if result < 40:
        raise ConfigError(f"invalid {name}: must be at least 40")
    return result


def _env_float(name: str, value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise ConfigError(f"invalid {name}: expected a number") from exc
    if result <= 0:
        raise ConfigError(f"invalid {name}: must be greater than 0")
    return result


def _env_overrides(config: AppConfig) -> tuple[DictionaryConfig, DisplayConfig, TTSConfig]:
    dictionary = config.dictionary
    display = config.display
    tts = config.tts
    if "DICTTERM_LANGUAGE" in os.environ:
        dictionary = DictionaryConfig(
            language=os.environ["DICTTERM_LANGUAGE"],
            locale=dictionary.locale,
            variant=dictionary.variant,
            all_case_variants=dictionary.all_case_variants,
        )
    if "DICTTERM_LOCALE" in os.environ:
        dictionary = DictionaryConfig(
            language=dictionary.language,
            locale=os.environ["DICTTERM_LOCALE"],
            variant=dictionary.variant,
            all_case_variants=dictionary.all_case_variants,
        )
    if "DICTTERM_VARIANT" in os.environ:
        try:
            variant = validate_managed_variant(os.environ["DICTTERM_VARIANT"])
        except ValueError as exc:
            allowed = ", ".join(MANAGED_VARIANTS)
            raise ConfigError(f"invalid DICTTERM_VARIANT: expected one of: {allowed}") from exc
        dictionary = DictionaryConfig(
            language=dictionary.language,
            locale=dictionary.locale,
            variant=variant,
            all_case_variants=dictionary.all_case_variants,
        )
    if "DICTTERM_ALL_CASE_VARIANTS" in os.environ:
        dictionary = DictionaryConfig(
            language=dictionary.language,
            locale=dictionary.locale,
            variant=dictionary.variant,
            all_case_variants=_env_bool(
                "DICTTERM_ALL_CASE_VARIANTS", os.environ["DICTTERM_ALL_CASE_VARIANTS"]
            ),
        )
    if "DICTTERM_MODE" in os.environ:
        mode = os.environ["DICTTERM_MODE"]
        if mode not in {"auto", "tui", "plain"}:
            raise ConfigError("invalid DICTTERM_MODE: expected auto, tui, or plain")
        display = DisplayConfig(mode=mode, width=display.width, no_color=display.no_color)
    if "DICTTERM_WIDTH" in os.environ:
        display = DisplayConfig(
            mode=display.mode,
            width=_env_int("DICTTERM_WIDTH", os.environ["DICTTERM_WIDTH"]),
            no_color=display.no_color,
        )
    if "DICTTERM_NO_COLOR" in os.environ:
        display = DisplayConfig(
            mode=display.mode,
            width=display.width,
            no_color=_env_bool("DICTTERM_NO_COLOR", os.environ["DICTTERM_NO_COLOR"]),
        )
    changes = {
        "enabled": _env_bool("DICTTERM_TTS_ENABLED", os.environ["DICTTERM_TTS_ENABLED"])
        if "DICTTERM_TTS_ENABLED" in os.environ
        else tts.enabled,
        "voice": os.environ.get("DICTTERM_TTS_VOICE", tts.voice),
        "language": os.environ.get("DICTTERM_TTS_LANGUAGE", tts.language),
        "speed": _env_float("DICTTERM_TTS_SPEED", os.environ["DICTTERM_TTS_SPEED"])
        if "DICTTERM_TTS_SPEED" in os.environ
        else tts.speed,
    }
    for field_name in ("provider", "model_source", "model_variant", "model_quality"):
        changes[field_name] = os.environ.get(
            f"DICTTERM_TTS_{field_name.upper()}", getattr(tts, field_name)
        )
    tts = TTSConfig(**changes)
    return dictionary, display, tts


def resolve_settings(
    overrides: SettingsOverrides | argparse.Namespace, config: AppConfig
) -> EffectiveSettings:
    if isinstance(overrides, argparse.Namespace):
        overrides = SettingsOverrides.from_namespace(overrides)
    dictionary, display, tts = _env_overrides(config)

    def explicit(value: object, current: object) -> object:
        return current if value is None else value

    try:
        variant = validate_managed_variant(str(explicit(overrides.variant, dictionary.variant)))
    except ValueError as exc:
        allowed = ", ".join(MANAGED_VARIANTS)
        raise ConfigError(f"invalid dictionary variant: expected one of: {allowed}") from exc
    dictionary = DictionaryConfig(
        language=str(explicit(overrides.language, dictionary.language)),
        locale=explicit(overrides.locale, dictionary.locale),
        variant=variant,
        all_case_variants=bool(explicit(overrides.all_case_variants, dictionary.all_case_variants)),
    )
    mode = display.mode
    if overrides.plain:
        mode = "plain"
    elif overrides.tui:
        mode = "tui"
    display = DisplayConfig(
        mode,
        explicit(overrides.width, display.width),
        explicit(overrides.no_color, display.no_color),
    )
    return EffectiveSettings(
        language=dictionary.language,
        locale=dictionary.locale,
        variant=dictionary.variant,
        all_case_variants=dictionary.all_case_variants,
        mode=display.mode,
        width=display.width,
        no_color=display.no_color,
        tts=tts,
    )


def write_default_config(path: Path | None = None) -> Path:
    config_path = _config_path(path)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("x", encoding="utf-8") as stream:
            stream.write(_DEFAULT_CONFIG)
    except FileExistsError as exc:
        raise ConfigError(f"config file already exists: {config_path}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot write config file {config_path}: {exc}") from exc
    return config_path
