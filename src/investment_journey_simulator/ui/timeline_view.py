"""The timeline app's visual layer.

Deliberately separate from `result_view`: the classic dashboard is
working and is not touched by anything here. This module renders the
same engine's answers through a different lens - a horizontal
timeline you add events to, rather than a form you fill in.

Design intent: dark, quiet, and typographic. The chrome recedes so
the numbers carry the page. Colour is spent only where it means
something, which is the same rule `palette.py` enforces everywhere
else.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from investment_journey_simulator.formatting import (
    format_compact_money_str,
    format_money_amount_str,
)
from investment_journey_simulator.palette import (
    GAIN_COLOUR_STR,
    LOSS_COLOUR_STR,
    PAUSE_COLOUR_STR,
    PORTFOLIO_VALUE_COLOUR_STR,
    TAX_COLOUR_STR,
)
from investment_journey_simulator.timeline import (
    EVENT_EXPLANATION_DICT,
    EVENT_INCOME_STR,
    EVENT_LUMPSUM_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_RETIRE_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
)

SURFACE_COLOUR_STR: str = "#0E1B29"
PANEL_COLOUR_STR: str = "#152637"
INK_COLOUR_STR: str = "#E2E8F0"
MUTED_COLOUR_STR: str = "#94A3B8"
ACCENT_COLOUR_STR: str = "#2DD4BF"
RAIL_COLOUR_STR: str = "#25384B"

EVENT_MARKER_COLOUR_DICT: dict[str, str] = {
    EVENT_STEPUP_STR: GAIN_COLOUR_STR,
    EVENT_PAUSE_STR: PAUSE_COLOUR_STR,
    EVENT_RESUME_STR: ACCENT_COLOUR_STR,
    EVENT_LUMPSUM_STR: "#D97706",
    EVENT_WITHDRAW_STR: LOSS_COLOUR_STR,
    EVENT_RETIRE_STR: "#7C3AED",
    EVENT_INCOME_STR: TAX_COLOUR_STR,
}
EVENT_MARKER_SYMBOL_DICT: dict[str, str] = {
    EVENT_STEPUP_STR: "triangle-up",
    EVENT_PAUSE_STR: "square",
    EVENT_RESUME_STR: "triangle-right",
    EVENT_LUMPSUM_STR: "diamond",
    EVENT_WITHDRAW_STR: "triangle-down",
    EVENT_RETIRE_STR: "star",
    EVENT_INCOME_STR: "hexagon",
}
DEFAULT_MARKER_COLOUR_STR: str = ACCENT_COLOUR_STR
DEFAULT_MARKER_SYMBOL_STR: str = "circle"
INVESTED_FILL_STR: str = "rgba(148,163,184,.10)"
CORPUS_FILL_STR: str = "rgba(45,212,191,.13)"
GRID_COLOUR_STR: str = "rgba(148,163,184,.12)"
TRANSPARENT_STR: str = "rgba(0,0,0,0)"
TIMELINE_HEIGHT_INT: int = 440
MARKER_SIZE_INT: int = 15
OUTCOME_CARD_SPECIFICATION_TUPLE: tuple = (
    ("Invested", "invested", "what you actually paid in", ""),
    (
        "Value before tax",
        "corpus",
        "the number brochures quote",
        "",
    ),
    (
        "Tax and charges",
        "exit_cost",
        "payable on a full exit",
        "warn",
    ),
    (
        "Yours to spend",
        "spendable",
        "value after tax and charges",
        "accent",
    ),
)

# This page used to paint itself. It force-set `.stApp` to a dark
# gradient and then force-set every heading, label, caption and
# markdown block to a pale ink, because it began life as a
# standalone dark app before the portal had a theme of its own.
#
# That is what produced pale text on white buttons: the rules below
# reached the button's *label*, so the label went pale, while the
# button's *background* still came from whichever theme Streamlit
# was running - white, in the light theme. The block's own comments
# recorded the fight, patching inputs back to dark "or it would
# vanish the other way round".
#
# None of that is needed now. The app has one theme, declared in
# `.streamlit/config.toml` and checked by `test_theme_config.py`, so
# this page paints nothing and forces no colour. What remains is
# presentation - size, weight, spacing - and the few colours it does
# need come from `currentColor`, so they follow whatever surface
# they land on.
PAGE_STYLE_STR: str = """
<style>
  .tl-title {
      font-size: 2.6rem; font-weight: 200; letter-spacing: -.02em;
      margin: .2rem 0 .1rem 0; line-height: 1.1;
  }
  .tl-sub {
      color: color-mix(in srgb, currentColor 70%, transparent);
      font-size: .95rem; font-weight: 300; margin-bottom: 1.4rem;
  }
  .tl-card {
      background: color-mix(in srgb, currentColor 4%, transparent);
      border: 1px solid
          color-mix(in srgb, currentColor 14%, transparent);
      border-radius: 3px; padding: 1.1rem 1.3rem;
  }
  .tl-label {
      color: color-mix(in srgb, currentColor 62%, transparent);
      font-size: .74rem; font-weight: 500;
      letter-spacing: .12em; text-transform: uppercase;
  }
  .tl-value {
      font-size: 1.85rem; font-weight: 300;
      letter-spacing: -.02em; margin-top: .15rem;
  }
  .tl-value.accent {
      color: color-mix(in srgb, #28887E 72%, currentColor);
  }
  .tl-value.warn {
      color: color-mix(in srgb, #A9762F 72%, currentColor);
  }
  .tl-foot {
      color: color-mix(in srgb, currentColor 55%, transparent);
      font-size: .72rem; margin-top: .3rem;
  }
</style>
"""


def render_page_style() -> None:
    """Inject the page's visual language once.

    Presentation only: size, weight and spacing. It sets no page
    background and forces no text colour, so the screen looks like
    every other screen and reads in whichever theme is running.

    Returns:
        None: A style block is written to the page.
    """
    st.markdown(PAGE_STYLE_STR, unsafe_allow_html=True)


def render_hero(title_str: str, subtitle_str: str) -> None:
    """Write the page's headline block.

    Brief:
        Light type at a large size reads as calm rather than loud,
        which suits a page whose job is to make numbers legible.

    Arguments:
        title_str (str): Headline.
        subtitle_str (str): One-line description beneath it.

    Returns:
        None: Markup is written to the page.

    Warning:
        Both strings are rendered as HTML.
    """
    st.markdown(
        f'<div class="tl-title">{title_str}</div>'
        f'<div class="tl-sub">{subtitle_str}</div>',
        unsafe_allow_html=True,
    )


def render_stat_card(
    label_str: str,
    value_str: str,
    footnote_str: str = "",
    tone_str: str = "",
) -> None:
    """Write one headline figure as a card.

    Brief:
        Label above, figure below, optional footnote under that.
        The footnote is where the caveat lives, so a number never
        travels without its qualifier.

    Arguments:
        label_str (str): Small uppercase label.
        value_str (str): The figure itself.
        footnote_str (str): Optional qualifier.
        tone_str (str): Empty, "accent" or "warn".

    Returns:
        None: Markup is written to the page.

    Warning:
        Strings are rendered as HTML.
    """
    footnote_html_str = (
        f'<div class="tl-foot">{footnote_str}</div>'
        if footnote_str
        else ""
    )
    st.markdown(
        f'<div class="tl-card">'
        f'<div class="tl-label">{label_str}</div>'
        f'<div class="tl-value {tone_str}">{value_str}</div>'
        f"{footnote_html_str}</div>",
        unsafe_allow_html=True,
    )


def _build_event_hover_str(event: TimelineEvent) -> str:
    """Compose the hover card for one event marker.

    Brief:
        Names the event, dates it, states its amount, and explains
        what it does - so hovering teaches rather than just
        labelling.

    Arguments:
        event (TimelineEvent): Event being described.

    Returns:
        str: HTML hover text.

    Warning:
        Plotly needs explicit line breaks; newlines do nothing.
    """
    detail_str = ""
    if event.amount_float:
        detail_str = (
            f"<br>{format_money_amount_str(event.amount_float)}"
        )
    elif event.percent_float:
        detail_str = f"<br>{event.percent_float:.1f}% a year"
    explanation_str = EVENT_EXPLANATION_DICT.get(
        event.event_type_str, ""
    )
    return (
        f"<b>{event.event_type_str}</b><br>"
        f"{event.event_date:%b %Y}{detail_str}"
        f"<br><span style='color:#94A3B8'>{explanation_str}</span>"
        "<extra></extra>"
    )


def build_timeline_figure(
    plan: TimelinePlan,
    month_date_list: list,
    portfolio_value_list: list[float],
    invested_list: list[float],
) -> go.Figure:
    """Draw the plan as a horizontal, zoomable timeline.

    Brief:
        The corpus curve is the timeline. Events sit on it as
        shaped, coloured markers, so the reader sees not just when
        something happened but what it did to the money.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        month_date_list (list): Month axis.
        portfolio_value_list (List[float]): Corpus by month.
        invested_list (List[float]): Principal by month.

    Returns:
        go.Figure: Interactive timeline with a range slider.

    Warning:
        Markers are placed on the corpus curve, so an event dated
        beyond the horizon is clamped to the last month drawn.
    """
    figure = go.Figure()
    _add_timeline_areas(
        figure, month_date_list, portfolio_value_list, invested_list
    )
    _add_event_markers(
        figure, plan, month_date_list, portfolio_value_list
    )
    return _apply_timeline_layout(figure)


def _add_timeline_areas(
    figure: go.Figure,
    month_date_list: list,
    portfolio_value_list: list[float],
    invested_list: list[float],
) -> None:
    """Add the corpus and principal bands.

    Brief:
        Principal is drawn as a quiet filled band beneath the
        corpus, so the gap between them *is* the gain and needs no
        separate series.

    Arguments:
        figure (go.Figure): Figure being populated.
        month_date_list (list): Month axis.
        portfolio_value_list (List[float]): Corpus by month.
        invested_list (List[float]): Principal by month.

    Returns:
        None: Traces are added in place.

    Warning:
        Order matters; the corpus must be added last to sit above.
    """
    figure.add_trace(
        _build_band_trace(
            month_date_list,
            invested_list,
            "Invested",
            (1.5, MUTED_COLOUR_STR, "tozeroy", INVESTED_FILL_STR),
        )
    )
    figure.add_trace(
        _build_band_trace(
            month_date_list,
            portfolio_value_list,
            "Value",
            (2.5, ACCENT_COLOUR_STR, "tonexty", CORPUS_FILL_STR),
        )
    )


def _build_band_trace(
    month_date_list: list,
    value_list: list[float],
    name_str: str,
    style_tuple: tuple,
) -> go.Scatter:
    """Build one filled band of the timeline.

    Brief:
        Shared by the principal and corpus bands so their shape,
        hover and fill behaviour stay identical.

    Arguments:
        month_date_list (list): Month axis.
        value_list (List[float]): Values to plot.
        name_str (str): Legend label.
        style_tuple (tuple): Width, colour, fill mode and fill
            colour, in that order.

    Returns:
        go.Scatter: Configured band trace.

    Warning:
        The corpus band fills to the previous trace, so the
        principal band must be added first.
    """
    width_float, colour_str, fill_str, fill_colour_str = style_tuple
    return go.Scatter(
        x=month_date_list,
        y=value_list,
        name=name_str,
        mode="lines",
        line=dict(width=width_float, color=colour_str),
        fill=fill_str,
        fillcolor=fill_colour_str,
        hovertemplate=(
            "%{x|%b %Y}<br>"
            + name_str
            + " %{y:,.0f}<extra></extra>"
        ),
    )


def _add_event_markers(
    figure: go.Figure,
    plan: TimelinePlan,
    month_date_list: list,
    portfolio_value_list: list[float],
) -> None:
    """Place one marker per event on the corpus curve.

    Brief:
        Shape carries the event type as well as colour, so the
        timeline reads without relying on hue alone.

    Arguments:
        figure (go.Figure): Figure being populated.
        plan (TimelinePlan): Plan supplying the events.
        month_date_list (list): Month axis.
        portfolio_value_list (List[float]): Corpus by month.

    Returns:
        None: One trace per event type is added.

    Warning:
        Silently skips events when the plan has no months yet.
    """
    if not month_date_list:
        return
    for event in plan.ordered_event_list:
        index_int = min(
            max(0, _locate_month_index_int(plan, event)),
            len(month_date_list) - 1,
        )
        figure.add_trace(
            _build_marker_trace(
                event,
                month_date_list[index_int],
                portfolio_value_list[index_int],
            )
        )


def _build_marker_trace(
    event: TimelineEvent,
    marker_date,
    marker_value_float: float,
) -> go.Scatter:
    """Build the marker for one event.

    Brief:
        Shape and colour both encode the event type, so the
        timeline reads without relying on hue alone.

    Arguments:
        event (TimelineEvent): Event being drawn.
        marker_date: Month the marker sits on.
        marker_value_float (float): Corpus at that month.

    Returns:
        go.Scatter: Single-point marker trace.

    Warning:
        Kept out of the legend; the hover card carries the label.
    """
    return go.Scatter(
        x=[marker_date],
        y=[marker_value_float],
        mode="markers",
        name=event.event_type_str,
        showlegend=False,
        marker=dict(
            size=MARKER_SIZE_INT,
            symbol=EVENT_MARKER_SYMBOL_DICT.get(
                event.event_type_str, DEFAULT_MARKER_SYMBOL_STR
            ),
            color=EVENT_MARKER_COLOUR_DICT.get(
                event.event_type_str, DEFAULT_MARKER_COLOUR_STR
            ),
            line=dict(width=2, color=SURFACE_COLOUR_STR),
        ),
        hovertemplate=_build_event_hover_str(event),
    )


def _locate_month_index_int(
    plan: TimelinePlan,
    event: TimelineEvent,
) -> int:
    """Month index of one event on the plan grid.

    Brief:
        Thin wrapper so the marker builder does not import the
        compiler's private helper.

    Arguments:
        plan (TimelinePlan): Plan providing the origin.
        event (TimelineEvent): Event being located.

    Returns:
        int: Zero-based month index, never negative.

    Warning:
        Callers must still clamp against the axis length.
    """
    month_gap_int = (
        event.event_date.year - plan.start_date.year
    ) * 12 + (event.event_date.month - plan.start_date.month)
    return max(0, month_gap_int)


def _apply_timeline_layout(figure: go.Figure) -> go.Figure:
    """Style the timeline and switch its zoom controls on.

    Brief:
        A range slider under the axis gives click-and-drag zoom
        without any custom JavaScript, and range buttons jump to
        common spans.

    Arguments:
        figure (go.Figure): Figure being styled.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        The slider adds height; the figure is sized to allow it.
    """
    figure.update_layout(
        height=TIMELINE_HEIGHT_INT,
        margin=dict(t=20, l=10, r=10, b=10),
        paper_bgcolor=TRANSPARENT_STR,
        plot_bgcolor=TRANSPARENT_STR,
        font=dict(color=INK_COLOUR_STR, size=13),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor=PANEL_COLOUR_STR,
            bordercolor=ACCENT_COLOUR_STR,
            font=dict(color=INK_COLOUR_STR, size=12),
        ),
        legend=dict(
            orientation="h", y=1.08, x=0, bgcolor=TRANSPARENT_STR
        ),
        xaxis=_build_time_axis_dict(),
        yaxis=dict(
            showgrid=True,
            gridcolor=GRID_COLOUR_STR,
            zeroline=False,
            tickprefix="₹",
            tickformat=".2s",
        ),
    )
    return figure


def _build_time_axis_dict() -> dict:
    """Build the zoomable time axis.

    Brief:
        A range slider plus range buttons give drag-to-zoom and
        one-click spans without any custom JavaScript.

    Arguments:
        None.

    Returns:
        dict: Plotly x-axis configuration.

    Warning:
        The slider consumes vertical space, which the figure
        height already allows for.
    """
    return dict(
        showgrid=False,
        linecolor=RAIL_COLOUR_STR,
        rangeslider=dict(visible=True, thickness=0.07),
        rangeselector=dict(
            bgcolor=PANEL_COLOUR_STR,
            activecolor=ACCENT_COLOUR_STR,
            bordercolor=RAIL_COLOUR_STR,
            borderwidth=1,
            font=dict(color=INK_COLOUR_STR, size=11),
            buttons=[
                dict(count=5, label="5Y", step="year",
                     stepmode="backward"),
                dict(count=10, label="10Y", step="year",
                     stepmode="backward"),
                dict(step="all", label="All"),
            ],
        ),
    )


def render_outcome_cards(outcome_dict: dict[str, float]) -> None:
    """Render the four headline figures as cards.

    Brief:
        Invested, corpus before tax, tax and charges, and what is
        actually spendable - in that order, because the last one
        is the answer and the others explain how it got there.

    Arguments:
        outcome_dict (Dict[str, float]): Figures to display.

    Returns:
        None: Cards are written to the page.

    Warning:
        Missing keys render as zero rather than raising.
    """
    specification_tuple = OUTCOME_CARD_SPECIFICATION_TUPLE
    column_list = st.columns(len(specification_tuple))
    for column, specification in zip(
        column_list, specification_tuple, strict=True
    ):
        label_str, key_str, footnote_str, tone_str = specification
        with column:
            render_stat_card(
                label_str,
                format_compact_money_str(
                    outcome_dict.get(key_str, 0.0)
                ),
                footnote_str,
                tone_str,
            )


def render_return_cards(outcome_dict: dict[str, float]) -> None:
    """Render the gain and money-weighted return cards.

    Brief:
        Gain answers "how much", the return answers "how well" -
        and the post-tax return is the one comparable with a
        broker statement.

    Arguments:
        outcome_dict (Dict[str, float]): Figures to display.

    Returns:
        None: Cards are written to the page.

    Warning:
        A missing return renders as "n/a" rather than zero.
    """
    column_list = st.columns(3)
    with column_list[0]:
        render_stat_card(
            "Gain",
            format_compact_money_str(
                outcome_dict.get("gain", 0.0)
            ),
            "value minus what you paid in",
        )
    with column_list[1]:
        render_stat_card(
            "Return before tax",
            _format_percent_str(outcome_dict.get("xirr_pre")),
            "money-weighted (XIRR)",
        )
    with column_list[2]:
        render_stat_card(
            "Return after tax",
            _format_percent_str(outcome_dict.get("xirr_post")),
            "what you actually kept",
            "accent",
        )


def _format_percent_str(value_float: float | None) -> str:
    """Render a rate, or say it is unavailable.

    Brief:
        A plan that never both pays in and takes out has no
        money-weighted return at all, and that must not display
        as zero percent.

    Arguments:
        value_float (Optional[float]): Solved rate.

    Returns:
        str: Formatted percentage or the unavailable marker.

    Warning:
        Never substitutes zero for an unsolvable series.
    """
    if value_float is None:
        return "n/a"
    return f"{float(value_float):.2f}%"


def build_tax_colour_str() -> str:
    """Expose the tax accent used by this page.

    Brief:
        Kept as a function so the page and its tests agree on one
        source of truth for the colour.

    Arguments:
        None.

    Returns:
        str: Hex colour reserved for tax and cost.

    Warning:
        Reserved: never reuse it to identify a fund.
    """
    return TAX_COLOUR_STR


def build_portfolio_colour_str() -> str:
    """Expose the corpus accent used by this page.

    Brief:
        Mirrors the classic dashboard so the same concept keeps
        the same colour across both interfaces.

    Arguments:
        None.

    Returns:
        str: Hex colour used for portfolio value.

    Warning:
        Changing it desynchronises the two pages.
    """
    return PORTFOLIO_VALUE_COLOUR_STR
