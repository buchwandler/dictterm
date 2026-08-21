# dictshow

`dictshow` is an offline dictionary CLI with an interactive terminal viewer. **Lexhint owns
datasets and dictionary access; dictshow owns terminal presentation.**

The renderer is intentionally close to the clean `rdict` style: a compact part-of-speech badge and
word header, followed by pronunciation, etymology, forms, definitions, examples, and relations when
Lexhint provides them. Interactive navigation keeps large results at the first entry instead of
leaving the user at the end of terminal scrollback.

## Requirements

- Python 3.10+
- `lexhint>=0.1.0`
- `rich>=14.2`
- `textual>=8.2.8,<9`
- a Lexhint **rich** dataset for the language you want to query

## Install

Once both projects are available from PyPI:

```bash
python -m pip install dictshow
lexhint dataset download en --variant rich
dictshow lavish
```

During development, while Lexhint is installed from a checkout:

```bash
python -m pip install -e ../lexhint
python -m pip install -e . --no-deps
lexhint dataset download en --variant rich
dictshow lavish
```

## Usage

```text
dictshow WORD [-l LANGUAGE] [--dataset-version VERSION] [--path FILE]
              [--width COLUMNS] [--no-color] [--plain | --tui]
```

Examples:

```bash
dictshow lavish                 # interactive viewer in a terminal
dictshow love -l en
dictshow Haus -l de
dictshow compiler --dataset-version 2026.08.20
dictshow compiler --path ./lexhint-en.sqlite3
dictshow love --plain         # one-shot output
dictshow love --plain | less -R
```

In a terminal, `dictshow` opens the interactive viewer by default. Use `--plain` for deterministic
one-shot Rich output. Piped, redirected, captured, and non-interactive input/output automatically use
plain mode. `--tui` forces the viewer and requires both stdin and stdout to be terminals.

Viewer keys:

| Key | Action |
| --- | --- |
| Arrow keys, mouse wheel | Scroll |
| Page Up / Page Down | Page scroll |
| Home / End | Document start / end |
| `j` / `k` | Scroll down / up |
| `[` / `]` | Previous / next dictionary entry |
| `n` / `v` | First noun / verb entry |
| `1` through `9` | Jump to indexed entry |
| `q` | Quit |
| `?` | Show key help |

The CLI asks Lexhint for the installed `rich` artifact. It does **not** download, update, build, or
mutate datasets. If the rich artifact is missing, the CLI points the user to:

```bash
lexhint dataset download en --variant rich
```

## Versioning

The package version is dynamic and comes from Git tags via `setuptools-scm`.

```bash
git tag v0.1.0
python -m build
```

An unpacked source tree without Git metadata reports `0+unknown` rather than pretending to be a
release. At runtime `dictshow.__version__` reads installed package metadata via
`importlib.metadata`.

## Project layout

There is deliberately no `src/` directory:

```text
dictshow/
├── dictshow/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── render.py
│   ├── tui.py
│   └── py.typed
├── tests/
├── LICENSE
├── README.md
└── pyproject.toml
```

## Licensing

The **dictshow source code** is licensed under the Apache License 2.0. Lexhint datasets are
external data artifacts and retain the licensing and provenance documented by Lexhint; this
project does not relicense them.
