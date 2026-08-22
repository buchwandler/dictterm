from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from ..cli_options import add_config_option
from ..config import (
    ConfigError,
    SettingsOverrides,
    default_config_path,
    load_config,
    resolve_settings,
)


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "tts",
        help="inspect the optional speech stack",
        description="Inspect the optional direct PyKokoro speech stack.",
    )
    commands = parser.add_subparsers(dest="tts_command", required=True)
    check = commands.add_parser("check", help="diagnose the configured TTS playback stack")
    add_config_option(check)
    return parser


def _config_path(args: argparse.Namespace) -> Path:
    return args.config.expanduser() if args.config is not None else default_config_path()


def _print_config_error(err: Console, exc: ConfigError) -> int:
    err.print(f"error: {exc}", soft_wrap=True)
    return 2


def run(args: argparse.Namespace, out: Console, err: Console) -> int:
    path = _config_path(args)
    try:
        settings = resolve_settings(SettingsOverrides(), load_config(path))
    except ConfigError as exc:
        return _print_config_error(err, exc)

    from ..speech import (
        PyKokoroSpeechService,
        SpeechError,
        SpeechRequest,
        SpeechUnavailable,
    )

    config = settings.tts
    out.print("dictterm TTS check")
    out.print(f"config          {path}")
    out.print(f"enabled         {'yes' if config.enabled else 'no'}")
    out.print(f"voice           {config.voice}")
    out.print(f"language        {config.language}")
    out.print(f"speed           {config.speed}")
    if not config.enabled:
        return 0

    service = PyKokoroSpeechService(config)
    try:
        service._get_pipeline()
        out.print("pykokoro        available")
        out.print("pipeline        initialized")
        service.speak(
            SpeechRequest("tts-check", "dictterm TTS check", config.language, "headword", 0)
        )
        out.print("streaming       ok")
    except SpeechUnavailable as exc:
        out.print("pykokoro        unavailable")
        err.print(f"error: {exc}")
        return 2
    except SpeechError as exc:
        err.print(f"error: {exc}")
        return 2
    finally:
        service.close()
    return 0
