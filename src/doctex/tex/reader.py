"""LaTeX parser: .tex source -> IR tree."""

from __future__ import annotations

import re
import sys

from pylatexenc.latexwalker import (
    LatexWalker,
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
)
from pylatexenc.macrospec import (
    LatexContextDb,
    MacroSpec,
    EnvironmentSpec,
)
from pylatexenc import macrospec as ms

from doctex.ir import (
    Abstract,
    Comment,
    Document,
    Formatted,
    FormatKind,
    Image,
    LineBreak,
    List,
    ListItem,
    ListKind,
    Math,
    Metadata,
    Node,
    Paragraph,
    Preamble,
    RawLatex,
    Reference,
    RefKind,
    Section,
    SectionLevel,
    Table,
    TableCell,
    TableRow,
    Text,
)
from doctex.errors import ParseError, UnsupportedConstructError


def _build_context_db() -> LatexContextDb:
    """Build a LatexContextDb with the macros and environments we support."""
    db = LatexContextDb()
    db.set_unknown_macro_spec(MacroSpec("", args_parser=ms.MacroStandardArgsParser("")))
    db.set_unknown_environment_spec(EnvironmentSpec("", args_parser=ms.MacroStandardArgsParser("")))
    db.add_context_category(
        "doctex-macros",
        macros=[
            MacroSpec("documentclass", args_parser=ms.MacroStandardArgsParser("[{")),
            MacroSpec("usepackage", args_parser=ms.MacroStandardArgsParser("[{")),
            MacroSpec("title", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("author", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("date", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("maketitle", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("section", args_parser=ms.MacroStandardArgsParser("*{")),
            MacroSpec("subsection", args_parser=ms.MacroStandardArgsParser("*{")),
            MacroSpec("subsubsection", args_parser=ms.MacroStandardArgsParser("*{")),
            MacroSpec("textbf", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("textit", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("underline", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("emph", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("includegraphics", args_parser=ms.MacroStandardArgsParser("[{")),
            MacroSpec("label", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("ref", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("cite", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("item", args_parser=ms.MacroStandardArgsParser("[")),
            MacroSpec("hline", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("newline", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("\\", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("bibliography", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("bibliographystyle", args_parser=ms.MacroStandardArgsParser("{")),
            # Escaped special characters
            MacroSpec("&", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("%", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("$", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("#", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("_", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("textasciitilde", args_parser=ms.MacroStandardArgsParser("{")),
            MacroSpec("textasciicircum", args_parser=ms.MacroStandardArgsParser("{")),
            # Layout macros
            MacroSpec("noindent", args_parser=ms.MacroStandardArgsParser("")),
            MacroSpec("resizebox", args_parser=ms.MacroStandardArgsParser("{{{")),
            MacroSpec("textwidth", args_parser=ms.MacroStandardArgsParser("")),
        ],
        environments=[
            EnvironmentSpec("document"),
            EnvironmentSpec("abstract"),
            EnvironmentSpec("itemize"),
            EnvironmentSpec("enumerate"),
            EnvironmentSpec("tabular", args_parser=ms.MacroStandardArgsParser("{")),
            EnvironmentSpec("table", args_parser=ms.MacroStandardArgsParser("[")),
            EnvironmentSpec("figure", args_parser=ms.MacroStandardArgsParser("[")),
            EnvironmentSpec("equation"),
            EnvironmentSpec("equation*"),
            EnvironmentSpec("align"),
            EnvironmentSpec("align*"),
            EnvironmentSpec("center"),
        ],
    )
    return db


def _get_node_verbatim(node) -> str:
    """Get the original LaTeX source for a node."""
    if hasattr(node, "latex_verbatim"):
        return node.latex_verbatim()
    return ""


def _extract_macro_arg(node: LatexMacroNode, idx: int) -> str | None:
    """Extract the text content of a macro's argument by index.

    Arguments are stored in node.nodeargd.argnlist.
    Each can be a LatexGroupNode, LatexCharsNode, or None.
    """
    if node.nodeargd is None or node.nodeargd.argnlist is None:
        return None
    args = node.nodeargd.argnlist
    if idx >= len(args) or args[idx] is None:
        return None
    arg = args[idx]
    if hasattr(arg, "latex_verbatim"):
        raw = arg.latex_verbatim()
        # Strip surrounding braces/brackets
        if raw.startswith("{") and raw.endswith("}"):
            return raw[1:-1]
        if raw.startswith("[") and raw.endswith("]"):
            return raw[1:-1]
        return raw
    return None


def _extract_arg_nodelist(node: LatexMacroNode, idx: int) -> list | None:
    """Get the nodelist inside a macro argument group."""
    if node.nodeargd is None or node.nodeargd.argnlist is None:
        return None
    args = node.nodeargd.argnlist
    if idx >= len(args) or args[idx] is None:
        return None
    arg = args[idx]
    if hasattr(arg, "nodelist"):
        return arg.nodelist or []
    # If it's a single node, wrap it
    return [arg]


class TexReader:
    """Parse a .tex file string into an IR Document tree."""

    SECTION_CMDS = {
        "section": SectionLevel.SECTION,
        "subsection": SectionLevel.SUBSECTION,
        "subsubsection": SectionLevel.SUBSUBSECTION,
    }

    FORMAT_CMDS = {
        "textbf": FormatKind.BOLD,
        "textit": FormatKind.ITALIC,
        "emph": FormatKind.ITALIC,
        "underline": FormatKind.UNDERLINE,
    }

    ESCAPED_CHARS = {
        "&": "&",
        "%": "%",
        "$": "$",
        "#": "#",
        "_": "_",
    }

    REF_CMDS = {
        "label": RefKind.LABEL,
        "ref": RefKind.REF,
        "cite": RefKind.CITE,
    }

    def __init__(self, source: str, strict: bool = False):
        self.source = source
        self.strict = strict
        self.warnings: list[str] = []

    def parse(self) -> Document:
        ctx_db = _build_context_db()
        walker = LatexWalker(self.source, latex_context=ctx_db, tolerant_parsing=True)
        nodelist, _, _ = walker.get_latex_nodes()

        doc = Document()
        self._split_preamble_and_body(nodelist, doc)

        if self.warnings:
            for w in self.warnings:
                print(f"Warning: {w}", file=sys.stderr)

        return doc

    def _split_preamble_and_body(self, nodelist: list, doc: Document) -> None:
        """Find \\begin{document}, split into preamble + body."""
        preamble_nodes = []
        body_nodes = None

        for node in nodelist:
            if isinstance(node, LatexEnvironmentNode) and node.environmentname == "document":
                body_nodes = node.nodelist or []
                break
            preamble_nodes.append(node)

        if body_nodes is None:
            # No \begin{document} found — treat everything as body
            self.warnings.append("No \\begin{document} found — treating entire input as body")
            body_nodes = nodelist
            preamble_nodes = []

        if preamble_nodes:
            preamble, metadata = self._parse_preamble(preamble_nodes)
            doc.children.append(preamble)
            if metadata.title or metadata.author or metadata.date:
                doc.children.append(metadata)

        self._parse_body(body_nodes, doc)

    def _parse_preamble(self, nodes: list) -> tuple[Preamble, Metadata]:
        preamble = Preamble()
        metadata = Metadata()

        for node in nodes:
            if isinstance(node, LatexMacroNode):
                name = node.macroname
                if name == "documentclass":
                    opts = _extract_macro_arg(node, 0)  # optional arg
                    cls = _extract_macro_arg(node, 1)    # required arg
                    if cls:
                        preamble.document_class = cls
                    if opts:
                        preamble.class_options = [o.strip() for o in opts.split(",")]
                elif name == "usepackage":
                    opts_str = _extract_macro_arg(node, 0) or ""
                    pkg = _extract_macro_arg(node, 1) or ""
                    opts = [o.strip() for o in opts_str.split(",") if o.strip()] if opts_str else []
                    if pkg:
                        preamble.packages.append((pkg, opts))
                elif name == "title":
                    metadata.title = _extract_macro_arg(node, 0)
                elif name == "author":
                    metadata.author = _extract_macro_arg(node, 0)
                elif name == "date":
                    metadata.date = _extract_macro_arg(node, 0)
                else:
                    preamble.raw_preamble_lines.append(_get_node_verbatim(node))
            elif isinstance(node, LatexCommentNode):
                preamble.raw_preamble_lines.append(f"% {node.comment}")
            elif isinstance(node, LatexCharsNode):
                stripped = node.chars.strip()
                if stripped:
                    preamble.raw_preamble_lines.append(stripped)
            else:
                verb = _get_node_verbatim(node)
                if verb.strip():
                    preamble.raw_preamble_lines.append(verb)

        return preamble, metadata

    def _parse_body(self, nodes: list, parent: Node) -> None:
        """Parse body nodes into the parent's children."""
        # Collect inline content, flush as paragraphs on double-newline
        inline_buffer: list[Node] = []

        def flush_paragraph():
            if inline_buffer:
                # Filter out whitespace-only text nodes
                meaningful = [
                    n for n in inline_buffer
                    if not (isinstance(n, Text) and not n.content.strip())
                ]
                if meaningful:
                    parent.children.append(Paragraph(children=list(meaningful)))
                inline_buffer.clear()

        for node in nodes:
            if node is None:
                continue

            if isinstance(node, LatexMacroNode):
                name = node.macroname
                if name in self.SECTION_CMDS:
                    flush_paragraph()
                    self._handle_section(node, parent)
                elif name in self.FORMAT_CMDS:
                    inline_buffer.extend(self._handle_format(node))
                elif name in self.REF_CMDS:
                    inline_buffer.append(self._handle_reference(node))
                elif name == "includegraphics":
                    inline_buffer.append(self._handle_image(node))
                elif name == "maketitle":
                    continue  # handled by Metadata presence
                elif name == "item":
                    continue  # handled inside list environments
                elif name in ("\\", "newline"):
                    inline_buffer.append(LineBreak())
                elif name == "hline":
                    continue  # handled in tabular
                elif name in ("bibliography", "bibliographystyle"):
                    flush_paragraph()
                    parent.children.append(RawLatex(content=_get_node_verbatim(node)))
                elif name in self.ESCAPED_CHARS:
                    # \& \% \$ \# \_ -> literal character
                    inline_buffer.append(Text(content=self.ESCAPED_CHARS[name]))
                elif name in ("textasciitilde", "textasciicircum"):
                    char = "~" if name == "textasciitilde" else "^"
                    inline_buffer.append(Text(content=char))
                elif name == "noindent":
                    continue  # skip layout commands
                elif name == "resizebox":
                    # \resizebox{width}{height}{content} — parse content (arg 2)
                    content_nodes = _extract_arg_nodelist(node, 2)
                    if content_nodes:
                        self._parse_body(content_nodes, parent)
                    else:
                        # Fallback: try to get the verbatim and re-parse
                        flush_paragraph()
                elif name == "textwidth":
                    continue  # dimensionless, skip
                else:
                    self._handle_unknown_macro(node, inline_buffer, parent, flush_paragraph)

            elif isinstance(node, LatexEnvironmentNode):
                flush_paragraph()
                self._handle_environment(node, parent)

            elif isinstance(node, LatexCommentNode):
                flush_paragraph()
                parent.children.append(Comment(content=node.comment.strip()))

            elif isinstance(node, LatexCharsNode):
                self._handle_chars(node, inline_buffer, flush_paragraph)

            elif isinstance(node, LatexMathNode):
                inline_buffer.append(self._handle_math(node))

            elif isinstance(node, LatexGroupNode):
                # A bare group {text} — parse its contents inline
                if node.nodelist:
                    for child_node in node.nodelist:
                        if isinstance(child_node, LatexCharsNode):
                            inline_buffer.append(Text(content=child_node.chars))
                        elif isinstance(child_node, LatexMacroNode):
                            if child_node.macroname in self.FORMAT_CMDS:
                                inline_buffer.extend(self._handle_format(child_node))
                            else:
                                inline_buffer.append(RawLatex(content=_get_node_verbatim(child_node)))

            else:
                verb = _get_node_verbatim(node)
                if verb.strip():
                    if self.strict:
                        raise UnsupportedConstructError(f"Unsupported node: {verb[:50]}")
                    self.warnings.append(f"Unsupported node preserved as raw: {verb[:50]}")
                    inline_buffer.append(RawLatex(content=verb))

        flush_paragraph()

    def _handle_chars(self, node: LatexCharsNode, inline_buffer: list[Node],
                      flush_paragraph) -> None:
        """Handle character nodes, splitting on double newlines for paragraph breaks."""
        text = node.chars

        # Split on double-newline (paragraph boundary)
        parts = re.split(r"\n\s*\n", text)

        for i, part in enumerate(parts):
            if i > 0:
                flush_paragraph()
            # Normalize whitespace within a paragraph piece
            normalized = re.sub(r"\s+", " ", part)
            if not normalized.strip():
                continue
            # Preserve leading/trailing spaces when there might be adjacent
            # inline content (formatted text, math, etc.). We keep exactly
            # one space on each side if the original had whitespace there.
            # The paragraph-level flush will handle overall trimming.
            if inline_buffer and normalized.startswith(" "):
                # Keep leading space — it separates from previous inline node
                content = normalized.lstrip(" ")
                content = " " + content
            else:
                content = normalized.lstrip()
            # Keep trailing space if present — might precede a formatted node
            if not content.endswith(" ") and normalized.endswith(" "):
                content = content + " "  # will be meaningful if next node is inline
            elif not normalized.rstrip():
                content = content
            inline_buffer.append(Text(content=content))

    def _handle_section(self, node: LatexMacroNode, parent: Node) -> None:
        level = self.SECTION_CMDS[node.macroname]
        # Star variant detection: arg 0 is the optional * (or None)
        title = _extract_macro_arg(node, 1) or _extract_macro_arg(node, 0) or ""
        parent.children.append(Section(level=level, title=title))

    def _handle_format(self, node: LatexMacroNode) -> list[Node]:
        kind = self.FORMAT_CMDS[node.macroname]
        arg_nodes = _extract_arg_nodelist(node, 0)
        if arg_nodes:
            children = self._parse_inline_nodes(arg_nodes)
        else:
            text = _extract_macro_arg(node, 0) or ""
            children = [Text(content=text)]
        return [Formatted(kind=kind, children=children)]

    def _handle_reference(self, node: LatexMacroNode) -> Reference:
        kind = self.REF_CMDS[node.macroname]
        key = _extract_macro_arg(node, 0) or ""
        return Reference(kind=kind, key=key)

    def _handle_image(self, node: LatexMacroNode) -> Image:
        opts_str = _extract_macro_arg(node, 0) or ""
        path = _extract_macro_arg(node, 1) or ""
        width = None
        height = None
        if opts_str:
            for opt in opts_str.split(","):
                opt = opt.strip()
                if opt.startswith("width="):
                    width = opt[6:]
                elif opt.startswith("height="):
                    height = opt[7:]
        return Image(path=path, width=width, height=height)

    def _handle_math(self, node: LatexMathNode) -> Math:
        # Get the inner content (without delimiters)
        if node.nodelist:
            content = "".join(_get_node_verbatim(n) for n in node.nodelist)
        else:
            # Fallback: extract from verbatim
            verb = _get_node_verbatim(node)
            # Strip delimiters
            for start, end in [("\\[", "\\]"), ("$$", "$$"), ("$", "$")]:
                if verb.startswith(start) and verb.endswith(end):
                    content = verb[len(start):-len(end)]
                    break
            else:
                content = verb
        display = node.displaytype == "display"
        return Math(content=content.strip(), display=display)

    def _handle_environment(self, node: LatexEnvironmentNode, parent: Node) -> None:
        name = node.environmentname
        body = node.nodelist or []

        if name == "abstract":
            abstract = Abstract()
            self._parse_body(body, abstract)
            parent.children.append(abstract)
        elif name == "itemize":
            self._parse_list(body, ListKind.BULLETED, parent)
        elif name == "enumerate":
            self._parse_list(body, ListKind.NUMBERED, parent)
        elif name == "tabular":
            self._parse_tabular(node, parent)
        elif name in ("figure", "table"):
            # Wrapper environments — parse their contents directly
            self._parse_body(body, parent)
        elif name == "center":
            self._parse_body(body, parent)
        elif name in ("equation", "equation*", "align", "align*"):
            content = "".join(_get_node_verbatim(n) for n in body)
            parent.children.append(Math(content=content.strip(), display=True))
        else:
            verb = _get_node_verbatim(node)
            if self.strict:
                raise UnsupportedConstructError(f"Unsupported environment: {name}")
            self.warnings.append(f"Unsupported environment '{name}' preserved as raw")
            parent.children.append(RawLatex(content=verb))

    def _parse_list(self, nodes: list, kind: ListKind, parent: Node) -> None:
        """Parse \\item nodes inside an itemize/enumerate."""
        lst = List(kind=kind)
        current_item: ListItem | None = None

        for node in nodes:
            if node is None:
                continue
            if isinstance(node, LatexMacroNode) and node.macroname == "item":
                current_item = ListItem()
                lst.children.append(current_item)
                # Item might have optional label in [...]
            elif current_item is not None:
                if isinstance(node, LatexCharsNode):
                    # Normalize whitespace but preserve spaces between inline elements
                    text = re.sub(r"\s+", " ", node.chars)
                    # Only strip leading space if this is the first content in the item
                    if not current_item.children:
                        text = text.lstrip()
                    if text:
                        current_item.children.append(Text(content=text))
                elif isinstance(node, LatexMacroNode):
                    if node.macroname in self.FORMAT_CMDS:
                        current_item.children.extend(self._handle_format(node))
                    elif node.macroname in self.REF_CMDS:
                        current_item.children.append(self._handle_reference(node))
                    elif node.macroname == "includegraphics":
                        current_item.children.append(self._handle_image(node))
                    else:
                        current_item.children.append(RawLatex(content=_get_node_verbatim(node)))
                elif isinstance(node, LatexMathNode):
                    current_item.children.append(self._handle_math(node))
                elif isinstance(node, LatexEnvironmentNode):
                    # Nested list
                    if node.environmentname in ("itemize", "enumerate"):
                        nested_kind = ListKind.BULLETED if node.environmentname == "itemize" else ListKind.NUMBERED
                        self._parse_list(node.nodelist or [], nested_kind, current_item)
                    else:
                        current_item.children.append(RawLatex(content=_get_node_verbatim(node)))

        parent.children.append(lst)

    def _parse_tabular(self, env_node: LatexEnvironmentNode, parent: Node) -> None:
        """Parse a tabular environment into a Table with rows and cells."""
        # Extract column spec from the environment's argument
        col_spec = None
        if env_node.nodeargd and env_node.nodeargd.argnlist:
            for arg in env_node.nodeargd.argnlist:
                if arg is not None:
                    raw = _get_node_verbatim(arg)
                    if raw.startswith("{") and raw.endswith("}"):
                        col_spec = raw[1:-1]
                    else:
                        col_spec = raw
                    break

        table = Table(col_spec=col_spec)
        body_nodes = env_node.nodelist or []

        # Split nodes into rows by \\ macro, then cells by & chars
        current_row_nodes: list = []
        rows_of_nodes: list[list] = []

        for node in body_nodes:
            if node is None:
                continue
            if isinstance(node, LatexMacroNode) and node.macroname == "\\":
                rows_of_nodes.append(current_row_nodes)
                current_row_nodes = []
            elif isinstance(node, LatexMacroNode) and node.macroname == "hline":
                continue
            else:
                current_row_nodes.append(node)

        if current_row_nodes:
            rows_of_nodes.append(current_row_nodes)

        for row_nodes in rows_of_nodes:
            # Split row nodes into cells by & (LatexCharsNode containing &)
            cells_nodes: list[list] = [[]]
            for node in row_nodes:
                if isinstance(node, LatexCharsNode) and "&" in node.chars:
                    # Split on &
                    parts = node.chars.split("&")
                    # First part goes to current cell
                    if parts[0].strip():
                        cells_nodes[-1].append(
                            type(node)(chars=parts[0], pos=node.pos, pos_end=node.pos_end)
                        )
                    # Each subsequent part starts a new cell
                    for part in parts[1:]:
                        cells_nodes.append([])
                        if part.strip():
                            cells_nodes[-1].append(
                                type(node)(chars=part, pos=node.pos, pos_end=node.pos_end)
                            )
                elif isinstance(node, LatexMacroNode) and node.macroname == "&":
                    cells_nodes.append([])
                else:
                    cells_nodes[-1].append(node)

            # Skip empty rows
            if all(not cn for cn in cells_nodes):
                continue

            row = TableRow()
            for cell_nodes in cells_nodes:
                # Parse cell nodes as inline content
                children = self._parse_inline_nodes(cell_nodes)
                row.children.append(TableCell(children=children))

            # Skip rows where all cells are empty
            has_content = any(
                any(not (isinstance(c, Text) and not c.content.strip())
                    for c in cell.children)
                for cell in row.children
                if cell.children
            )
            if row.children and has_content:
                table.children.append(row)

        parent.children.append(table)

    def _parse_inline_nodes(self, nodes: list) -> list[Node]:
        """Convert a list of latex nodes into inline IR nodes."""
        result: list[Node] = []
        for node in nodes:
            if node is None:
                continue
            if isinstance(node, LatexCharsNode):
                if node.chars.strip():
                    result.append(Text(content=node.chars))
            elif isinstance(node, LatexMacroNode):
                if node.macroname in self.FORMAT_CMDS:
                    result.extend(self._handle_format(node))
                elif node.macroname in self.REF_CMDS:
                    result.append(self._handle_reference(node))
                elif node.macroname == "includegraphics":
                    result.append(self._handle_image(node))
                elif node.macroname in self.ESCAPED_CHARS:
                    result.append(Text(content=self.ESCAPED_CHARS[node.macroname]))
                elif node.macroname in ("textasciitilde", "textasciicircum"):
                    result.append(Text(content="~" if node.macroname == "textasciitilde" else "^"))
                elif node.macroname in ("\\", "newline"):
                    result.append(LineBreak())
                else:
                    result.append(RawLatex(content=_get_node_verbatim(node)))
            elif isinstance(node, LatexMathNode):
                result.append(self._handle_math(node))
            elif isinstance(node, LatexGroupNode):
                if node.nodelist:
                    result.extend(self._parse_inline_nodes(node.nodelist))
            else:
                verb = _get_node_verbatim(node)
                if verb.strip():
                    result.append(RawLatex(content=verb))
        return result

    def _handle_unknown_macro(self, node: LatexMacroNode, inline_buffer: list[Node],
                              parent: Node, flush_paragraph) -> None:
        verb = _get_node_verbatim(node)
        if self.strict:
            raise UnsupportedConstructError(f"Unsupported macro: \\{node.macroname}")
        self.warnings.append(f"Unsupported macro '\\{node.macroname}' preserved as raw")
        inline_buffer.append(RawLatex(content=verb))
