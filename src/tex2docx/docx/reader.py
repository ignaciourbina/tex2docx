"""DOCX reader: .docx file -> IR tree."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from docx import Document as DocxDocument
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from lxml import etree

from tex2docx.ir import (
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
from tex2docx.docx.styles import LATEX_COMMENT_STYLE, LATEX_RAW_STYLE
from tex2docx.docx.math import omml_to_latex, OMML_NS


# Pattern to match reference markers like [cite:key], [ref:key], [label:key]
REF_PATTERN = re.compile(r"\[(label|ref|cite):(.+?)\]")


class DocxReader:
    """Read a .docx file and produce an IR tree."""

    def __init__(self, image_dir: str | None = None, output_dir: str | None = None):
        self.image_dir = image_dir or "./images"
        self.output_dir = output_dir  # directory of the output .tex file
        self._image_map: dict[str, str] = {}  # rId -> saved path

    def read(self, path: str) -> Document:
        self.docx_doc = DocxDocument(path)
        self._docx_path = path
        ir_doc = Document()

        # Recover preamble from custom property
        preamble = self._recover_preamble()
        if preamble:
            ir_doc.children.append(preamble)

        # Extract images
        self._extract_images()

        # Walk body elements in document order
        self._walk_body(ir_doc)

        return ir_doc

    def _recover_preamble(self) -> Preamble | None:
        """Try to recover preamble from the keywords custom property."""
        try:
            keywords = self.docx_doc.core_properties.keywords or ""
            if keywords.startswith("doctex_preamble:"):
                data = json.loads(keywords[len("doctex_preamble:"):])
                preamble = Preamble(
                    document_class=data.get("document_class", "article"),
                    class_options=data.get("class_options", []),
                    packages=[(p[0], p[1]) for p in data.get("packages", [])],
                    raw_preamble_lines=data.get("raw_preamble_lines", []),
                )
                return preamble
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None

    def _extract_images(self) -> None:
        """Extract all images from the DOCX and save to image_dir."""
        img_dir = Path(self.image_dir)
        img_dir.mkdir(parents=True, exist_ok=True)

        # Determine base for relative paths
        if self.output_dir:
            base = Path(self.output_dir).resolve()
        else:
            base = Path.cwd()

        counter = 0
        for rel in self.docx_doc.part.rels.values():
            if "image" in rel.reltype:
                counter += 1
                ext = os.path.splitext(rel.target_ref)[1] or ".png"
                filename = f"image_{counter:03d}{ext}"
                save_path = img_dir / filename

                with open(save_path, "wb") as f:
                    f.write(rel.target_part.blob)

                # Store relative path for LaTeX output
                try:
                    rel_path = os.path.relpath(save_path.resolve(), base)
                except ValueError:
                    rel_path = str(save_path)
                self._image_map[rel.rId] = rel_path

    def _walk_body(self, ir_doc: Document) -> None:
        """Walk the document body elements in order."""
        metadata = Metadata()
        found_title = False
        found_author = False
        found_date = False
        in_abstract = False
        abstract_node: Abstract | None = None
        current_list: List | None = None
        current_list_kind: ListKind | None = None

        for element in self.docx_doc.element.body:
            tag = element.tag

            if tag.endswith("}p"):  # paragraph
                para = self._find_paragraph(element)
                if para is None:
                    continue

                style_name = para.style.name if para.style else ""

                # Check for OMML math in this paragraph
                omml_elements = element.findall(f".//{{{OMML_NS}}}oMath")
                has_omml = len(omml_elements) > 0

                # Detect if math is inline (mixed with text) or display (standalone)
                if has_omml:
                    para_text = (para.text or "").strip()
                    # Check if there are non-math runs with real text
                    non_math_text = ""
                    for run in para.runs:
                        if run.text and run.text.strip():
                            non_math_text += run.text.strip()
                    is_inline_math = len(non_math_text) > 0

                    if not is_inline_math:
                        # Pure math paragraph -> display math
                        if current_list:
                            ir_doc.children.append(current_list)
                            current_list = None
                            current_list_kind = None
                        target = abstract_node if in_abstract else ir_doc
                        self._handle_math_para(omml_elements, target, display=True)
                        continue
                    # else: inline math — fall through to normal paragraph handling

                if style_name == "Title":
                    metadata.title = para.text
                    found_title = True
                    continue

                # Detect author/date: italic centered paragraphs right after title
                if found_title and not found_date:
                    is_centered = para.alignment == 1  # CENTER
                    is_italic = (para.runs and
                                 all(run.italic for run in para.runs if run.text.strip()))
                    if is_centered and is_italic:
                        if not found_author:
                            metadata.author = para.text
                            found_author = True
                            continue
                        else:
                            metadata.date = para.text
                            found_date = True
                            continue

                if style_name and style_name.startswith("Heading"):
                    # Flush list
                    if current_list:
                        ir_doc.children.append(current_list)
                        current_list = None
                        current_list_kind = None

                    # End abstract if we were in one
                    if in_abstract and abstract_node:
                        ir_doc.children.append(abstract_node)
                        in_abstract = False
                        abstract_node = None

                    heading_text = (para.text or "").strip()
                    level = self._parse_heading_level(style_name)

                    # Detect "Abstract" heading -> abstract environment
                    if heading_text.lower() == "abstract":
                        abstract_node = Abstract()
                        in_abstract = True
                        continue

                    section = Section(
                        level=self._int_to_section_level(level),
                        title=heading_text,
                    )
                    ir_doc.children.append(section)
                    continue

                # List detection
                list_kind = self._detect_list_style(style_name)
                if list_kind is not None:
                    if current_list is None or current_list_kind != list_kind:
                        if current_list:
                            target = abstract_node if in_abstract else ir_doc
                            target.children.append(current_list)
                        current_list = List(kind=list_kind)
                        current_list_kind = list_kind
                    item = ListItem(children=self._parse_runs(para))
                    current_list.children.append(item)
                    continue

                # Flush list if we hit a non-list paragraph
                if current_list:
                    target = abstract_node if in_abstract else ir_doc
                    target.children.append(current_list)
                    current_list = None
                    current_list_kind = None

                # Comment style
                if style_name == LATEX_COMMENT_STYLE:
                    text = para.text or ""
                    if text.startswith("% "):
                        text = text[2:]
                    target = abstract_node if in_abstract else ir_doc
                    target.children.append(Comment(content=text))
                    continue

                # Raw latex style
                if style_name == LATEX_RAW_STYLE:
                    target = abstract_node if in_abstract else ir_doc
                    target.children.append(RawLatex(content=para.text or ""))
                    continue

                # Normal paragraph (may contain inline math)
                children = self._parse_runs_with_math(para, element) if has_omml else self._parse_runs(para)
                if children:
                    target = abstract_node if in_abstract else ir_doc
                    target.children.append(Paragraph(children=children))

            elif tag.endswith("}tbl"):  # table
                # Flush list
                if current_list:
                    target = abstract_node if in_abstract else ir_doc
                    target.children.append(current_list)
                    current_list = None
                    current_list_kind = None

                tbl = self._find_table(element)
                if tbl:
                    target = abstract_node if in_abstract else ir_doc
                    self._handle_table(tbl, target)

        # Flush remaining list
        if current_list:
            ir_doc.children.append(current_list)

        # Flush abstract if still open
        if in_abstract and abstract_node:
            ir_doc.children.append(abstract_node)

        # Insert metadata if found
        has_metadata = found_title or found_author
        if has_metadata and (metadata.title or metadata.author):
            ir_doc.children.insert(0 if not any(isinstance(c, Preamble) for c in ir_doc.children) else 1, metadata)

    def _find_paragraph(self, element):
        """Find the python-docx Paragraph object for an XML element."""
        for para in self.docx_doc.paragraphs:
            if para._element is element:
                return para
        # Fallback: create a paragraph wrapper
        from docx.text.paragraph import Paragraph as DocxParagraph
        return DocxParagraph(element, self.docx_doc.element.body)

    def _find_table(self, element):
        """Find the python-docx Table object for an XML element."""
        for table in self.docx_doc.tables:
            if table._element is element:
                return table
        return None

    def _parse_heading_level(self, style_name: str) -> int:
        """Extract heading level from style name like 'Heading 1'."""
        match = re.search(r"(\d+)", style_name)
        if match:
            return int(match.group(1))
        return 1

    def _int_to_section_level(self, level: int) -> SectionLevel:
        if level <= 1:
            return SectionLevel.SECTION
        elif level == 2:
            return SectionLevel.SUBSECTION
        else:
            return SectionLevel.SUBSUBSECTION

    def _detect_list_style(self, style_name: str) -> ListKind | None:
        if not style_name:
            return None
        name_lower = style_name.lower()
        if "list bullet" in name_lower:
            return ListKind.BULLETED
        if "list number" in name_lower:
            return ListKind.NUMBERED
        return None

    def _parse_runs(self, para) -> list[Node]:
        """Convert a paragraph's runs into inline IR nodes."""
        nodes: list[Node] = []

        for run in para.runs:
            text = run.text
            if not text:
                # Check for inline images
                inline_images = run._element.findall(f".//{qn('wp:inline')}")
                if inline_images:
                    img_node = self._extract_run_image(run)
                    if img_node:
                        nodes.append(img_node)
                continue

            # Check for reference markers
            ref_match = REF_PATTERN.match(text)
            if ref_match:
                kind_str = ref_match.group(1).upper()
                key = ref_match.group(2)
                nodes.append(Reference(kind=RefKind[kind_str], key=key))
                continue

            # Build node with formatting
            text_node: Node = Text(content=text)

            has_format = False
            if run.bold:
                text_node = Formatted(kind=FormatKind.BOLD, children=[text_node])
                has_format = True
            if run.italic:
                text_node = Formatted(kind=FormatKind.ITALIC, children=[text_node])
                has_format = True
            if run.underline:
                text_node = Formatted(kind=FormatKind.UNDERLINE, children=[text_node])
                has_format = True

            nodes.append(text_node)

        return nodes

    def _extract_run_image(self, run) -> Image | None:
        """Extract an image from a run's inline drawing."""
        blip_elements = run._element.findall(f".//{qn('a:blip')}")
        if not blip_elements:
            return None

        blip = blip_elements[0]
        embed = blip.get(qn("r:embed"))
        if embed and embed in self._image_map:
            return Image(path=self._image_map[embed])
        return None

    def _handle_table(self, table, ir_doc: Document) -> None:
        """Convert a python-docx Table to IR."""
        # First, build raw rows
        raw_rows: list[list[list[Node]]] = []  # row -> cell -> nodes
        for row in table.rows:
            raw_row = []
            for cell in row.cells:
                cell_content: list[Node] = []
                paragraphs = cell.paragraphs
                for p_idx, para in enumerate(paragraphs):
                    runs = self._parse_runs(para)
                    cell_content.extend(runs)
                    if p_idx < len(paragraphs) - 1 and runs:
                        cell_content.append(LineBreak())
                raw_row.append(cell_content)
            raw_rows.append(raw_row)

        # Merge consecutive rows with identical data columns
        # (common pattern: description row + parenthetical row with same numbers)
        merged_rows = self._merge_duplicate_rows(raw_rows)

        ir_table = Table()
        for row_cells in merged_rows:
            ir_row = TableRow()
            for cell_nodes in row_cells:
                ir_row.children.append(TableCell(children=cell_nodes))
            ir_table.children.append(ir_row)

        ir_doc.children.append(ir_table)

    @staticmethod
    def _merge_duplicate_rows(raw_rows: list[list[list[Node]]]) -> list[list[list[Node]]]:
        """Merge consecutive rows that have identical data columns (all cols except first).

        This handles the common Word pattern where a table cell spans two rows visually
        but is represented as two rows with the first column having description/sub-description
        and all other columns having identical data.
        """
        if len(raw_rows) <= 1:
            return raw_rows

        def _cell_text(nodes: list[Node]) -> str:
            """Extract plain text from cell nodes for comparison."""
            parts = []
            for n in nodes:
                if isinstance(n, Text):
                    parts.append(n.content.strip())
                elif hasattr(n, "children"):
                    parts.append(_cell_text(n.children))
            return " ".join(parts).strip()

        merged = []
        i = 0
        while i < len(raw_rows):
            current = raw_rows[i]
            # Look ahead: does next row have same data in cols 1+?
            if i + 1 < len(raw_rows) and len(current) > 1:
                next_row = raw_rows[i + 1]
                if len(next_row) == len(current):
                    # Compare data columns (skip col 0)
                    data_match = all(
                        _cell_text(current[c]) == _cell_text(next_row[c])
                        for c in range(1, len(current))
                    )
                    if data_match:
                        # Merge: combine col 0 with a LineBreak, keep other cols from current
                        combined_col0 = list(current[0])
                        if combined_col0:
                            combined_col0.append(LineBreak())
                        combined_col0.extend(next_row[0])
                        merged_row = [combined_col0] + current[1:]
                        merged.append(merged_row)
                        i += 2
                        continue
            merged.append(current)
            i += 1
        return merged

    def _parse_runs_with_math(self, para, element) -> list[Node]:
        """Parse a paragraph that contains both text runs and inline OMML math."""
        nodes: list[Node] = []

        # Walk the XML children of the paragraph in order
        for child_el in element:
            child_tag = child_el.tag
            local = child_tag.split("}")[-1] if "}" in child_tag else child_tag

            if local == "oMath":
                # Inline math
                try:
                    latex_content = omml_to_latex(child_el)
                    if latex_content:
                        nodes.append(Math(content=latex_content, display=False))
                except Exception:
                    raw = etree.tostring(child_el, encoding="unicode")
                    nodes.append(RawLatex(content=raw))

            elif local == "r":
                # Regular run — find matching python-docx run
                for run in para.runs:
                    if run._element is child_el:
                        text = run.text
                        if not text:
                            # Check for images
                            inline_images = run._element.findall(f".//{qn('wp:inline')}")
                            if inline_images:
                                img_node = self._extract_run_image(run)
                                if img_node:
                                    nodes.append(img_node)
                            break

                        # Reference markers
                        ref_match = REF_PATTERN.match(text)
                        if ref_match:
                            kind_str = ref_match.group(1).upper()
                            key = ref_match.group(2)
                            nodes.append(Reference(kind=RefKind[kind_str], key=key))
                            break

                        # Formatting
                        text_node: Node = Text(content=text)
                        if run.bold:
                            text_node = Formatted(kind=FormatKind.BOLD, children=[text_node])
                        if run.italic:
                            text_node = Formatted(kind=FormatKind.ITALIC, children=[text_node])
                        if run.underline:
                            text_node = Formatted(kind=FormatKind.UNDERLINE, children=[text_node])
                        nodes.append(text_node)
                        break

        return nodes

    def _handle_math_para(self, omml_elements: list, target: Node,
                          display: bool = True) -> None:
        """Convert OMML math elements to Math IR nodes."""
        for omml_el in omml_elements:
            try:
                latex_content = omml_to_latex(omml_el)
                if latex_content:
                    target.children.append(Math(content=latex_content, display=display))
            except Exception:
                # Fallback: serialize as raw
                raw = etree.tostring(omml_el, encoding="unicode")
                target.children.append(RawLatex(content=raw))
