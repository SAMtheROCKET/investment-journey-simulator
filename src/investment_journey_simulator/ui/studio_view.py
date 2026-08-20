"""The studio's visual layer, denominated in whatever you choose.

The classic dashboard is frozen: it works, it is tested, and it is
not touched by anything here. The timeline is an event rail. This is
the third shape - a **form-driven dashboard that knows what currency
it is speaking** - and it exists so the newer machinery (currencies,
tax regimes, slider-or-keyboard inputs) has a home that does not
disturb either of the other two.

Every figure on this page is formatted through `currency.py`, so
the symbol, the digit grouping and the words for large numbers all
follow one choice. Nothing here holds a rupee assumption.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from investment_journey_simulator.currency import (
    Currency,
    format_money_str,
)
from investment_journey_simulator.ui.timeline_view import render_stat_card

STUDIO_INK_COLOUR_STR: str = "#E2E8F0"
STUDIO_MUTED_COLOUR_STR: str = "#94A3B8"
STUDIO_ACCENT_COLOUR_STR: str = "#38BDF8"
STUDIO_PRINCIPAL_COLOUR_STR: str = "#94A3B8"
STUDIO_GRID_COLOUR_STR: str = "rgba(148,163,184,.12)"
TRANSPARENT_STR: str = "rgba(0,0,0,0)"
CHART_HEIGHT_INT: int = 420

CARD_SPECIFICATION_TUPLE: tuple = (
    ("Invested", "invested", "what you actually paid in", ""),
    ("Value", "corpus", "before any exit tax", ""),
    ("Tax and charges", "exit_cost", "payable on a full exit", "warn"),
    (
        "Yours to spend",
        "spendable",
        "value after tax and charges",
        "accent",
    ),
)


def compact_money_str(
    amount_float: float,
    currency: Currency,
) -> str:
    """Shorten an amount using its own currency's suffixes.

    Brief:
        A headline tile has no room for thirteen digits, and the
        suffix has to belong to the currency - "L" means lakh and
        is meaningless against a dollar figure.

    Arguments:
        amount_float (float): Amount to shorten.
        currency (Currency): Currency it is denominated in.

    Returns:
        str: For example "₹1.24Cr" or "$1.24M".

    Warning:
        Rounded to two decimals, so differences below one percent
        of the displayed unit are hidden.
    """
    signed_float = float(amount_float)
    sign_str = "-" if signed_float < 0 else ""
    absolute_float = abs(signed_float)
    for unit_float, suffix_str in currency.compact_tuple:
        if absolute_float >= unit_float:
            scaled_float = absolute_float / unit_float
            return (
                f"{sign_str}{currency.symbol_str}"
                f"{scaled_float:.2f}{suffix_str}"
            )
    return format_money_str(signed_float, currency)


def render_outcome_cards(
    outcome_dict: dict,
    currency: Currency,
) -> None:
    """Render the headline figures, in the chosen currency.

    Brief:
        Invested, corpus, what tax takes, and what is actually
        left - in that order, because the last one is the answer
        and the others explain how it got there.

    Arguments:
        outcome_dict (dict): Figures to display.
        currency (Currency): Currency to display them in.

    Returns:
        None: Cards are written to the page.

    Warning:
        Missing keys render as zero rather than raising.
    """
    column_list = st.columns(len(CARD_SPECIFICATION_TUPLE))
    for column, specification_tuple in zip(
        column_list, CARD_SPECIFICATION_TUPLE, strict=True
    ):
        label_str, key_str, footnote_str, tone_str = (
            specification_tuple
        )
        with column:
            render_stat_card(
                label_str,
                compact_money_str(
                    outcome_dict.get(key_str, 0.0), currency
                ),
                footnote_str,
                tone_str,
            )


def render_return_cards(
    outcome_dict: dict,
    currency: Currency,
) -> None:
    """Render the gain and both money-weighted returns.

    Brief:
        Gain answers "how much", the returns answer "how well" -
        and the post-tax one is what compares with a statement.

    Arguments:
        outcome_dict (dict): Figures to display.
        currency (Currency): Currency to display them in.

    Returns:
        None: Cards are written to the page.

    Warning:
        A return that cannot be solved shows as "n/a", never zero.
    """
    column_list = st.columns(3)
    with column_list[0]:
        render_stat_card(
            "Gain",
            compact_money_str(
                outcome_dict.get("gain", 0.0), currency
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
    """Render a solved rate, or say it is unavailable.

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


def build_growth_figure(
    month_date_list: list,
    portfolio_value_list: list[float],
    invested_list: list[float],
    currency: Currency,
) -> go.Figure:
    """Draw corpus against principal, in the chosen currency.

    Brief:
        The principal sits beneath the corpus as a quiet band, so
        the gap between them *is* the gain and needs no third
        series to explain it.

    Arguments:
        month_date_list (list): Month axis.
        portfolio_value_list (List[float]): Corpus by month.
        invested_list (List[float]): Principal by month.
        currency (Currency): Currency for the value axis.

    Returns:
        go.Figure: The growth chart.

    Warning:
        The axis is prefixed with the currency symbol, so a plan
        can never be read in the wrong denomination.
    """
    figure = go.Figure()
    figure.add_trace(
        _build_band_trace(
            month_date_list,
            invested_list,
            "Paid in",
            STUDIO_PRINCIPAL_COLOUR_STR,
            "rgba(148,163,184,.12)",
            "tozeroy",
        )
    )
    figure.add_trace(
        _build_band_trace(
            month_date_list,
            portfolio_value_list,
            "Value",
            STUDIO_ACCENT_COLOUR_STR,
            "rgba(56,189,248,.14)",
            "tonexty",
        )
    )
    return _apply_growth_layout(figure, currency)


def _build_band_trace(
    month_date_list: list,
    value_list: list[float],
    name_str: str,
    colour_str: str,
    fill_colour_str: str,
    fill_mode_str: str,
) -> go.Scatter:
    """Build one filled band of the growth chart.

    Brief:
        Shared by the principal and corpus bands so their shape
        and hover behaviour stay identical.

    Arguments:
        month_date_list (list): Month axis.
        value_list (List[float]): Values to plot.
        name_str (str): Legend label.
        colour_str (str): Line colour.
        fill_colour_str (str): Fill colour.
        fill_mode_str (str): Plotly fill mode.

    Returns:
        go.Scatter: Configured band trace.

    Warning:
        The corpus fills to the previous trace, so the principal
        band must be added first.
    """
    return go.Scatter(
        x=month_date_list,
        y=value_list,
        name=name_str,
        mode="lines",
        line=dict(width=2.0, color=colour_str),
        fill=fill_mode_str,
        fillcolor=fill_colour_str,
        hovertemplate=(
            "%{x|%b %Y}<br>" + name_str + " %{y:,.0f}<extra></extra>"
        ),
    )


def _apply_growth_layout(
    figure: go.Figure,
    currency: Currency,
) -> go.Figure:
    """Style the growth chart and denominate its axis.

    Brief:
        The value axis carries the currency symbol so the chart
        cannot be read in the wrong denomination.

    Arguments:
        figure (go.Figure): Figure being styled.
        currency (Currency): Currency for the value axis.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        Tick values use SI shortening, which is currency-neutral.
    """
    figure.update_layout(
        height=CHART_HEIGHT_INT,
        margin=dict(t=20, l=10, r=10, b=10),
        paper_bgcolor=TRANSPARENT_STR,
        plot_bgcolor=TRANSPARENT_STR,
        font=dict(color=STUDIO_INK_COLOUR_STR, size=13),
        hovermode="x unified",
        legend=dict(
            orientation="h", y=1.08, x=0, bgcolor=TRANSPARENT_STR
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color=STUDIO_MUTED_COLOUR_STR, size=11),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=STUDIO_GRID_COLOUR_STR,
            zeroline=False,
            tickprefix=currency.symbol_str,
            tickformat=".2s",
            tickfont=dict(color=STUDIO_MUTED_COLOUR_STR, size=11),
        ),
    )
    return figure


def build_year_row_list(
    snapshot_list: list,
    currency: Currency,
) -> list[dict]:
    """Summarise the plan one row per completed year.

    Brief:
        A month-by-month table is unreadable over thirty years,
        and a single ending figure explains nothing. A yearly
        table is the size a person can actually check.

    Arguments:
        snapshot_list (list): Simulated monthly snapshots.
        currency (Currency): Currency to render amounts in.

    Returns:
        List[dict]: One row per year, ready for a table.

    Warning:
        Reports the closing month of each year, so a partial
        final year is omitted rather than shown as complete.
    """
    row_list: list[dict] = []
    for snapshot_index_int in range(11, len(snapshot_list), 12):
        snapshot = snapshot_list[snapshot_index_int]
        gain_float = (
            snapshot.portfolio_value_float
            - snapshot.invested_amount_float
        )
        row_list.append(
            {
                "Year": snapshot_index_int // 12 + 1,
                "As of": f"{snapshot.month_date:%b %Y}",
                "Paid in": format_money_str(
                    snapshot.invested_amount_float, currency
                ),
                "Value": format_money_str(
                    snapshot.portfolio_value_float, currency
                ),
                "Gain": format_money_str(gain_float, currency),
                "Tax so far": format_money_str(
                    snapshot.tax_paid_float, currency
                ),
            }
        )
    return row_list
