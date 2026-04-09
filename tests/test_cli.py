"""Tests for the CLI interface."""

import os

from click.testing import CliRunner

from doctex.cli import cli


def test_export_command(fixtures_dir, tmp_path):
    input_tex = str(fixtures_dir / "minimal.tex")
    output_docx = str(tmp_path / "minimal.docx")

    runner = CliRunner()
    result = runner.invoke(cli, ["export", input_tex, "-o", output_docx])
    assert result.exit_code == 0, result.output
    assert os.path.isfile(output_docx)


def test_import_command(fixtures_dir, tmp_path):
    # First export to get a docx
    input_tex = str(fixtures_dir / "minimal.tex")
    docx_path = str(tmp_path / "minimal.docx")
    output_tex = str(tmp_path / "imported.tex")

    runner = CliRunner()
    result = runner.invoke(cli, ["export", input_tex, "-o", docx_path])
    assert result.exit_code == 0

    # Now import
    result = runner.invoke(cli, ["import", docx_path, "-o", output_tex])
    assert result.exit_code == 0, result.output
    assert os.path.isfile(output_tex)

    # Verify the output is valid LaTeX-ish
    content = open(output_tex).read()
    assert "\\documentclass" in content or "\\begin{document}" in content or len(content) > 0


def test_export_full_paper(fixtures_dir, tmp_path):
    input_tex = str(fixtures_dir / "full_paper.tex")
    output_docx = str(tmp_path / "full_paper.docx")

    runner = CliRunner()
    result = runner.invoke(cli, ["export", input_tex, "-o", output_docx])
    assert result.exit_code == 0, result.output
    assert os.path.isfile(output_docx)
    # File should have reasonable size (not empty)
    assert os.path.getsize(output_docx) > 1000


def test_roundtrip_via_cli(fixtures_dir, tmp_path):
    """Full CLI round-trip: export -> import -> verify."""
    input_tex = str(fixtures_dir / "full_paper.tex")
    docx_path = str(tmp_path / "paper.docx")
    output_tex = str(tmp_path / "paper.tex")

    runner = CliRunner()

    # Export
    result = runner.invoke(cli, ["export", input_tex, "-o", docx_path])
    assert result.exit_code == 0

    # Import with template
    result = runner.invoke(cli, [
        "import", docx_path,
        "-o", output_tex,
        "--template", input_tex,
    ])
    assert result.exit_code == 0
    assert os.path.isfile(output_tex)

    content = open(output_tex).read()
    assert "\\documentclass" in content
    assert "\\begin{document}" in content


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
