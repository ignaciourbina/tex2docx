"""Tests for LaTeX input flattening."""

from tex2docx.tex.flatten import flatten_tex_file


def test_flatten_regular_input(tmp_path):
    main = tmp_path / "main.tex"
    section = tmp_path / "sections" / "intro.tex"
    section.parent.mkdir()
    section.write_text("Intro body.\n", encoding="utf-8")
    main.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\input{sections/intro}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    flattened = flatten_tex_file(main)

    assert "Intro body." in flattened
    assert "\\input{sections/intro}" not in flattened


def test_flatten_nested_input(tmp_path):
    main = tmp_path / "main.tex"
    chapter = tmp_path / "chapter.tex"
    section = tmp_path / "section.tex"
    section.write_text("Nested body.\n", encoding="utf-8")
    chapter.write_text("Chapter start.\n\\input{section}\n", encoding="utf-8")
    main.write_text("\\begin{document}\n\\input{chapter}\n\\end{document}\n", encoding="utf-8")

    flattened = flatten_tex_file(main)

    assert "Chapter start." in flattened
    assert "Nested body." in flattened
    assert "\\input{chapter}" not in flattened
    assert "\\input{section}" not in flattened


def test_flatten_macro_path_input(tmp_path):
    main = tmp_path / "main.tex"
    tables = tmp_path / "output" / "tex_tables"
    tables.mkdir(parents=True)
    table = tables / "summary.tex"
    table.write_text("\\begin{tabular}{c}A\\\\\\end{tabular}\n", encoding="utf-8")
    main.write_text(
        "\\newcommand{\\textables}{output/tex_tables}\n"
        "\\begin{document}\n"
        "\\input{\\textables/summary.tex}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    flattened = flatten_tex_file(main)

    assert "\\begin{tabular}{c}A\\\\\\end{tabular}" in flattened
    assert "\\input{\\textables/summary.tex}" not in flattened


def test_flatten_ignores_commented_input(tmp_path):
    main = tmp_path / "main.tex"
    section = tmp_path / "section.tex"
    section.write_text("Should not appear.\n", encoding="utf-8")
    main.write_text(
        "\\begin{document}\n"
        "% \\input{section}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    flattened = flatten_tex_file(main)

    assert "% \\input{section}" in flattened
    assert "Should not appear." not in flattened


def test_flatten_preserves_missing_input(tmp_path):
    main = tmp_path / "main.tex"
    main.write_text("\\begin{document}\n\\input{missing}\n\\end{document}\n", encoding="utf-8")

    flattened = flatten_tex_file(main)

    assert "\\input{missing}" in flattened
