"""Word style constants and helpers for doctex."""

from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.style import WD_STYLE_TYPE


LATEX_COMMENT_STYLE = "LaTeX Comment"
LATEX_RAW_STYLE = "LaTeX Raw"


def ensure_styles(doc: DocxDocument) -> None:
    """Add custom doctex styles to the document if they don't exist."""
    styles = doc.styles

    if LATEX_COMMENT_STYLE not in [s.name for s in styles]:
        style = styles.add_style(LATEX_COMMENT_STYLE, WD_STYLE_TYPE.PARAGRAPH)
        style.font.hidden = True
        style.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        style.font.size = Pt(8)
        style.font.name = "Courier New"

    if LATEX_RAW_STYLE not in [s.name for s in styles]:
        style = styles.add_style(LATEX_RAW_STYLE, WD_STYLE_TYPE.PARAGRAPH)
        style.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
        style.font.size = Pt(8)
        style.font.name = "Courier New"
