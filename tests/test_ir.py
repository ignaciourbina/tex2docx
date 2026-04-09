"""Tests for the IR node definitions and tree utilities."""

from doctex.ir import (
    Document, Preamble, Metadata, Section, SectionLevel,
    Paragraph, Text, Formatted, FormatKind,
    List, ListItem, ListKind, Table, TableRow, TableCell,
    Image, Reference, RefKind, Comment, Math, RawLatex,
    walk, find_all, pretty_print,
)


def test_walk_simple():
    doc = Document(children=[
        Paragraph(children=[Text(content="hello")]),
        Paragraph(children=[Text(content="world")]),
    ])
    nodes = list(walk(doc))
    assert len(nodes) == 5  # doc + 2 para + 2 text


def test_walk_nested():
    doc = Document(children=[
        Section(level=SectionLevel.SECTION, title="S1", children=[
            Paragraph(children=[
                Formatted(kind=FormatKind.BOLD, children=[Text(content="bold")])
            ]),
        ]),
    ])
    nodes = list(walk(doc))
    assert len(nodes) == 5  # doc, section, paragraph, formatted, text


def test_find_all():
    doc = Document(children=[
        Paragraph(children=[Text(content="a")]),
        Section(level=SectionLevel.SECTION, title="S", children=[
            Paragraph(children=[Text(content="b")]),
        ]),
    ])
    texts = find_all(doc, Text)
    assert len(texts) == 2
    assert texts[0].content == "a"
    assert texts[1].content == "b"


def test_find_all_specific_type():
    doc = Document(children=[
        Paragraph(children=[
            Text(content="hello"),
            Formatted(kind=FormatKind.BOLD, children=[Text(content="bold")]),
            Reference(kind=RefKind.CITE, key="abc"),
        ]),
    ])
    refs = find_all(doc, Reference)
    assert len(refs) == 1
    assert refs[0].key == "abc"


def test_pretty_print():
    doc = Document(children=[
        Section(level=SectionLevel.SECTION, title="Intro", children=[
            Paragraph(children=[Text(content="Hello")]),
        ]),
    ])
    output = pretty_print(doc)
    assert "Document" in output
    assert "Section" in output
    assert "Intro" in output
    assert "Text" in output
    assert "Hello" in output


def test_node_defaults():
    p = Paragraph()
    assert p.children == []

    t = Text()
    assert t.content == ""

    s = Section()
    assert s.level == SectionLevel.SECTION
    assert s.title == ""

    m = Math()
    assert m.content == ""
    assert m.display is False

    img = Image()
    assert img.path == ""
    assert img.width is None
