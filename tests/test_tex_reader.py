"""Tests for LaTeX parser (tex -> IR)."""

from tex2docx.tex.reader import TexReader
from tex2docx.ir import (
    Abstract, Comment, Document, Formatted, FormatKind,
    Image, List, ListItem, ListKind, Math, Metadata,
    Paragraph, Preamble, RawLatex, Reference, RefKind,
    Section, SectionLevel, Table, TableRow, TableCell, Text,
    find_all,
)


def test_minimal(minimal_tex):
    doc = TexReader(minimal_tex).parse()
    assert isinstance(doc, Document)
    # Should have a preamble
    preambles = find_all(doc, Preamble)
    assert len(preambles) == 1
    assert preambles[0].document_class == "article"


def test_paragraphs():
    source = r"""
\documentclass{article}
\begin{document}

First paragraph here.

Second paragraph here.

\end{document}
"""
    doc = TexReader(source).parse()
    paragraphs = find_all(doc, Paragraph)
    assert len(paragraphs) >= 2


def test_sections():
    source = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
Some text.

\subsection{Background}
More text.

\subsubsection{Details}
Even more.

\end{document}
"""
    doc = TexReader(source).parse()
    sections = find_all(doc, Section)
    assert len(sections) == 3
    assert sections[0].title == "Introduction"
    assert sections[0].level == SectionLevel.SECTION
    assert sections[1].title == "Background"
    assert sections[1].level == SectionLevel.SUBSECTION
    assert sections[2].title == "Details"
    assert sections[2].level == SectionLevel.SUBSUBSECTION


def test_formatting():
    source = r"""
\documentclass{article}
\begin{document}

This is \textbf{bold} and \textit{italic} and \underline{underlined}.

\end{document}
"""
    doc = TexReader(source).parse()
    formatted = find_all(doc, Formatted)
    assert len(formatted) == 3
    kinds = {f.kind for f in formatted}
    assert FormatKind.BOLD in kinds
    assert FormatKind.ITALIC in kinds
    assert FormatKind.UNDERLINE in kinds


def test_itemize():
    source = r"""
\documentclass{article}
\begin{document}

\begin{itemize}
  \item First item
  \item Second item
  \item Third item
\end{itemize}

\end{document}
"""
    doc = TexReader(source).parse()
    lists = find_all(doc, List)
    assert len(lists) == 1
    assert lists[0].kind == ListKind.BULLETED
    assert len(lists[0].children) == 3  # 3 items


def test_enumerate():
    source = r"""
\documentclass{article}
\begin{document}

\begin{enumerate}
  \item First
  \item Second
\end{enumerate}

\end{document}
"""
    doc = TexReader(source).parse()
    lists = find_all(doc, List)
    assert len(lists) == 1
    assert lists[0].kind == ListKind.NUMBERED
    assert len(lists[0].children) == 2


def test_tabular():
    source = r"""
\documentclass{article}
\begin{document}

\begin{tabular}{|c|c|c|}
\hline
A & B & C \\
\hline
1 & 2 & 3 \\
\hline
\end{tabular}

\end{document}
"""
    doc = TexReader(source).parse()
    tables = find_all(doc, Table)
    assert len(tables) == 1
    assert len(tables[0].children) == 2  # 2 rows (header + data)
    assert len(tables[0].children[0].children) == 3  # 3 columns


def test_references():
    source = r"""
\documentclass{article}
\begin{document}

See \ref{fig:1} and \cite{paper2024}.
\label{sec:intro}

\end{document}
"""
    doc = TexReader(source).parse()
    refs = find_all(doc, Reference)
    assert len(refs) == 3
    kinds = {(r.kind, r.key) for r in refs}
    assert (RefKind.REF, "fig:1") in kinds
    assert (RefKind.CITE, "paper2024") in kinds
    assert (RefKind.LABEL, "sec:intro") in kinds


def test_comments():
    source = r"""
\documentclass{article}
\begin{document}

% This is a comment
Some text.

\end{document}
"""
    doc = TexReader(source).parse()
    comments = find_all(doc, Comment)
    assert len(comments) >= 1
    assert "This is a comment" in comments[0].content


def test_metadata():
    source = r"""
\documentclass{article}
\title{My Paper}
\author{John Smith}
\date{2026}

\begin{document}
\maketitle
\end{document}
"""
    doc = TexReader(source).parse()
    metadata = find_all(doc, Metadata)
    assert len(metadata) == 1
    assert metadata[0].title == "My Paper"
    assert metadata[0].author == "John Smith"
    assert metadata[0].date == "2026"


def test_abstract():
    source = r"""
\documentclass{article}
\begin{document}

\begin{abstract}
This is the abstract text.
\end{abstract}

\end{document}
"""
    doc = TexReader(source).parse()
    abstracts = find_all(doc, Abstract)
    assert len(abstracts) == 1


def test_inline_math():
    source = r"""
\documentclass{article}
\begin{document}

The equation $E = mc^2$ is famous.

\end{document}
"""
    doc = TexReader(source).parse()
    maths = find_all(doc, Math)
    assert len(maths) >= 1
    assert maths[0].display is False


def test_display_math():
    source = r"""
\documentclass{article}
\begin{document}

\[
  x = \frac{-b}{2a}
\]

\end{document}
"""
    doc = TexReader(source).parse()
    maths = find_all(doc, Math)
    assert len(maths) >= 1
    assert maths[0].display is True


def test_includegraphics():
    source = r"""
\documentclass{article}
\usepackage{graphicx}
\begin{document}

\includegraphics[width=0.8\textwidth]{figures/plot.png}

\end{document}
"""
    doc = TexReader(source).parse()
    images = find_all(doc, Image)
    assert len(images) == 1
    assert images[0].path == "figures/plot.png"
    assert images[0].width == "0.8\\textwidth"


def test_preamble_packages():
    source = r"""
\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{graphicx}
\usepackage{amsmath}

\begin{document}
Hello.
\end{document}
"""
    doc = TexReader(source).parse()
    preamble = find_all(doc, Preamble)[0]
    assert preamble.document_class == "article"
    assert "12pt" in preamble.class_options
    assert "a4paper" in preamble.class_options
    pkg_names = [p[0] for p in preamble.packages]
    assert "inputenc" in pkg_names
    assert "graphicx" in pkg_names
    assert "amsmath" in pkg_names


def test_full_paper(full_paper_tex):
    """Smoke test: parse the full paper fixture without errors."""
    doc = TexReader(full_paper_tex).parse()
    assert isinstance(doc, Document)
    # Should have sections, paragraphs, lists, table, math, references
    assert len(find_all(doc, Section)) >= 4
    assert len(find_all(doc, Paragraph)) >= 3
    assert len(find_all(doc, List)) >= 2
    assert len(find_all(doc, Table)) >= 1
    assert len(find_all(doc, Math)) >= 1
    assert len(find_all(doc, Reference)) >= 2


def test_unknown_macro_preserved():
    source = r"""
\documentclass{article}
\begin{document}
\customcommand{arg}
\end{document}
"""
    doc = TexReader(source).parse()
    raw = find_all(doc, RawLatex)
    assert len(raw) >= 1
