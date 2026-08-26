from __future__ import annotations

import argparse
import sys

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
from ..cli_options import dictionary_source, entry_selection, view_options
from ..config import ConfigError, SettingsOverrides, load_config, resolve_settings
from ..dataset_policy import require_dictterm_capabilities
from ..render import render_lookup
from ..selection import parse_pos_list


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "lookup",
        help="look up and display a dictionary entry",
        description="Look up and display a dictionary entry.",
    )
    parser.add_argument("word", nargs="?", help="word to look up")
    from ..cli_options import (
        add_config_option,
        add_dictionary_source_options,
        add_entry_selection_options,
        add_view_options,
    )

    add_dictionary_source_options(parser)
    add_entry_selection_options(parser)
    add_view_options(parser)
    add_config_option(parser)
    return parser


def _open_lexicon(source, settings, lexicon_cls: type[Lexicon]) -> Lexicon:
    if source.path is not None:
        if source.dataset_version is not None:
            raise ValueError("--path cannot be combined with --dataset-version")
        if source.variant is not None:
            raise ValueError("--path cannot be combined with --variant")
        lexicon = lexicon_cls.from_path(
            source.path,
            language=source.language,
            locale=settings.locale,
        )
    else:
        lexicon = lexicon_cls(
            settings.language,
            variant=settings.variant,
            dataset_version=source.dataset_version,
            locale=settings.locale,
        )
    require_dictterm_capabilities(lexicon)
    return lexicon


def _open_backend(args: argparse.Namespace, settings, lexicon_cls: type[Lexicon]) -> LexhintBackend:
    source = dictionary_source(args)
    selection = entry_selection(args)
    return LexhintBackend(
        _open_lexicon(source, settings, lexicon_cls),
        all_case_variants=settings.all_case_variants,
        include_pos=parse_pos_list(selection.include_pos),
        exclude_pos=parse_pos_list(selection.exclude_pos),
    )


def _use_tui(view) -> bool:
    if view.plain:
        return False
    if view.tui:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError("--tui requires an interactive terminal")
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def _print_config_error(err: Console, exc: ConfigError) -> int:
    error = Text("error: ", style="bold red")
    error.append(str(exc))
    err.print(error, soft_wrap=True)
    return 2


def _settings(args: argparse.Namespace):
    return resolve_settings(SettingsOverrides.from_namespace(args), load_config(args.config))


def _dataset_install_command(language: str, variant: str, dataset_version: str | None) -> str:
    command = f"lexhint dataset download {language} --variant {variant}"
    if dataset_version is not None:
        command += f" --version {dataset_version}"
    return command


def run(
    args: argparse.Namespace,
    out: Console,
    err: Console,
    *,
    lexicon_cls: type[Lexicon] = Lexicon,
) -> int:
    try:
        settings = _settings(args)
    except ConfigError as exc:
        return _print_config_error(err, exc)

    view = view_options(args)
    if view.width is not None and view.width < 40:
        raise ValueError("--width must be at least 40")

    try:
        use_tui = _use_tui(view)
        if args.word is None and not use_tui:
            raise ValueError("a word is required outside an interactive terminal")
        backend = _open_backend(args, settings, lexicon_cls)
        if args.word is None:
            from ..tui import run_viewer

            run_viewer(
                backend,
                word=None,
                entries=(),
                width=settings.width,
                no_color=settings.no_color,
                tts_config=settings.tts,
                open_lookup_on_mount=True,
            )
            return 0
        result = backend.lookup(args.word)
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
        return 2

    if not result.entries and not result.relations:
        selection = entry_selection(args)
        empty_message = None
        if selection.include_pos or selection.exclude_pos:
            selected = selection.include_pos or ""
            excluded = selection.exclude_pos or ""
            if selected and excluded:
                label = f"{selected} (excluding {excluded})"
            elif selected:
                label = selected
            else:
                label = f"not {excluded}"
            empty_message = f"No {label} entry found for {args.word!r}."
        render_lookup(out, result, empty_message=empty_message)
        return 1

    if use_tui:
        from ..tui import run_viewer

        run_viewer(
            backend,
            result=result,
            width=settings.width,
            no_color=settings.no_color,
            tts_config=settings.tts,
        )
    else:
        render_lookup(out, result)
    return 0 if result.entries else 1
