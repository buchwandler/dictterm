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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dictshow",
        description="Show rich offline dictionary entries using lexhint datasets.",
    )
    parser.add_argument("word", help="word to look up")
    parser.add_argument(
        "-l",
        "--language",
        default=os.environ.get("DICTSHOW_LANGUAGE", "en"),
        help="dictionary language (default: %(default)s)",
    )
    parser.add_argument(
        "--dataset-version",
        help="select an exact installed lexhint dataset release",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="open a specific lexhint SQLite artifact instead of the managed rich dataset",
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
        lexicon = Lexicon(args.language, path=args.path)
    else:
        # Dictionary inspection requires Lexhint's rich artifact. Dataset acquisition
        # deliberately remains Lexhint's responsibility.
        lexicon = Lexicon(args.language, variant="rich", dataset_version=args.dataset_version)
    return lexicon.entries(args.word)


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
        entries = _lookup(args)
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
            hint.append(f"lexhint dataset download {args.language} --variant rich", style="bold")
            err.print(hint)
        return 2

    if not entries:
        render_entries(out, args.word, entries)
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
