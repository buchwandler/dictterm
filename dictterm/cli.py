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
from .render import THEME, render_entries
from .selection import filter_entries, parse_pos_list


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dictterm",
        description="Interactive offline dictionary frontend powered by Lexhint.",
    )
    parser.add_argument("word", help="word to look up")
    parser.add_argument(
        "-l",
        "--language",
        default=os.environ.get("DICTTERM_LANGUAGE"),
        help="dictionary language; defaults to en for managed datasets",
    )
    parser.add_argument("--locale", help="locale preference passed to Lexhint")
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
    parser.add_argument("--width", type=int, help="override terminal render width")
    parser.add_argument("--no-color", action="store_true", help="disable terminal colors")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--plain",
        action="store_true",
        help="force one-shot Rich output even in a terminal",
    )
    mode.add_argument(
        "--tui",
        action="store_true",
        help="force the interactive viewer; requires a terminal",
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


def _lookup(args: argparse.Namespace):
    if args.path is not None:
        if args.dataset_version is not None:
            raise ValueError("--path cannot be combined with --dataset-version")
        lexicon = Lexicon.from_path(
            args.path,
            language=args.language,
            locale=args.locale,
        )
    else:
        # Dictionary inspection requires Lexhint's rich artifact. Dataset acquisition
        # deliberately remains Lexhint's responsibility.
        lexicon = Lexicon(
            args.language or "en",
            variant="rich",
            dataset_version=args.dataset_version,
            locale=args.locale,
        )
    return lexicon.entries(
        args.word,
        all_case_variants=getattr(args, "all_case_variants", False),
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.width is not None and args.width < 40:
        _parser().error("--width must be at least 40")

    out = _console(no_color=args.no_color, width=args.width)
    err = _console(no_color=args.no_color, width=args.width, stderr=True)

    try:
        raw_entries = _lookup(args)
        include = parse_pos_list(args.pos)
        exclude = parse_pos_list(args.exclude_pos)
        entries = filter_entries(raw_entries, include=include, exclude=exclude)
        use_tui = _use_tui(args)
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
        err.print(error)
        if args.path is None:
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
        if raw_entries and (args.pos or args.exclude_pos):
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
            args.word,
            entries,
            width=args.width,
            no_color=args.no_color,
        )
    else:
        render_entries(out, args.word, entries)
    return 0
