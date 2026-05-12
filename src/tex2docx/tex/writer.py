"""LaTeX writer: IR tree -> .tex source string."""

from __future__ import annotations

from tex2docx.ir import (
    Abstract,
    Comment,
    Document,
    Formatted,
    FormatKind,
    Image,
    LineBreak,
    List,
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
    Text,
)


class TexWriter:
    """Walk an IR tree and produce a .tex string."""

    SECTION_CMD = {
        SectionLevel.SECTION: "section",
        SectionLevel.SUBSECTION: "subsection",
        SectionLevel.SUBSUBSECTION: "subsubsection",
    }

    FORMAT_CMD = {
        FormatKind.BOLD: "textbf",
        FormatKind.ITALIC: "textit",
        FormatKind.UNDERLINE: "underline",
    }

    REF_CMD = {
        RefKind.LABEL: "label",
        RefKind.REF: "ref",
        RefKind.CITE: "cite",
    }

    def __init__(self):
        self.lines: list[str] = []

    def write(self, ir_doc: Document) -> str:
        has_preamble = any(isinstance(c, Preamble) for c in ir_doc.children)

        # Separate preamble nodes from body nodes
        preamble_nodes = []
        body_nodes = []
        for child in ir_doc.children:
            if isinstance(child, (Preamble, Metadata)):
                preamble_nodes.append(child)
            else:
                body_nodes.append(child)

        # Emit preamble
        for node in preamble_nodes:
            self._emit(node)

        if has_preamble:
            self._line("\\begin{document}")
            self._line("")
            # Emit \maketitle if we have a title
            for node in preamble_nodes:
                if isinstance(node, Metadata) and node.title:
                    self._line("\\maketitle")
                    self._line("")
                    break

        # Emit body
        for node in body_nodes:
            self._emit(node)

        if has_preamble:
            self._line("\\end{document}")

        return "\n".join(self.lines) + "\n"

    def _emit(self, node: Node) -> None:
        match node:
            case Preamble():
                self._emit_preamble(node)
            case Metadata():
                self._emit_metadata(node)
            case Abstract():
                self._emit_abstract(node)
            case Section():
                self._emit_section(node)
            case Paragraph():
                self._emit_paragraph(node)
            case List():
                self._emit_list(node)
            case Table():
                self._emit_table(node)
            case Comment():
                self._emit_comment(node)
            case Math():
                self._emit_math_block(node)
            case RawLatex():
                self._line(node.content)
            case _:
                for child in node.children:
                    self._emit(child)

    def _emit_preamble(self, node: Preamble) -> None:
        opts = ",".join(node.class_options)
        if opts:
            self._line(f"\\documentclass[{opts}]{{{node.document_class}}}")
        else:
            self._line(f"\\documentclass{{{node.document_class}}}")

        for pkg, pkg_opts in node.packages:
            if pkg_opts:
                self._line(f"\\usepackage[{','.join(pkg_opts)}]{{{pkg}}}")
            else:
                self._line(f"\\usepackage{{{pkg}}}")

        for raw in node.raw_preamble_lines:
            self._line(raw)

        self._line("")

    def _emit_metadata(self, node: Metadata) -> None:
        if node.title:
            self._line(f"\\title{{{node.title}}}")
        if node.author:
            self._line(f"\\author{{{node.author}}}")
        if node.date:
            self._line(f"\\date{{{node.date}}}")
        self._line("")

    def _emit_abstract(self, node: Abstract) -> None:
        self._line("\\begin{abstract}")
        for child in node.children:
            self._emit(child)
        self._line("\\end{abstract}")
        self._line("")

    def _emit_section(self, node: Section) -> None:
        cmd = self.SECTION_CMD[node.level]
        self._line(f"\\{cmd}{{{node.title}}}")
        self._line("")
        for child in node.children:
            self._emit(child)

    def _emit_paragraph(self, node: Paragraph) -> None:
        # Check if paragraph contains images — emit them as centered figures
        has_image = any(isinstance(c, Image) for c in node.children)
        if has_image:
            for c in node.children:
                if isinstance(c, Image):
                    self._line("\\begin{center}")
                    self._line(f"  {self._inline_to_str(c)}")
                    self._line("\\end{center}")
                else:
                    inline = self._inline_to_str(c)
                    if inline.strip():
                        self._line(inline)
            self._line("")
        else:
            parts = [self._inline_to_str(c) for c in node.children]
            self._line("".join(parts))
            self._line("")

    def _emit_list(self, node: List) -> None:
        env = "itemize" if node.kind == ListKind.BULLETED else "enumerate"
        self._line(f"\\begin{{{env}}}")
        for item in node.children:
            parts = []
            for child in item.children:
                if isinstance(child, List):
                    # Nested list — emit the \item first, then the sublist
                    pass
                else:
                    parts.append(self._inline_to_str(child))
            self._line(f"  \\item {''.join(parts)}")
            # Emit nested lists after the item text
            for child in item.children:
                if isinstance(child, List):
                    self._emit_list(child)
        self._line(f"\\end{{{env}}}")
        self._line("")

    def _emit_table(self, node: Table) -> None:
        if not node.children:
            return

        # If col_spec exists, table came from LaTeX — preserve as-is
        # If col_spec is None, table came from DOCX — wrap in resizebox
        from_docx = node.col_spec is None
        col_spec = node.col_spec or self._default_col_spec(node)

        if from_docx:
            self._line("\\noindent\\resizebox{\\textwidth}{!}{%")

        self._line(f"\\begin{{tabular}}{{{col_spec}}}")
        self._line("\\hline")
        for row in node.children:
            cells = " & ".join(
                self._cell_to_str(cell, False)
                for cell in row.children
            )
            self._line(f"  {cells} \\\\")
            self._line("  \\hline")
        self._line("\\end{tabular}")

        if from_docx:
            self._line("}")

        self._line("")

    def _cell_to_str(self, cell, multiline: bool) -> str:
        """Convert a table cell to LaTeX string."""
        parts = []
        for c in cell.children:
            if isinstance(c, LineBreak):
                if multiline:
                    parts.append(" \\newline ")
                else:
                    parts.append(" ")
            else:
                parts.append(self._inline_to_str(c))
        return "".join(parts).strip()

    def _emit_comment(self, node: Comment) -> None:
        self._line(f"% {node.content}")

    def _emit_math_block(self, node: Math) -> None:
        if node.display:
            self._line("\\[")
            self._line(f"  {node.content}")
            self._line("\\]")
        else:
            # Inline math in a standalone paragraph context
            self._line(f"${node.content}$")
        self._line("")

    @staticmethod
    def _escape_latex(text: str) -> str:
        """Escape LaTeX special characters in plain text."""
        # Order matters: backslash first, then others
        # Don't escape if text already contains LaTeX commands
        if "\\" in text:
            return text  # Already has LaTeX commands, don't double-escape
        replacements = [
            ("&", r"\&"),
            ("%", r"\%"),
            ("$", r"\$"),
            ("#", r"\#"),
            ("_", r"\_"),
            ("{", r"\{"),
            ("}", r"\}"),
            ("~", r"\textasciitilde{}"),
            ("^", r"\textasciicircum{}"),
        ]
        for char, escaped in replacements:
            text = text.replace(char, escaped)
        return text

    def _inline_to_str(self, node: Node) -> str:
        match node:
            case Text(content=c):
                return self._escape_latex(c)
            case Formatted(kind=kind):
                cmd = self.FORMAT_CMD[kind]
                inner = "".join(self._inline_to_str(c) for c in node.children)
                return f"\\{cmd}{{{inner}}}"
            case Reference(kind=kind, key=key):
                cmd = self.REF_CMD[kind]
                return f"\\{cmd}{{{key}}}"
            case Image(path=p, width=w, height=h):
                opts = []
                if w:
                    opts.append(f"width={w}")
                elif not h:
                    # Default: constrain to text width for DOCX-imported images
                    opts.append("width=\\textwidth")
                if h:
                    opts.append(f"height={h}")
                opt_str = f"[{','.join(opts)}]" if opts else ""
                return f"\\includegraphics{opt_str}{{{p}}}"
            case Math(content=c, display=d):
                if d:
                    return f"\\[{c}\\]"
                return f"${c}$"
            case LineBreak():
                return " \\\\\n"
            case RawLatex(content=c):
                return c
            case _:
                return "".join(self._inline_to_str(c) for c in node.children)

    def _smart_col_spec(self, table: Table) -> str:
        """Generate column spec based on content analysis."""
        if not table.children:
            return "c"
        ncols = max(len(row.children) for row in table.children)

        # Measure max text length per column
        col_maxlen = [0] * ncols
        for row in table.children:
            for j, cell in enumerate(row.children):
                if j < ncols:
                    text = "".join(self._inline_to_str(c) for c in cell.children)
                    col_maxlen[j] = max(col_maxlen[j], len(text))

        # Classify columns: short (<10 chars) = 'c', medium = proportional 'p{}'
        total_text = sum(col_maxlen) or 1
        specs = []
        for j in range(ncols):
            if col_maxlen[j] <= 8:
                specs.append("c")
            else:
                # Proportional width based on content, in fractions of textwidth
                fraction = max(0.08, col_maxlen[j] / total_text)
                fraction = min(0.6, fraction)  # cap at 60%
                specs.append(f"p{{{fraction:.2f}\\textwidth}}")

        return " | ".join(specs)

    def _is_numeric_table(self, table: Table) -> bool:
        """Check if most columns contain short numeric data."""
        if not table.children:
            return False
        ncols = max(len(row.children) for row in table.children)
        if ncols < 4:
            return False
        short_cols = 0
        for j in range(ncols):
            max_len = 0
            for row in table.children:
                if j < len(row.children):
                    text = "".join(self._inline_to_str(c) for c in row.children[j].children)
                    max_len = max(max_len, len(text))
            if max_len <= 8:
                short_cols += 1
        return short_cols >= ncols * 0.6  # 60%+ columns are short

    def _default_col_spec(self, table: Table) -> str:
        if not table.children:
            return "c"
        ncols = max(len(row.children) for row in table.children)
        return " | ".join(["c"] * ncols)

    def _line(self, text: str) -> None:
        self.lines.append(text)
