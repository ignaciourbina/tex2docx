"""Custom exception hierarchy for doctex."""


class DoctexError(Exception):
    """Base exception for doctex."""


class ParseError(DoctexError):
    """Failed to parse LaTeX source."""


class UnsupportedConstructError(DoctexError):
    """Encountered unsupported LaTeX construct in strict mode."""


class ImageNotFoundError(DoctexError):
    """Referenced image file not found."""


class DocxReadError(DoctexError):
    """Failed to read or interpret DOCX content."""
