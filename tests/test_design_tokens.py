"""Chrome token tests.

`design_tokens.py` writes its measured worst cases into its own
docstring. A docstring is a claim; these are the checks that make it
one nobody can quietly break.

Two properties are guarded. Text a reader must read to use the
screen clears WCAG AA against the surface it is drawn on, in both
themes. And the page background stays light enough for the
categorical chart set in `palette.py`, which is the constraint that
decides how warm the canvas is allowed to be - the diagrams may go
deeper because no data lands on them.
"""

from __future__ import annotations

import pytest

from investment_journey_simulator.design_tokens import (
    DARK_CHROME,
    HINT_CONTRAST_GATE_FLOAT,
    LIGHT_CHROME,
    TEXT_CONTRAST_GATE_FLOAT,
    ChromeTokens,
    contrast_ratio_float,
    relative_luminance_float,
    resolve_chrome,
)
from investment_journey_simulator.palette import (
    DARK_FUND_COLOUR_TUPLE,
    LIGHT_FUND_COLOUR_TUPLE,
)

CHART_SURFACE_GATE_FLOAT: float = 3.0

THEME_TUPLE: tuple = (
    ("light", LIGHT_CHROME),
    ("dark", DARK_CHROME),
)


def text_pair_list(chrome: ChromeTokens) -> list[tuple]:
    """Every text-on-surface pair a reader has to read."""
    return [
        ("ink on canvas", chrome.ink_str, chrome.canvas_str),
        ("ink on plate", chrome.ink_str, chrome.plate_str),
        ("ink on app canvas", chrome.ink_str, chrome.app_canvas_str),
        ("ink soft on plate", chrome.ink_soft_str, chrome.plate_str),
        ("muted on plate", chrome.muted_str, chrome.plate_str),
        ("muted on canvas", chrome.muted_str, chrome.canvas_str),
        ("muted on sunk", chrome.muted_str, chrome.sunk_str),
        ("brass on plate", chrome.brass_str, chrome.plate_str),
        ("brass on canvas", chrome.brass_str, chrome.canvas_str),
        ("brass on wash", chrome.brass_str, chrome.brass_wash_str),
        ("verdigris on plate", chrome.verdigris_str, chrome.plate_str),
        (
            "verdigris on wash",
            chrome.verdigris_str,
            chrome.verdigris_wash_str,
        ),
    ]


@pytest.mark.parametrize(
    ("theme_name_str", "chrome"),
    THEME_TUPLE,
    ids=[name for name, _tokens in THEME_TUPLE],
)
def test_every_readable_pair_clears_the_text_gate(
    theme_name_str, chrome
):
    """Body text is AA against whatever it is drawn on."""
    for label_str, ink_str, surface_str in text_pair_list(chrome):
        ratio_float = contrast_ratio_float(ink_str, surface_str)
        assert ratio_float >= TEXT_CONTRAST_GATE_FLOAT, (
            f"{theme_name_str}: {label_str} measures "
            f"{ratio_float:.2f}, under "
            f"{TEXT_CONTRAST_GATE_FLOAT}."
        )


@pytest.mark.parametrize(
    ("theme_name_str", "chrome"),
    THEME_TUPLE,
    ids=[name for name, _tokens in THEME_TUPLE],
)
def test_the_faint_hint_clears_the_non_text_gate(
    theme_name_str, chrome
):
    """The faintest ink still separates from the plate.

    It never carries meaning on its own, so it is held to the 3:1
    non-text gate rather than to AA.
    """
    ratio_float = contrast_ratio_float(
        chrome.faint_str, chrome.plate_str
    )
    assert ratio_float >= HINT_CONTRAST_GATE_FLOAT, (
        f"{theme_name_str}: faint measures {ratio_float:.2f}."
    )


@pytest.mark.parametrize(
    ("theme_name_str", "chrome", "colour_tuple"),
    (
        ("light", LIGHT_CHROME, LIGHT_FUND_COLOUR_TUPLE),
        ("dark", DARK_CHROME, DARK_FUND_COLOUR_TUPLE),
    ),
    ids=("light", "dark"),
)
def test_the_page_stays_light_enough_for_the_chart_set(
    theme_name_str, chrome, colour_tuple
):
    """The canvas is bound by the data, not by taste.

    Plotly traces land on the page background, so warming it is
    only allowed as far as the validated categorical set survives.
    Amber is the binding constraint in light mode and has the least
    headroom of the six; if this fails, the canvas went too deep.
    """
    for colour_str in colour_tuple:
        ratio_float = contrast_ratio_float(
            colour_str, chrome.app_canvas_str
        )
        assert ratio_float >= CHART_SURFACE_GATE_FLOAT, (
            f"{theme_name_str}: fund colour {colour_str} measures "
            f"{ratio_float:.2f} on {chrome.app_canvas_str}. Either "
            "lighten the canvas or re-run the palette validator."
        )


def test_the_dark_set_is_not_an_inversion_of_the_light_one():
    """Each theme's accents were chosen against its own surface.

    Flipping a warm palette by lightness is the usual way a dark
    mode ends up unreadable, so the two brasses must differ.
    """
    assert LIGHT_CHROME.brass_str != DARK_CHROME.brass_str
    assert (
        LIGHT_CHROME.verdigris_str != DARK_CHROME.verdigris_str
    )
    light_on_dark_float = contrast_ratio_float(
        LIGHT_CHROME.brass_str, DARK_CHROME.plate_str
    )
    assert light_on_dark_float < TEXT_CONTRAST_GATE_FLOAT, (
        "The light brass now passes on the dark plate, so the "
        "reason the two sets are separate no longer holds. Check "
        "whether one of them drifted."
    )


def test_resolving_a_theme_returns_the_matching_set():
    """The single entry point picks by the flag it is given."""
    assert resolve_chrome(False) is LIGHT_CHROME
    assert resolve_chrome(True) is DARK_CHROME


def test_luminance_rejects_a_colour_it_cannot_measure():
    """A shorthand or an alpha channel raises rather than lying."""
    with pytest.raises(ValueError):
        relative_luminance_float("#FFF")


def test_contrast_is_order_independent():
    """A caller cannot get a different answer by swapping them."""
    forward_float = contrast_ratio_float("#111C24", "#FBF9F4")
    reverse_float = contrast_ratio_float("#FBF9F4", "#111C24")
    assert forward_float == pytest.approx(reverse_float)


# ------------------------------------------------------------------
# Polarity. The chrome used to pick its colours from a guess about
# which theme was running - `st.context.theme` reports the browser's
# preference, the app's theme comes from config.toml, and when those
# disagreed the page drew one theme's ink on the other's paper.
#
# Measured, that is 1.09:1 and 1.07:1: not poor contrast but
# invisible text. Re-tuning the values cannot fix a polarity decided
# by a coin flip, so the colours are now derived from the page's own
# `currentColor` and these check the derivation instead.
# ------------------------------------------------------------------
LIGHT_PAGE_TUPLE: tuple = ("light page", "#111C24", "#FBF9F4")
DARK_PAGE_TUPLE: tuple = ("dark page", "#EAF0F2", "#0D141A")
CONSOLE_TUPLE: tuple = ("console", "#EAF0F2", "#141E26")
SURFACE_CONTEXT_TUPLE: tuple = (
    LIGHT_PAGE_TUPLE,
    DARK_PAGE_TUPLE,
    CONSOLE_TUPLE,
)

PLATE_SHARE_FLOAT: float = 0.035
TEXT_SHARE_TUPLE: tuple = (
    ("ink", 1.0, TEXT_CONTRAST_GATE_FLOAT),
    ("ink soft", 0.84, TEXT_CONTRAST_GATE_FLOAT),
    ("muted", 0.70, TEXT_CONTRAST_GATE_FLOAT),
    ("faint", 0.55, HINT_CONTRAST_GATE_FLOAT),
)
ACCENT_SHARE_FLOAT: float = 0.72


def _channel_tuple(colour_str: str) -> tuple:
    """Split a hex colour into its three channels."""
    digit_str = colour_str.lstrip("#")
    return tuple(
        int(digit_str[index_int:index_int + 2], 16)
        for index_int in (0, 2, 4)
    )


def _blend_str(
    front_str: str,
    back_str: str,
    share_float: float,
) -> str:
    """Composite one colour over another at a given share.

    This is what `color-mix(in srgb, X n%, transparent)` resolves to
    once the browser paints it over whatever is behind.
    """
    front_tuple = _channel_tuple(front_str)
    back_tuple = _channel_tuple(back_str)
    channel_list = [
        round(
            share_float * front_tuple[index_int]
            + (1.0 - share_float) * back_tuple[index_int]
        )
        for index_int in range(3)
    ]
    return "#" + "".join(
        f"{channel_int:02X}" for channel_int in channel_list
    )


@pytest.mark.parametrize(
    "context_tuple",
    SURFACE_CONTEXT_TUPLE,
    ids=[name for name, _ink, _page in SURFACE_CONTEXT_TUPLE],
)
def test_derived_text_reads_on_every_surface(context_tuple):
    """Ink derived from the page's own colour always reads.

    Whatever the page's text colour is, fading it toward
    transparent can only move it toward the background it is drawn
    on - never past it and out the other side. That is the property
    the old fixed tokens did not have.
    """
    name_str, ink_str, page_str = context_tuple
    plate_str = _blend_str(ink_str, page_str, PLATE_SHARE_FLOAT)
    for label_str, share_float, gate_float in TEXT_SHARE_TUPLE:
        effective_str = _blend_str(ink_str, plate_str, share_float)
        ratio_float = contrast_ratio_float(effective_str, plate_str)
        assert ratio_float >= gate_float, (
            f"{name_str}: {label_str} measures {ratio_float:.2f}, "
            f"under {gate_float}"
        )


@pytest.mark.parametrize(
    "context_tuple",
    SURFACE_CONTEXT_TUPLE,
    ids=[name for name, _ink, _page in SURFACE_CONTEXT_TUPLE],
)
def test_derived_accents_read_on_every_surface(context_tuple):
    """Brass and verdigris follow the page they land on.

    Each is mixed toward the page's own text colour, which pulls it
    light on a dark ground and dark on a light one. A fixed pigment
    could not do that, which is why there used to be two of each.
    """
    from investment_journey_simulator.ui.chrome import (
        BRASS_PIGMENT_STR,
        VERDIGRIS_PIGMENT_STR,
    )

    name_str, ink_str, page_str = context_tuple
    plate_str = _blend_str(ink_str, page_str, PLATE_SHARE_FLOAT)
    for label_str, pigment_str in (
        ("brass", BRASS_PIGMENT_STR),
        ("verdigris", VERDIGRIS_PIGMENT_STR),
    ):
        accent_str = _blend_str(
            pigment_str, ink_str, ACCENT_SHARE_FLOAT
        )
        for surface_name_str, surface_str in (
            ("plate", plate_str),
            ("page", page_str),
        ):
            ratio_float = contrast_ratio_float(
                accent_str, surface_str
            )
            assert ratio_float >= TEXT_CONTRAST_GATE_FLOAT, (
                f"{name_str}: {label_str} on {surface_name_str} "
                f"measures {ratio_float:.2f}"
            )


def test_the_stylesheet_hardcodes_no_text_colour():
    """The guarantee, enforced rather than described.

    A fixed colour in a text rule is exactly how the polarity bug
    got in. The two pigments are allowed because they are mixed
    toward `currentColor` before they are ever used, and the mark's
    ring is allowed because it sits on saturated pigment rather
    than on the page.
    """
    import re

    from investment_journey_simulator.ui.chrome import (
        _stylesheet_str,
    )

    allowed_tuple = ("#A9762F", "#28887E", "#6d4711", "#fff7ea")
    found_list = [
        found_str
        for found_str in re.findall(
            r"#[0-9A-Fa-f]{6}", _stylesheet_str()
        )
        if found_str not in allowed_tuple
    ]
    assert found_list == [], (
        f"the stylesheet hardcodes {found_list}; derive it from "
        "currentColor instead"
    )


def test_every_colour_token_is_derived_from_current_colour():
    """No token may carry a fixed value of its own."""
    from investment_journey_simulator.ui.chrome import (
        _stylesheet_str,
    )

    for line_str in _stylesheet_str().split("\n"):
        stripped_str = line_str.strip()
        if not stripped_str.startswith("--ijs-"):
            continue
        is_derived_bool = "currentColor" in stripped_str
        is_translucent_bool = "transparent" in stripped_str
        assert is_derived_bool or is_translucent_bool, (
            f"token {stripped_str!r} carries an opaque colour of "
            "its own. Derive it from currentColor, or mix it "
            "toward transparent so it composites over whatever is "
            "behind it."
        )


# ------------------------------------------------------------------
# The instrument panel. The timeline and the Gantt are control
# surfaces rather than documents, and they had always been drawn
# dark. When the page stopped force-painting itself dark they were
# left drawing pale ink on whatever the page happened to be, which
# on the vellum canvas is pale on pale.
#
# They now carry their own ground, the way the money-flow diagrams
# do. These check that ground holds its own ink.
# ------------------------------------------------------------------
PANEL_PAIR_TUPLE: tuple = (
    ("ink", "PANEL_INK_STR", TEXT_CONTRAST_GATE_FLOAT),
    ("muted", "PANEL_MUTED_STR", TEXT_CONTRAST_GATE_FLOAT),
    ("accent", "PANEL_ACCENT_STR", TEXT_CONTRAST_GATE_FLOAT),
    ("warn", "PANEL_WARN_STR", TEXT_CONTRAST_GATE_FLOAT),
    ("faint", "PANEL_FAINT_STR", HINT_CONTRAST_GATE_FLOAT),
    ("line", "PANEL_LINE_STR", HINT_CONTRAST_GATE_FLOAT),
)


@pytest.mark.parametrize(
    ("label_str", "token_name_str", "gate_float"),
    PANEL_PAIR_TUPLE,
    ids=[pair[0] for pair in PANEL_PAIR_TUPLE],
)
def test_the_panel_holds_its_own_ink(
    label_str, token_name_str, gate_float
):
    """Every mark on the panel reads against the panel."""
    from investment_journey_simulator import design_tokens

    ratio_float = contrast_ratio_float(
        getattr(design_tokens, token_name_str),
        design_tokens.PANEL_SURFACE_STR,
    )
    assert ratio_float >= gate_float, (
        f"panel {label_str} measures {ratio_float:.2f}"
    )


def test_the_panel_is_visible_on_both_pages():
    """It has to read as an object placed on the page.

    On the vellum canvas that is obvious. On the dark canvas it
    must still be distinguishable, or the panel stops being a panel
    and the rail floats.
    """
    from investment_journey_simulator.design_tokens import (
        DARK_CHROME,
        LIGHT_CHROME,
        PANEL_SURFACE_STR,
    )

    assert (
        contrast_ratio_float(
            PANEL_SURFACE_STR, LIGHT_CHROME.app_canvas_str
        )
        > 3.0
    )
    assert (
        contrast_ratio_float(
            PANEL_SURFACE_STR, DARK_CHROME.app_canvas_str
        )
        > 1.15
    )


def test_no_data_colour_is_ever_drawn_on_the_panel():
    """The panel is structure, so no fund series may land on it.

    The categorical set is validated against the page canvas and
    against nothing else, which is exactly why the timeline carries
    no data series and the data charts carry no panel.
    """
    from investment_journey_simulator.design_tokens import (
        PANEL_SURFACE_STR,
    )

    weak_list = [
        colour_str
        for colour_str in LIGHT_FUND_COLOUR_TUPLE
        if contrast_ratio_float(colour_str, PANEL_SURFACE_STR)
        < CHART_SURFACE_GATE_FLOAT
    ]
    assert weak_list, (
        "the light fund colours now all clear the panel, so the "
        "reason they are kept off it no longer holds. Check "
        "whether the panel drifted."
    )
