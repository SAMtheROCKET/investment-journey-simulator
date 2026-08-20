"""One person's actual setup, providers named. Export only.

The other three diagrams describe the process. This one documents an
implementation: the specific banks, remittance provider, fund
platform and broker that one person actually uses, in the order they
actually use them.

Why this is a separate module
-----------------------------
`tests/test_no_product_names.py` bans naming another product
anywhere in this project, and that rule is right for everything the
application shows: a diagram inside the app that names a broker is
an advertisement the reader did not ask for, and it dates the moment
that broker changes its name.

This file is the single, deliberate exception, carved narrowly:

*It is never rendered in the app.* It is not in
`money_flow.DIAGRAM_BUILDER_DICT`, which is what the Guides screen
draws from. It lives in `EXPORT_BUILDER_DICT` here, which only
`tools/render_diagrams.py` reads. Adding it to a screen would take a
deliberate edit, not an accident.

*It is an export.* Its output is an SVG for a post or a slide, meant
to sit beside a link to the application rather than inside it.

*It labels itself.* "Example only, not a recommendation" is drawn
into the picture rather than written in a caption beside it, because
a picture travels and a caption does not.

*It names, it does not depict.* Providers appear as their names set
in a tile. No logo is reproduced, because a name in a sentence is a
reference and a redrawn logo is a use of somebody's mark.

The shape is taken from the author's own hand-drawn flow: the
remittance lands in the NRE account, moves across to the NRO, and
everything is bought from there down two routes - a mandate into
mutual funds, and a broker into equity held in demat.
"""

from __future__ import annotations

from investment_journey_simulator.design_tokens import (
    ChromeTokens,
    resolve_chrome,
)
from investment_journey_simulator.diagrams.money_flow import (
    CONTENT_RIGHT_INT,
    MARGIN_INT,
    RUPEE_STR,
    YEN_STR,
    Stage,
    _chip_str,
    _document_str,
    _footnote_str,
    _heading_str,
    _plate_geometry_tuple,
    _spine_str,
    _stage_plate_str,
)
from investment_journey_simulator.diagrams.svg_kit import (
    ANCHOR_END_STR,
    chevron_mark_str,
    icon_mark_str,
    kicker_mark_str,
    line_mark_str,
    path_mark_str,
    rect_mark_str,
    text_mark_str,
)

PERSONAL_HEIGHT_INT: int = 1120

DISCLAIMER_STR: str = "Example only - not a recommendation"
PERSONAL_LEAD_STR: str = (
    "The exact route one person uses. Every provider named here is "
    "one choice among several that work."
)
PERSONAL_ZONE_KICKER_STR: str = (
    "Steps 1-5 - getting yen into the account I invest from"
)
PERSONAL_FOOTNOTE_TUPLE: tuple = (
    "These are the providers I happen to use, named so the picture "
    "is checkable rather than vague. None of it is advice, none of "
    "it is a comparison, and none of these firms had any part in "
    "it. Eligibility and charges change; confirm before you act.",
)

# Provider is drawn as a tile above the plate. The name only - no
# mark is reproduced, because naming a firm is a reference and
# redrawing its logo is a use of its trademark.
PERSONAL_STAGE_TUPLE: tuple = (
    (
        "Employer",
        Stage(
            "01 - Earn",
            "Salary in Japan",
            ("Employment income, paid", "monthly in yen."),
            "coins",
            YEN_STR,
        ),
    ),
    (
        "Japanese bank",
        Stage(
            "02 - Receive",
            "Local bank account",
            ("The salary is credited", "where I live."),
            "bank",
            YEN_STR,
        ),
    ),
    (
        "Wise",
        Stage(
            "03 - Cross",
            "Remittance provider",
            ("Converts yen to rupees", "and sends it on."),
            "globe",
            "yen to rupees",
        ),
    ),
    (
        "Indian bank - NRE",
        Stage(
            "04 - Land",
            "NRE account",
            ("Where the remittance is", "credited. Foreign earnings."),
            "passbook",
            RUPEE_STR,
        ),
    ),
    (
        "Indian bank - NRO",
        Stage(
            "05 - Move",
            "NRO account",
            ("Moved across, and every", "purchase below buys here."),
            "bank",
            RUPEE_STR,
        ),
    ),
)

PERSONAL_ROUTE_TUPLE: tuple = (
    (
        "Route A - mutual funds",
        "a mandate does the work each month",
        (
            (
                "Coin",
                "eNACH mandate",
                ("Pulls the agreed amount on", "the same day monthly."),
                "repeat",
                (),
            ),
            (
                "Coin",
                "Mutual fund units",
                ("Bought at the applicable", "NAV against my folio."),
                "screen",
                (),
            ),
            (
                "",
                "Two ways money goes in",
                ("The mandate monthly, and a", "one-off when there is spare."),
                "growth",
                ("SIP - monthly", "Lump sum - ad hoc"),
            ),
        ),
    ),
    (
        "Route B - direct equity",
        "each purchase is a decision I make",
        (
            (
                "Zerodha",
                "Fund the broker",
                ("Money moves from the NRO to", "the broker first."),
                "screen",
                (),
            ),
            (
                "Kite",
                "Order as CNC delivery",
                ("Delivery rather than", "intraday - I intend to hold."),
                "coins",
                (),
            ),
            (
                "",
                "Shares in demat",
                ("Settles the next working", "day and shows in demat."),
                "growth",
                ("T+1 - settled",),
            ),
        ),
    ),
)


def _provider_tile_str(
    provider_str: str,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Name the provider in a tile above its step.

    A name set in a box, never a redrawn mark.
    """
    if not provider_str:
        return ""
    width_float = 18.0 + len(provider_str) * 7.4
    return rect_mark_str(
        x_float,
        y_float,
        width_float,
        24,
        chrome.brass_wash_str,
        chrome.brass_edge_str,
        2,
    ) + text_mark_str(
        x_float + 9,
        y_float + 16.5,
        provider_str,
        11.5,
        chrome.brass_str,
        weight_int=700,
        tracking_float=0.3,
    )


def _disclaimer_str(chrome: ChromeTokens) -> str:
    """Draw the label into the picture, not beside it.

    A caption stays behind when an image is shared; this does not.
    """
    width_float = 26.0 + len(DISCLAIMER_STR) * 7.0
    x_float = CONTENT_RIGHT_INT - width_float
    return rect_mark_str(
        x_float,
        44,
        width_float,
        30,
        chrome.brass_wash_str,
        chrome.brass_str,
        2,
    ) + text_mark_str(
        x_float + 13,
        64,
        DISCLAIMER_STR,
        12.5,
        chrome.brass_str,
        weight_int=700,
        tracking_float=0.4,
    )


def _personal_step_str(
    step_tuple: tuple,
    x_float: float,
    y_float: float,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """One plate in a route lane, with its provider named."""
    provider_str, title_str, body_tuple, icon_str, leaf_tuple = (
        step_tuple
    )
    part_list: list = [
        _provider_tile_str(
            provider_str, x_float, y_float - 34, chrome
        ),
        rect_mark_str(
            x_float,
            y_float,
            width_float,
            156,
            chrome.plate_str,
            chrome.hairline_str,
        ),
        icon_mark_str(
            icon_str,
            x_float + 20,
            y_float + 22,
            chrome.verdigris_str,
        ),
        text_mark_str(
            x_float + 56,
            y_float + 40,
            title_str,
            15,
            chrome.ink_str,
            weight_int=670,
        ),
    ]
    part_list.append(
        _step_copy_str(body_tuple, x_float + 20, y_float, chrome)
    )
    part_list.append(
        _leaf_str(leaf_tuple, x_float + 20, y_float + 120, chrome)
    )
    return "".join(part_list)


def _step_copy_str(
    body_tuple: tuple,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """The body lines inside one lane plate."""
    return "".join(
        text_mark_str(
            x_float,
            y_float + 80 + line_int * 19,
            body_str,
            12,
            chrome.muted_str,
        )
        for line_int, body_str in enumerate(body_tuple)
    )


def _leaf_str(
    leaf_tuple: tuple,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Close a step on its branches, or on its currency."""
    if not leaf_tuple:
        return _chip_str(x_float, y_float, RUPEE_STR, chrome)
    offset_float = 0.0
    part_list = []
    for leaf_str in leaf_tuple:
        part_list.append(
            _chip_str(
                x_float + offset_float,
                y_float,
                leaf_str,
                chrome,
                is_accent_bool=True,
            )
        )
        offset_float += 20.0 + len(leaf_str) * 6.0 + 8.0
    return "".join(part_list)


def _lane_header_str(
    label_str: str,
    lead_str: str,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Name a lane, with its one-line explanation trailing it."""
    return kicker_mark_str(
        x_float, y_float - 52, label_str, chrome.brass_str
    ) + text_mark_str(
        x_float + len(label_str) * 7.4 + 22,
        y_float - 52,
        lead_str,
        11.5,
        chrome.faint_str,
    )


def _personal_route_str(
    route_tuple: tuple,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one investing route as a three-plate lane."""
    label_str, lead_str, step_tuple = route_tuple
    lane_left_float = 176.0
    lane_width_float = (CONTENT_RIGHT_INT - lane_left_float - 48) / 3
    left_list = [
        lane_left_float + index_int * (lane_width_float + 24)
        for index_int in range(3)
    ]
    part_list = [
        _lane_header_str(
            label_str, lead_str, lane_left_float, y_float, chrome
        ),
        line_mark_str(
            left_list[0],
            y_float + 78,
            left_list[-1] + lane_width_float,
            y_float + 78,
            chrome.hairline_str,
            2.0,
        ),
    ]
    part_list.extend(
        chevron_mark_str(
            left_list[index_int] + lane_width_float + 12,
            y_float + 78,
            chrome.brass_str,
            5.0,
        )
        for index_int in range(2)
    )
    part_list.extend(
        _personal_step_str(
            step_tuple[index_int],
            left_list[index_int],
            y_float,
            lane_width_float,
            chrome,
        )
        for index_int in range(len(step_tuple))
    )
    return "".join(part_list)


def _personal_sweep_str(
    left_tuple: tuple,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Route both lanes back to the one account they buy from."""
    centre_float = left_tuple[-1] + width_float / 2
    part_list = [
        path_mark_str(
            f"M{centre_float} 416 V444 Q{centre_float} 458 "
            f"{centre_float - 14} 458 H144 Q130 458 130 472 V914",
            chrome.brass_edge_str,
            1.6,
        ),
        text_mark_str(
            centre_float - 28,
            450,
            "both routes buy from the NRO",
            11.5,
            chrome.brass_str,
            anchor_str=ANCHOR_END_STR,
        ),
    ]
    for tap_y_float in (674.0, 914.0):
        part_list.append(
            line_mark_str(
                130,
                tap_y_float,
                158,
                tap_y_float,
                chrome.brass_edge_str,
                1.6,
            )
        )
        part_list.append(
            chevron_mark_str(
                166, tap_y_float, chrome.brass_str, 5.0
            )
        )
    return "".join(part_list)


def _opening_part_list(
    left_tuple: tuple,
    width_float: float,
    plate_top_float: float,
    plate_height_float: float,
    chrome: ChromeTokens,
) -> list:
    """Title, disclaimer, zone mark and the spine beneath them."""
    return [
        _heading_str(
            "My actual implementation - Japan to India",
            PERSONAL_LEAD_STR,
            chrome,
        ),
        _disclaimer_str(chrome),
        kicker_mark_str(
            MARGIN_INT,
            128,
            PERSONAL_ZONE_KICKER_STR,
            chrome.brass_str,
        ),
        _spine_str(
            plate_top_float + plate_height_float / 2,
            left_tuple,
            width_float,
            chrome,
        ),
    ]


def _stage_row_str(
    left_tuple: tuple,
    width_float: float,
    plate_top_float: float,
    plate_height_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw the five plates that get the money into the account."""
    part_list = []
    for index_int, pair_tuple in enumerate(PERSONAL_STAGE_TUPLE):
        provider_str, stage = pair_tuple
        part_list.append(
            _provider_tile_str(
                provider_str,
                left_tuple[index_int],
                plate_top_float - 58,
                chrome,
            )
        )
        part_list.append(
            _stage_plate_str(
                stage,
                left_tuple[index_int],
                plate_top_float,
                width_float,
                plate_height_float,
                chrome,
            )
        )
    return "".join(part_list)


def build_personal_flow_svg_str(
    is_dark_mode_bool: bool = False,
) -> str:
    """Draw the author's own implementation, providers named.

    The only diagram allowed to name a firm, and it earns that by
    never appearing in the application. Do not add it to
    `money_flow.DIAGRAM_BUILDER_DICT`.

    Arguments:
        is_dark_mode_bool (bool): Draw for a dark surface.

    Returns:
        str: A complete, self-contained SVG document.
    """
    chrome = resolve_chrome(is_dark_mode_bool)
    width_float, left_tuple = _plate_geometry_tuple(
        len(PERSONAL_STAGE_TUPLE)
    )
    plate_top_float, plate_height_float = 216.0, 200.0
    part_list = _opening_part_list(
        left_tuple, width_float, plate_top_float,
        plate_height_float, chrome,
    )
    part_list.append(
        _stage_row_str(
            left_tuple, width_float, plate_top_float,
            plate_height_float, chrome,
        )
    )
    part_list.extend(
        (
            _personal_sweep_str(left_tuple, width_float, chrome),
            _personal_route_str(
                PERSONAL_ROUTE_TUPLE[0], 596.0, chrome
            ),
            _personal_route_str(
                PERSONAL_ROUTE_TUPLE[1], 836.0, chrome
            ),
            _footnote_str(
                1030.0,
                "Named on purpose, and only here",
                PERSONAL_FOOTNOTE_TUPLE,
                chrome,
            ),
        )
    )
    return _document_str(PERSONAL_HEIGHT_INT, chrome, part_list)


# Deliberately its own registry. `money_flow.DIAGRAM_BUILDER_DICT`
# is what the application renders; this is what the export tool
# renders, and keeping them apart is what makes "never in the app"
# a structural fact rather than a promise.
EXPORT_BUILDER_DICT: dict = {
    "personal_implementation": build_personal_flow_svg_str,
}
