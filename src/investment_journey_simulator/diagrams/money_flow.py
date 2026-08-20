"""How the money actually gets from a foreign salary into a holding.

Three views of one process, deliberately separated, because they
answer three different questions and merging them is what made every
previous version of this picture hard to read:

    high level   what shape is this?           six steps, no names
    detailed     what decides each step?       the two real forks
    worked       what does one person do?      an actual path, named

The conceptual move that matters
--------------------------------
A row of boxes joined by arrows shows *sequence*. Sequence was never
the hard part - anyone can guess that money leaves a salary before it
reaches a fund. The three things a reader genuinely cannot guess are:

    1. which side of a border the money is on at each moment,
    2. what currency it is denominated in,
    3. which legal wrapper it has landed in, because that is what
       decides whether it can ever come back out.

So the high-level diagram draws all three at once. A territory band
runs behind the stages and changes colour at the border; a currency
chip under every stage makes the conversion a visible event rather
than a footnote; and the account stage is the one the detail view
then opens up, because NRE versus NRO is the only choice on the whole
path that is expensive to get wrong.

What is deliberately absent
---------------------------
No provider is named anywhere, no tax rate is drawn, and no
repatriation limit appears as a number. The rates and limits are
left out because they change and a number baked into a picture is a
number nobody re-checks. The provider names are left out for a
separate reason, set down in `tests/test_no_product_names.py`: a
name turns a diagram into somebody's advertisement, and it teaches
a reader nothing they could not get from the mechanism.

So the worked example is concrete about everything that is
transferable - the currency, the instrument, the mandate, the
settlement - and silent about the brands, which are the one part a
reader would have to swap out anyway.
"""

from __future__ import annotations

from dataclasses import dataclass

from investment_journey_simulator.design_tokens import (
    ChromeTokens,
    resolve_chrome,
)
from investment_journey_simulator.diagrams.svg_kit import (
    ANCHOR_END_STR,
    ANCHOR_MIDDLE_STR,
    chevron_mark_str,
    icon_mark_str,
    kicker_mark_str,
    line_mark_str,
    open_svg_str,
    path_mark_str,
    rect_mark_str,
    text_mark_str,
)

CANVAS_WIDTH_INT: int = 1640
MARGIN_INT: int = 62
CONTENT_RIGHT_INT: int = CANVAS_WIDTH_INT - MARGIN_INT

HIGH_LEVEL_HEIGHT_INT: int = 700
DETAILED_HEIGHT_INT: int = 970
WORKED_HEIGHT_INT: int = 970

FOREIGN_CURRENCY_STR: str = "local currency"
RUPEE_STR: str = "₹ INR"
YEN_STR: str = "¥ JPY"


@dataclass(frozen=True)
class Stage:
    """One step on the path.

    Arguments:
        kicker_str (str): The numbered section mark above the plate.
        title_str (str): What happens here, in plain words.
        body_tuple (tuple): Pre-split lines. Split here rather than
            wrapped at draw time, because SVG has no line box and a
            measured guess wraps differently in every font.
        icon_str (str): Key into the icon set.
        currency_str (str): What the money is denominated in.
    """

    kicker_str: str
    title_str: str
    body_tuple: tuple
    icon_str: str
    currency_str: str


HIGH_LEVEL_STAGE_TUPLE: tuple = (
    Stage(
        "01 · Earn",
        "Income where you live",
        (
            "Salary or business income,",
            "paid in the local currency.",
        ),
        "coins",
        FOREIGN_CURRENCY_STR,
    ),
    Stage(
        "02 · Receive",
        "Your bank abroad",
        (
            "It lands in the ordinary",
            "account you already use.",
        ),
        "bank",
        FOREIGN_CURRENCY_STR,
    ),
    Stage(
        "03 · Cross",
        "Send it to India",
        (
            "A regulated channel converts",
            "it and carries it across.",
        ),
        "globe",
        "converted here",
    ),
    Stage(
        "04 · Bank",
        "An NRE or NRO account",
        (
            "Which of the two depends on",
            "where the money came from.",
        ),
        "passbook",
        RUPEE_STR,
    ),
    Stage(
        "05 · Access",
        "An investment account",
        (
            "A fund platform, or a broker",
            "together with a demat.",
        ),
        "screen",
        RUPEE_STR,
    ),
    Stage(
        "06 · Hold",
        "Your portfolio",
        (
            "Funds, shares, or whatever",
            "else you chose to hold.",
        ),
        "growth",
        RUPEE_STR,
    ),
)

# What has to already be true before each step will work at all.
# This rail is the part a first-timer needs most and the part every
# version of this diagram left out: the sequence is easy, the
# preconditions are what actually block people for weeks.
PRECONDITION_TUPLE: tuple = (
    ("Nothing", ("No paperwork gates this step.",)),
    ("A local account", ("Opened where you live.",)),
    (
        "Proof of source",
        ("The channel will ask where", "the money came from."),
    ),
    (
        "Your status, declared",
        ("The bank has to be told it", "changed. That duty is yours."),
    ),
    (
        "KYC, done again",
        ("PAN, plus KYC redone under", "your new status."),
    ),
    ("Nothing further", ("Holding is the easy part.",)),
)


HIGH_LEVEL_LEAD_STR: str = (
    "Six steps, one border, one change of currency. No provider "
    "names: implementation examples come later."
)
DETAILED_LEAD_STR: str = (
    "The same six steps, plus the only two choices on the route "
    "that change what you end up with."
)
WORKED_ZONE_KICKER_STR: str = (
    "Steps 1-5 · getting it into the account you invest from"
)
WORKED_LEAD_STR: str = (
    "One person's actual path, described by what each step does "
    "rather than by whose logo is on it."
)

HIGH_LEVEL_FOOTNOTE_TUPLE: tuple = (
    "Eligibility, limits and the paperwork each institution asks "
    "for are revised, sometimes yearly. Confirm anything you are "
    "about to act on with the institution itself.",
)
DETAILED_FOOTNOTE_TUPLE: tuple = (
    "Every figure that would date this picture has been left out "
    "of it. The guide beside it carries the detail, and the guide "
    "can be dated.",
)
WORKED_FOOTNOTE_TUPLE: tuple = (
    "One route that works, not a recommendation and not a "
    "comparison. Providers are deliberately unnamed: the "
    "mechanism is what transfers, and the brand is the part you "
    "would have to swap out anyway.",
)


def _plate_geometry_tuple(count_int: int) -> tuple:
    """Space plates evenly across the content width.

    Brief:
        Returns width and left edges rather than a list of boxes, so
        the same spacing can be reused by the rail underneath and
        the two stay in column no matter how many stages there are.

    Arguments:
        count_int (int): How many plates to fit.

    Returns:
        Tuple: `(width_float, tuple_of_left_edges)`.

    Warning:
        Assumes a fixed gap. Fewer than two plates would divide by
        zero, so it is guarded.
    """
    gap_float = 32.0
    span_float = float(CONTENT_RIGHT_INT - MARGIN_INT)
    if count_int < 2:
        return span_float, (float(MARGIN_INT),)
    width_float = (
        span_float - gap_float * (count_int - 1)
    ) / count_int
    left_tuple = tuple(
        MARGIN_INT + index_int * (width_float + gap_float)
        for index_int in range(count_int)
    )
    return width_float, left_tuple


def _chip_palette_tuple(
    chrome: ChromeTokens,
    is_accent_bool: bool,
) -> tuple:
    """Pick a chip's three colours.

    Brief:
        Brass marks the one moment on the path that costs money and
        attention - the currency conversion. Verdigris marks every
        step that is merely somewhere the money is sitting.

    Arguments:
        chrome (ChromeTokens): Surface tokens.
        is_accent_bool (bool): Draw in brass rather than verdigris.

    Returns:
        Tuple: `(fill, edge, ink)`.
    """
    if is_accent_bool:
        return (
            chrome.brass_wash_str,
            chrome.brass_edge_str,
            chrome.brass_str,
        )
    return (
        chrome.verdigris_wash_str,
        chrome.verdigris_edge_str,
        chrome.verdigris_str,
    )


def _chip_str(
    x_float: float,
    y_float: float,
    body_str: str,
    chrome: ChromeTokens,
    is_accent_bool: bool = False,
) -> str:
    """Draw a small labelled chip.

    Brief:
        Width is derived from the character count rather than
        measured, which is why the type inside is set small and
        the padding generous: an estimate that is a little wide
        looks deliberate, and one that is too narrow looks broken.

    Arguments:
        x_float (float): Left edge.
        y_float (float): Top edge.
        body_str (str): Chip text.
        chrome (ChromeTokens): Surface tokens.
        is_accent_bool (bool): Draw in brass rather than verdigris.

    Returns:
        str: The chip's elements.
    """
    fill_str, edge_str, ink_str = _chip_palette_tuple(
        chrome, is_accent_bool
    )
    width_float = 20.0 + len(body_str) * 6.0
    return rect_mark_str(
        x_float, y_float, width_float, 22, fill_str, edge_str, 2
    ) + text_mark_str(
        x_float + 10,
        y_float + 15,
        body_str,
        11,
        ink_str,
        weight_int=650,
        tracking_float=0.2,
    )


def _document_str(
    height_int: int,
    chrome: ChromeTokens,
    part_list: list,
) -> str:
    """Wrap drawn parts in a root element on a painted ground.

    Brief:
        The ground is `canvas_str`, which is deliberately a shade
        deeper than the page the diagram lands on. That makes the
        picture read as an inset plate rather than as loose marks
        floating on the page.

    Arguments:
        height_int (int): Design height in user units.
        chrome (ChromeTokens): Surface tokens.
        part_list (list): Drawn fragments, in paint order.

    Returns:
        str: A complete SVG document.
    """
    ground_str = rect_mark_str(
        0,
        0,
        CANVAS_WIDTH_INT,
        height_int,
        chrome.canvas_str,
        radius_int=0,
    )
    body_str = "".join(part_list)
    return (
        f"{open_svg_str(CANVAS_WIDTH_INT, height_int)}"
        f"{ground_str}{body_str}</svg>"
    )


def _column_rail_str(
    top_float: float,
    kicker_str: str,
    item_tuple: tuple,
    left_tuple: tuple,
    chrome: ChromeTokens,
) -> str:
    """Draw a ruled rail of short notes, one per column.

    Brief:
        Used twice - for what must be true before each step, and
        for what governs the route as a whole. Sharing it is what
        keeps the two rails in the same rhythm.

    Arguments:
        top_float (float): Height of the rule above the rail.
        kicker_str (str): Section mark for the rail.
        item_tuple (tuple): `(head, lines)` per column.
        left_tuple (tuple): Left edge of each column.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The rail's elements.

    Warning:
        Draws as many columns as it has items, so the item count
        and the column count must already agree.
    """
    part_list = [
        line_mark_str(
            MARGIN_INT,
            top_float,
            CONTENT_RIGHT_INT,
            top_float,
            chrome.hairline_str,
            1.0,
        ),
        kicker_mark_str(
            MARGIN_INT, top_float + 26, kicker_str, chrome.brass_str
        ),
    ]
    part_list.extend(
        _rail_column_str(
            item_pair, left_tuple[index_int], top_float, chrome
        )
        for index_int, item_pair in enumerate(item_tuple)
    )
    return "".join(part_list)


def _rail_column_str(
    item_pair: tuple,
    x_float: float,
    top_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one column of a rail: a head and its lines.

    Arguments:
        item_pair (tuple): `(head, lines)`.
        x_float (float): Left edge of the column.
        top_float (float): Height of the rail's rule.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The column's text elements.
    """
    head_str, line_tuple = item_pair
    part_list = [
        text_mark_str(
            x_float,
            top_float + 56,
            head_str,
            13,
            chrome.ink_soft_str,
            weight_int=650,
        )
    ]
    part_list.extend(
        text_mark_str(
            x_float,
            top_float + 77 + line_int * 18,
            body_str,
            11.5,
            chrome.faint_str,
        )
        for line_int, body_str in enumerate(line_tuple)
    )
    return "".join(part_list)


def _heading_str(
    title_str: str,
    lead_str: str,
    chrome: ChromeTokens,
) -> str:
    """Draw the title block every diagram opens with."""
    return text_mark_str(
        MARGIN_INT,
        62,
        title_str,
        31,
        chrome.ink_str,
        weight_int=700,
        tracking_float=-0.6,
    ) + text_mark_str(
        MARGIN_INT, 93, lead_str, 15, chrome.muted_str
    )


def _footnote_str(
    y_float: float,
    label_str: str,
    line_tuple: tuple,
    chrome: ChromeTokens,
) -> str:
    """Draw the closing note, as a ruled block rather than a bar.

    Brief:
        The predecessor drew this as a filled dark pill, which reads
        as a banner ad. A rule and a brass label reads as a footnote
        in a document, which is what it is.
    """
    part_list = [
        line_mark_str(
            MARGIN_INT,
            y_float,
            CONTENT_RIGHT_INT,
            y_float,
            chrome.hairline_str,
            1.0,
        ),
        kicker_mark_str(
            MARGIN_INT, y_float + 26, label_str, chrome.brass_str
        ),
    ]
    part_list.extend(
        text_mark_str(
            MARGIN_INT,
            y_float + 48 + index_int * 20,
            body_str,
            12.5,
            chrome.muted_str,
        )
        for index_int, body_str in enumerate(line_tuple)
    )
    return "".join(part_list)


def _spine_str(
    y_float: float,
    left_tuple: tuple,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw the continuous rule the plates sit on.

    Brief:
        One line from the first plate to the last, drawn *before*
        the plates so it is occluded by them and shows only in the
        gaps. That is what makes six plates read as one path rather
        than six things with arrows between them.

    Arguments:
        y_float (float): Height of the rule.
        left_tuple (tuple): Left edge of every plate.
        width_float (float): Plate width.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The rule and its direction chevrons.
    """
    part_list = [
        line_mark_str(
            left_tuple[0],
            y_float,
            left_tuple[-1] + width_float,
            y_float,
            chrome.hairline_str,
            2.0,
        )
    ]
    part_list.extend(
        chevron_mark_str(
            (
                left_tuple[index_int] + width_float
                + left_tuple[index_int + 1]
            )
            / 2,
            y_float,
            chrome.brass_str,
            5.0,
        )
        for index_int in range(len(left_tuple) - 1)
    )
    return "".join(part_list)


def _stage_copy_str(
    stage: Stage,
    x_float: float,
    plate_top_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw a stage's title and body lines.

    Arguments:
        stage (Stage): Stage being drawn.
        x_float (float): Left edge of the text column.
        plate_top_float (float): Top of the plate the text sits in.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The text elements.
    """
    part_list = [
        text_mark_str(
            x_float,
            plate_top_float + 84,
            stage.title_str,
            16.5,
            chrome.ink_str,
            weight_int=680,
            tracking_float=-0.2,
        )
    ]
    part_list.extend(
        text_mark_str(
            x_float,
            plate_top_float + 110 + index_int * 19,
            body_str,
            12.5,
            chrome.muted_str,
        )
        for index_int, body_str in enumerate(stage.body_tuple)
    )
    return "".join(part_list)


def _stage_plate_str(
    stage: Stage,
    x_float: float,
    y_float: float,
    width_float: float,
    height_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one stage: mark above the plate, content inside it."""
    part_list = [
        kicker_mark_str(
            x_float, y_float - 16, stage.kicker_str, chrome.brass_str
        ),
        rect_mark_str(
            x_float,
            y_float,
            width_float,
            height_float,
            chrome.plate_str,
            chrome.hairline_str,
        ),
        icon_mark_str(
            stage.icon_str,
            x_float + 22,
            y_float + 24,
            chrome.verdigris_str,
        ),
    ]
    part_list.append(
        _stage_copy_str(stage, x_float + 22, y_float, chrome)
    )
    part_list.append(
        _currency_chip_str(
            stage, x_float + 22, y_float + height_float - 44, chrome
        )
    )
    return "".join(part_list)


def _currency_chip_str(
    stage: Stage,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw a stage's currency chip in the right colour.

    Brief:
        A chip reading anything other than a settled currency means
        the money is mid-conversion, and that is the one moment on
        the path worth an accent. Deciding it here rather than at
        each call site is what keeps all three diagrams agreeing.

    Arguments:
        stage (Stage): Stage owning the chip.
        x_float (float): Left edge.
        y_float (float): Top edge.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The chip's elements.
    """
    is_settled_bool = stage.currency_str in (
        RUPEE_STR,
        YEN_STR,
        FOREIGN_CURRENCY_STR,
    )
    return _chip_str(
        x_float,
        y_float,
        stage.currency_str,
        chrome,
        is_accent_bool=not is_settled_bool,
    )


TERRITORY_TOP_FLOAT: float = 112.0


def _territory_region_tuple(
    cross_start_float: float,
    cross_end_float: float,
    chrome: ChromeTokens,
) -> tuple:
    """Describe the three territories, left to right.

    Brief:
        Data rather than drawing, so the regions can be asserted by
        a test without rendering anything.

    Arguments:
        cross_start_float (float): Where leaving home begins.
        cross_end_float (float): Where arriving in India begins.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        Tuple: `(start, end, fill, label, ink)` for each region.
    """
    return (
        (
            MARGIN_INT - 22,
            cross_start_float,
            chrome.sunk_str,
            "Outside India",
            chrome.muted_str,
        ),
        (
            cross_start_float,
            cross_end_float,
            chrome.brass_wash_str,
            "The crossing",
            chrome.brass_str,
        ),
        (
            cross_end_float,
            CONTENT_RIGHT_INT + 22,
            chrome.verdigris_wash_str,
            "Inside India",
            chrome.verdigris_str,
        ),
    )


def _territory_band_str(
    region_tuple: tuple,
    top_float: float,
    bottom_float: float,
) -> str:
    """Draw one territory as a tinted band with a label.

    Arguments:
        region_tuple (tuple): One row from the region table.
        top_float (float): Top of the band.
        bottom_float (float): Bottom of the band.

    Returns:
        str: The band and its label.
    """
    start_float, end_float, fill_str, label_str, ink_str = (
        region_tuple
    )
    return rect_mark_str(
        start_float,
        top_float,
        end_float - start_float,
        bottom_float - top_float,
        fill_str,
        "none",
        2,
        opacity_float=0.75,
    ) + kicker_mark_str(
        start_float + 16, top_float + 24, label_str, ink_str
    )


def _territory_str(
    left_tuple: tuple,
    chrome: ChromeTokens,
) -> str:
    """Draw the three territories the money passes through.

    The device that turns a sequence into a map: a reader sees,
    before reading a word, that only step three crosses anything.
    The band label sits above the stage marks, never beside them,
    or the two collide into one run of small caps.
    """
    top_float, bottom_float = TERRITORY_TOP_FLOAT, 444.0
    cross_start_float = left_tuple[2] - 22
    cross_end_float = left_tuple[3] - 10
    part_list = [
        _territory_band_str(region, top_float, bottom_float)
        for region in _territory_region_tuple(
            cross_start_float, cross_end_float, chrome
        )
    ]
    part_list.extend(
        line_mark_str(
            divider_float,
            top_float,
            divider_float,
            bottom_float,
            chrome.brass_edge_str,
            1.4,
            dash_str="5 5",
        )
        for divider_float in (cross_start_float, cross_end_float)
    )
    part_list.append(
        text_mark_str(
            (cross_start_float + cross_end_float) / 2,
            bottom_float - 14,
            "the currency changes here",
            12,
            chrome.brass_str,
            anchor_str=ANCHOR_MIDDLE_STR,
            opacity_float=0.9,
        )
    )
    return "".join(part_list)


def _stage_row_str(
    stage_tuple: tuple,
    left_tuple: tuple,
    width_float: float,
    top_float: float,
    height_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw a spine and the full-size stage plates sitting on it."""
    part_list = [
        _spine_str(
            top_float + height_float / 2,
            left_tuple,
            width_float,
            chrome,
        )
    ]
    part_list.extend(
        _stage_plate_str(
            stage,
            left_tuple[index_int],
            top_float,
            width_float,
            height_float,
            chrome,
        )
        for index_int, stage in enumerate(stage_tuple)
    )
    return "".join(part_list)


def build_high_level_svg_str(is_dark_mode_bool: bool = False) -> str:
    """Draw the generic six-step flow.

    Names no bank, no provider and no country of origin, so it
    stays true for a reader in Osaka, Dubai or Toronto. Nothing
    here may ever gain a provider name, or it stops describing the
    process and starts describing one implementation of it.

    Arguments:
        is_dark_mode_bool (bool): Draw for a dark surface.

    Returns:
        str: A complete, self-contained SVG document.
    """
    chrome = resolve_chrome(is_dark_mode_bool)
    width_float, left_tuple = _plate_geometry_tuple(
        len(HIGH_LEVEL_STAGE_TUPLE)
    )
    plate_top_float, plate_height_float = 188.0, 232.0
    part_list = [
        _heading_str(
            "How the money moves", HIGH_LEVEL_LEAD_STR, chrome
        ),
        _territory_str(left_tuple, chrome),
        _stage_row_str(
            HIGH_LEVEL_STAGE_TUPLE,
            left_tuple,
            width_float,
            plate_top_float,
            plate_height_float,
            chrome,
        ),
        _column_rail_str(
            496.0,
            "What has to be true before the step works",
            PRECONDITION_TUPLE,
            left_tuple,
            chrome,
        ),
        _footnote_str(
            616.0,
            "Read this as a shape, not as a rulebook",
            HIGH_LEVEL_FOOTNOTE_TUPLE,
            chrome,
        ),
    ]
    return _document_str(HIGH_LEVEL_HEIGHT_INT, chrome, part_list)


# ------------------------------------------------------------------
# The detailed view: the two forks that actually decide the outcome.
# ------------------------------------------------------------------
FORK_ACCOUNT_TUPLE: tuple = (
    (
        "NRE",
        "The foreign-earnings account",
        (
            ("Funded by", "Money you earned abroad"),
            ("Taking it back out", "Freely, principal and interest"),
            ("Interest taxed in India", "No"),
        ),
    ),
    (
        "NRO",
        "The India-arising account",
        (
            ("Funded by", "Rent, dividends, an old salary"),
            ("Taking it back out", "Capped, and with paperwork"),
            ("Interest taxed in India", "Yes, deducted at source"),
        ),
    ),
)

FORK_ROUTE_TUPLE: tuple = (
    (
        "Funds",
        "The mutual fund route",
        (
            ("What you need", "A fund platform, or the AMC"),
            ("How money moves", "A standing mandate, or one-off"),
            ("What you hold", "Units, recorded by the registrar"),
        ),
    ),
    (
        "Equity",
        "The direct equity route",
        (
            ("What you need", "A broker, plus a demat account"),
            ("How money moves", "Transfer, then a delivery order"),
            ("What you hold", "Shares in demat, settled next day"),
        ),
    ),
)

GOVERNS_TUPLE: tuple = (
    (
        "Your residential status",
        (
            "Decided by day-count rules, not by",
            "intention or by when you told anyone.",
        ),
    ),
    (
        "Where the money arose",
        (
            "Foreign earnings and India-arising",
            "income cannot share one account.",
        ),
    ),
    (
        "KYC, done a second time",
        (
            "Status has to change at the bank, the",
            "registrar and the broker separately.",
        ),
    ),
    (
        "The rules on the day",
        (
            "Caps and eligibility get revised.",
            "Check before you act, not after.",
        ),
    ),
)


def _fork_badge_str(
    badge_str: str,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw the small brass tag that names a fork option."""
    return rect_mark_str(
        x_float,
        y_float,
        22 + len(badge_str) * 8.4,
        22,
        chrome.brass_wash_str,
        chrome.brass_edge_str,
        2,
    ) + text_mark_str(
        x_float + 11,
        y_float + 15,
        badge_str,
        11.5,
        chrome.brass_str,
        weight_int=700,
        tracking_float=0.6,
    )


def _fork_option_str(
    badge_str: str,
    title_str: str,
    row_tuple: tuple,
    x_float: float,
    y_float: float,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one side of a fork as a small ruled comparison."""
    part_list = [
        rect_mark_str(
            x_float,
            y_float,
            width_float,
            216,
            chrome.plate_str,
            chrome.hairline_str,
        ),
        _fork_badge_str(
            badge_str, x_float + 18, y_float + 18, chrome
        ),
        text_mark_str(
            x_float + 18,
            y_float + 66,
            title_str,
            15,
            chrome.ink_str,
            weight_int=670,
        ),
    ]
    part_list.extend(
        _fork_row_str(
            row_pair,
            x_float,
            y_float + 92 + index_int * 44,
            width_float,
            chrome,
        )
        for index_int, row_pair in enumerate(row_tuple)
    )
    return "".join(part_list)


def _fork_row_str(
    row_pair: tuple,
    x_float: float,
    row_y_float: float,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one labelled row of a fork comparison.

    Label above value, not beside it: these values are short
    sentences rather than figures, and a two-column layout would
    wrap each of them at a different point.
    """
    label_str, value_str = row_pair
    return (
        line_mark_str(
            x_float + 18,
            row_y_float - 8,
            x_float + width_float - 18,
            row_y_float - 8,
            chrome.hairline_soft_str,
            1.0,
        )
        + text_mark_str(
            x_float + 18,
            row_y_float + 8,
            label_str,
            10,
            chrome.faint_str,
            weight_int=650,
            tracking_float=0.8,
        )
        + text_mark_str(
            x_float + 18,
            row_y_float + 27,
            value_str,
            12.5,
            chrome.ink_soft_str,
        )
    )


def _fork_panel_str(
    title_str: str,
    lead_str: str,
    option_tuple: tuple,
    x_float: float,
    y_float: float,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw a labelled zone holding one fork's two options."""
    option_width_float = (width_float - 68) / 2
    part_list = [
        rect_mark_str(
            x_float,
            y_float,
            width_float,
            320,
            chrome.sunk_str,
            chrome.hairline_str,
        ),
        text_mark_str(
            x_float + 24,
            y_float + 38,
            title_str,
            16.5,
            chrome.ink_str,
            weight_int=680,
        ),
        text_mark_str(
            x_float + 24, y_float + 60, lead_str, 12.5,
            chrome.muted_str,
        ),
    ]
    part_list.extend(
        _fork_option_str(
            option[0],
            option[1],
            option[2],
            x_float + 24 + index_int * (option_width_float + 20),
            y_float + 78,
            option_width_float,
            chrome,
        )
        for index_int, option in enumerate(option_tuple)
    )
    return "".join(part_list)


def build_detailed_svg_str(is_dark_mode_bool: bool = False) -> str:
    """Draw the mechanism: the path, then the two real decisions.

    Brief:
        Not a bigger flowchart. A branching graph of every path
        would be complete and unreadable; only two choices change
        the outcome, so those two get a comparison each.

    Arguments:
        is_dark_mode_bool (bool): Draw for a dark surface.

    Returns:
        str: A complete, self-contained SVG document.

    Warning:
        The rows carry no rates and no limits. A number here would
        be stale within a budget cycle, and nobody re-reads a
        picture.
    """
    chrome = resolve_chrome(is_dark_mode_bool)
    width_float, left_tuple = _plate_geometry_tuple(
        len(HIGH_LEVEL_STAGE_TUPLE)
    )
    part_list = [
        _heading_str(
            "How the money moves - the mechanism",
            DETAILED_LEAD_STR,
            chrome,
        ),
        kicker_mark_str(
            MARGIN_INT, 138, "The path", chrome.brass_str
        ),
        _compact_path_str(left_tuple, width_float, chrome),
        _fork_bracket_str(left_tuple, width_float, chrome),
        _fork_zone_str(chrome),
        _column_rail_str(
            750.0,
            "What governs the whole route",
            GOVERNS_TUPLE,
            _plate_geometry_tuple(len(GOVERNS_TUPLE))[1],
            chrome,
        ),
        _footnote_str(
            872.0,
            "Shape only - no rates, no limits, on purpose",
            DETAILED_FOOTNOTE_TUPLE,
            chrome,
        ),
    ]
    return _document_str(DETAILED_HEIGHT_INT, chrome, part_list)


COMPACT_PLATE_TOP_FLOAT: float = 172.0
COMPACT_PLATE_HEIGHT_FLOAT: float = 150.0


def _compact_stage_str(
    stage: Stage,
    x_float: float,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one stage in the detail view's shorter plate.

    The mark goes inside the plate rather than above it: the
    detail view needs the room below it for the forks.
    """
    top_float = COMPACT_PLATE_TOP_FLOAT
    return (
        rect_mark_str(
            x_float,
            top_float,
            width_float,
            COMPACT_PLATE_HEIGHT_FLOAT,
            chrome.plate_str,
            chrome.hairline_str,
        )
        + text_mark_str(
            x_float + 18,
            top_float + 28,
            stage.kicker_str.upper(),
            10,
            chrome.brass_str,
            weight_int=700,
            tracking_float=1.5,
        )
        + _compact_copy_str(stage, x_float + 18, chrome)
        + _currency_chip_str(
            stage,
            x_float + 18,
            top_float + COMPACT_PLATE_HEIGHT_FLOAT - 34,
            chrome,
        )
    )


def _compact_copy_str(
    stage: Stage,
    x_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw a compact stage's title and body lines."""
    top_float = COMPACT_PLATE_TOP_FLOAT
    part_list = [
        text_mark_str(
            x_float,
            top_float + 54,
            stage.title_str,
            14.5,
            chrome.ink_str,
            weight_int=670,
        )
    ]
    part_list.extend(
        text_mark_str(
            x_float,
            top_float + 76 + line_int * 17,
            body_str,
            11.5,
            chrome.muted_str,
        )
        for line_int, body_str in enumerate(stage.body_tuple)
    )
    return "".join(part_list)


def _compact_path_str(
    left_tuple: tuple,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw the six-stage spine in its compact form.

    Arguments:
        left_tuple (tuple): Left edge of each plate.
        width_float (float): Plate width.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The spine and every plate on it.
    """
    part_list = [
        _spine_str(
            COMPACT_PLATE_TOP_FLOAT
            + COMPACT_PLATE_HEIGHT_FLOAT / 2,
            left_tuple,
            width_float,
            chrome,
        )
    ]
    part_list.extend(
        _compact_stage_str(
            stage, left_tuple[index_int], width_float, chrome
        )
        for index_int, stage in enumerate(HIGH_LEVEL_STAGE_TUPLE)
    )
    return "".join(part_list)


def _fork_bracket_str(
    left_tuple: tuple,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Tie the account plate to the forks that open it up.

    Brief:
        Drawn rather than left to be inferred. Without the bracket
        a reader has to work out for themselves which of the six
        plates the comparison below belongs to, and most will not.

    Arguments:
        left_tuple (tuple): Left edge of each plate.
        width_float (float): Plate width.
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: One routed path.
    """
    centre_float = left_tuple[3] + width_float / 2
    return path_mark_str(
        f"M{centre_float} "
        f"{COMPACT_PLATE_TOP_FLOAT + COMPACT_PLATE_HEIGHT_FLOAT} "
        f"V352 Q{centre_float} 366 {centre_float - 14} 366 "
        f"H446 Q432 366 432 380 V396",
        chrome.brass_edge_str,
        1.6,
    )


def _fork_zone_str(chrome: ChromeTokens) -> str:
    """Draw the two fork panels side by side.

    Arguments:
        chrome (ChromeTokens): Surface tokens.

    Returns:
        str: The zone mark and both panels.
    """
    panel_width_float = (CONTENT_RIGHT_INT - MARGIN_INT - 36) / 2
    return (
        kicker_mark_str(
            MARGIN_INT,
            374,
            "Two decisions that change the outcome",
            chrome.brass_str,
        )
        + _fork_panel_str(
            "Which account receives it",
            "Decided by where the money arose, not by preference. "
            "Most people end up needing both.",
            FORK_ACCOUNT_TUPLE,
            MARGIN_INT,
            396,
            panel_width_float,
            chrome,
        )
        + _fork_panel_str(
            "How you actually buy",
            "Both start from the same rupee balance. They differ "
            "in what you need open first.",
            FORK_ROUTE_TUPLE,
            MARGIN_INT + panel_width_float + 36,
            396,
            panel_width_float,
            chrome,
        )
    )



# ------------------------------------------------------------------
# The worked example: one real path, named, and labelled as one.
# ------------------------------------------------------------------
WORKED_STAGE_TUPLE: tuple = (
    Stage(
        "01 · Earn",
        "Salary in Japan",
        ("Employment income, paid monthly", "in yen."),
        "coins",
        YEN_STR,
    ),
    Stage(
        "02 · Receive",
        "Japanese bank account",
        ("The salary is credited to the", "local account."),
        "bank",
        YEN_STR,
    ),
    Stage(
        "03 · Cross",
        "A remittance provider",
        ("Converts yen to rupees and sends", "it on, with a paper trail."),
        "globe",
        "yen to rupees",
    ),
    Stage(
        "04 · Land",
        "NRE account in India",
        (
            "Where the remittance is credited.",
            "Foreign earnings, so this one.",
        ),
        "passbook",
        RUPEE_STR,
    ),
    # Sequential, not an alternative. Both accounts exist, and in
    # this person's setup money arrives in the NRE and is then
    # moved across before anything is bought. Drawing the two as a
    # fork would describe a different arrangement from the one this
    # example is documenting.
    Stage(
        "05 · Move",
        "NRO account, then invest",
        (
            "Moved across from the NRE, and",
            "everything below buys from here.",
        ),
        "bank",
        RUPEE_STR,
    ),
)

# Each step is (title, body lines, icon, leaf chips). The leaves
# exist because the reference flow ends in a fan rather than a
# point: the fund route arrives at units that can be bought two
# different ways, and drawing that as one box would lose the only
# branch at the end of the whole picture.
WORKED_ROUTE_TUPLE: tuple = (
    (
        "Route A · mutual funds",
        "a mandate does the work each month",
        (
            (
                "A mandate on the fund platform",
                (
                    "An eNACH mandate pulls the agreed amount",
                    "on the same day every month.",
                ),
                "repeat",
                (),
            ),
            (
                "Mutual fund units",
                (
                    "Bought at the applicable NAV, held in a",
                    "folio or in demat - the platform decides.",
                ),
                "screen",
                (),
            ),
            (
                "Two ways money goes in",
                (
                    "The mandate every month, and a one-off",
                    "whenever there is something spare.",
                ),
                "growth",
                ("SIP · monthly", "Lump sum · ad hoc"),
            ),
        ),
    ),
    (
        "Route B · direct equity",
        "each purchase is a decision you make",
        (
            (
                "Money moved to the broker",
                (
                    "Transferred from the account to the broker",
                    "before any order can be placed.",
                ),
                "screen",
                (),
            ),
            (
                "Order placed as CNC delivery",
                (
                    "Delivery rather than intraday, because the",
                    "intent is to hold it.",
                ),
                "coins",
                (),
            ),
            (
                "Shares in demat",
                (
                    "Settles the next working day and appears",
                    "in the demat holding.",
                ),
                "growth",
                ("T+1 · settled",),
            ),
        ),
    ),
)


def _lane_header_str(
    label_str: str,
    lead_str: str,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Name a lane, with its one-line explanation trailing it."""
    return kicker_mark_str(
        x_float, y_float - 16, label_str, chrome.brass_str
    ) + text_mark_str(
        x_float + len(label_str) * 7.4 + 22,
        y_float - 16,
        lead_str,
        11.5,
        chrome.faint_str,
    )


def _worked_route_str(
    route_tuple: tuple,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one investing route as a three-plate lane."""
    label_str, lead_str, step_tuple = route_tuple
    lane_left_float = 176.0
    lane_width_float = (
        CONTENT_RIGHT_INT - lane_left_float - 48
    ) / 3
    part_list = [
        _lane_header_str(
            label_str, lead_str, lane_left_float, y_float, chrome
        )
    ]
    left_list = [
        lane_left_float + index_int * (lane_width_float + 24)
        for index_int in range(3)
    ]
    part_list.append(
        line_mark_str(
            left_list[0],
            y_float + 80,
            left_list[-1] + lane_width_float,
            y_float + 80,
            chrome.hairline_str,
            2.0,
        )
    )
    part_list.extend(
        chevron_mark_str(
            left_list[index_int] + lane_width_float + 12,
            y_float + 80,
            chrome.brass_str,
            5.0,
        )
        for index_int in range(2)
    )
    part_list.extend(
        _worked_step_str(
            step, left_list[index_int], y_float, lane_width_float,
            chrome,
        )
        for index_int, step in enumerate(step_tuple)
    )
    return "".join(part_list)


def _worked_step_str(
    step_tuple: tuple,
    x_float: float,
    y_float: float,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw one plate in an investing lane."""
    title_str, body_line_tuple, icon_str, leaf_tuple = step_tuple
    part_list = [
        rect_mark_str(
            x_float,
            y_float,
            width_float,
            160,
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
    part_list.extend(
        text_mark_str(
            x_float + 20,
            y_float + 82 + line_int * 19,
            body_str,
            12,
            chrome.muted_str,
        )
        for line_int, body_str in enumerate(body_line_tuple)
    )
    part_list.append(
        _leaf_chip_str(leaf_tuple, x_float + 20, y_float + 124,
                       chrome)
    )
    return "".join(part_list)


def _leaf_chip_str(
    leaf_tuple: tuple,
    x_float: float,
    y_float: float,
    chrome: ChromeTokens,
) -> str:
    """Draw a step's closing chips.

    A step with no leaves closes on the currency, because that is
    still the useful thing to say. A step that fans out closes on
    its branches instead, drawn in brass so the fan reads as the
    end of the path rather than as more of it.
    """
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


def build_worked_example_svg_str(
    is_dark_mode_bool: bool = False,
) -> str:
    """Draw one person's actual path, providers and all.

    The only diagram here allowed to name anything. It earns that
    by saying on its face that it is one path among many. Naming a
    provider is not a recommendation, and this must not be lifted
    into the guide as though it were the process itself.

    Arguments:
        is_dark_mode_bool (bool): Draw for a dark surface.

    Returns:
        str: A complete, self-contained SVG document.
    """
    chrome = resolve_chrome(is_dark_mode_bool)
    width_float, left_tuple = _plate_geometry_tuple(
        len(WORKED_STAGE_TUPLE)
    )
    plate_top_float, plate_height_float = 188.0, 200.0

    part_list = [
        _heading_str(
            "A worked example - Japan to India",
            WORKED_LEAD_STR,
            chrome,
        ),
        kicker_mark_str(
            MARGIN_INT, 138, WORKED_ZONE_KICKER_STR, chrome.brass_str
        ),
        _stage_row_str(
            WORKED_STAGE_TUPLE,
            left_tuple,
            width_float,
            plate_top_float,
            plate_height_float,
            chrome,
        ),
        _worked_sweep_str(left_tuple, width_float, chrome),
        _worked_route_str(WORKED_ROUTE_TUPLE[0], 472.0, chrome),
        _worked_route_str(WORKED_ROUTE_TUPLE[1], 690.0, chrome),
        _footnote_str(
            886.0,
            "One path, not the path",
            WORKED_FOOTNOTE_TUPLE,
            chrome,
        ),
    ]
    return _document_str(WORKED_HEIGHT_INT, chrome, part_list)


ROUTE_TAP_Y_TUPLE: tuple = (552.0, 770.0)


def _worked_sweep_str(
    left_tuple: tuple,
    width_float: float,
    chrome: ChromeTokens,
) -> str:
    """Route both investing lanes back to the one account.

    Both routes leave the same rupee balance, so the drawing
    carries one rule down and back across rather than restating
    the account above each lane. Restating it is how the previous
    diagram ended up implying two separate accounts.
    """
    centre_float = left_tuple[-1] + width_float / 2
    part_list = [
        path_mark_str(
            f"M{centre_float} 388 "
            f"V416 Q{centre_float} 430 {centre_float - 14} 430 "
            f"H144 Q130 430 130 444 V770",
            chrome.brass_edge_str,
            1.6,
        ),
        text_mark_str(
            centre_float - 28,
            422,
            "both routes start here",
            11.5,
            chrome.brass_str,
            anchor_str=ANCHOR_END_STR,
        ),
    ]
    for tap_y_float in ROUTE_TAP_Y_TUPLE:
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


DIAGRAM_BUILDER_DICT: dict = {
    "high_level": build_high_level_svg_str,
    "detailed": build_detailed_svg_str,
    "worked_example": build_worked_example_svg_str,
}
