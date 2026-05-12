# tex2docx

`tex2docx` is a bidirectional TeX and DOCX conversion project for academic papers.

The Python module path and public CLI are both `tex2docx`.

It provides:

- `tex2docx export`: convert `.tex` to `.docx`
- `tex2docx import`: convert `.docx` to `.tex`

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

## Usage

```bash
tex2docx export path/to/paper.tex -o path/to/paper.docx
tex2docx import path/to/paper.docx -o path/to/paper.tex
```

## Test

```bash
.venv/bin/pytest -q
```
