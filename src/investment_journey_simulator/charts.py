"""Plotly figures assembled from simulation tables."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from investment_journey_simulator.constants import (
    DASHBOARD_HEIGHT_INT,
    DONUT_HOLE_RATIO_FLOAT,
    MONEY_TOLERANCE_FLOAT,
    PERCENT_TOTAL_FLOAT,
    PLOTLY_TEMPLATE_STR,
    SERIES_INVESTED_STR,
    SERIES_MONTH_STR,
    SERIES_MONTHLY_SIP_STR,
    SERIES_MONTHLY_WITHDRAWAL_STR,
    SERIES_PORTFOLIO_VALUE_STR,
    SERIES_WITHDRAWN_STR,
    SUMMARY_ENDING_VALUE_STR,
    SUMMARY_FUND_NAME_STR,
    SUMMARY_GAIN_STR,
    SUMMARY_INVESTED_STR,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.formatting import (
    format_compact_money_str,
    format_money_amount_str,
    resolve_display_currency,
)
from investment_journey_simulator.palette import (
    GAIN_COLOUR_STR,
    INVESTED_COLOUR_STR,
    LOSS_COLOUR_STR,
    MONTHLY_SIP_COLOUR_STR,
    PAUSE_COLOUR_STR,
    PORTFOLIO_VALUE_COLOUR_STR,
    REBALANCE_COLOUR_STR,
    TARGET_LINE_COLOUR_STR,
    TARGET_LINE_DASH_STR,
    WITHDRAWAL_COLOUR_STR,
    resolve_fund_colour_str,
    resolve_fund_dash_str,
)

GROWTH_PANEL_TITLE_STR: str = "Growth (Monthly Steps)"
INVESTED_PANEL_TITLE_STR: str = "Invested Split"
GAIN_PANEL_TITLE_STR: str = "Gain or Loss by Fund"
ENDING_PANEL_TITLE_STR: str = "End Value Split"
EMPTY_DONUT_LABEL_STR: str = "No positive gains"
EMPTY_DONUT_NOTE_STR: str = "Every fund is at or below zero gain"
CASHFLOW_BAR_OPACITY_FLOAT: float = 0.25
LINE_WIDTH_FLOAT: float = 2.5
PAUSE_OPACITY_FLOAT: float = 0.18
SECONDARY_FIGURE_HEIGHT_INT: int = 420
GROWTH_LINE_SPECIFICATIONS_TUPLE: tuple = (
    (
        SERIES_INVESTED_STR,
        "Invested (Principal)",
        False,
        INVESTED_COLOUR_STR,
    ),
    (
        SERIES_PORTFOLIO_VALUE_STR,
        "Portfolio Value (End)",
        False,
        PORTFOLIO_VALUE_COLOUR_STR,
    ),
    (
        SERIES_WITHDRAWN_STR,
        "Withdrawn (Cumulative)",
        True,
        WITHDRAWAL_COLOUR_STR,
    ),
)
CASHFLOW_BAR_SPECIFICATIONS_TUPLE: tuple = (
    (
        SERIES_MONTHLY_SIP_STR,
        "Monthly SIP (in)",
        False,
        MONTHLY_SIP_COLOUR_STR,
    ),
    (
        SERIES_MONTHLY_WITHDRAWAL_STR,
        "Monthly SWP (out)",
        True,
        WITHDRAWAL_COLOUR_STR,
    ),
)
DONUT_PANEL_SPECIFICATIONS_TUPLE: tuple = (
    (SUMMARY_INVESTED_STR, 1, 2),
    (SUMMARY_ENDING_VALUE_STR, 2, 2),
)


def apply_dense_grid_to_axes(
    figure: go.Figure,
    row_int: int | None = None,
    column_int: int | None = None,
) -> go.Figure:
    """Draw a fine measuring grid on one subplot.

    Brief:
        Minor gridlines make it easy to read intermediate values
        straight off a panel.

    Arguments:
        figure (go.Figure): Figure being styled.
        row_int (Optional[int]): Subplot row, None if standalone.
        column_int (Optional[int]): Subplot column, None if
            the figure has no subplot grid.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        Applies to Cartesian axes only, never to donut panels.
    """
    axis_style_dict = dict(
        showgrid=True,
        gridwidth=1,
        showline=True,
        linewidth=1,
        mirror=True,
        ticks="outside",
        ticklen=6,
        minor=dict(showgrid=True, gridwidth=0.5),
    )
    if row_int is not None:
        axis_style_dict["row"] = row_int
        axis_style_dict["col"] = column_int
    figure.update_xaxes(**axis_style_dict)
    figure.update_yaxes(**axis_style_dict)
    return figure


def _build_money_hover_tuple(
    amount_sequence: Sequence[float],
    trace_name_str: str,
    currency: Currency | None = None,
) -> tuple:
    """Precompute money hover labels and their template.

    Brief:
        Shared by the line and bar builders so both show the same
        formatting for the same amount.

    Arguments:
        amount_sequence (Sequence[float]): Values being plotted.
        trace_name_str (str): Legend label of the trace.
        currency (Optional[Currency]): Currency of the amounts.

    Returns:
        tuple: Custom data list and the hover template string.

    Warning:
        Labels are materialised eagerly, so a very long horizon
        enlarges the rendered figure.
    """
    return (
        [
            format_money_amount_str(amount_float, currency)
            for amount_float in amount_sequence
        ],
        "%{x|%b %Y}<br>"
        + trace_name_str
        + ": %{customdata}<extra></extra>",
    )


def _build_line_style_dict(
    is_dashed_bool: bool,
    colour_str: str | None,
    dash_str: str | None,
) -> dict:
    """Assemble the line style of one growth trace.

    Brief:
        An explicit dash pattern wins over the plain dashed flag,
        because it carries fund identity rather than decoration.

    Arguments:
        is_dashed_bool (bool): Legacy dashed-line flag.
        colour_str (Optional[str]): Explicit line colour.
        dash_str (Optional[str]): Explicit dash pattern.

    Returns:
        dict: Plotly line style mapping.

    Warning:
        Leaving the colour unset lets Plotly assign one by trace
        position, which is the repaint defect this avoids.
    """
    line_style_dict: dict[str, object] = {
        "width": LINE_WIDTH_FLOAT
    }
    if is_dashed_bool:
        line_style_dict["dash"] = "dot"
    if dash_str is not None:
        line_style_dict["dash"] = dash_str
    if colour_str is not None:
        line_style_dict["color"] = colour_str
    return line_style_dict


def build_stepped_line_trace(
    month_dates_sequence: Sequence,
    amount_sequence: Sequence[float],
    trace_name_str: str,
    is_dashed_bool: bool = False,
    colour_str: str | None = None,
    dash_str: str | None = None,
    currency: Currency | None = None,
) -> go.Scatter:
    """Build one stepped growth line with money hover labels.

    Brief:
        Monthly compounding is a step function, so a stepped line
        is more honest than a smooth interpolation.

    Arguments:
        month_dates_sequence (Sequence): Month axis values.
        amount_sequence (Sequence[float]): Values to plot.
        trace_name_str (str): Legend label of the line.
        is_dashed_bool (bool): Draw the line dashed when True.
        colour_str (Optional[str]): Explicit line colour. Passing
            it stops Plotly assigning a colour by trace position.
        dash_str (Optional[str]): Explicit dash pattern, which
            carries identity redundantly with the colour.
        currency (Optional[Currency]): Currency of the amounts.

    Returns:
        go.Scatter: Configured stepped line trace.

    Warning:
        Hover text is precomputed, so very long horizons increase
        the size of the rendered figure.
    """
    custom_data_list, hover_template_str = (
        _build_money_hover_tuple(
            amount_sequence, trace_name_str, currency
        )
    )
    return go.Scatter(
        x=list(month_dates_sequence),
        y=list(amount_sequence),
        name=trace_name_str,
        mode="lines",
        line_shape="hv",
        line=_build_line_style_dict(
            is_dashed_bool, colour_str, dash_str
        ),
        customdata=custom_data_list,
        hovertemplate=hover_template_str,
    )


def build_cashflow_bar_trace(
    month_dates_sequence: Sequence,
    amount_sequence: Sequence[float],
    trace_name_str: str,
    is_outflow_bool: bool = False,
    colour_str: str | None = None,
    currency: Currency | None = None,
) -> go.Bar:
    """Build a translucent bar series for a monthly cash flow.

    Brief:
        Contributions point up and withdrawals point down.

    Arguments:
        month_dates_sequence (Sequence): Month axis values.
        amount_sequence (Sequence[float]): Cash flow per month.
        trace_name_str (str): Legend label of the bars.
        is_outflow_bool (bool): Draw below the axis when True.
        colour_str (Optional[str]): Explicit bar colour.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        go.Bar: Configured translucent bar trace.

    Warning:
        A contribution is deliberately not green; green means gain.
    """
    sign_float = -1.0 if is_outflow_bool else 1.0
    custom_data_list, hover_template_str = (
        _build_money_hover_tuple(
            amount_sequence, trace_name_str, currency
        )
    )
    default_colour_str = (
        WITHDRAWAL_COLOUR_STR
        if is_outflow_bool
        else MONTHLY_SIP_COLOUR_STR
    )
    return go.Bar(
        x=list(month_dates_sequence),
        y=[
            sign_float * float(amount_float)
            for amount_float in amount_sequence
        ],
        name=trace_name_str,
        opacity=CASHFLOW_BAR_OPACITY_FLOAT,
        marker=dict(color=colour_str or default_colour_str),
        customdata=custom_data_list,
        hovertemplate=hover_template_str,
    )


def build_donut_trace(
    fund_names_list: list[str],
    amount_list: list[float],
    currency: Currency | None = None,
) -> go.Pie:
    """Build a share donut that tolerates non-positive values.

    Brief:
        Negative or zero slices cannot be drawn, so an all-negative
        panel falls back to a single explanatory slice.

    Arguments:
        fund_names_list (List[str]): Slice labels.
        amount_list (List[float]): Slice values.
        currency (Optional[Currency]): Currency of the amounts.

    Returns:
        go.Pie: Configured donut trace.

    Warning:
        Negative amounts are clipped to zero, which is why gains
        are drawn as a diverging bar chart instead.
    """
    positive_amount_list = [
        max(0.0, float(amount_float)) for amount_float in amount_list
    ]
    if sum(positive_amount_list) <= MONEY_TOLERANCE_FLOAT:
        slice_label_list = [EMPTY_DONUT_LABEL_STR]
        slice_value_list = [1.0]
        hover_text_list = [EMPTY_DONUT_NOTE_STR]
    else:
        slice_label_list = list(fund_names_list)
        slice_value_list = positive_amount_list
        hover_text_list = [
            f"{format_money_amount_str(amount_float, currency)} "
            f"({format_compact_money_str(amount_float, currency)})"
            for amount_float in amount_list
        ]
    return go.Pie(
        labels=slice_label_list,
        values=slice_value_list,
        hole=DONUT_HOLE_RATIO_FLOAT,
        textinfo="percent",
        customdata=hover_text_list,
        hovertemplate="%{label}<br>%{customdata}<extra></extra>",
        sort=False,
        marker=dict(line=dict(width=1)),
        showlegend=False,
    )


def build_gain_loss_bar_trace(
    fund_names_list: list[str],
    gain_list: list[float],
    currency: Currency | None = None,
) -> go.Bar:
    """Build a diverging bar of gains and losses by fund.

    Brief:
        A pie cannot represent a loss. A diverging bar shows both
        directions honestly, which is why it replaces the old
        positive-only gains donut.

    Arguments:
        fund_names_list (List[str]): Fund labels.
        gain_list (List[float]): Gain per fund, may be negative.
        currency (Optional[Currency]): Currency of the amounts.

    Returns:
        go.Bar: Configured diverging bar trace.

    Warning:
        Bars are absolute amounts, not shares, so they cannot be
        read as percentages of the portfolio.
    """
    return go.Bar(
        x=list(fund_names_list),
        y=[float(gain_float) for gain_float in gain_list],
        name="Gain / Loss",
        marker=dict(
            color=[
                GAIN_COLOUR_STR if gain_float >= 0 else LOSS_COLOUR_STR
                for gain_float in gain_list
            ]
        ),
        customdata=[
            format_money_amount_str(gain_float, currency)
            for gain_float in gain_list
        ],
        hovertemplate="%{x}<br>%{customdata}<extra></extra>",
        showlegend=False,
    )


def build_dashboard_figure(
    monthly_series_dataframe: pd.DataFrame,
    fund_summary_dataframe: pd.DataFrame,
    figure_title_str: str,
    rebalance_dates_list: list | None = None,
    pause_dates_list: list | None = None,
    currency: Currency | None = None,
) -> go.Figure:
    """Assemble the four-panel dashboard for one simulation run.

    Brief:
        Growth panel with rebalance markers and pause shading,
        then the invested split, gain bar and end split.

    Arguments:
        monthly_series_dataframe (pd.DataFrame): Monthly series.
        fund_summary_dataframe (pd.DataFrame): Per-fund summary.
        figure_title_str (str): Headline shown above the panels.
        rebalance_dates_list (Optional[List]): Trade dates to mark.
        pause_dates_list (Optional[List]): Paused months to shade.
        currency (Optional[Currency]): Sets axes and hovers.

    Returns:
        go.Figure: Fully styled dashboard figure.

    Warning:
        Both tables must come from the same simulation run.
    """
    figure = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "xy"}, {"type": "domain"}],
            [{"type": "xy"}, {"type": "domain"}],
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
        subplot_titles=(
            GROWTH_PANEL_TITLE_STR,
            INVESTED_PANEL_TITLE_STR,
            GAIN_PANEL_TITLE_STR,
            ENDING_PANEL_TITLE_STR,
        ),
    )
    _add_growth_panel(figure, monthly_series_dataframe, currency)
    _add_event_markers(
        figure, rebalance_dates_list, pause_dates_list
    )
    _add_split_panels(figure, fund_summary_dataframe, currency)
    return _apply_dashboard_layout(figure, figure_title_str)


def _apply_dashboard_layout(
    figure: go.Figure,
    figure_title_str: str,
) -> go.Figure:
    """Apply the shared layout of every dashboard figure.

    Brief:
        Keeps the template, legend and spacing identical between
        the nominal and the inflation-adjusted charts.

    Arguments:
        figure (go.Figure): Figure being styled.
        figure_title_str (str): Headline shown above the panels.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        The fixed height suits a desktop screen, not a phone.
    """
    figure.update_layout(
        template=PLOTLY_TEMPLATE_STR,
        barmode="overlay",
        hovermode="x unified",
        height=DASHBOARD_HEIGHT_INT,
        title=figure_title_str,
        title_x=0.02,
        margin=dict(t=95, l=30, r=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="left",
            x=0.02,
        ),
        font=dict(size=14),
    )
    return figure


def _add_growth_panel(
    figure: go.Figure,
    monthly_series_dataframe: pd.DataFrame,
    currency: Currency | None = None,
) -> None:
    """Add the stepped growth lines and cash-flow bars.

    Brief:
        Contributions point up, withdrawals point down.

    Arguments:
        figure (go.Figure): Figure being populated.
        monthly_series_dataframe (pd.DataFrame): The series.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        None: Traces are added in place.
    """
    month_dates_sequence = monthly_series_dataframe[SERIES_MONTH_STR]
    for column_str, label_str, is_dashed_bool, colour_str in (
        GROWTH_LINE_SPECIFICATIONS_TUPLE
    ):
        figure.add_trace(
            build_stepped_line_trace(
                month_dates_sequence,
                monthly_series_dataframe[column_str],
                label_str,
                is_dashed_bool,
                colour_str=colour_str,
                currency=currency,
            ),
            row=1,
            col=1,
        )
    for column_str, label_str, is_outflow_bool, colour_str in (
        CASHFLOW_BAR_SPECIFICATIONS_TUPLE
    ):
        figure.add_trace(
            build_cashflow_bar_trace(
                month_dates_sequence,
                monthly_series_dataframe[column_str],
                label_str,
                is_outflow_bool,
                colour_str=colour_str,
                currency=currency,
            ),
            row=1,
            col=1,
        )
    _style_growth_axes(figure, currency)


def _style_growth_axes(
    figure: go.Figure,
    currency: Currency | None = None,
) -> None:
    """Label and grid the growth panel axes.

    Brief:
        Kept separate so the trace builder stays short.

    Arguments:
        figure (go.Figure): Figure being styled.
        currency (Optional[Currency]): Currency to name on the
            value axis.

    Returns:
        None: Axes are styled in place.

    Warning:
        Targets the top-left subplot only.
    """
    symbol_str = resolve_display_currency(currency).symbol_str
    figure.update_xaxes(title_text="Month", row=1, col=1)
    figure.update_yaxes(
        title_text=f"Amount ({symbol_str})", row=1, col=1
    )
    apply_dense_grid_to_axes(figure, row_int=1, column_int=1)


def _add_event_markers(
    figure: go.Figure,
    rebalance_dates_list: list | None,
    pause_dates_list: list | None,
) -> None:
    """Mark rebalancing trades and shade paused months.

    Brief:
        Turns the growth panel into a timeline of what the plan
        actually did, not just what it was worth.

    Arguments:
        figure (go.Figure): Figure being annotated.
        rebalance_dates_list (Optional[List]): Trade dates.
        pause_dates_list (Optional[List]): Paused months.

    Returns:
        None: Shapes are added to the figure in place.

    Warning:
        Very frequent events make the panel visually noisy.
    """
    for pause_date in pause_dates_list or []:
        figure.add_vrect(
            x0=pause_date,
            x1=pause_date + pd.DateOffset(months=1),
            fillcolor=PAUSE_COLOUR_STR,
            opacity=PAUSE_OPACITY_FLOAT,
            line_width=0,
            row=1,
            col=1,
        )
    for rebalance_date in rebalance_dates_list or []:
        figure.add_vline(
            x=rebalance_date,
            line_width=1,
            line_dash="dash",
            line_color=REBALANCE_COLOUR_STR,
            row=1,
            col=1,
        )


def _add_split_panels(
    figure: go.Figure,
    fund_summary_dataframe: pd.DataFrame,
    currency: Currency | None = None,
) -> None:
    """Add the invested donut, gain bar and end-value donut.

    Brief:
        Gains use a diverging bar; a pie cannot draw a loss.

    Arguments:
        figure (go.Figure): Figure being populated.
        fund_summary_dataframe (pd.DataFrame): Fund summary.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        None: Traces are added in place.
    """
    fund_names_list = fund_summary_dataframe[
        SUMMARY_FUND_NAME_STR
    ].tolist()
    for column_str, row_int, column_index_int in (
        DONUT_PANEL_SPECIFICATIONS_TUPLE
    ):
        figure.add_trace(
            build_donut_trace(
                fund_names_list,
                fund_summary_dataframe[column_str].tolist(),
                currency,
            ),
            row=row_int,
            col=column_index_int,
        )
    figure.add_trace(
        build_gain_loss_bar_trace(
            fund_names_list,
            fund_summary_dataframe[SUMMARY_GAIN_STR].tolist(),
            currency,
        ),
        row=2,
        col=1,
    )
    figure.update_yaxes(
        title_text=(
            f"Gain ({resolve_display_currency(currency).symbol_str})"
        ),
        row=2,
        col=1,
    )
    apply_dense_grid_to_axes(figure, row_int=2, column_int=1)


def calculate_drawdown_series(value_series: pd.Series) -> pd.Series:
    """Measure how far a value series sits below its own peak.

    Brief:
        Drawdown is zero at every new high and negative in between.

    Arguments:
        value_series (pd.Series): Portfolio value by month.

    Returns:
        pd.Series: Percentage below the running peak.

    Warning:
        Months before the first rupee arrives report zero, since a
        portfolio worth nothing has no peak to fall from.
    """
    numeric_series = value_series.astype(float)
    peak_series = numeric_series.cummax()
    drawdown_series = pd.Series(
        0.0, index=numeric_series.index, dtype=float
    )
    is_priced_mask = peak_series > 0.0
    drawdown_series[is_priced_mask] = (
        (
            numeric_series[is_priced_mask]
            - peak_series[is_priced_mask]
        )
        / peak_series[is_priced_mask]
        * PERCENT_TOTAL_FLOAT
    )
    return drawdown_series


def build_drawdown_figure(
    monthly_series_dataframe: pd.DataFrame,
) -> go.Figure:
    """Plot how far the portfolio sits below its own peak.

    Brief:
        The honest picture of a withdrawal plan: a corpus that
        never recovers its peak is being consumed.

    Arguments:
        monthly_series_dataframe (pd.DataFrame): Monthly series.

    Returns:
        go.Figure: Filled drawdown figure in percent.

    Warning:
        Drawdown here comes from withdrawals and charges, not from
        market falls, because returns are deterministic.
    """
    drawdown_series = calculate_drawdown_series(
        monthly_series_dataframe[SERIES_PORTFOLIO_VALUE_STR]
    )
    figure = go.Figure(
        go.Scatter(
            x=monthly_series_dataframe[SERIES_MONTH_STR],
            y=drawdown_series,
            fill="tozeroy",
            mode="lines",
            line=dict(color=LOSS_COLOUR_STR, width=1.5),
            name="Drawdown",
            hovertemplate=(
                "%{x|%b %Y}<br>%{y:.2f}%<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        template=PLOTLY_TEMPLATE_STR,
        height=SECONDARY_FIGURE_HEIGHT_INT,
        title="Drawdown from peak value",
        margin=dict(t=60, l=30, r=30, b=30),
        yaxis_title="Below peak (%)",
    )
    return apply_dense_grid_to_axes(figure)


def _collect_fund_name_list(
    fund_history_dataframe: pd.DataFrame,
) -> list[str]:
    """List every fund present in a history table.

    Brief:
        The colour resolver keys on the whole plan, not on one
        trace, so it needs the full roster before drawing starts.

    Arguments:
        fund_history_dataframe (pd.DataFrame): Per-fund history.

    Returns:
        List[str]: Fund names, duplicates removed.

    Warning:
        An empty or column-less frame yields an empty list rather
        than raising, because empty portfolios are legal.
    """
    if "Fund" not in fund_history_dataframe.columns:
        return []
    return [
        str(fund_name)
        for fund_name in fund_history_dataframe["Fund"].unique()
    ]


def build_fund_history_figure(
    fund_history_dataframe: pd.DataFrame,
    is_dark_mode_bool: bool = False,
    currency: Currency | None = None,
) -> go.Figure:
    """Plot the value of every fund month by month.

    Brief:
        Shows which fund actually carried the portfolio, which
        the end-value donut alone cannot reveal.

    Arguments:
        fund_history_dataframe (pd.DataFrame): Fund history.
        is_dark_mode_bool (bool): Use the dark colour set.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        go.Figure: One stepped line per fund.
    """
    figure = go.Figure()
    fund_name_list = _collect_fund_name_list(fund_history_dataframe)
    for fund_name_str, fund_frame in fund_history_dataframe.groupby(
        "Fund"
    ):
        figure.add_trace(
            build_stepped_line_trace(
                fund_frame["Date"],
                fund_frame["Closing value"],
                str(fund_name_str),
                colour_str=resolve_fund_colour_str(
                    str(fund_name_str),
                    fund_name_list,
                    is_dark_mode_bool,
                ),
                dash_str=resolve_fund_dash_str(
                    str(fund_name_str), fund_name_list
                ),
                currency=currency,
            )
        )
    symbol_str = resolve_display_currency(currency).symbol_str
    figure.update_layout(
        template=PLOTLY_TEMPLATE_STR,
        height=SECONDARY_FIGURE_HEIGHT_INT,
        title="Value by fund over time",
        margin=dict(t=60, l=30, r=30, b=30),
        yaxis_title=f"Value ({symbol_str})",
        hovermode="x unified",
    )
    return apply_dense_grid_to_axes(figure)


def _add_target_weight_lines(
    figure: go.Figure,
    target_weight_dict: dict[str, float] | None,
) -> None:
    """Draw a dotted line at each configured target weight.

    Brief:
        Lets the reader see how far actual weights strayed.

    Arguments:
        figure (go.Figure): Figure being annotated.
        target_weight_dict (Optional[Dict[str, float]]): Targets.

    Returns:
        None: Lines are added in place.

    Warning:
        Zero targets are skipped, since a passive run has none.
    """
    for fund_name_str, target_float in (
        target_weight_dict or {}
    ).items():
        if float(target_float) <= 0.0:
            continue
        figure.add_hline(
            y=float(target_float),
            line_width=1,
            line_dash=TARGET_LINE_DASH_STR,
            line_color=TARGET_LINE_COLOUR_STR,
            annotation_text=f"target {fund_name_str}",
            annotation_position="right",
        )


def _build_weight_trace(
    fund_frame: pd.DataFrame,
    fund_name_str: str,
    fund_name_list: list[str],
    is_dark_mode_bool: bool = False,
) -> go.Scatter:
    """Build one fund's weight line.

    Brief:
        Colour and dash pattern both come from the fund's slot, so
        identity survives a reader who cannot separate the hues.

    Arguments:
        fund_frame (pd.DataFrame): Rows for one fund.
        fund_name_str (str): Fund being drawn.
        fund_name_list (List[str]): Every fund in the plan.
        is_dark_mode_bool (bool): Use the dark categorical set.

    Returns:
        go.Scatter: Configured weight line.

    Warning:
        Weights are ratios, so this trace is byte identical
        between the nominal and real runs and needs a distinct
        element key when rendered.
    """
    return go.Scatter(
        x=fund_frame["Date"],
        y=fund_frame["Weight %"],
        mode="lines",
        line=dict(
            width=2,
            color=resolve_fund_colour_str(
                fund_name_str, fund_name_list, is_dark_mode_bool
            ),
            dash=resolve_fund_dash_str(
                fund_name_str, fund_name_list
            ),
        ),
        name=fund_name_str,
        hovertemplate="%{x|%b %Y}<br>%{y:.2f}%<extra></extra>",
    )


def build_allocation_figure(
    fund_history_dataframe: pd.DataFrame,
    target_weight_dict: dict[str, float] | None = None,
    is_dark_mode_bool: bool = False,
) -> go.Figure:
    """Plot actual fund weights against their targets.

    Brief:
        Makes allocation drift, and whether rebalancing corrected
        it, visible directly.

    Arguments:
        fund_history_dataframe (pd.DataFrame): Per-fund history.
        target_weight_dict (Optional[Dict[str, float]]): Targets.
        is_dark_mode_bool (bool): Use the dark categorical set.

    Returns:
        go.Figure: Actual weights with dashed target lines.

    Warning:
        Target lines are omitted when no target was configured.
    """
    figure = go.Figure()
    fund_name_list = _collect_fund_name_list(fund_history_dataframe)
    for fund_name_str, fund_frame in fund_history_dataframe.groupby(
        "Fund"
    ):
        figure.add_trace(
            _build_weight_trace(
                fund_frame,
                str(fund_name_str),
                fund_name_list,
                is_dark_mode_bool,
            )
        )
    _add_target_weight_lines(figure, target_weight_dict)
    figure.update_layout(
        template=PLOTLY_TEMPLATE_STR,
        height=SECONDARY_FIGURE_HEIGHT_INT,
        title="Actual weight versus target",
        margin=dict(t=60, l=30, r=30, b=30),
        yaxis_title="Weight (%)",
        hovermode="x unified",
    )
    return apply_dense_grid_to_axes(figure)
