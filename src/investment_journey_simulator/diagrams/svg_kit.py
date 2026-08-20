"""The small vocabulary every diagram in this package is drawn in.

Deliberately tiny. Six primitives and a plate, because a diagram
language with twenty shapes stops being a language and becomes a
drawing program - and a drawing program is how you end up with two
diagrams that no longer look related.

Three rules are enforced here rather than left to whoever draws the
next one:

*No glyph icons.* Every mark is a stroked path or primitive. The
predecessor of these diagrams used `¤ ▣ ◇ ▥` as icons, which are
absent from most sans fonts and rendered as empty boxes in the
exported PNG. A drawn icon cannot go missing.

*No drop shadows.* Depth comes from a hairline and a change of
surface. Soft shadows under every card is the single most reliable
tell of a generated interface.

*Corners are 3px.* Not 20. The plates should read as machined, not
as inflated.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

FONT_STACK_STR: str = (
    "ui-sans-serif,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
)
PLATE_RADIUS_INT: int = 3
ICON_BOX_INT: int = 24

# Anchors, spelled out so a call site never passes a raw SVG string.
ANCHOR_START_STR: str = "start"
ANCHOR_MIDDLE_STR: str = "middle"
ANCHOR_END_STR: str = "end"


def text_mark_str(
    x_float: float,
    y_float: float,
    body_str: str,
    size_float: float,
    colour_str: str,
    weight_int: int = 400,
    tracking_float: float = 0.0,
    anchor_str: str = ANCHOR_START_STR,
    opacity_float: float = 1.0,
) -> str:
    """Draw one run of text, escaping its body.

    Arguments:
        x_float (float): Left, centre or right edge, per anchor.
        y_float (float): Baseline, not the top of the glyphs.
        body_str (str): Text to draw.
        size_float (float): Font size in user units.
        colour_str (str): Fill colour.
        weight_int (int): CSS font weight.
        tracking_float (float): Letter spacing.
        anchor_str (str): One of the module's anchor constants.
        opacity_float (float): Fill opacity.

    Returns:
        str: One `<text>` element.

    Warning:
        `y_float` is the baseline. Passing the top of a box here is
        the commonest way to end up with text overhanging a plate.
    """
    tracking_str = (
        f" letter-spacing='{tracking_float}'"
        if tracking_float
        else ""
    )
    opacity_str = (
        f" fill-opacity='{opacity_float}'"
        if opacity_float != 1.0
        else ""
    )
    return (
        f"<text x='{x_float}' y='{y_float}' "
        f"font-family=\"{FONT_STACK_STR}\" "
        f"font-size='{size_float}' font-weight='{weight_int}' "
        f"fill='{colour_str}' text-anchor='{anchor_str}'"
        f"{tracking_str}{opacity_str}>{escape(body_str)}</text>"
    )


def kicker_mark_str(
    x_float: float,
    y_float: float,
    body_str: str,
    colour_str: str,
) -> str:
    """Draw a section mark: small, letterspaced, upper case.

    Brief:
        The one typographic device that carries the whole system.
        Every zone in every diagram is introduced by one of these,
        which is what makes three separate pictures read as three
        views of one document.

    Arguments:
        x_float (float): Left edge.
        y_float (float): Baseline.
        body_str (str): Label, upper-cased for you.
        colour_str (str): Fill colour, normally brass.

    Returns:
        str: One `<text>` element.

    Warning:
        Never used for anything a reader must read to follow the
        diagram. It labels; it does not explain.
    """
    return text_mark_str(
        x_float,
        y_float,
        body_str.upper(),
        10.5,
        colour_str,
        weight_int=700,
        tracking_float=1.9,
    )


def rect_mark_str(
    x_float: float,
    y_float: float,
    width_float: float,
    height_float: float,
    fill_str: str,
    stroke_str: str = "none",
    radius_int: int = PLATE_RADIUS_INT,
    opacity_float: float = 1.0,
) -> str:
    """Draw a rectangle.

    Arguments:
        x_float (float): Left edge.
        y_float (float): Top edge.
        width_float (float): Width.
        height_float (float): Height.
        fill_str (str): Fill colour, or "none".
        stroke_str (str): Stroke colour, or "none".
        radius_int (int): Corner radius.
        opacity_float (float): Fill opacity.

    Returns:
        str: One `<rect>` element.
    """
    return (
        f"<rect x='{x_float}' y='{y_float}' "
        f"width='{width_float}' height='{height_float}' "
        f"rx='{radius_int}' fill='{fill_str}' "
        f"fill-opacity='{opacity_float}' stroke='{stroke_str}' "
        f"stroke-width='1'/>"
    )


def line_mark_str(
    x1_float: float,
    y1_float: float,
    x2_float: float,
    y2_float: float,
    colour_str: str,
    width_float: float = 1.0,
    dash_str: str = "",
) -> str:
    """Draw a straight rule.

    Arguments:
        x1_float (float): Start x.
        y1_float (float): Start y.
        x2_float (float): End x.
        y2_float (float): End y.
        colour_str (str): Stroke colour.
        width_float (float): Stroke width.
        dash_str (str): Dash array, empty for solid.

    Returns:
        str: One `<line>` element.
    """
    dash_attribute_str = (
        f" stroke-dasharray='{dash_str}'" if dash_str else ""
    )
    return (
        f"<line x1='{x1_float}' y1='{y1_float}' "
        f"x2='{x2_float}' y2='{y2_float}' stroke='{colour_str}' "
        f"stroke-width='{width_float}' stroke-linecap='round'"
        f"{dash_attribute_str}/>"
    )


def path_mark_str(
    definition_str: str,
    stroke_str: str,
    width_float: float = 1.6,
    fill_str: str = "none",
) -> str:
    """Draw an open path.

    Arguments:
        definition_str (str): SVG path data.
        stroke_str (str): Stroke colour.
        width_float (float): Stroke width.
        fill_str (str): Fill colour, normally "none".

    Returns:
        str: One `<path>` element.
    """
    return (
        f"<path d='{definition_str}' fill='{fill_str}' "
        f"stroke='{stroke_str}' stroke-width='{width_float}' "
        f"stroke-linecap='round' stroke-linejoin='round'/>"
    )


def chevron_mark_str(
    x_float: float,
    y_float: float,
    colour_str: str,
    size_float: float = 6.0,
) -> str:
    """Draw the flow direction mark that sits in a gap.

    Brief:
        A chevron rather than a filled arrowhead. The spine is one
        continuous rule running behind the plates and showing
        through the gaps; a solid triangle would break it into
        separate arrows and lose the sense of one continuous path.

    Arguments:
        x_float (float): Centre x.
        y_float (float): Centre y.
        colour_str (str): Stroke colour.
        size_float (float): Half-height of the chevron.

    Returns:
        str: One `<path>` element.
    """
    return path_mark_str(
        f"M{x_float - size_float * 0.6} {y_float - size_float} "
        f"L{x_float + size_float * 0.6} {y_float} "
        f"L{x_float - size_float * 0.6} {y_float + size_float}",
        colour_str,
        width_float=2.2,
    )


# ------------------------------------------------------------------
# Icons. Each is drawn inside a 24x24 box whose top-left corner is
# the origin passed in. Stroked, never filled, never a font glyph.
# ------------------------------------------------------------------
def _coins_icon_str(x: float, y: float, colour_str: str) -> str:
    """Money you earned: a stack of three coins."""
    marks = [
        f"<ellipse cx='{x + 12}' cy='{y + 6}' rx='8.5' ry='3.4' "
        f"fill='none' stroke='{colour_str}' stroke-width='1.6'/>",
        path_mark_str(
            f"M{x + 3.5} {y + 6} v5.5 a8.5 3.4 0 0 0 17 0 V{y + 6}",
            colour_str,
        ),
        path_mark_str(
            f"M{x + 3.5} {y + 11.5} v5.5 a8.5 3.4 0 0 0 17 0 "
            f"V{y + 11.5}",
            colour_str,
        ),
    ]
    return "".join(marks)


def _bank_icon_str(x: float, y: float, colour_str: str) -> str:
    """A bank: pediment, columns, plinth."""
    marks = [
        path_mark_str(
            f"M{x + 2} {y + 9} L{x + 12} {y + 3} L{x + 22} {y + 9}",
            colour_str,
        ),
        line_mark_str(x + 2, y + 21, x + 22, y + 21, colour_str, 1.6),
    ]
    marks.extend(
        line_mark_str(
            x + offset, y + 11, x + offset, y + 18, colour_str, 1.6
        )
        for offset in (5.5, 12.0, 18.5)
    )
    return "".join(marks)


def _globe_icon_str(x: float, y: float, colour_str: str) -> str:
    """Crossing a border: a meridian globe."""
    marks = [
        f"<circle cx='{x + 12}' cy='{y + 12}' r='9' fill='none' "
        f"stroke='{colour_str}' stroke-width='1.6'/>",
        f"<ellipse cx='{x + 12}' cy='{y + 12}' rx='4.2' ry='9' "
        f"fill='none' stroke='{colour_str}' stroke-width='1.6'/>",
        line_mark_str(x + 3, y + 12, x + 21, y + 12, colour_str, 1.6),
    ]
    return "".join(marks)


def _passbook_icon_str(x: float, y: float, colour_str: str) -> str:
    """An account: a passbook with a band and a signature line."""
    marks = [
        rect_mark_str(
            x + 2.5,
            y + 5,
            19,
            14,
            "none",
            colour_str,
            radius_int=2,
        ),
        line_mark_str(
            x + 2.5, y + 10, x + 21.5, y + 10, colour_str, 1.6
        ),
        line_mark_str(
            x + 6.5, y + 15, x + 13, y + 15, colour_str, 1.6
        ),
    ]
    return "".join(marks)


def _screen_icon_str(x: float, y: float, colour_str: str) -> str:
    """A platform: a screen on a stand, with two list rows."""
    marks = [
        rect_mark_str(
            x + 2.5,
            y + 4,
            19,
            13,
            "none",
            colour_str,
            radius_int=2,
        ),
        line_mark_str(x + 12, y + 17, x + 12, y + 20, colour_str, 1.6),
        line_mark_str(x + 8, y + 20, x + 16, y + 20, colour_str, 1.6),
        line_mark_str(x + 6.5, y + 8, x + 13, y + 8, colour_str, 1.4),
        line_mark_str(
            x + 6.5, y + 11.5, x + 11, y + 11.5, colour_str, 1.4
        ),
    ]
    return "".join(marks)


def _growth_icon_str(x: float, y: float, colour_str: str) -> str:
    """A portfolio: four bars on a baseline, rising."""
    marks = [
        line_mark_str(x + 2, y + 21, x + 22, y + 21, colour_str, 1.6)
    ]
    marks.extend(
        line_mark_str(
            x + offset, y + 21, x + offset, y + top, colour_str, 2.2
        )
        for offset, top in ((5, 14), (10, 9), (15, 11.5), (20, 4))
    )
    return "".join(marks)


def _repeat_icon_str(x: float, y: float, colour_str: str) -> str:
    """A recurring instruction: a loop with a head."""
    marks = [
        path_mark_str(
            f"M{x + 20} {y + 12} a8 8 0 1 1 -3.2 -6.4",
            colour_str,
        ),
        path_mark_str(
            f"M{x + 20} {y + 3} L{x + 20} {y + 8.5} "
            f"L{x + 14.5} {y + 8.5}",
            colour_str,
        ),
    ]
    return "".join(marks)


ICON_BUILDER_DICT: dict = {
    "coins": _coins_icon_str,
    "bank": _bank_icon_str,
    "globe": _globe_icon_str,
    "passbook": _passbook_icon_str,
    "screen": _screen_icon_str,
    "growth": _growth_icon_str,
    "repeat": _repeat_icon_str,
}


def icon_mark_str(
    name_str: str,
    x_float: float,
    y_float: float,
    colour_str: str,
) -> str:
    """Draw one icon by name.

    Arguments:
        name_str (str): Key in `ICON_BUILDER_DICT`.
        x_float (float): Left edge of the 24x24 box.
        y_float (float): Top edge of the 24x24 box.
        colour_str (str): Stroke colour.

    Returns:
        str: The icon's elements.

    Warning:
        An unknown name raises rather than drawing nothing. A
        silently missing icon leaves a hole that survives review;
        a crash does not.
    """
    if name_str not in ICON_BUILDER_DICT:
        raise KeyError(f"no icon named {name_str!r}")
    return ICON_BUILDER_DICT[name_str](
        x_float, y_float, colour_str
    )


def open_svg_str(width_int: int, height_int: int) -> str:
    """Open a responsive root element.

    Brief:
        Carries a viewBox and no fixed pixel size, so the same
        markup scales from a phone to a print export without
        being redrawn.

    Arguments:
        width_int (int): Design width in user units.
        height_int (int): Design height in user units.

    Returns:
        str: The opening `<svg>` tag.
    """
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' "
        f"viewBox='0 0 {width_int} {height_int}' "
        f"width='100%' role='img' "
        f"preserveAspectRatio='xMidYMid meet'>"
    )
