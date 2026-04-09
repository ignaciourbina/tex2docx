"""DOCX writer: IR tree -> .docx file."""

from __future__ import annotations

import json
import os
import re

from docx import Document as DocxDocument
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.oxml.ns import qn

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
    Text,
)
from doctex.docx.styles import ensure_styles, LATEX_COMMENT_STYLE, LATEX_RAW_STYLE
from doctex.docx.math import latex_to_omml


class DocxWriter:
    """Walk an IR tree and produce a .docx file."""

    def __init__(self, image_dir: str | None = None):
        self.image_dir = image_dir
        self.doc: DocxDocument = None  # type: ignore

    def write(self, ir_doc: Document, output_path: str) -> None:
        self.doc = DocxDocument()
        ensure_styles(self.doc)

        for child in ir_doc.children:
            self._emit(child)

        self._embed_preamble(ir_doc)
        self.doc.save(output_path)

    def _emit(self, node: Node) -> None:
        match node:
            case Preamble():
                pass  # Handled by _embed_preamble
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
                self._emit_raw_latex(node)
            case _:
                for child in node.children:
                    self._emit(child)

    def _emit_metadata(self, node: Metadata) -> None:
        if node.title:
            self.doc.core_properties.title = node.title
            self.doc.add_heading(node.title, level=0)
        if node.author:
            self.doc.core_properties.author = node.author
            para = self.doc.add_paragraph()
            run = para.add_run(node.author)
            run.italic = True
            para.alignment = 1  # CENTER
        if node.date:
            para = self.doc.add_paragraph()
            run = para.add_run(node.date)
            run.italic = True
            para.alignment = 1  # CENTER

    def _emit_abstract(self, node: Abstract) -> None:
        self.doc.add_heading("Abstract", level=2)
        for child in node.children:
            if isinstance(child, Paragraph):
                para = self.doc.add_paragraph()
                para.paragraph_format.first_line_indent = Cm(1)
                for inline in child.children:
                    self._add_inline(para, inline)
            else:
                self._emit(child)

    def _emit_section(self, node: Section) -> None:
        self.doc.add_heading(node.title, level=node.level.value)
        for child in node.children:
            self._emit(child)

    def _emit_paragraph(self, node: Paragraph) -> None:
        para = self.doc.add_paragraph()
        for child in node.children:
            self._add_inline(para, child)

    def _add_inline(self, para, node: Node) -> None:
        match node:
            case Text(content=c):
                para.add_run(c)
            case Formatted(kind=kind):
                self._add_formatted(para, node)
            case Reference(kind=kind, key=key):
                run = para.add_run(f"[{kind.name.lower()}:{key}]")
                run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
            case Image():
                self._emit_image_inline(para, node)
            case Math(content=c, display=d):
                self._emit_math_inline(para, node)
            case LineBreak():
                para.add_run().add_break()
            case RawLatex(content=c):
                run = para.add_run(c)
                run.font.name = "Courier New"
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            case _:
                for child in node.children:
                    self._add_inline(para, child)

    def _add_formatted(self, para, node: Formatted) -> None:
        """Add formatted text — collect leaf text and apply formatting."""
        for child in node.children:
            match child:
                case Text(content=c):
                    run = para.add_run(c)
                    self._apply_format(run, node.kind)
                case Formatted():
                    # Nested formatting: create runs with combined styles
                    self._add_nested_formatted(para, child, [node.kind])
                case _:
                    self._add_inline(para, child)

    def _add_nested_formatted(self, para, node: Formatted, kinds: list[FormatKind]) -> None:
        """Handle nested formatting like \\textbf{\\textit{text}}."""
        combined = kinds + [node.kind]
        for child in node.children:
            match child:
                case Text(content=c):
                    run = para.add_run(c)
                    for k in combined:
                        self._apply_format(run, k)
                case Formatted():
                    self._add_nested_formatted(para, child, combined)
                case _:
                    self._add_inline(para, child)

    def _apply_format(self, run, kind: FormatKind) -> None:
        if kind == FormatKind.BOLD:
            run.bold = True
        elif kind == FormatKind.ITALIC:
            run.italic = True
        elif kind == FormatKind.UNDERLINE:
            run.underline = True

    def _emit_list(self, node: List) -> None:
        style = "List Bullet" if node.kind == ListKind.BULLETED else "List Number"
        for item in node.children:
            para = self.doc.add_paragraph(style=style)
            for child in item.children:
                if isinstance(child, List):
                    # Nested list
                    self._emit_list(child)
                else:
                    self._add_inline(para, child)

    def _emit_table(self, node: Table) -> None:
        if not node.children:
            return
        nrows = len(node.children)
        ncols = max(len(row.children) for row in node.children)
        table = self.doc.add_table(rows=nrows, cols=ncols)
        table.style = "Table Grid"

        for i, row_node in enumerate(node.children):
            for j, cell_node in enumerate(row_node.children):
                cell = table.cell(i, j)
                # Clear default paragraph
                cell.paragraphs[0].text = ""
                for child in cell_node.children:
                    self._add_inline(cell.paragraphs[0], child)

    def _emit_image_inline(self, para, node: Image) -> None:
        path = node.resolved_path or node.path
        if self.image_dir and not os.path.isabs(path):
            path = os.path.join(self.image_dir, path)

        if os.path.isfile(path):
            width = self._parse_width(node.width)
            run = para.add_run()
            run.add_picture(path, width=width)
        else:
            run = para.add_run(f"[Image: {node.path}]")
            run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)

    def _parse_width(self, width_str: str | None) -> Inches | None:
        if not width_str:
            return Inches(5)  # Default width
        # Handle common LaTeX width specs
        if "\\textwidth" in width_str:
            match = re.match(r"([\d.]+)", width_str)
            if match:
                factor = float(match.group(1))
                return Inches(6.5 * factor)  # ~6.5 inch text width
        if width_str.endswith("in"):
            try:
                return Inches(float(width_str[:-2]))
            except ValueError:
                pass
        if width_str.endswith("cm"):
            try:
                return Cm(float(width_str[:-2]))
            except ValueError:
                pass
        return Inches(5)

    def _emit_math_block(self, node: Math) -> None:
        """Emit display math as an OMML equation paragraph."""
        para = self.doc.add_paragraph()
        self._insert_omml(para, node.content, display=True)

    def _emit_math_inline(self, para, node: Math) -> None:
        """Insert math as OMML into a paragraph."""
        self._insert_omml(para, node.content, display=node.display)

    def _insert_omml(self, para, latex_content: str, display: bool = False) -> None:
        """Convert LaTeX math to OMML and insert into paragraph."""
        try:
            omml = latex_to_omml(latex_content, display=display)
            para._element.append(omml)
        except Exception:
            # Fallback: render as gray monospace text
            delim = "\\[{}\\]" if display else "${}$"
            text = delim.format(latex_content)
            run = para.add_run(text)
            run.font.name = "Courier New"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    def _emit_comment(self, node: Comment) -> None:
        para = self.doc.add_paragraph(style=LATEX_COMMENT_STYLE)
        run = para.add_run(f"% {node.content}")
        run.font.hidden = True
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    def _emit_raw_latex(self, node: RawLatex) -> None:
        para = self.doc.add_paragraph(style=LATEX_RAW_STYLE)
        run = para.add_run(node.content)
        run.font.name = "Courier New"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    def _embed_preamble(self, ir_doc: Document) -> None:
        """Serialize preamble as JSON in a custom document property."""
        for child in ir_doc.children:
            if isinstance(child, Preamble):
                data = {
                    "document_class": child.document_class,
                    "class_options": child.class_options,
                    "packages": child.packages,
                    "raw_preamble_lines": child.raw_preamble_lines,
                }
                # Store as custom property via core properties' keywords field
                # (python-docx doesn't support custom properties directly,
                # so we use the 'keywords' field as a carrier)
                self.doc.core_properties.keywords = f"doctex_preamble:{json.dumps(data)}"
                break
