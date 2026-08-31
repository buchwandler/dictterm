from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from lexhint import Lexicon
from rich.console import Console

from . import __version__
from .cli_options import ViewOptions
from .commands import config as config_command
from .commands import lookup as lookup_command
from .commands import pronunciation as pronunciation_command
from .commands import tts as tts_command
from .render import THEME

_COMMANDS = frozenset({"lookup", "config", "tts", "pronunciation"})
_ROOT_ACTIONS = frozenset({"-h", "--help", "--version"})


def normalize_argv(argv: Sequence[str]) -> list[str]:
    """Rewrite the implicit lookup form into the explicit lookup command."""
    values = list(argv)
    if not values:
        return ["lookup"]
    if values[0] in _COMMANDS or values[0] in _ROOT_ACTIONS:
        return values
    return ["lookup", *values]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dictterm",
        description="Interactive offline dictionary frontend powered by Lexhint.",
        epilog=(
            "Common forms: dictterm (interactive lookup), dictterm WORD, and "
            "dictterm lookup WORD. Command words are reserved at position 1; use "
            "'dictterm lookup WORD' to look up a reserved word."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    lookup_command.add_parser(commands)
    config_command.add_parser(commands)
    tts_command.add_parser(commands)
    pronunciation_command.add_parser(commands)
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


def _use_tui(args: argparse.Namespace) -> bool:
    """Compatibility helper for callers that inspect lookup mode selection."""
    return lookup_command._use_tui(
        ViewOptions(
            width=getattr(args, "width", None),
            no_color=getattr(args, "no_color", None),
            plain=getattr(args, "plain", False),
            tui=getattr(args, "tui", False),
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(normalize_argv(sys.argv[1:] if argv is None else argv))
    width = getattr(args, "width", None)
    if width is not None and width < 40:
        parser.error("--width must be at least 40")

    out = _console(no_color=bool(getattr(args, "no_color", False)), width=width)
    err = _console(no_color=bool(getattr(args, "no_color", False)), width=width, stderr=True)
    if args.command == "lookup":
        return lookup_command.run(args, out, err, lexicon_cls=Lexicon)
    if args.command == "config":
        return config_command.run(args, out, err)
    if args.command == "tts":
        return tts_command.run(args, out, err)
    if args.command == "pronunciation":
        return pronunciation_command.run(args, out, err, lexicon_cls=Lexicon)
    parser.error(f"unknown command: {args.command}")
    return 2
