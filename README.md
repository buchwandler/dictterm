# dictterm

`dictterm` is an offline dictionary CLI with an interactive terminal viewer. **Lexhint owns
datasets and dictionary access; dictterm owns terminal presentation.**

The renderer is intentionally close to the clean `rdict` style: a compact part-of-speech badge and
word header, followed by pronunciation, etymology, forms, definitions, examples, and relations when
Lexhint provides them. Interactive navigation keeps large results at the first entry instead of
leaving the user at the end of terminal scrollback.

## Requirements

- Python 3.10+
- `lexhint>=0.4.2`
- `rich>=14.2`
- `textual>=8.2.8,<9`
- a Lexhint **dictionary-capable** dataset for the language you want to query

## Lexhint schema compatibility

Dictterm requires a Lexhint schema 10 release and a schema 10 dictionary-capable artifact. Lexhint owns schema compatibility and rejects older artifacts. Schema 9 artifacts are not migrated in place. Install or rebuild the corresponding schema 10 dataset with Lexhint before using Dictterm.

Headword-level relations supplied by Lexhint are shown as query-level context in plain output and the TUI. Lexhint sense IDs and source provenance remain opaque machine metadata and are not displayed or spoken by default.

## Install

Install dictterm and its Lexhint dependency from PyPI:

```bash
python -m pip install dictterm
lexhint dataset download en --variant dictionary
dictterm lavish
```

Optional direct PyKokoro speech support is installed separately:

```bash
python -m pip install "dictterm[tts]"
```

The base `dictterm` installation does not load or require the speech stack.
For development, while Lexhint is installed from a checkout:

```bash
python -m pip install -e ../lexhint
python -m pip install -e . --no-deps
lexhint dataset download en --variant dictionary
dictterm lavish
```

## Usage

```text
dictterm [WORD] [lookup options]
dictterm lookup [WORD] [lookup options]
dictterm config path|init|show [options]
dictterm tts check [options]
dictterm pronunciation WORD [pronunciation options]
```

The normal dictionary action stays short. These forms are equivalent lookup entry points:

```bash
dictterm                          # interactive lookup mode in a terminal
dictterm lavish                    # open a word in the viewer
dictterm lookup lavish             # explicit lookup form
dictterm lookup config             # look up a reserved command word
dictterm love -l en
dictterm Haus -l de
dictterm color --locale en-US
dictterm love --pos noun,verb
dictterm compiler --path ./lexhint-en.sqlite3
dictterm love --plain              # one-shot output
dictterm --plain love              # shorthand options may precede WORD
```

At argv position 1, `lookup`, `config`, `tts`, and `pronunciation` are reserved command families. Use
`dictterm lookup WORD` when the word itself is reserved. `dictterm` and `dictterm lookup`
open interactive lookup mode in a terminal. Outside a terminal, a word is required and
the command uses plain output. `--tui` forces the viewer and requires terminal input/output.

In a terminal, bare `dictterm` opens interactive lookup mode. Type a word to see live candidate
headwords, use Up/Down to choose one, and press Enter to open it. `dictterm WORD` opens that word
directly in the viewer. Use `--plain` for deterministic one-shot Rich output; a word is required
for plain or other non-interactive invocations. Piped, redirected, captured, and non-interactive
input/output automatically use plain mode. `--tui` forces the viewer and requires both stdin and
stdout to be terminals.

## Pronunciation lookup

Use the focused pronunciation command when definitions and other dictionary metadata are not needed:

```bash
dictterm pronunciation love
dictterm pronunciation love --region Canada
dictterm pronunciation love --locale en_CA
dictterm pronunciation love --locale en_US --include-neutral
dictterm pronunciation love --pos noun,verb
```

Pronunciations are grouped by part of speech and retain Lexhint's source tags. `--region` performs exact normalized source-tag matching; `--locale` uses Lexhint's locale profile, including `en_CA`, `en_US`, and `en_GB`. `--include-neutral` requires a region or locale. A valid lookup with no matching pronunciation prints an explanation and exits with status 0.
## Dataset variants

dictterm defaults to Lexhint's `dictionary` variant because it contains dictionary entries and
lexical completion without the larger search indexes. Use `--variant rich` when a search-capable
artifact is desired. Lexhint's `lexical` and `runtime` variants do not contain dictionary entries
and cannot power the dictterm viewer.

```bash
dictterm love --variant dictionary
dictterm love --variant rich
dictterm love --variant dictionary --dataset-version 2026.08.20
```


Lexhint 0.4.2 also provides explicit catalog-backed dataset operations. Dictterm does not invoke these operations or contact the network automatically:

```bash
lexhint dataset available
lexhint dataset check
lexhint dataset update
lexhint dataset download en --variant dictionary
```

Use `available` to inspect compatible releases, `check` to inspect installed updates, and `update` to refresh installed languages and variants. Dataset catalog caching, downloads, integrity checks, and updates remain owned by Lexhint.

Viewer keys:

| Key                     | Action                            |
| ----------------------- | --------------------------------- |
| Arrow keys, mouse wheel | Scroll                            |
| Page Up / Page Down     | Page scroll                       |
| Space / `b`             | Page down / up                    |
| Home / End              | Document start / end              |
| `g` / `G`               | Document start / end aliases      |
| `j` / `k`               | Scroll down / up                  |
| `[` / `]`               | Previous / next dictionary entry  |
| `n` / `v`               | Cycle noun / verb entries         |
| `a` / `r`               | Cycle adjective / adverb entries  |
| `1` through `9`         | Jump to indexed entry             |
| Enter on `▶`            | Read focused semantic text (TTS)  |
| `/`                     | Look up another word              |
| `q`                     | Quit                              |
| `?`                     | Open key help (Esc / q closes it) |

The CLI asks Lexhint for the configured dictionary-capable managed artifact. The default is
`dictionary`; `rich` may be selected explicitly. It does **not** download, update, build, or mutate
datasets. If the selected artifact is missing, the CLI points you to the matching Lexhint command:

```bash
lexhint dataset download en --variant dictionary
```

## Configuration and TTS

The optional configuration file is resolved at `$XDG_CONFIG_HOME/dictterm/config.toml`, or at
`~/.config/dictterm/config.toml` when `XDG_CONFIG_HOME` is unset. Manage it with:

```bash
dictterm config path
dictterm config init
dictterm config show
dictterm config show --config ./test.toml
```

`config init` creates a commented starter file and refuses to overwrite an existing file.
`config show` displays effective settings after built-in defaults, TOML, `DICTTERM_*`
environment variables, and explicit command-line overrides. Unknown keys and invalid values are rejected.
The `--config PATH` option selects an alternate configuration source for lookup, config, and TTS commands.

Enable direct in-memory PyKokoro playback in the `[tts]` table:

```toml
[tts]
enabled = true
voice = "af_heart"
language = "en-us"
speed = 1.0
```

Then run `dictterm tts check` and open a word in the TUI. Read controls appear only when TTS is
enabled. Speech uses PyKokoro's in-memory sentence streaming: the first generated sentence starts
playing while later sentence audio is generated, using one output stream for each read request. No
external player, subprocess, temporary WAV, or complete generated-audio cache is used. `--plain`
remains deterministic and never adds speech controls.

## Exit status

- `0`: lookup succeeded
- `1`: no dictionary entry matched, or POS filtering removed every entry
- `2`: invalid invocation, dataset, or runtime error

## Versioning

The package version is dynamic and comes from Git tags via `setuptools-scm`.

```bash
git tag v0.1.0
python -m build
```

An unpacked source tree without Git metadata reports `0+unknown` rather than pretending to be a
release. At runtime `dictterm.__version__` reads installed package metadata via
`importlib.metadata`.

## Project layout

There is deliberately no `src/` directory:

```text
dictterm/
├── dictterm/
│   ├── __init__.py
│   ├── __main__.py
│   ├── backend.py
│   ├── cli.py
│   ├── cli_options.py
│   ├── commands/
│   │   ├── config.py
│   │   ├── lookup.py
│   │   └── tts.py
│   ├── config.py
│   ├── render.py
│   ├── selection.py
│   ├── speech.py
│   ├── tui.py
│   └── py.typed
├── tests/
├── LICENSE
├── README.md
└── pyproject.toml
```

## Licensing

The **dictterm source code** is licensed under the Apache License 2.0. Lexhint datasets are
external data artifacts and retain the licensing and provenance documented by Lexhint; this
project does not relicense them.
