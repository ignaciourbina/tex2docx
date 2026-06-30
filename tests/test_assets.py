"""Tests for portable image asset handling."""

from tex2docx.assets import extract_graphics_paths, prepare_document_images, resolve_image_path
from tex2docx.ir import Document, Image, Paragraph


def test_extract_graphics_paths(tmp_path):
    source = r"\graphicspath{{figures/}{../shared/figs/}}"

    paths = extract_graphics_paths(source, tmp_path)

    assert paths == [
        (tmp_path / "figures").resolve(),
        (tmp_path / "../shared/figs").resolve(),
    ]


def test_resolve_extensionless_image(tmp_path):
    fig_dir = tmp_path / "figures"
    fig_dir.mkdir()
    image = fig_dir / "plot.png"
    image.write_bytes(b"png")

    resolved = resolve_image_path("plot", [fig_dir])

    assert resolved == image.resolve()


def test_prepare_document_images_copies_raster(tmp_path):
    fig_dir = tmp_path / "figures"
    fig_dir.mkdir()
    image = fig_dir / "plot.png"
    image.write_bytes(b"png")
    ir_doc = Document(children=[
        Paragraph(children=[Image(path="plot.png")]),
    ])

    prepare_document_images(ir_doc, search_dirs=[fig_dir], asset_dir=tmp_path / "assets")

    resolved = ir_doc.children[0].children[0].resolved_path
    assert resolved is not None
    assert resolved.endswith("assets/plot.png")
