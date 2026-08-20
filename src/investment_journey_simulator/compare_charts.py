"""Charts that show why journeys diverged, not just that they did.

Two figures live here. The overlay answers *how far apart*, and the
waterfall answers *why*, which is the question the whole comparison
exists to settle.

Colours come from `palette.py`, whose sets were checked by
computation against WCAG contrast and OKLab colour-vision separation
rather than chosen by eye. Nothing here invents a colour.
"""

from __future__ import annotations

import plotly.graph_objects as go

from investment_journey_simulator.attribution import Attribution
from investment_journey_simulator.charts import apply_dense_grid_to_axes
from investment_journey_simulator.currency import Currency, format_money_str
from investment_journey_simulator.palette import (
    GAIN_COLOUR_STR,
    LOSS_COLOUR_STR,
    PORTFOLIO_VALUE_COLOUR_STR,
    resolve_fund_colour_str,
)

OVERLAY_TITLE_STR: str = "How the journeys diverge"
WATERFALL_TITLE_STR: str = "Where the difference came from"
FIGURE_HEIGHT_INT: int = 460


def build_overlay_figure(
    series_dict: dict[str, list],
    month_date_list: list,
    currency: Currency,
    is_dark_mode_bool: bool = False,
) -> go.Figure:
    """Draw every journey's corpus on one axis.

    Brief:
        One line per journey, on a shared axis, so the moment they
        part company is visible rather than inferred.

    Arguments:
        series_dict (Dict[str, list]): Journey name to values.
        month_date_list (List): Dates of the month grid.
        currency (Currency): Currency of the amounts.
        is_dark_mode_bool (bool): Dark surface flag.

    Returns:
        go.Figure: The overlay chart.

    Warning:
        Assumes every journey shares the month grid, which the
        basis check on the comparison already enforces.
    """
    figure = go.Figure()
    # Colour follows the journey's name rather than the order its
    # trace was added, so a journey keeps its colour between the
    # overlay, the tiles and any later chart.
    name_str_list = list(series_dict)
    for name_str, value_list in series_dict.items():
        figure.add_trace(
            _build_journey_trace(
                name_str,
                value_list,
                month_date_list,
                name_str_list,
                is_dark_mode_bool,
            )
        )
    _apply_overlay_layout(figure, currency)
    return figure


def _apply_overlay_layout(
    figure: go.Figure,
    currency: Currency,
) -> None:
    """Style the overlay, with the legend above the plot.

    Brief:
        A horizontal legend on top keeps journey names readable at
        full length; down the side they would be truncated, and a
        comparison whose labels are cut off explains nothing.

    Arguments:
        figure (go.Figure): Figure being styled.
        currency (Currency): Currency, named on the axis.

    Returns:
        None: The figure is styled in place.

    Warning:
        Unified hover assumes a shared month grid.
    """
    figure.update_layout(
        title=OVERLAY_TITLE_STR,
        height=FIGURE_HEIGHT_INT,
        hovermode="x unified",
        yaxis_title=f"Portfolio value ({currency.code_str})",
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )
    apply_dense_grid_to_axes(figure)


def _build_journey_trace(
    name_str: str,
    value_list: list,
    month_date_list: list,
    name_str_list: list,
    is_dark_mode_bool: bool,
) -> go.Scatter:
    """Build one journey's line on the overlay."""
    return go.Scatter(
        x=month_date_list[: len(value_list)],
        y=value_list,
        name=name_str,
        mode="lines",
        line={
            "width": 2.5,
            "color": resolve_fund_colour_str(
                name_str, name_str_list, is_dark_mode_bool
            ),
        },
        hovertemplate=(
            f"<b>{name_str}</b><br>%{{x|%b %Y}}<br>"
            "%{y:,.0f}<extra></extra>"
        ),
    )


def build_attribution_figure(
    attribution: Attribution,
    currency: Currency,
) -> go.Figure:
    """Draw the gap as a waterfall of named causes.

    Brief:
        Starts at the better journey, subtracts each cause in turn,
        and lands on the worse one. Because the causes are exact,
        the bars really do reach the final total rather than
        approximately reaching it.

    Arguments:
        attribution (Attribution): The split to draw.
        currency (Currency): Currency of the amounts.

    Returns:
        go.Figure: The waterfall chart.

    Warning:
        A residual bar is drawn whenever one exists, rather than
        being folded into the nearest cause.
    """
    label_list = [attribution.baseline_name_str]
    value_list: list[float] = [attribution.baseline_value_float]
    measure_list = ["absolute"]
    for cause in attribution.ranked_cause_list:
        label_list.append(cause.label_str)
        value_list.append(cause.amount_float)
        measure_list.append("relative")
    if round(attribution.residual_float, 2) != 0.0:
        label_list.append("Unexplained")
        value_list.append(attribution.residual_float)
        measure_list.append("relative")
    label_list.append(attribution.variant_name_str)
    value_list.append(0.0)
    measure_list.append("total")
    return _build_waterfall_figure(
        label_list, value_list, measure_list, currency
    )


def _build_waterfall_figure(
    label_list: list,
    value_list: list,
    measure_list: list,
    currency: Currency,
) -> go.Figure:
    """Assemble the waterfall from its already-built columns."""
    figure = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=measure_list,
            x=label_list,
            y=value_list,
            text=[
                format_money_str(value_float, currency)
                for value_float in value_list
            ],
            textposition="outside",
            connector={"line": {"width": 1}},
            decreasing={"marker": {"color": LOSS_COLOUR_STR}},
            increasing={"marker": {"color": GAIN_COLOUR_STR}},
            totals={
                "marker": {"color": PORTFOLIO_VALUE_COLOUR_STR}
            },
            hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=WATERFALL_TITLE_STR,
        height=FIGURE_HEIGHT_INT,
        showlegend=False,
        yaxis_title=f"Portfolio value ({currency.code_str})",
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
    )
    apply_dense_grid_to_axes(figure)
    return figure
