from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from .dataset_policy import DEFAULT_VARIANT, MANAGED_VARIANTS


@dataclass(frozen=True)
class DictionarySourceOptions:
    language: str | None = None
    locale: str | None = None
    variant: str | None = None
    dataset_version: str | None = None
    path: Path | None = None


@dataclass(frozen=True)
class EntrySelectionOptions:
    all_case_variants: bool | None = None
    include_pos: str | None = None
    exclude_pos: str | None = None


@dataclass(frozen=True)
class ViewOptions:
    width: int | None = None
    no_color: bool | None = None
    plain: bool | None = None
    tui: bool | None = None


def add_config_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="load a specific TOML configuration file")


def add_dictionary_source_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="dictionary language; defaults to en for managed datasets",
    )
    parser.add_argument("--locale", default=None, help="locale preference passed to Lexhint")
    parser.add_argument(
        "--variant",
        choices=MANAGED_VARIANTS,
        default=None,
        help=f"select a managed Lexhint dictionary variant; default: {DEFAULT_VARIANT}",
    )
    parser.add_argument(
        "--dataset-version",
        help="select an exact installed lexhint dataset release",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="open a specific lexhint SQLite artifact instead of a managed Lexhint dataset",
    )


def add_entry_selection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--all-case-variants",
        action="store_true",
        default=None,
        help="include alternate display-case entries",
    )
    parser.add_argument("--pos", metavar="POS[,POS...]", help="include only these parts of speech")
    parser.add_argument(
        "--exclude-pos",
        metavar="POS[,POS...]",
        help="exclude these parts of speech",
    )


def add_view_options(parser: argparse.ArgumentParser) -> None:
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


def add_settings_override_options(parser: argparse.ArgumentParser) -> None:
    """Add configuration values that can be overridden for ``config show``."""
    add_config_option(parser)
    parser.add_argument("-l", "--language", default=None, help="override dictionary language")
    parser.add_argument("--locale", default=None, help="override dictionary locale")
    parser.add_argument(
        "--variant",
        choices=MANAGED_VARIANTS,
        default=None,
        help=f"override managed Lexhint dictionary variant; default: {DEFAULT_VARIANT}",
    )
    parser.add_argument(
        "--all-case-variants",
        action="store_true",
        default=None,
        help="override dictionary case-variant setting",
    )
    parser.add_argument("--width", type=int, default=None, help="override terminal render width")
    parser.add_argument(
        "--no-color", action="store_true", default=None, help="override terminal colors"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plain", action="store_true", default=None, help="set plain display mode")
    mode.add_argument("--tui", action="store_true", default=None, help="set TUI display mode")


def dictionary_source(args: argparse.Namespace) -> DictionarySourceOptions:
    return DictionarySourceOptions(
        language=args.language,
        locale=args.locale,
        variant=args.variant,
        dataset_version=args.dataset_version,
        path=args.path,
    )


def entry_selection(args: argparse.Namespace) -> EntrySelectionOptions:
    return EntrySelectionOptions(
        all_case_variants=args.all_case_variants,
        include_pos=args.pos,
        exclude_pos=args.exclude_pos,
    )


def view_options(args: argparse.Namespace) -> ViewOptions:
    return ViewOptions(
        width=args.width,
        no_color=args.no_color,
        plain=args.plain,
        tui=args.tui,
    )
