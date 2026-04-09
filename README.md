# tex2docx

`tex2docx` is a bidirectional LaTeX and DOCX conversion project for academic papers.

The current Python package name is `doctex`. It provides:

- `doctex export`: convert `.tex` to `.docx`
- `doctex import`: convert `.docx` to `.tex`

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

## Usage

```bash
doctex export path/to/paper.tex -o path/to/paper.docx
doctex import path/to/paper.docx -o path/to/paper.tex
```

## Test

```bash
.venv/bin/pytest -q
```
