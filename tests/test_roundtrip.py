"""Round-trip tests: tex -> docx -> tex and structural equivalence."""

import os

from tex2docx.tex.reader import TexReader
from tex2docx.tex.writer import TexWriter
from tex2docx.docx.writer import DocxWriter
from tex2docx.docx.reader import DocxReader
from tex2docx.ir import (
    Document, find_all, Paragraph, Section, List, Table,
    Formatted, Reference, Comment, Text, Math,
)


def _roundtrip_tex_docx_tex(source: str, tmp_path) -> Document:
    """tex -> IR -> docx -> IR -> tex -> IR"""
    # Parse original
    ir1 = TexReader(source).parse()

    # Write to docx
    docx_path = str(tmp_path / "roundtrip.docx")
    DocxWriter().write(ir1, docx_path)
    assert os.path.isfile(docx_path)

    # Read back from docx
    ir2 = DocxReader(image_dir=str(tmp_path / "images")).read(docx_path)

    # Write back to tex
    tex_output = TexWriter().write(ir2)

    # Parse the output tex
    ir3 = TexReader(tex_output).parse()

    return ir3


def test_roundtrip_sections(tmp_path):
    source = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
Some text here.

\subsection{Background}
More text.

\section{Conclusion}
Final text.

\end{document}
"""
    ir = _roundtrip_tex_docx_tex(source, tmp_path)
    sections = find_all(ir, Section)
    assert len(sections) >= 3
    titles = [s.title for s in sections]
    assert "Introduction" in titles
    assert "Background" in titles
    assert "Conclusion" in titles


def test_roundtrip_formatting(tmp_path):
    source = r"""
\documentclass{article}
\begin{document}

This has \textbf{bold} and \textit{italic} text.

\end{document}
"""
    ir = _roundtrip_tex_docx_tex(source, tmp_path)
    formatted = find_all(ir, Formatted)
    assert len(formatted) >= 2


def test_roundtrip_lists(tmp_path):
    source = r"""
\documentclass{article}
\begin{document}

\begin{itemize}
  \item First
  \item Second
\end{itemize}

\begin{enumerate}
  \item One
  \item Two
\end{enumerate}

\end{document}
"""
    ir = _roundtrip_tex_docx_tex(source, tmp_path)
    lists = find_all(ir, List)
    assert len(lists) >= 2


def test_roundtrip_table(tmp_path):
    """Test table survives tex -> docx -> IR round-trip."""
    source = r"""
\documentclass{article}
\begin{document}

\begin{tabular}{|c|c|}
\hline
A & B \\
\hline
1 & 2 \\
\hline
\end{tabular}

\end{document}
"""
    # Parse original
    ir1 = TexReader(source).parse()

    # Write to docx
    docx_path = str(tmp_path / "roundtrip.docx")
    DocxWriter().write(ir1, docx_path)

    # Read back from docx — table should survive at IR level
    ir2 = DocxReader(image_dir=str(tmp_path / "images")).read(docx_path)
    tables = find_all(ir2, Table)
    assert len(tables) >= 1
    assert len(tables[0].children) >= 2  # at least 2 rows


def test_roundtrip_references(tmp_path):
    source = r"""
\documentclass{article}
\begin{document}

See \cite{knuth1984} and \ref{fig:1}.

\end{document}
"""
    ir = _roundtrip_tex_docx_tex(source, tmp_path)
    refs = find_all(ir, Reference)
    assert len(refs) >= 2


def test_roundtrip_full_paper(full_paper_tex, tmp_path):
    """Full paper round-trip smoke test."""
    ir = _roundtrip_tex_docx_tex(full_paper_tex, tmp_path)
    # Should preserve the major structural elements
    assert len(find_all(ir, Section)) >= 3
    assert len(find_all(ir, Paragraph)) >= 2
