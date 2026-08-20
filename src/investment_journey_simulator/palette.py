"""Colour tokens for every figure the dashboard draws.

Two separate jobs, kept apart on purpose:

*Status* colours carry meaning (gain, loss, tax, rebalance, pause).
They are reserved and never reused to identify a fund.

*Categorical* colours carry identity only. They are assigned to a
fund by name, never by position, so removing one fund from a plan
cannot repaint the funds that remain.

Both sets were validated by computation rather than by eye, against
the six checks in the data-visualisation guidance: OKLCH lightness
band, OKLCH chroma floor, OKLab colour-vision-deficiency separation
under the Machado-Oliveira-Fernandes protanopia and deuteranopia
transforms, the normal-vision separation floor, and WCAG contrast
against the chart surface. Measured worst cases, all pairs:

    light   CVD dE 10.3   normal dE 15.8   contrast all >= 3:1
    dark    CVD dE  9.4   normal dE 16.6   contrast all >= 3:1

Six distinct fund colours in light mode and five in dark is the
ceiling, not a stylistic choice: exhaustive search over a
twenty-seven colour pool found no seven-colour set that clears the
same gates. Beyond the ceiling the palette repeats, so charts of
more funds than that need direct labels to stay readable.

Never add a colour here without re-running the validator.

Three rules of use, which no validator can check
------------------------------------------------
A palette that measures well can still be applied badly, and these
are the three ways a financial chart usually goes wrong.

*No Christmas tree.* Red and green mean a number moved, and nothing
else. They are never a fill, never a background, never decoration.
This one is enforced: the status colours above are reserved, and
`test_status_colours_are_never_used_for_identity` fails if any of
them is ever handed out as a fund's identity.

*Baselines are grey, not coloured.* The moment a chart overlays a
reference trajectory against something the reader is experimenting
with - a "before" line, an inflation-adjusted twin, a do-nothing
case - the reference takes a neutral grey and the experiment keeps
the colour. `INVESTED_COLOUR_STR` is that grey. Giving both a hue
makes the reader work out which one is theirs.

*Dense paths are drawn at low opacity.* A chart with a hundred
simulated futures on it is a density map, not a hundred lines: draw
them at 10 to 15 percent and the shape of the distribution appears
by itself. `DENSE_PATH_OPACITY_FLOAT` is that value. Nothing in this
program draws such a chart today; the constant and this note exist
so that whoever adds one does not have to rediscover the number.
"""

from __future__ import annotations

# ------------------------------------------------------------------
# Status colours. Reserved: never used to identify a fund.
# ------------------------------------------------------------------
GAIN_COLOUR_STR: str = "#2E7D32"
LOSS_COLOUR_STR: str = "#C62828"
REBALANCE_COLOUR_STR: str = "#6A1B9A"
PAUSE_COLOUR_STR: str = "#9E9E9E"
TAX_COLOUR_STR: str = "#B45309"

# ------------------------------------------------------------------
# Named portfolio series. Fixed, so the same concept is the same
# colour in every figure and in the exports.
# ------------------------------------------------------------------
PORTFOLIO_VALUE_COLOUR_STR: str = "#0F766E"
INVESTED_COLOUR_STR: str = "#5B677A"
MONTHLY_SIP_COLOUR_STR: str = "#2563EB"
WITHDRAWAL_COLOUR_STR: str = LOSS_COLOUR_STR
TARGET_LINE_COLOUR_STR: str = "#12304A"

# ------------------------------------------------------------------
# Categorical fund identity, in fixed order.
# ------------------------------------------------------------------
LIGHT_FUND_COLOUR_TUPLE: tuple = (
    "#2563EB",
    "#D97706",
    "#0891B2",
    "#DB2777",
    "#5B21B6",
    "#92400E",
)
DARK_FUND_COLOUR_TUPLE: tuple = (
    "#4A8BF7",
    "#D97706",
    "#0D9488",
    "#E11D48",
    "#7C3AED",
)

# Opacity for a chart that draws many overlapping simulated paths.
# See the third rule of use in the module docstring.
DENSE_PATH_OPACITY_FLOAT: float = 0.12

# ------------------------------------------------------------------
# Redundant encodings, so meaning never rests on colour alone.
# ------------------------------------------------------------------
# Seven patterns against six colours on purpose: the counts are
# coprime, so a plan that runs past the colour ceiling reuses a hue
# with a different line style rather than repeating both at once.
# The last entry is an explicit dash array because Plotly ships only
# six named patterns.
FUND_DASH_PATTERN_TUPLE: tuple = (
    "solid",
    "dash",
    "dot",
    "dashdot",
    "longdash",
    "longdashdot",
    "3px,3px",
)
TARGET_LINE_DASH_STR: str = "dot"
WITHDRAWAL_DASH_STR: str = "dash"


def resolve_fund_colour_tuple(is_dark_mode_bool: bool) -> tuple:
    """Pick the categorical set matching the viewer's theme.

    Brief:
        Dark mode is a *selected* palette, not an automatic flip of
        the light one: each set was validated against its own
        surface, and a light-mode hue on a dark background fails
        the contrast gate.

    Arguments:
        is_dark_mode_bool (bool): True when the page is dark.

    Returns:
        tuple: Ordered hex colours for fund identity.

    Warning:
        The dark set holds five colours against the light set's
        six, so a six-fund plan wraps in dark mode. That is the
        measured ceiling, not an oversight.
    """
    if is_dark_mode_bool:
        return DARK_FUND_COLOUR_TUPLE
    return LIGHT_FUND_COLOUR_TUPLE


def _resolve_slot_index_int(
    fund_name_str: str,
    fund_name_list: list[str] | None,
) -> int:
    """Find the palette slot one fund occupies.

    Brief:
        The slot is the fund's position in the *sorted* roster of
        the whole plan, not its position in the order traces
        happen to be drawn. Sorting is what makes the assignment
        identical in every figure and on every run, whatever order
        a groupby or a dictionary hands the funds over in.

    Arguments:
        fund_name_str (str): Fund needing a slot.
        fund_name_list (Optional[List[str]]): Every fund in the
            plan. A missing roster falls back to the first slot.

    Returns:
        int: Zero-based slot index.

    Warning:
        Two plans that contain different funds assign different
        slots, which is intended: the roster is the unit of
        identity here, and editing the plan makes a new one.
    """
    ordered_name_list = sorted(
        {str(name) for name in (fund_name_list or [])}
    )
    if str(fund_name_str) not in ordered_name_list:
        return 0
    return ordered_name_list.index(str(fund_name_str))


def resolve_fund_colour_str(
    fund_name_str: str,
    fund_name_list: list[str] | None = None,
    is_dark_mode_bool: bool = False,
) -> str:
    """Pick the colour that belongs to one fund.

    Brief:
        Colour follows the fund's identity within its plan rather
        than the order its trace was added, so the same fund is
        the same colour in the value chart, the weight chart, the
        nominal run and the real run.

    Arguments:
        fund_name_str (str): Fund needing a colour.
        fund_name_list (Optional[List[str]]): Every fund in plan.
        is_dark_mode_bool (bool): Use the dark categorical set.

    Returns:
        str: Hex colour for that fund.

    Warning:
        A plan holding more funds than the validated ceiling wraps
        around and repeats colours. Those charts need direct
        labels, because two funds really will share a hue.
    """
    colour_tuple = resolve_fund_colour_tuple(is_dark_mode_bool)
    return colour_tuple[
        _resolve_slot_index_int(fund_name_str, fund_name_list)
        % len(colour_tuple)
    ]


def resolve_fund_dash_str(
    fund_name_str: str,
    fund_name_list: list[str] | None = None,
) -> str:
    """Pick the line pattern that belongs to one fund.

    Brief:
        Pattern rides alongside colour so the chart still reads
        for someone with a colour vision deficiency, in print, or
        under a forced-colours display mode.

    Arguments:
        fund_name_str (str): Fund needing a pattern.
        fund_name_list (Optional[List[str]]): Every fund in plan.

    Returns:
        str: Plotly dash pattern name.

    Warning:
        Keyed to the same slot as the colour, so the two must be
        changed together or they will fall out of step. Because
        the pattern tuple is longer than the colour tuple, a plan
        that wraps around still separates the wrapped funds.
    """
    return FUND_DASH_PATTERN_TUPLE[
        _resolve_slot_index_int(fund_name_str, fund_name_list)
        % len(FUND_DASH_PATTERN_TUPLE)
    ]
