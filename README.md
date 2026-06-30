# tex2docx

Bidirectional LaTeX-to-DOCX converter for academic papers. The Python package and the installed CLI are both named `tex2docx` (`tooling/tex2doc/pyproject.toml:6`, `tooling/tex2doc/pyproject.toml:21`).

Conversion goes through an intermediate representation (`tooling/tex2doc/src/tex2docx/ir.py:1`). Both directions share the same IR tree: source -> IR -> target (`tooling/tex2doc/src/tex2docx/pipeline.py:28`, `tooling/tex2doc/src/tex2docx/pipeline.py:71`).

## Commands

Two subcommands are registered on the `tex2docx` group (`tooling/tex2doc/src/tex2docx/cli.py:8`):

- `tex2docx export INPUT.tex` writes a `.docx` next to the input (or to `-o PATH`) (`tooling/tex2doc/src/tex2docx/cli.py:14`, `tooling/tex2doc/src/tex2docx/pipeline.py:30`).
- `tex2docx import INPUT.docx` writes a `.tex` (`tooling/tex2doc/src/tex2docx/cli.py:41`, `tooling/tex2doc/src/tex2docx/pipeline.py:73`).

### Export options

- `--image-dir DIR` overrides the directory used to resolve `\includegraphics` paths; defaults to the input `.tex` directory (`tooling/tex2doc/src/tex2docx/cli.py:18`, `tooling/tex2doc/src/tex2docx/pipeline.py:31`). `\graphicspath{...}` entries in the TeX source are also honored (`tooling/tex2doc/src/tex2docx/assets.py:17`).
- `--asset-dir DIR` sets where portable copies and PDF-to-PNG conversions of figures are written; defaults to `<output_stem>_assets/` next to the `.docx` (`tooling/tex2doc/src/tex2docx/cli.py:20`, `tooling/tex2doc/src/tex2docx/pipeline.py:32`).
- `--pdf-dpi N` controls DPI for PDF figure rasterization (default 220) (`tooling/tex2doc/src/tex2docx/cli.py:22`).
- `--flatten` inlines resolvable `\input` and `\include` files before parsing; `--flatten-output PATH` writes the flattened source and implies `--flatten` (`tooling/tex2doc/src/tex2docx/cli.py:24`, `tooling/tex2doc/src/tex2docx/cli.py:34`, `tooling/tex2doc/src/tex2docx/tex/flatten.py:17`).
- `--strict` fails on unsupported constructs instead of preserving them (`tooling/tex2doc/src/tex2docx/cli.py:28`).
- `-v/--verbose` enables extra logging (`tooling/tex2doc/src/tex2docx/cli.py:30`).

### Import options

- `--image-dir DIR` sets where extracted images are written; defaults to `images/` next to the output `.tex` (`tooling/tex2doc/src/tex2docx/cli.py:45`, `tooling/tex2doc/src/tex2docx/pipeline.py:74`).
- `--template TEX` reuses a reference `.tex` preamble in the output for round-trip fidelity (`tooling/tex2doc/src/tex2docx/cli.py:47`, `tooling/tex2doc/src/tex2docx/pipeline.py:95`).
- `--strict` and `-v/--verbose` mirror the export side (`tooling/tex2doc/src/tex2docx/cli.py:49`).

## Install

Python 3.12 or newer is required (`tooling/tex2doc/pyproject.toml:9`). From this directory:

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

Runtime dependencies pulled in by the install: `pylatexenc>=3.0a30`, `python-docx>=1.1.0`, `click>=8.0`, `Pillow>=10.0`, `latex2mathml`, `lxml`, `pymupdf>=1.24` (`tooling/tex2doc/pyproject.toml:10`).

The `dev` extra adds `pytest>=8.0` and `pytest-cov` (`tooling/tex2doc/pyproject.toml:29`).

## Tests

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

`pytest` is configured to discover tests under `tests/` (`tooling/tex2doc/pyproject.toml:26`). Fixtures live in `tests/fixtures/`, including `minimal.tex`, `full_paper.tex`, and a round-trip pair `docx/Urbina-Smirnov AI Attitudes v5.tex` / `docx/Urbina-Smirnov AI Attitudes v5.docx` (`tooling/tex2doc/tests/conftest.py:7`).

## Layout

- `src/tex2docx/cli.py` — Click CLI entry points.
- `src/tex2docx/pipeline.py` — orchestrates source -> IR -> target.
- `src/tex2docx/ir.py` — IR node definitions (`Document`, `Preamble`, `Paragraph`, `Image`, `Math`, etc.).
- `src/tex2docx/tex/` — TeX reader, writer, table handling, and flatten pass.
- `src/tex2docx/docx/` — DOCX reader, writer, math conversion, and styles.
- `src/tex2docx/assets.py` — image resolution and PDF-to-PNG asset preparation.
- `src/tex2docx/errors.py` — error types.
