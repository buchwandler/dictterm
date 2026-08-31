from __future__ import annotations

import argparse

from lexhint import (
    Lexicon,
    LexiconCapabilityError,
    LexiconCoverageError,
    LexiconIncompatible,
    LexiconNotInstalled,
)
from rich.console import Console
from rich.text import Text

from ..backend import LexhintBackend
from ..cli_options import (
    add_config_option,
    add_dictionary_source_options,
    add_entry_selection_options,
    dictionary_source,
    entry_selection,
)
from ..config import ConfigError, SettingsOverrides, load_config, resolve_settings
from ..render import render_pronunciations
from ..selection import parse_pos_list
from .lookup import _dataset_install_command, _open_lexicon


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "pronunciation",
        help="look up pronunciation data",
        description="Look up and display pronunciation data.",
    )
    parser.add_argument("word", help="word to look up")
    add_dictionary_source_options(parser)
    add_entry_selection_options(parser)
    parser.add_argument("--region", help="match an exact normalized pronunciation region tag")
    parser.add_argument(
        "--include-neutral",
        action="store_true",
        help="include pronunciations without regional tags; requires --region or --locale",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable terminal colors",
    )
    add_config_option(parser)
    return parser


def _print_error(err: Console, exc: Exception) -> int:
    error = Text("error: ", style="bold red")
    error.append(str(exc))
    err.print(error, soft_wrap=True)
    return 2


def run(
    args: argparse.Namespace,
    out: Console,
    err: Console,
    *,
    lexicon_cls: type[Lexicon] = Lexicon,
) -> int:
    try:
        settings = resolve_settings(
            SettingsOverrides.from_namespace(args), load_config(args.config)
        )
        source = dictionary_source(args)
        if args.region is not None and settings.locale is not None:
            raise ValueError("--region cannot be combined with --locale or configured locale")
        if args.include_neutral and args.region is None and settings.locale is None:
            raise ValueError("--include-neutral requires --region or --locale")
        lexicon = _open_lexicon(source, settings, lexicon_cls)
        backend = LexhintBackend(
            lexicon,
            include_pos=parse_pos_list(entry_selection(args).include_pos),
            exclude_pos=parse_pos_list(entry_selection(args).exclude_pos),
        )
        groups = backend.pronunciations(
            args.word,
            region=args.region,
            include_neutral=args.include_neutral,
        )
    except (
        LexiconCapabilityError,
        LexiconCoverageError,
        LexiconIncompatible,
        LexiconNotInstalled,
        OSError,
        RuntimeError,
        ValueError,
        ConfigError,
    ) as exc:
        result = _print_error(err, exc)
        source = dictionary_source(args)
        if source.path is None and isinstance(exc, (LexiconNotInstalled, LexiconCapabilityError)):
            hint = Text("hint: ", style="dim")
            hint.append("install the selected dictionary dataset with ")
            hint.append(
                _dataset_install_command(
                    settings.language, settings.variant, source.dataset_version
                ),
                style="bold",
            )
            err.print(hint, soft_wrap=True)
        return result

    render_pronunciations(out, args.word, groups, region=args.region, locale=settings.locale)
    return 0
