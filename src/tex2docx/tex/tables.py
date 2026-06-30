"""LaTeX table construction helpers."""

from __future__ import annotations

from collections.abc import Callable

from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
)

from tex2docx.ir import Node, Paragraph, Table, TableCell, TableRow, Text


TABLE_CONTROL_MACROS = {
    "hline",
    "toprule",
    "midrule",
    "bottomrule",
    "addlinespace",
    "endfirsthead",
    "endhead",
    "endfoot",
    "endlastfoot",
    "label",
}


def parse_table_environment(
    env_node: LatexEnvironmentNode,
    parse_inline_nodes: Callable[[list], list[Node]],
) -> list[Node]:
    """Convert a tabular-like LaTeX environment to caption/table IR nodes."""
    col_spec = _extract_col_spec(env_node)
    body_nodes = env_node.nodelist or []
    caption_nodes: list[Node] = []

    if env_node.environmentname == "longtable":
        caption_nodes, table_nodes = _prepare_longtable_nodes(body_nodes, parse_inline_nodes)
    else:
        table_nodes = body_nodes

    table = _parse_rows(table_nodes, col_spec, parse_inline_nodes)
    result: list[Node] = []
    if caption_nodes:
        result.append(Paragraph(children=caption_nodes))
    if table.children:
        result.append(table)
    return result


def _prepare_longtable_nodes(
    body_nodes: list,
    parse_inline_nodes: Callable[[list], list[Node]],
) -> tuple[list[Node], list]:
    caption_nodes: list[Node] = []
    firsthead_nodes: list = []
    body_content_nodes: list = []
    lastfoot_nodes: list = []
    region = "firsthead"
    saw_region_marker = False

    for node in body_nodes:
        if isinstance(node, LatexMacroNode):
            name = node.macroname
            if name == "caption":
                caption_arg_nodes = _last_arg_nodelist(node)
                if caption_arg_nodes:
                    caption_nodes = parse_inline_nodes(caption_arg_nodes)
                continue
            if name == "label":
                continue
            if name == "endfirsthead":
                region = "head"
                saw_region_marker = True
                continue
            if name == "endhead":
                region = "foot"
                saw_region_marker = True
                continue
            if name == "endfoot":
                region = "lastfoot"
                saw_region_marker = True
                continue
            if name == "endlastfoot":
                region = "body"
                saw_region_marker = True
                continue

        if region == "firsthead":
            firsthead_nodes.append(node)
        elif region == "lastfoot":
            lastfoot_nodes.append(node)
        elif region == "body":
            body_content_nodes.append(node)

    if not saw_region_marker:
        return caption_nodes, firsthead_nodes
    return caption_nodes, firsthead_nodes + body_content_nodes + lastfoot_nodes


def _extract_col_spec(env_node: LatexEnvironmentNode) -> str | None:
    if env_node.nodeargd and env_node.nodeargd.argnlist:
        for arg in env_node.nodeargd.argnlist:
            if arg is None:
                continue
            raw = _get_node_verbatim(arg)
            if raw.startswith("{") and raw.endswith("}"):
                return raw[1:-1]
            return raw
    return None


def _parse_rows(
    body_nodes: list,
    col_spec: str | None,
    parse_inline_nodes: Callable[[list], list[Node]],
) -> Table:
    table = Table(col_spec=col_spec)
    current_row_nodes: list = []
    rows_of_nodes: list[list] = []

    for node in body_nodes:
        if node is None:
            continue
        if _is_row_break(node):
            rows_of_nodes.append(current_row_nodes)
            current_row_nodes = []
        else:
            current_row_nodes.append(node)

    if current_row_nodes:
        rows_of_nodes.append(current_row_nodes)

    for row_nodes in rows_of_nodes:
        row = _parse_row(row_nodes, parse_inline_nodes)
        if _row_has_content(row):
            table.children.append(row)

    return table


def _parse_row(
    row_nodes: list,
    parse_inline_nodes: Callable[[list], list[Node]],
) -> TableRow:
    cells_nodes: list[list] = [[]]

    for node in row_nodes:
        if _is_table_control(node):
            continue
        if isinstance(node, LatexCharsNode) and "&" in node.chars:
            parts = node.chars.split("&")
            if parts[0]:
                cells_nodes[-1].append(_chars_like(node, parts[0]))
            for part in parts[1:]:
                cells_nodes.append([])
                if part:
                    cells_nodes[-1].append(_chars_like(node, part))
        elif isinstance(node, LatexMacroNode) and node.macroname == "&":
            cells_nodes.append([])
        else:
            cells_nodes[-1].append(node)

    row = TableRow()
    for cell_nodes in cells_nodes:
        children = parse_inline_nodes(cell_nodes)
        row.children.append(TableCell(children=children))
    return row


def _row_has_content(row: TableRow) -> bool:
    for cell in row.children:
        for child in cell.children:
            if isinstance(child, Text) and not child.content.strip():
                continue
            return True
    return False


def _is_row_break(node) -> bool:
    return isinstance(node, LatexMacroNode) and node.macroname == "\\"


def _is_table_control(node) -> bool:
    return isinstance(node, LatexMacroNode) and node.macroname in TABLE_CONTROL_MACROS


def _chars_like(node: LatexCharsNode, chars: str) -> LatexCharsNode:
    return type(node)(chars=chars, pos=node.pos, pos_end=node.pos_end)


def _last_arg_nodelist(node: LatexMacroNode) -> list | None:
    if node.nodeargd is None or node.nodeargd.argnlist is None:
        return None
    for arg in reversed(node.nodeargd.argnlist):
        if arg is None:
            continue
        if hasattr(arg, "nodelist"):
            return arg.nodelist or []
        return [arg]
    return None


def _get_node_verbatim(node) -> str:
    if hasattr(node, "latex_verbatim"):
        return node.latex_verbatim()
    return ""
