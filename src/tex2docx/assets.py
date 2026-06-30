"""Portable asset preparation for DOCX export."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from tex2docx.ir import Document, Image, walk


GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\{[^{}]+\})+)\}")
GRAPHICSPATH_ENTRY_RE = re.compile(r"\{([^{}]+)\}")
IMAGE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".svg")


def extract_graphics_paths(source: str, tex_dir: Path) -> list[Path]:
    """Read LaTeX \\graphicspath entries as paths relative to the TeX file."""
    paths: list[Path] = []
    for match in GRAPHICSPATH_RE.finditer(source):
        for entry in GRAPHICSPATH_ENTRY_RE.findall(match.group(1)):
            candidate = Path(entry)
            if not candidate.is_absolute():
                candidate = tex_dir / candidate
            paths.append(candidate.resolve())
    return paths


def prepare_document_images(
    ir_doc: Document,
    *,
    search_dirs: list[Path],
    asset_dir: Path,
    pdf_dpi: int = 220,
) -> None:
    """Resolve images and rewrite them to portable assets for DOCX embedding."""
    asset_dir = asset_dir.resolve()
    asset_dir.mkdir(parents=True, exist_ok=True)
    for node in walk(ir_doc):
        if not isinstance(node, Image):
            continue
        source_path = resolve_image_path(node.path, search_dirs)
        if source_path is None:
            continue
        node.resolved_path = str(prepare_image_asset(source_path, asset_dir, pdf_dpi=pdf_dpi).resolve())


def resolve_image_path(path: str, search_dirs: list[Path]) -> Path | None:
    """Resolve an includegraphics path, including extensionless paths."""
    raw = Path(path)
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        for search_dir in search_dirs:
            candidates.append(search_dir / raw)

    expanded_candidates: list[Path] = []
    for candidate in candidates:
        expanded_candidates.append(candidate)
        if not candidate.suffix:
            expanded_candidates.extend(candidate.with_suffix(ext) for ext in IMAGE_EXTENSIONS)

    for candidate in expanded_candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def prepare_image_asset(source_path: Path, asset_dir: Path, *, pdf_dpi: int = 220) -> Path:
    """Copy or convert one image into the asset directory."""
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return convert_pdf_to_png(source_path, asset_dir, dpi=pdf_dpi)

    target = _unique_asset_path(asset_dir, source_path.stem, suffix)
    if not target.exists() or source_path.stat().st_mtime > target.stat().st_mtime:
        shutil.copy2(source_path, target)
    return target


def convert_pdf_to_png(source_path: Path, asset_dir: Path, *, dpi: int = 220) -> Path:
    """Convert the first page of a PDF figure to PNG for Word compatibility."""
    target = _unique_asset_path(asset_dir, source_path.stem, ".png")
    if target.exists() and target.stat().st_mtime >= source_path.stat().st_mtime:
        return target

    try:
        import fitz
    except ImportError as exc:
        fallback = source_path.with_suffix(".png")
        if fallback.is_file():
            shutil.copy2(fallback, target)
            return target
        raise RuntimeError(
            "PDF figure conversion requires PyMuPDF, or a same-stem PNG fallback."
        ) from exc

    doc = fitz.open(source_path)
    try:
        page = doc.load_page(0)
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pixmap.save(target)
    finally:
        doc.close()
    return target


def _unique_asset_path(asset_dir: Path, stem: str, suffix: str) -> Path:
    return asset_dir / f"{_safe_name(stem)}{suffix.lower()}"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "image"
