"""LaTeX math <-> OMML (Office Math Markup Language) conversion.

Uses python-docx's qn() for namespace resolution so OMML elements are
compatible with the document's namespace declarations.
"""

from __future__ import annotations

from lxml import etree
from docx.oxml.ns import qn
import latex2mathml.converter

OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

# Functions that use lower-limit notation (lim_{x \to 0})
_LIMIT_FUNCTIONS = {"lim", "liminf", "limsup", "inf", "sup", "min", "max", "det", "gcd"}

# Common math function names (rendered upright, not italic)
_MATH_FUNCTIONS = _LIMIT_FUNCTIONS | {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
    "log", "ln", "exp", "dim", "ker", "hom", "deg", "arg",
}

# Operator character mappings: MathML/Unicode chars that need remapping for OMML/Word
_OPERATOR_MAP = {
    "|": "\u2223",      # DIVIDES — renders as proper vertical bar, not logical OR
    "||": "\u2225",     # PARALLEL — double vertical bar
}

# MathML accent characters -> OMML combining accent characters
_ACCENT_MAP = {
    "^":        "\u0302",  # COMBINING CIRCUMFLEX (hat)
    "\u005E":   "\u0302",  # same, explicit codepoint
    "\u00AF":   "\u0304",  # MACRON -> COMBINING MACRON (bar)
    "\u00AF":   "\u0304",
    "\u00B4":   "\u0301",  # ACUTE
    "\u02C7":   "\u030C",  # CARON (check)
    "~":        "\u0303",  # COMBINING TILDE
    "\u007E":   "\u0303",
    "\u02D9":   "\u0307",  # DOT ABOVE -> COMBINING DOT ABOVE
    "\u0307":   "\u0307",  # already combining
    "\u02DA":   "\u030A",  # RING ABOVE
    "\u2192":   "\u20D7",  # RIGHT ARROW -> COMBINING RIGHT ARROW ABOVE (vec)
    "\u2190":   "\u20D6",  # LEFT ARROW -> COMBINING LEFT ARROW ABOVE
    "\u2015":   "\u0305",  # HORIZONTAL BAR -> COMBINING OVERLINE
    "\u2014":   "\u0305",  # EM DASH -> COMBINING OVERLINE
    "\u2013":   "\u0305",  # EN DASH -> COMBINING OVERLINE
    "\u00AF":   "\u0305",  # MACRON -> COMBINING OVERLINE (overline variant)
    "\u0305":   "\u0305",  # already combining overline
    "\u00A8":   "\u0308",  # DIAERESIS -> COMBINING DIAERESIS (ddot)
}

# Stretchy accent chars that should map to overline-style bar
_BAR_CHARS = {"\u00AF", "\u0304", "\u0305", "\u2015", "\u2014", "\u2013"}

# Unicode math symbols -> LaTeX commands (for OMML -> LaTeX reverse conversion)
_UNICODE_TO_LATEX = {
    "\u2202": r"\partial",   # ∂
    "\u2192": r"\to",        # →
    "\u221E": r"\infty",     # ∞
    "\u2264": r"\leq",       # ≤
    "\u2265": r"\geq",       # ≥
    "\u2260": r"\neq",       # ≠
    "\u2208": r"\in",        # ∈
    "\u2282": r"\subset",    # ⊂
    "\u03B1": r"\alpha",     # α
    "\u03B2": r"\beta",      # β
    "\u03B3": r"\gamma",     # γ
    "\u03C0": r"\pi",        # π
    "\u03C3": r"\sigma",     # σ
    "\u03BC": r"\mu",        # μ
    "\u2223": "|",           # ∣ (DIVIDES)
    "\u00D7": r"\times",     # ×
    "\u00B1": r"\pm",        # ±
    "\u2212": "-",           # − (MINUS SIGN)
    "\u22C5": r"\cdot",      # ⋅
    "\u2211": r"\sum",       # ∑
    "\u220F": r"\prod",      # ∏
    "\u222B": r"\int",       # ∫
    "\u221A": r"\sqrt",      # √
}

# OMML combining accent characters -> LaTeX accent commands
_ACCENT_CHAR_TO_LATEX = {
    "\u0302": r"\hat",       # COMBINING CIRCUMFLEX
    "\u0303": r"\tilde",     # COMBINING TILDE
    "\u0307": r"\dot",       # COMBINING DOT ABOVE
    "\u0308": r"\ddot",      # COMBINING DIAERESIS
    "\u20D7": r"\vec",       # COMBINING RIGHT ARROW ABOVE
    "\u0301": r"\acute",     # COMBINING ACUTE
    "\u0300": r"\grave",     # COMBINING GRAVE
    "\u030C": r"\check",     # COMBINING CARON
    "\u0306": r"\breve",     # COMBINING BREVE
    "\u030A": r"\mathring",  # COMBINING RING ABOVE
}


def latex_to_omml(latex_math: str, display: bool = False) -> etree._Element:
    """Convert a LaTeX math string to an OMML element for embedding in DOCX.

    Args:
        latex_math: LaTeX math content (without delimiters like $ or \\[)
        display: If True, wrap in m:oMathPara for display/block math.

    Returns:
        An lxml Element: m:oMathPara (display) or m:oMath (inline).
    """
    # Step 1: LaTeX -> MathML
    mathml_str = latex2mathml.converter.convert(latex_math)

    # Step 2: MathML -> OMML
    mathml_tree = etree.fromstring(mathml_str.encode("utf-8"))
    omath = _mathml_to_omml(mathml_tree)

    if display:
        omath_para = _make_el("m:oMathPara")
        omath_para.append(omath)
        return omath_para

    return omath


def omml_to_latex(omml_element: etree._Element) -> str:
    """Best-effort conversion of OMML back to LaTeX math string."""
    return _omml_node_to_latex(omml_element).strip()


# --- Helpers ---

def _make_el(tag: str) -> etree._Element:
    """Create an element using python-docx qualified name."""
    return etree.SubElement(etree.Element("_dummy"), qn(tag))


def _sub(parent: etree._Element, tag: str) -> etree._Element:
    """Add a sub-element using python-docx qn()."""
    return etree.SubElement(parent, qn(tag))


def _make_run(parent: etree._Element, text: str) -> etree._Element:
    """Create an m:r with m:t containing text."""
    r = _sub(parent, "m:r")
    t = _sub(r, "m:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    return r


def _make_styled_run(parent: etree._Element, text: str, style: str = "i") -> etree._Element:
    """Create an m:r with m:rPr (style) and m:t. rPr comes before t."""
    r = _sub(parent, "m:r")
    rpr = _sub(r, "m:rPr")
    sty = _sub(rpr, "m:sty")
    sty.set(qn("m:val"), style)
    t = _sub(r, "m:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    return r


# --- MathML -> OMML ---

def _mathml_to_omml(mathml: etree._Element) -> etree._Element:
    """Convert a MathML tree to an m:oMath element."""
    omath = etree.Element(qn("m:oMath"))
    _convert_children(mathml, omath)
    return omath


def _local_tag(el: etree._Element) -> str:
    """Get the local tag name, stripping namespace."""
    tag = el.tag
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


_OPEN_DELIMS = {"(", "[", "{", "|", "‖", "\u230A", "\u2308"}  # ( [ { | ‖ ⌊ ⌈
_CLOSE_DELIMS = {")", "]", "}", "|", "‖", "\u230B", "\u2309"}  # ) ] } | ‖ ⌋ ⌉
_DELIM_PAIRS = {"(": ")", "[": "]", "{": "}", "|": "|", "‖": "‖",
                "\u230A": "\u230B", "\u2308": "\u2309"}


def _is_open_delim(text: str) -> bool:
    return text.strip() in _OPEN_DELIMS


def _try_emit_delimited_matrix(siblings: list, i: int,
                               omml_parent: etree._Element) -> int:
    """Try to match: <mo>open</mo> <mtable>...</mtable> <mo>close</mo>.

    Also handles fence-only patterns like cases: <mo>{</mo> <mtable>...</mtable>
    Returns number of elements consumed (0 if no match).
    """
    open_el = siblings[i]
    open_char = (open_el.text or "").strip()

    # Look for mtable as next or next-after-whitespace sibling
    mtable_idx = None
    for j in range(i + 1, min(i + 3, len(siblings))):
        if _local_tag(siblings[j]) == "mtable":
            mtable_idx = j
            break
        # Skip whitespace-only text nodes
        if _local_tag(siblings[j]) in ("mtext", "mspace"):
            continue
        break

    if mtable_idx is None:
        return 0

    mtable_el = siblings[mtable_idx]

    # Look for closing delimiter after mtable
    close_char = ""
    close_idx = None
    for j in range(mtable_idx + 1, min(mtable_idx + 3, len(siblings))):
        if _local_tag(siblings[j]) == "mo":
            text = (siblings[j].text or "").strip()
            if text in _CLOSE_DELIMS:
                close_char = text
                close_idx = j
                break

    # Emit m:d (delimiter) wrapping m:m (matrix)
    d = _sub(omml_parent, "m:d")
    dpr = _sub(d, "m:dPr")
    beg = _sub(dpr, "m:begChr")
    beg.set(qn("m:val"), open_char)
    end_el = _sub(dpr, "m:endChr")
    end_el.set(qn("m:val"), close_char)
    _sub(dpr, "m:ctrlPr")

    e = _sub(d, "m:e")
    _emit_matrix(mtable_el, e)

    if close_idx is not None:
        return close_idx - i + 1  # consumed open + mtable + close
    else:
        return mtable_idx - i + 1  # consumed open + mtable (no close, like cases)


def _emit_matrix(mtable: etree._Element, omml_parent: etree._Element) -> None:
    """Convert MathML <mtable> to OMML m:m (matrix)."""
    rows = [c for c in mtable if _local_tag(c) == "mtr"]
    if not rows:
        return

    ncols = max(
        sum(1 for cell in row if _local_tag(cell) == "mtd")
        for row in rows
    )

    m = _sub(omml_parent, "m:m")
    mpr = _sub(m, "m:mPr")

    # Baseline justification
    basejc = _sub(mpr, "m:baseJc")
    basejc.set(qn("m:val"), "center")

    # Row spacing
    rsp = _sub(mpr, "m:rSp")
    rsp.set(qn("m:val"), "1")

    # Column properties — one mc per column for proper rendering
    mcs = _sub(mpr, "m:mcs")
    for _col in range(ncols):
        mc = _sub(mcs, "m:mc")
        mcpr = _sub(mc, "m:mcPr")
        count = _sub(mcpr, "m:count")
        count.set(qn("m:val"), "1")
        mcjc = _sub(mcpr, "m:mcJc")
        mcjc.set(qn("m:val"), "center")

    _sub(mpr, "m:ctrlPr")

    for row in rows:
        mr = _sub(m, "m:mr")
        cells = [c for c in row if _local_tag(c) == "mtd"]
        for cell in cells:
            e = _sub(mr, "m:e")
            _convert_children(cell, e)
        # Pad missing cells if row is short
        for _ in range(ncols - len(cells)):
            _sub(mr, "m:e")


def _emit_fenced(mfenced: etree._Element, omml_parent: etree._Element) -> None:
    """Convert MathML <mfenced> to OMML m:d (delimiter)."""
    open_char = mfenced.get("open", "(")
    close_char = mfenced.get("close", ")")

    d = _sub(omml_parent, "m:d")
    dpr = _sub(d, "m:dPr")
    beg = _sub(dpr, "m:begChr")
    beg.set(qn("m:val"), open_char)
    end_el = _sub(dpr, "m:endChr")
    end_el.set(qn("m:val"), close_char)
    _sub(dpr, "m:ctrlPr")

    e = _sub(d, "m:e")
    _convert_children(mfenced, e)


def _emit_accent(base_el: etree._Element, accent_el: etree._Element,
                  omml_parent: etree._Element) -> None:
    """Convert MathML <mover> accent to OMML m:acc or m:bar."""
    # Get the accent character
    accent_char = ""
    if _local_tag(accent_el) == "mo":
        accent_char = (accent_el.text or "").strip()
    elif accent_el.text:
        accent_char = accent_el.text.strip()

    # Check if this is a bar/overline (stretchy line over content)
    is_bar = accent_char in _BAR_CHARS or (
        accent_el.get("stretchy") == "true" and accent_char in _BAR_CHARS
    )

    if is_bar:
        # Use m:bar for overline/bar
        bar = _sub(omml_parent, "m:bar")
        barpr = _sub(bar, "m:barPr")
        pos = _sub(barpr, "m:pos")
        pos.set(qn("m:val"), "top")
        _sub(barpr, "m:ctrlPr")
        e = _sub(bar, "m:e")
        _convert_single(base_el, e)
    else:
        # Use m:acc for hat, vec, tilde, dot, ddot, etc.
        # Map the accent char to OMML combining character
        omml_char = _ACCENT_MAP.get(accent_char, accent_char)

        acc = _sub(omml_parent, "m:acc")
        accpr = _sub(acc, "m:accPr")
        chr_el = _sub(accpr, "m:chr")
        chr_el.set(qn("m:val"), omml_char)
        _sub(accpr, "m:ctrlPr")
        e = _sub(acc, "m:e")
        _convert_single(base_el, e)


def _is_limit_msub(child: etree._Element) -> str | None:
    """If child is msub/munder with a limit function base, return the function name."""
    tag = _local_tag(child)
    if tag not in ("msub", "munder"):
        return None
    children = list(child)
    if len(children) < 2:
        return None
    base_tag = _local_tag(children[0])
    base_text = (children[0].text or "").strip()
    if base_tag == "mo" and base_text in _LIMIT_FUNCTIONS:
        return base_text
    return None


def _emit_limit_func(child: etree._Element, next_sibling: etree._Element | None,
                     omml_parent: etree._Element) -> None:
    """Emit m:func { fName: limLow{lim, e}, e: next_sibling }."""
    children = list(child)
    base_text = (children[0].text or "").strip()

    func = _sub(omml_parent, "m:func")
    funcpr = _sub(func, "m:funcPr")
    _sub(funcpr, "m:ctrlPr")

    # Function name = limLow containing "lim" with subscript
    fname = _sub(func, "m:fName")
    limlow = _sub(fname, "m:limLow")
    limpr = _sub(limlow, "m:limLowPr")
    _sub(limpr, "m:ctrlPr")
    e_lim = _sub(limlow, "m:e")
    _make_styled_run(e_lim, base_text, "p")
    lim_el = _sub(limlow, "m:lim")
    _convert_single(children[1], lim_el)

    # Function argument = the next sibling element
    func_e = _sub(func, "m:e")
    if next_sibling is not None:
        _convert_single(next_sibling, func_e)


def _convert_children(mathml_parent: etree._Element, omml_parent: etree._Element) -> None:
    """Recursively convert MathML children to OMML."""
    siblings = list(mathml_parent)
    i = 0
    while i < len(siblings):
        child = siblings[i]
        tag = _local_tag(child)

        # Look-ahead: delimiter + matrix + delimiter pattern (e.g., pmatrix, bmatrix)
        if tag == "mo" and _is_open_delim(child.text or ""):
            consumed = _try_emit_delimited_matrix(siblings, i, omml_parent)
            if consumed > 0:
                i += consumed
                continue

        # Look-ahead: if this is a limit function (lim_{...}), consume next sibling
        limit_name = _is_limit_msub(child)
        if limit_name is not None:
            next_sib = siblings[i + 1] if i + 1 < len(siblings) else None
            _emit_limit_func(child, next_sib, omml_parent)
            i += 2 if next_sib is not None else 1  # skip next sibling (consumed)
            continue

        if tag == "math":
            _convert_children(child, omml_parent)

        elif tag == "mrow":
            _convert_children(child, omml_parent)

        elif tag == "mi":
            text = child.text or ""
            if len(text) == 1:
                _make_styled_run(omml_parent, text, "i")
            else:
                _make_run(omml_parent, text)

        elif tag == "mn":
            _make_run(omml_parent, child.text or "")

        elif tag == "mo":
            text = child.text or ""
            text = _OPERATOR_MAP.get(text, text)  # remap problematic chars
            if text in _MATH_FUNCTIONS:
                _make_styled_run(omml_parent, text, "p")
            else:
                _make_run(omml_parent, text)

        elif tag == "mtext":
            _make_run(omml_parent, child.text or "")

        elif tag == "mfrac":
            children = list(child)
            if len(children) >= 2:
                f = _sub(omml_parent, "m:f")
                fpr = _sub(f, "m:fPr")
                _sub(fpr, "m:ctrlPr")
                num = _sub(f, "m:num")
                den = _sub(f, "m:den")
                _convert_single(children[0], num)
                _convert_single(children[1], den)

        elif tag == "msup":
            children = list(child)
            if len(children) >= 2:
                ssup = _sub(omml_parent, "m:sSup")
                spr = _sub(ssup, "m:sSupPr")
                _sub(spr, "m:ctrlPr")
                e = _sub(ssup, "m:e")
                sup = _sub(ssup, "m:sup")
                _convert_single(children[0], e)
                _convert_single(children[1], sup)

        elif tag == "msub":
            children = list(child)
            if len(children) >= 2:
                ssub = _sub(omml_parent, "m:sSub")
                spr = _sub(ssub, "m:sSubPr")
                _sub(spr, "m:ctrlPr")
                e = _sub(ssub, "m:e")
                sub = _sub(ssub, "m:sub")
                _convert_single(children[0], e)
                _convert_single(children[1], sub)

        elif tag == "msubsup":
            children = list(child)
            if len(children) >= 3:
                ssubsup = _sub(omml_parent, "m:sSubSup")
                spr = _sub(ssubsup, "m:sSubSupPr")
                _sub(spr, "m:ctrlPr")
                e = _sub(ssubsup, "m:e")
                sub = _sub(ssubsup, "m:sub")
                sup = _sub(ssubsup, "m:sup")
                _convert_single(children[0], e)
                _convert_single(children[1], sub)
                _convert_single(children[2], sup)

        elif tag == "msqrt":
            rad = _sub(omml_parent, "m:rad")
            radpr = _sub(rad, "m:radPr")
            deg_hide = _sub(radpr, "m:degHide")
            deg_hide.set(qn("m:val"), "1")
            _sub(radpr, "m:ctrlPr")
            deg = _sub(rad, "m:deg")
            e = _sub(rad, "m:e")
            _convert_children(child, e)

        elif tag == "mover":
            children = list(child)
            if len(children) >= 2:
                _emit_accent(children[0], children[1], omml_parent)

        elif tag == "munder":
            # Limit functions are already handled by look-ahead above.
            # This handles non-limit munder (e.g., underbrace).
            children = list(child)
            if len(children) >= 2:
                ssub = _sub(omml_parent, "m:sSub")
                spr = _sub(ssub, "m:sSubPr")
                _sub(spr, "m:ctrlPr")
                e = _sub(ssub, "m:e")
                sub = _sub(ssub, "m:sub")
                _convert_single(children[0], e)
                _convert_single(children[1], sub)

        elif tag == "munderover":
            children = list(child)
            if len(children) >= 3:
                ssubsup = _sub(omml_parent, "m:sSubSup")
                spr = _sub(ssubsup, "m:sSubSupPr")
                _sub(spr, "m:ctrlPr")
                e = _sub(ssubsup, "m:e")
                sub = _sub(ssubsup, "m:sub")
                sup = _sub(ssubsup, "m:sup")
                _convert_single(children[0], e)
                _convert_single(children[1], sub)
                _convert_single(children[2], sup)

        elif tag == "mtable":
            _emit_matrix(child, omml_parent)

        elif tag == "mfenced":
            _emit_fenced(child, omml_parent)

        else:
            _convert_children(child, omml_parent)

        i += 1


def _convert_single(mathml_node: etree._Element, omml_parent: etree._Element) -> None:
    """Convert a single MathML node (leaf or subtree) into omml_parent.

    Unlike _convert_children which iterates over children, this wraps
    a single node by creating a temporary parent and dispatching through
    _convert_children so that mfrac, msup, etc. are handled properly.
    """
    tag = _local_tag(mathml_node)

    if tag in ("mi", "mn", "mo", "mtext") and mathml_node.text:
        if tag == "mi" and len(mathml_node.text) == 1:
            _make_styled_run(omml_parent, mathml_node.text, "i")
        else:
            _make_run(omml_parent, mathml_node.text)
    elif tag in ("mfrac", "msup", "msub", "msubsup", "msqrt", "munder",
                 "mover", "munderover", "mrow", "math", "mtable", "mfenced"):
        # Wrap in a temporary parent so _convert_children processes this node
        # as a sibling (handling its tag), not recursing into its children.
        from copy import deepcopy
        wrapper = etree.Element("_wrapper")
        wrapper.append(deepcopy(mathml_node))
        _convert_children(wrapper, omml_parent)
    elif len(mathml_node) > 0:
        _convert_children(mathml_node, omml_parent)
    elif mathml_node.text:
        _make_run(omml_parent, mathml_node.text)


# --- OMML -> LaTeX (reverse) ---

def _latex_escape_text(text: str) -> str:
    """Convert Unicode math symbols in text back to LaTeX commands."""
    if not text:
        return ""
    result = []
    for ch in text:
        latex_cmd = _UNICODE_TO_LATEX.get(ch)
        if latex_cmd is not None:
            # Add space before command if previous char was alphanumeric
            if result and result[-1] and result[-1][-1].isalnum():
                result.append(" ")
            result.append(latex_cmd)
            # LaTeX commands need trailing space or brace to separate from
            # following text, but since we join with spaces later, just add
            # a trailing space for commands starting with backslash
            if latex_cmd.startswith("\\"):
                result.append(" ")
        else:
            result.append(ch)
    return "".join(result).strip()


def _collect_children(node: etree._Element) -> str:
    """Collect LaTeX from all children of a node.

    In LaTeX math mode, spacing is handled automatically. We only insert
    spaces where LaTeX needs them: before \\commands that follow letters/digits.
    """
    parts = [p for p in (_omml_node_to_latex(c) for c in node) if p]
    if not parts:
        return ""

    result = parts[0]
    for i in range(1, len(parts)):
        prev = result[-1] if result else ""
        curr = parts[i]
        # Need space before \command if preceded by letter/digit
        if curr.startswith("\\") and prev.isalnum():
            result += " " + curr
        # Need space after \command (no braces) before letter or digit
        elif (not result.endswith("}") and not result.endswith(" ")
              and "\\" in result.rsplit(" ", 1)[-1]
              and curr[0:1].isalnum()):
            result += " " + curr
        else:
            result += curr
    return result


def _omml_node_to_latex(node: etree._Element) -> str:
    """Recursively convert an OMML node back to LaTeX."""
    tag = _local_tag(node)

    if tag in ("oMath", "oMathPara"):
        return _collect_children(node).strip()

    elif tag == "r":
        for child in node:
            if _local_tag(child) == "t":
                return _latex_escape_text(child.text or "")
        return ""

    elif tag == "f":
        num_text = ""
        den_text = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "num":
                num_text = _collect_children(child)
            elif ctag == "den":
                den_text = _collect_children(child)
        return f"\\frac{{{num_text}}}{{{den_text}}}"

    elif tag == "sSup":
        base = ""
        sup = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "e":
                base = _collect_children(child)
            elif ctag == "sup":
                sup = _collect_children(child)
        return f"{base}^{{{sup}}}"

    elif tag == "sSub":
        base = ""
        sub = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "e":
                base = _collect_children(child)
            elif ctag == "sub":
                sub = _collect_children(child)
        return f"{base}_{{{sub}}}"

    elif tag == "sSubSup":
        base = ""
        sub = ""
        sup = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "e":
                base = _collect_children(child)
            elif ctag == "sub":
                sub = _collect_children(child)
            elif ctag == "sup":
                sup = _collect_children(child)
        return f"{base}_{{{sub}}}^{{{sup}}}"

    elif tag == "rad":
        e_text = ""
        for child in node:
            if _local_tag(child) == "e":
                e_text = _collect_children(child)
        return f"\\sqrt{{{e_text}}}"

    elif tag == "func":
        # m:func: function name (m:fName) applied to argument (m:e)
        fname_text = ""
        arg_text = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "fName":
                fname_text = _collect_children(child)
            elif ctag == "e":
                arg_text = _collect_children(child)
        if arg_text:
            return f"{fname_text} {arg_text}"
        return fname_text

    elif tag == "limLow":
        # m:limLow: base with lower limit -> base_{limit}
        base_text = ""
        lim_text = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "e":
                base_text = _collect_children(child)
            elif ctag == "lim":
                lim_text = _collect_children(child)
        # Prefix known function names with backslash
        if base_text.strip() in _MATH_FUNCTIONS:
            base_text = f"\\{base_text.strip()}"
        return f"{base_text}_{{{lim_text}}}"

    elif tag == "limUpp":
        # m:limUpp: base with upper limit -> base^{limit}
        base_text = ""
        lim_text = ""
        for child in node:
            ctag = _local_tag(child)
            if ctag == "e":
                base_text = _collect_children(child)
            elif ctag == "lim":
                lim_text = _collect_children(child)
        return f"{base_text}^{{{lim_text}}}"

    elif tag == "bar":
        # m:bar -> \overline{...} or \underline{...}
        e_text = ""
        pos = "top"  # default
        for child in node:
            ctag = _local_tag(child)
            if ctag == "barPr":
                for prop in child:
                    if _local_tag(prop) == "pos":
                        pos = prop.get(qn("m:val"), "top")
            elif ctag == "e":
                e_text = _collect_children(child)
        if pos == "bot":
            return f"\\underline{{{e_text}}}"
        return f"\\overline{{{e_text}}}"

    elif tag == "acc":
        # m:acc -> \hat{...}, \vec{...}, \tilde{...}, \dot{...}, etc.
        e_text = ""
        accent_char = "\u0302"  # default: hat
        for child in node:
            ctag = _local_tag(child)
            if ctag == "accPr":
                for prop in child:
                    if _local_tag(prop) == "chr":
                        accent_char = prop.get(qn("m:val"), "\u0302")
            elif ctag == "e":
                e_text = _collect_children(child)
        latex_cmd = _ACCENT_CHAR_TO_LATEX.get(accent_char, r"\hat")
        return f"{latex_cmd}{{{e_text}}}"

    elif tag == "d":
        # m:d (delimiter): \left(...\right) or just (...)
        beg_chr = "("
        end_chr = ")"
        elements = []
        for child in node:
            ctag = _local_tag(child)
            if ctag == "dPr":
                for prop in child:
                    ptag = _local_tag(prop)
                    if ptag == "begChr":
                        beg_chr = prop.get(qn("m:val"), "(")
                    elif ptag == "endChr":
                        end_chr = prop.get(qn("m:val"), ")")
            elif ctag == "e":
                elements.append(_collect_children(child))
        inner = ", ".join(elements) if len(elements) > 1 else (elements[0] if elements else "")
        # Map empty delimiters to LaTeX \left.\right. style
        left = beg_chr if beg_chr else "."
        right = end_chr if end_chr else "."
        return f"\\left{left} {inner} \\right{right}"

    elif tag == "m":
        # m:m (matrix) -> \begin{pmatrix}...\end{pmatrix}
        # Determine delimiter from parent m:d if present
        rows = []
        for child in node:
            ctag = _local_tag(child)
            if ctag == "mr":
                cells = []
                for cell in child:
                    if _local_tag(cell) == "e":
                        cells.append(_collect_children(cell))
                rows.append(" & ".join(cells))
        matrix_body = " \\\\ ".join(rows)
        return f"\\begin{{pmatrix}} {matrix_body} \\end{{pmatrix}}"

    elif tag in ("rPr", "radPr", "fPr", "sSubPr", "sSupPr", "sSubSupPr",
                 "ctrlPr", "funcPr", "limLowPr", "limUppPr", "barPr",
                 "accPr", "dPr", "mPr"):
        return ""

    elif tag in ("num", "den", "e", "sub", "sup", "deg", "lim", "fName"):
        return _collect_children(node)

    else:
        parts = [_omml_node_to_latex(c) for c in node]
        return " ".join(p for p in parts if p)
