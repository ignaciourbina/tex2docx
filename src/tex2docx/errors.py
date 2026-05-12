"""Custom exception hierarchy for tex2docx."""


class DoctexError(Exception):
    """Base exception for tex2docx."""


class ParseError(DoctexError):
    """Failed to parse LaTeX source."""


class UnsupportedConstructError(DoctexError):
    """Encountered unsupported LaTeX construct in strict mode."""


class ImageNotFoundError(DoctexError):
    """Referenced image file not found."""


class DocxReadError(DoctexError):
    """Failed to read or interpret DOCX content."""
