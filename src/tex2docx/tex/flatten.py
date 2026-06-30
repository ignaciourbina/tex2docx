"""Flatten LaTeX input/include trees before conversion."""

from __future__ import annotations

import re
from pathlib import Path


INPUT_RE = re.compile(r"\\(input|include)\s*\{([^{}]+)\}")
NEWCOMMAND_RE = re.compile(
    r"\\(?:re)?newcommand\*?\s*\{\\([A-Za-z@]+)\}\s*"
    r"(?:\[[^\]]+\]\s*)?\{([^{}]*)\}"
)
DEF_RE = re.compile(r"\\def\\([A-Za-z@]+)\s*\{([^{}]*)\}")


def flatten_tex_file(path: str | Path, *, max_depth: int = 20) -> str:
    """Return a TeX source with resolvable \\input and \\include files inlined."""
    tex_path = Path(path).resolve()
    return _flatten_path(tex_path, macros={}, stack=[], max_depth=max_depth)


def _flatten_path(
    tex_path: Path,
    *,
    macros: dict[str, str],
    stack: list[Path],
    max_depth: int,
) -> str:
    if len(stack) >= max_depth:
        return f"% tex2docx flatten skipped {tex_path}: max include depth reached\n"
    if tex_path in stack:
        return f"% tex2docx flatten skipped {tex_path}: recursive include\n"

    source = tex_path.read_text(encoding="utf-8")
    local_macros = dict(macros)
    local_macros.update(_collect_path_macros(source, tex_path.parent))

    return _flatten_source(
        source,
        base_dir=tex_path.parent,
        macros=local_macros,
        stack=[*stack, tex_path],
        max_depth=max_depth,
    )


def _collect_path_macros(source: str, base_dir: Path | None = None) -> dict[str, str]:
    macros: dict[str, str] = {}
    for match in NEWCOMMAND_RE.finditer(source):
        name, value = match.groups()
        if _looks_like_path(value):
            macros[name] = _resolve_macro_value(value, base_dir)
    for match in DEF_RE.finditer(source):
        name, value = match.groups()
        if _looks_like_path(value):
            macros[name] = _resolve_macro_value(value, base_dir)
    return macros


def _looks_like_path(value: str) -> bool:
    return "/" in value or value.startswith(".")


def _resolve_macro_value(value: str, base_dir: Path | None) -> str:
    if base_dir is None:
        return value
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate)
    return str((base_dir / candidate).resolve())


def _flatten_source(
    source: str,
    *,
    base_dir: Path,
    macros: dict[str, str],
    stack: list[Path],
    max_depth: int,
) -> str:
    flattened_lines: list[str] = []

    for line in source.splitlines(keepends=True):
        code, comment = _split_unescaped_comment(line)
        code = INPUT_RE.sub(
            lambda match: _expand_input(match, base_dir, macros, stack, max_depth),
            code,
        )
        flattened_lines.append(code + comment)

    return "".join(flattened_lines)


def _split_unescaped_comment(line: str) -> tuple[str, str]:
    for idx, char in enumerate(line):
        if char == "%" and not _is_escaped(line, idx):
            return line[:idx], line[idx:]
    return line, ""


def _is_escaped(text: str, idx: int) -> bool:
    backslashes = 0
    cursor = idx - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _expand_input(
    match: re.Match[str],
    base_dir: Path,
    macros: dict[str, str],
    stack: list[Path],
    max_depth: int,
) -> str:
    original = match.group(0)
    raw_path = match.group(2).strip()
    resolved_path = _resolve_input_path(raw_path, base_dir, macros)

    if resolved_path is None or not resolved_path.is_file():
        return original

    return _flatten_path(
        resolved_path,
        macros=macros,
        stack=stack,
        max_depth=max_depth,
    )


def _resolve_input_path(
    raw_path: str,
    base_dir: Path,
    macros: dict[str, str],
) -> Path | None:
    expanded = raw_path
    for name, value in macros.items():
        expanded = expanded.replace(f"\\{name}", value)

    if not expanded:
        return None

    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = base_dir / candidate

    if candidate.suffix:
        return candidate.resolve()

    with_tex = candidate.with_suffix(".tex")
    if with_tex.is_file():
        return with_tex.resolve()
    return candidate.resolve()
