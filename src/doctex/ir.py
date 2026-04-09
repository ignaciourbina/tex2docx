"""Intermediate Representation for doctex document trees.

The IR is the central data structure. Every pipeline is Source -> IR -> Target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator


class FormatKind(Enum):
    BOLD = auto()
    ITALIC = auto()
    UNDERLINE = auto()


class ListKind(Enum):
    BULLETED = auto()
    NUMBERED = auto()


class RefKind(Enum):
    LABEL = auto()
    REF = auto()
    CITE = auto()


class SectionLevel(Enum):
    SECTION = 1
    SUBSECTION = 2
    SUBSUBSECTION = 3


# --- Node definitions ---


@dataclass
class Node:
    """Base for all IR nodes."""

    children: list[Node] = field(default_factory=list)


@dataclass
class Document(Node):
    """Root node of the document tree."""

    pass


@dataclass
class Preamble(Node):
    """Stores LaTeX preamble info (no DOCX equivalent — embedded as metadata)."""

    document_class: str = "article"
    class_options: list[str] = field(default_factory=list)
    packages: list[tuple[str, list[str]]] = field(default_factory=list)
    raw_preamble_lines: list[str] = field(default_factory=list)


@dataclass
class Metadata(Node):
    """Title, author, date."""

    title: str | None = None
    author: str | None = None
    date: str | None = None


@dataclass
class Abstract(Node):
    """Abstract environment. Children are paragraph nodes."""

    pass


@dataclass
class Section(Node):
    """A section heading. Children are the content under that section."""

    level: SectionLevel = SectionLevel.SECTION
    title: str = ""


@dataclass
class Paragraph(Node):
    """A paragraph. Children are inline nodes (Text, Formatted, etc.)."""

    pass


@dataclass
class Text(Node):
    """Leaf node: plain text."""

    content: str = ""


@dataclass
class Formatted(Node):
    """Inline formatting wrapper. Children are the formatted content."""

    kind: FormatKind = FormatKind.BOLD


@dataclass
class LineBreak(Node):
    """Explicit line break (\\\\)."""

    pass


@dataclass
class List(Node):
    """A list. Children are ListItem nodes."""

    kind: ListKind = ListKind.BULLETED


@dataclass
class ListItem(Node):
    """One \\item. Children are inline content."""

    pass


@dataclass
class Table(Node):
    """A table. Children are TableRow nodes."""

    col_spec: str | None = None


@dataclass
class TableRow(Node):
    """A table row. Children are TableCell nodes."""

    pass


@dataclass
class TableCell(Node):
    """A table cell. Children are inline content."""

    pass


@dataclass
class Image(Node):
    """An image reference."""

    path: str = ""
    resolved_path: str | None = None
    width: str | None = None
    height: str | None = None


@dataclass
class Reference(Node):
    """A cross-reference or citation marker."""

    kind: RefKind = RefKind.REF
    key: str = ""


@dataclass
class Comment(Node):
    """A LaTeX comment, preserved for round-trip fidelity."""

    content: str = ""


@dataclass
class Math(Node):
    """A math expression."""

    content: str = ""
    display: bool = False  # True for display math (\[...\]), False for inline ($...$)


@dataclass
class RawLatex(Node):
    """Unsupported LaTeX construct, preserved verbatim."""

    content: str = ""


# --- Tree utilities ---


def walk(node: Node) -> Iterator[Node]:
    """Depth-first traversal of the IR tree."""
    yield node
    for child in node.children:
        yield from walk(child)


def find_all(node: Node, node_type: type[Node]) -> list[Node]:
    """Find all descendants of a given type."""
    return [n for n in walk(node) if isinstance(n, node_type)]


def pretty_print(node: Node, indent: int = 0) -> str:
    """Debug representation of the IR tree."""
    prefix = "  " * indent
    parts = [f"{prefix}{type(node).__name__}"]

    # Add key attributes
    match node:
        case Text(content=c):
            parts[0] += f"({c!r})"
        case Section(level=lv, title=t):
            parts[0] += f"(level={lv.name}, title={t!r})"
        case Formatted(kind=k):
            parts[0] += f"(kind={k.name})"
        case List(kind=k):
            parts[0] += f"(kind={k.name})"
        case Image(path=p):
            parts[0] += f"(path={p!r})"
        case Reference(kind=k, key=key):
            parts[0] += f"(kind={k.name}, key={key!r})"
        case Comment(content=c):
            parts[0] += f"({c!r})"
        case Math(content=c, display=d):
            parts[0] += f"(display={d}, {c!r})"
        case RawLatex(content=c):
            parts[0] += f"({c!r})"
        case Preamble(document_class=dc):
            parts[0] += f"(class={dc!r})"
        case Metadata(title=t, author=a):
            parts[0] += f"(title={t!r}, author={a!r})"
        case Table(col_spec=cs):
            parts[0] += f"(col_spec={cs!r})"

    for child in node.children:
        parts.append(pretty_print(child, indent + 1))

    return "\n".join(parts)
