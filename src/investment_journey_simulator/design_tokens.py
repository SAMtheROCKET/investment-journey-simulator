"""Chrome tokens: the surfaces a reader looks *through*, not at.

`palette.py` owns the colours that carry data - a fund's identity, a
gain, a tax charge. This module owns everything else: canvas, plate,
rule, numeral, accent. The two sets are deliberately separate and the
boundary is a rule rather than a convention:

    **Nothing in this module may ever encode a value.**

Brass is structure. Verdigris is wayfinding. Neither means "up",
"good" or "fund three", and the moment one of them is used to
distinguish two numbers, a reader who has learned that brass means
*heading* has been lied to.

Why a warm neutral rather than the usual near-white
---------------------------------------------------
Every generated finance interface converges on the same surface -
#FFFFFF or #0F172A, a blue-violet accent, and 20px rounded cards.
The convergence is not a coincidence; it is the mean of the training
distribution. A vellum canvas with a burnished-brass accent and 3px
plate corners lands somewhere that mean does not, which is the whole
point: this program should look like somebody *chose* how it looks.

The choice is only defensible if it costs nothing in legibility, so
every text-on-surface pair below was measured rather than eyeballed.
Worst meaningful case, all pairs:

    light   3.49:1 (faint on plate, a non-essential hint)
            4.50:1 (muted on the recessed surface)
    dark    4.42:1 (faint on plate)
            6.48:1 (muted on plate)

`tests/test_design_tokens.py` asserts those gates. A token cannot be
changed here without the suite re-deriving them.
"""

from __future__ import annotations

from dataclasses import dataclass

# ------------------------------------------------------------------
# Gates. Body text and anything a reader must read to use the screen
# clears WCAG AA. Hints that merely decorate a plate clear the 3:1
# non-text gate and are never the only carrier of their meaning.
# ------------------------------------------------------------------
TEXT_CONTRAST_GATE_FLOAT: float = 4.5
HINT_CONTRAST_GATE_FLOAT: float = 3.0


@dataclass(frozen=True)
class ChromeTokens:
    """One complete set of surfaces, rules and accents.

    Brief:
        Frozen because a half-swapped theme is worse than either
        theme: a reader who sees a light plate on a dark canvas has
        been handed a rendering bug dressed as a design.

    Arguments:
        None: Constructed by the two module-level instances below.

    Returns:
        ChromeTokens: An immutable token set.

    Warning:
        Adding a field obliges you to fill it in for *both* themes
        and to add its contrast pair to the test module. A token
        that exists in light and not in dark is a crash waiting for
        whoever first opens the app at night.
    """

    # The page background. Separate from `canvas_str` because it
    # carries a constraint no other surface does: Plotly traces land
    # on it, so the categorical set in `palette.py` must still clear
    # its 3:1 gate against it. The light value is the warmest vellum
    # that does - amber #D97706 measures 3.03 there, which is a
    # shade better than the 3.02 it managed on the old cool
    # background. Anything deeper and the amber fails, which is why
    # the diagrams use their own, deeper ground and the page does
    # not.
    app_canvas_str: str

    # Surfaces, from furthest back to closest.
    canvas_str: str
    plate_str: str
    sunk_str: str

    # Type, from most to least important.
    ink_str: str
    ink_soft_str: str
    muted_str: str
    faint_str: str

    # Rules. Decorative hairlines: never an input outline or a focus
    # ring, both of which need 3:1 and must come from `ink_soft`.
    hairline_str: str
    hairline_soft_str: str

    # Structure accent. Headings, numerals, section marks.
    brass_str: str
    brass_wash_str: str
    brass_edge_str: str

    # Wayfinding accent. Current position, active state, flow.
    verdigris_str: str
    verdigris_wash_str: str
    verdigris_edge_str: str

    is_dark_bool: bool


LIGHT_CHROME: ChromeTokens = ChromeTokens(
    app_canvas_str="#FBF9F4",
    canvas_str="#F5F2EA",
    plate_str="#FFFDF7",
    sunk_str="#EDE8DC",
    ink_str="#111C24",
    ink_soft_str="#39474F",
    muted_str="#5C6B75",
    faint_str="#7C8A94",
    hairline_str="#DFD8C9",
    hairline_soft_str="#ECE6D9",
    brass_str="#8A5A16",
    brass_wash_str="#F2E7D3",
    brass_edge_str="#DCC59B",
    verdigris_str="#0B6259",
    verdigris_wash_str="#DDEDEA",
    verdigris_edge_str="#A8CFC9",
    is_dark_bool=False,
)

# Not an inversion of the light set. Brass at #8A5A16 measures 1.9:1
# on a #161F27 plate and is unreadable there; the dark brass is a
# separate, lighter pigment chosen against its own surface. The same
# is true of verdigris. Flipping a warm palette by lightness is the
# usual way a dark mode ends up unreadable.
DARK_CHROME: ChromeTokens = ChromeTokens(
    app_canvas_str="#0D141A",
    canvas_str="#0D141A",
    plate_str="#161F27",
    sunk_str="#111A21",
    ink_str="#EAF0F2",
    ink_soft_str="#C2CFD6",
    muted_str="#93A4AE",
    faint_str="#75868F",
    hairline_str="#27333C",
    hairline_soft_str="#1E2830",
    brass_str="#D2A567",
    brass_wash_str="#2A2216",
    brass_edge_str="#4A3B22",
    verdigris_str="#54BFB2",
    verdigris_wash_str="#122B2A",
    verdigris_edge_str="#255049",
    is_dark_bool=True,
)


def resolve_chrome(is_dark_mode_bool: bool) -> ChromeTokens:
    """Pick the token set matching the surface being drawn on.

    Brief:
        The single entry point. Nothing outside this module should
        name a token set directly, so that adding a third theme
        later is one edit here rather than a search across the app.

    Arguments:
        is_dark_mode_bool (bool): True when the page is dark.

    Returns:
        ChromeTokens: The set validated against that surface.

    Warning:
        Light is the safe default everywhere in this codebase, for
        the reason `ui/theme.py` gives: being wrong about the theme
        should cost contrast, never correctness.
    """
    if is_dark_mode_bool:
        return DARK_CHROME
    return LIGHT_CHROME


def _linear_channel_float(channel_int: int) -> float:
    """Undo the sRGB transfer function for one channel.

    Arguments:
        channel_int (int): Channel value, 0-255.

    Returns:
        float: Linear-light value, 0-1.
    """
    ratio_float = channel_int / 255.0
    if ratio_float <= 0.04045:
        return ratio_float / 12.92
    return ((ratio_float + 0.055) / 1.055) ** 2.4


def relative_luminance_float(colour_str: str) -> float:
    """Compute WCAG relative luminance for a hex colour.

    Brief:
        Lives here rather than in a test so that the gates are part
        of the shipped module and can be asserted by anything that
        imports it, not only by the suite.

    Arguments:
        colour_str (str): Hex colour, with or without a leading #.

    Returns:
        float: Relative luminance, 0-1.

    Warning:
        Accepts six-digit hex only. A three-digit shorthand or an
        alpha channel raises rather than silently mismeasuring.
    """
    digit_str = colour_str.lstrip("#")
    if len(digit_str) != 6:
        raise ValueError(
            f"expected six hex digits, got {colour_str!r}"
        )
    red_int = int(digit_str[0:2], 16)
    green_int = int(digit_str[2:4], 16)
    blue_int = int(digit_str[4:6], 16)
    return (
        0.2126 * _linear_channel_float(red_int)
        + 0.7152 * _linear_channel_float(green_int)
        + 0.0722 * _linear_channel_float(blue_int)
    )


def contrast_ratio_float(
    first_colour_str: str,
    second_colour_str: str,
) -> float:
    """Compute the WCAG contrast ratio between two colours.

    Arguments:
        first_colour_str (str): One hex colour.
        second_colour_str (str): The other hex colour.

    Returns:
        float: Ratio from 1.0 (identical) to 21.0 (black on white).

    Warning:
        Order-independent by construction, so a caller cannot get a
        different answer by passing foreground and background the
        wrong way round.
    """
    first_float = relative_luminance_float(first_colour_str)
    second_float = relative_luminance_float(second_colour_str)
    lighter_float = max(first_float, second_float)
    darker_float = min(first_float, second_float)
    return (lighter_float + 0.05) / (darker_float + 0.05)


# ------------------------------------------------------------------
# The instrument panel.
#
# The timeline and the Gantt are not documents to read; they are
# control surfaces to work on, and they had always been drawn dark
# because that is what a control surface looks like. When the page
# stopped force-painting itself dark, they were left drawing pale
# ink on whatever the page happened to be - which on the vellum
# canvas is pale ink on pale paper.
#
# The fix is the same one the money-flow diagrams already use: the
# figure carries its own ground. A Plotly figure is a picture placed
# on the page, not text flowing through it, so it can hold a surface
# of its own without any risk of inverting against something else.
# That restores the darker rail and makes it correct in both themes
# at once, because it no longer depends on either.
#
# These are NOT chart data colours. Nothing here may carry a value;
# the fund colours in `palette.py` still own that, and they are
# validated against the page canvas rather than against this panel,
# which is why no data series is ever drawn on it.
PANEL_SURFACE_STR: str = "#1B2836"
PANEL_INK_STR: str = "#E8EEF2"
PANEL_MUTED_STR: str = "#A3B4C1"
PANEL_FAINT_STR: str = "#8496A4"
PANEL_LINE_STR: str = "#63809C"
PANEL_ACCENT_STR: str = "#4FC3B4"
PANEL_WARN_STR: str = "#D9A45B"
PANEL_SPAN_STR: str = "#3F5568"
# A gridline is structure, not data: barely there on purpose.
PANEL_GRID_STR: str = "#243444"

# One stack for the page and every figure on it. Plotly otherwise
# picks its own, and a chart set in a different face reads as
# something pasted in rather than part of the screen.
FONT_STACK_STR: str = (
    "ui-sans-serif, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)
