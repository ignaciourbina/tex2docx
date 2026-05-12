"""CLI interface for tex2docx."""

import click

from tex2docx.pipeline import export_pipeline, import_pipeline


@click.group()
@click.version_option(package_name="tex2docx")
def cli():
    """Convert between LaTeX and Word documents."""


@cli.command("export")
@click.argument("input_tex", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", type=click.Path(), default=None,
              help="Output .docx path. Default: same name with .docx extension.")
@click.option("--image-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="Directory to resolve \\includegraphics paths. Default: directory of input .tex.")
@click.option("--strict/--no-strict", default=False,
              help="Fail on unsupported constructs instead of preserving them.")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def export_cmd(input_tex, output, image_dir, strict, verbose):
    """Convert a .tex file to .docx."""
    export_pipeline(input_tex, output=output, image_dir=image_dir,
                    strict=strict, verbose=verbose)


@cli.command("import")
@click.argument("input_docx", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", type=click.Path(), default=None,
              help="Output .tex path. Default: same name with .tex extension.")
@click.option("--image-dir", type=click.Path(), default=None,
              help="Directory to save extracted images. Default: ./images/ relative to output.")
@click.option("--template", type=click.Path(exists=True, dir_okay=False), default=None,
              help="A .tex file whose preamble to reuse for round-trip fidelity.")
@click.option("--strict/--no-strict", default=False,
              help="Fail on unrecognizable DOCX content.")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def import_cmd(input_docx, output, image_dir, template, strict, verbose):
    """Convert a .docx file to .tex."""
    import_pipeline(input_docx, output=output, image_dir=image_dir,
                    template=template, strict=strict, verbose=verbose)
