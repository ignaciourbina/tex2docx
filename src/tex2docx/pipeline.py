"""Pipeline orchestration: wires readers to writers."""

from pathlib import Path

import click

from tex2docx.ir import Document, Image, walk
from tex2docx.tex.reader import TexReader
from tex2docx.tex.writer import TexWriter
from tex2docx.docx.writer import DocxWriter
from tex2docx.docx.reader import DocxReader


def export_pipeline(
    input_tex: str,
    *,
    output: str | None = None,
    image_dir: str | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> None:
    """tex -> IR -> docx"""
    tex_path = Path(input_tex).resolve()
    output_path = Path(output) if output else tex_path.with_suffix(".docx")
    img_dir = Path(image_dir) if image_dir else tex_path.parent

    source = tex_path.read_text(encoding="utf-8")
    ir_doc = TexReader(source, strict=strict).parse()

    _resolve_images(ir_doc, img_dir)

    DocxWriter(image_dir=str(img_dir)).write(ir_doc, str(output_path))
    click.echo(f"Wrote {output_path}")


def import_pipeline(
    input_docx: str,
    *,
    output: str | None = None,
    image_dir: str | None = None,
    template: str | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> None:
    """docx -> IR -> tex"""
    docx_path = Path(input_docx).resolve()
    output_path = Path(output) if output else docx_path.with_suffix(".tex")
    img_dir = Path(image_dir) if image_dir else output_path.parent / "images"

    ir_doc = DocxReader(image_dir=str(img_dir), output_dir=str(output_path.parent)).read(str(docx_path))

    if template:
        _apply_template_preamble(ir_doc, template)

    tex_source = TexWriter().write(ir_doc)
    output_path.write_text(tex_source, encoding="utf-8")
    click.echo(f"Wrote {output_path}")


def _resolve_images(ir_doc: Document, base_dir: Path) -> None:
    """Resolve each Image node's path relative to base_dir."""
    for node in walk(ir_doc):
        if isinstance(node, Image):
            candidate = base_dir / node.path
            if candidate.is_file():
                node.resolved_path = str(candidate)


def _apply_template_preamble(ir_doc: Document, template_path: str) -> None:
    """Replace ir_doc's preamble with the template's preamble."""
    from tex2docx.ir import Preamble

    template_source = Path(template_path).read_text(encoding="utf-8")
    template_doc = TexReader(template_source, strict=False).parse()

    template_preamble = None
    for child in template_doc.children:
        if isinstance(child, Preamble):
            template_preamble = child
            break

    if template_preamble is None:
        return

    # Replace or prepend
    for i, child in enumerate(ir_doc.children):
        if isinstance(child, Preamble):
            ir_doc.children[i] = template_preamble
            return
    ir_doc.children.insert(0, template_preamble)
