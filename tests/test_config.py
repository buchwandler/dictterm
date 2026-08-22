from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from dictterm.config import (
    AppConfig,
    ConfigError,
    default_config_path,
    load_config,
    resolve_settings,
    write_default_config,
)


def test_missing_config_returns_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.toml")
    assert config == AppConfig()


def test_default_path_uses_xdg(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_config_path() == tmp_path / "dictterm" / "config.toml"


def test_valid_config_and_strict_validation(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'version = 1\n[dictionary]\nlanguage = "de"\n'
        '[display]\nmode = "plain"\nwidth = 80\n'
        "[tts]\nenabled = true\nspeed = 1.25\n"
    )
    config = load_config(path)
    assert config.dictionary.language == "de"
    assert config.display.mode == "plain"
    assert config.tts.speed == 1.25

    path.write_text("[tts]\nvoce = true\n")
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(path)


def test_version_type_and_speed_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("version = 2\n")
    with pytest.raises(ConfigError, match="unsupported config version"):
        load_config(path)
    path.write_text("[tts]\nspeed = 0\n")
    with pytest.raises(ConfigError, match="greater than 0"):
        load_config(path)


def test_precedence_defaults_config_environment_cli(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[dictionary]\nlanguage = "de"\n[display]\nwidth = 60\n')
    monkeypatch.setenv("DICTTERM_LANGUAGE", "fr")
    monkeypatch.setenv("DICTTERM_WIDTH", "70")
    args = Namespace(
        language="it",
        width=80,
        locale=None,
        all_case_variants=None,
        plain=None,
        tui=None,
        no_color=None,
    )
    settings = resolve_settings(args, load_config(path))
    assert settings.language == "it"
    assert settings.width == 80


def test_init_config_does_not_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.toml"
    assert write_default_config(path) == path
    assert "version = 1" in path.read_text()
    with pytest.raises(ConfigError, match="already exists"):
        write_default_config(path)
