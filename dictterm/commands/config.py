from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from ..cli_options import add_config_option, add_settings_override_options
from ..config import (
    ConfigError,
    SettingsOverrides,
    default_config_path,
    load_config,
    resolve_settings,
    write_default_config,
)


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "config",
        help="inspect or initialize dictterm configuration",
        description="Inspect or initialize dictterm configuration.",
    )
    commands = parser.add_subparsers(dest="config_command", required=True)

    for name, help_text in (
        ("path", "print the resolved configuration path"),
        ("init", "create a starter configuration without overwriting"),
    ):
        child = commands.add_parser(name, help=help_text, description=help_text.capitalize() + ".")
        add_config_option(child)

    show = commands.add_parser(
        "show",
        help="show effective configuration",
        description="Show effective configuration after TOML, environment, and CLI overrides.",
    )
    add_settings_override_options(show)
    return parser


def _config_path(args: argparse.Namespace) -> Path:
    return args.config.expanduser() if args.config is not None else default_config_path()


def _print_error(err: Console, exc: ConfigError) -> int:
    err.print(f"error: {exc}", soft_wrap=True)
    return 2


def _show(args: argparse.Namespace, out: Console, err: Console) -> int:
    path = _config_path(args)
    try:
        settings = resolve_settings(SettingsOverrides.from_namespace(args), load_config(path))
    except ConfigError as exc:
        return _print_error(err, exc)

    print(f"config          {path}")
    out.print(f"language        {settings.language}")
    out.print(f"locale          {settings.locale or '(none)'}")
    out.print(f"variant         {settings.variant}")
    out.print(f"all_case_variants {'yes' if settings.all_case_variants else 'no'}")
    out.print(f"mode            {settings.mode}")
    out.print(f"width           {settings.width if settings.width is not None else '(auto)'}")
    out.print(f"no_color        {'yes' if settings.no_color else 'no'}")
    out.print(f"tts.enabled     {'yes' if settings.tts.enabled else 'no'}")
    out.print(f"tts.voice       {settings.tts.voice}")
    out.print(f"tts.language    {settings.tts.language}")
    out.print(f"tts.speed       {settings.tts.speed:g}")
    for name in ("provider", "model_source", "model_variant", "model_quality"):
        value = getattr(settings.tts, name)
        if value is not None:
            out.print(f"tts.{name}     {value}")
    return 0


def run(args: argparse.Namespace, out: Console, err: Console) -> int:
    path = _config_path(args)
    if args.config_command == "path":
        print(path)
        return 0
    if args.config_command == "init":
        try:
            print(write_default_config(path))
        except ConfigError as exc:
            return _print_error(err, exc)
        return 0
    return _show(args, out, err)
