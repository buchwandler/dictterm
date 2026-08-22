from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from lexhint import (
    Lexicon,
    LexiconCapabilityError,
    LexiconCoverageError,
    LexiconIncompatible,
    LexiconNotInstalled,
)
from rich.console import Console
from rich.text import Text

from . import __version__
from .backend import LexhintBackend
from .config import (
    ConfigError,
    default_config_path,
    load_config,
    resolve_settings,
    write_default_config,
)
from .render import THEME, render_entries
from .selection import parse_pos_list


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dictterm",
        description="Interactive offline dictionary frontend powered by Lexhint.",
    )
    parser.add_argument("word", nargs="?", help="word to look up")
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="dictionary language; defaults to en for managed datasets",
    )
    parser.add_argument("--locale", default=None, help="locale preference passed to Lexhint")
    parser.add_argument(
        "--dataset-version",
        help="select an exact installed lexhint dataset release",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="open a specific lexhint SQLite artifact instead of the managed rich dataset",
    )
    parser.add_argument(
        "--all-case-variants",
        action="store_true",
        default=None,
        help="include alternate display-case entries",
    )
    parser.add_argument(
        "--pos",
        metavar="POS[,POS...]",
        help="include only these parts of speech",
    )
    parser.add_argument(
        "--exclude-pos",
        metavar="POS[,POS...]",
        help="exclude these parts of speech",
    )
    parser.add_argument("--width", type=int, default=None, help="override terminal render width")
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=None,
        help="disable terminal colors",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--plain",
        action="store_true",
        default=None,
        help="force one-shot Rich output even in a terminal",
    )
    mode.add_argument(
        "--tui",
        action="store_true",
        default=None,
        help="force the interactive viewer; requires a terminal",
    )
    parser.add_argument("--config", type=Path, help="load a specific TOML configuration file")
    parser.add_argument(
        "--config-path",
        action="store_true",
        help="print the resolved configuration path and exit",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="create a commented starter configuration and exit",
    )
    parser.add_argument(
        "--tts-check",
        action="store_true",
        help="diagnose the configured direct PyKokoro playback stack",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _console(*, no_color: bool, width: int | None, stderr: bool = False) -> Console:
    env_no_color = os.environ.get("NO_COLOR") is not None
    return Console(
        theme=THEME,
        no_color=no_color or env_no_color,
        width=width,
        stderr=stderr,
        highlight=False,
    )


def _open_lexicon(args: argparse.Namespace) -> Lexicon:
    if args.path is not None:
        if args.dataset_version is not None:
            raise ValueError("--path cannot be combined with --dataset-version")
        return Lexicon.from_path(
            args.path,
            language=getattr(args, "_path_language", args.language),
            locale=args.locale,
        )
    return Lexicon(
        args.language,
        variant="rich",
        dataset_version=args.dataset_version,
        locale=args.locale,
    )


def _open_backend(
    args: argparse.Namespace,
    *,
    include_pos: tuple[str, ...] = (),
    exclude_pos: tuple[str, ...] = (),
) -> LexhintBackend:
    return LexhintBackend(
        _open_lexicon(args),
        all_case_variants=args.all_case_variants,
        include_pos=include_pos,
        exclude_pos=exclude_pos,
    )


def _resolved_language(args: argparse.Namespace) -> str:
    return args.language or "en"


def _use_tui(args: argparse.Namespace) -> bool:
    if args.plain:
        return False
    if args.tui:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError("--tui requires an interactive terminal")
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def _print_config_error(err: Console, exc: ConfigError) -> int:
    error = Text("error: ", style="bold red")
    error.append(str(exc))
    err.print(error, soft_wrap=True)
    return 2


def _tts_check(config, config_path: Path, out: Console, err: Console) -> int:
    from .speech import (
        PyKokoroSpeechService,
        SpeechPlaybackError,
        SpeechRequest,
        SpeechSynthesisError,
        SpeechUnavailable,
    )

    out.print("dictterm TTS check")
    out.print(f"config          {config_path}")
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
        out.print("synthesis       ok")
        out.print("playback        ok")
    except SpeechUnavailable as exc:
        out.print("pykokoro        unavailable")
        err.print(f"error: {exc}")
        return 2
    except SpeechSynthesisError as exc:
        err.print(f"error: {exc}")
        return 2
    except SpeechPlaybackError as exc:
        err.print(f"error: {exc}")
        return 2
    finally:
        service.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.width is not None and args.width < 40:
        _parser().error("--width must be at least 40")

    out = _console(no_color=bool(args.no_color), width=args.width)
    err = _console(no_color=bool(args.no_color), width=args.width, stderr=True)
    config_path = args.config.expanduser() if args.config is not None else default_config_path()

    if args.config_path:
        print(config_path)
        return 0
    if args.init_config:
        try:
            print(write_default_config(config_path))
        except ConfigError as exc:
            return _print_config_error(err, exc)
        return 0

    try:
        config = load_config(config_path)
        settings = resolve_settings(args, config)
    except ConfigError as exc:
        return _print_config_error(err, exc)

    args.language = settings.language
    args.locale = settings.locale
    args.all_case_variants = settings.all_case_variants
    args.width = settings.width
    args.no_color = settings.no_color
    args.plain = settings.mode == "plain"
    args.tui = settings.mode == "tui"
    args._path_language = settings.language if settings.language != "en" else None
    args.tts_config = settings.tts
    if args.tts_check:
        return _tts_check(args.tts_config, config_path, out, err)

    try:
        include = parse_pos_list(args.pos)
        exclude = parse_pos_list(args.exclude_pos)
        use_tui = _use_tui(args)
        if args.word is None and not use_tui:
            raise ValueError("a word is required outside an interactive terminal")
        backend = _open_backend(args, include_pos=include, exclude_pos=exclude)
        if args.word is None:
            from .tui import run_viewer

            run_viewer(
                backend,
                word=None,
                entries=(),
                width=args.width,
                no_color=args.no_color,
                tts_config=args.tts_config,
                open_lookup_on_mount=True,
            )
            return 0
        entries = backend.entries(args.word)
    except (
        LexiconCapabilityError,
        LexiconCoverageError,
        LexiconIncompatible,
        LexiconNotInstalled,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        error = Text("error: ", style="bold red")
        error.append(str(exc))
        err.print(error, soft_wrap=True)
        if args.path is None and isinstance(exc, (LexiconNotInstalled, LexiconCapabilityError)):
            hint = Text("hint: ", style="dim")
            hint.append("install a rich dictionary dataset with ")
            hint.append(
                f"lexhint dataset download {_resolved_language(args)} --variant rich",
                style="bold",
            )
            err.print(hint, soft_wrap=True)
        return 2

    if not entries:
        empty_message = None
        if args.pos or args.exclude_pos:
            selected = args.pos or ""
            excluded = args.exclude_pos or ""
            if selected and excluded:
                label = f"{selected} (excluding {excluded})"
            elif selected:
                label = selected
            else:
                label = f"not {excluded}"
            empty_message = f"No {label} entry found for {args.word!r}."
        render_entries(out, args.word, entries, empty_message=empty_message)
        return 1

    if use_tui:
        from .tui import run_viewer

        run_viewer(
            backend,
            word=args.word,
            entries=entries,
            width=args.width,
            no_color=args.no_color,
            tts_config=args.tts_config,
        )
    else:
        render_entries(out, args.word, entries)
    return 0
