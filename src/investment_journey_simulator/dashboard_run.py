"""Bundling of one simulation run with its tables and figure."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from investment_journey_simulator.allocation import resolve_target_weight_dict
from investment_journey_simulator.charts import (
    build_allocation_figure,
    build_dashboard_figure,
    build_drawdown_figure,
    build_fund_history_figure,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.formatting import format_money_amount_str
from investment_journey_simulator.inflation import build_real_result
from investment_journey_simulator.ledgers import build_fund_history_dataframe
from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationResult,
    SimulationSettings,
)
from investment_journey_simulator.money_weighted import (
    calculate_post_tax_xirr_percent_float,
    calculate_pre_tax_xirr_percent_float,
)
from investment_journey_simulator.narrative import build_summary_lines_list
from investment_journey_simulator.tables import (
    build_fund_summary_dataframe,
    build_monthly_series_dataframe,
)

NOMINAL_LABEL_STR: str = "Nominal"
REAL_LABEL_STR: str = "Real"


@dataclass(frozen=True)
class DashboardRun:
    """One simulation run together with everything it renders."""

    label_str: str
    result: SimulationResult
    monthly_series_dataframe: pd.DataFrame
    fund_summary_dataframe: pd.DataFrame
    fund_history_dataframe: pd.DataFrame
    figure: go.Figure
    drawdown_figure: go.Figure
    fund_history_figure: go.Figure
    allocation_figure: go.Figure
    summary_lines_list: list[str]
    pre_tax_xirr_percent_float: float | None = None
    post_tax_xirr_percent_float: float | None = None
    currency: Currency | None = None
    # Carried on the bundle rather than passed to every view, so a
    # figure and the table beside it can never disagree about how
    # an amount is written.


def collect_rebalance_dates_list(
    simulation_result: SimulationResult,
) -> list:
    """List the months in which a rebalancing trade executed.

    Brief:
        Used to mark the growth chart so the reader can see when
        the portfolio was realigned.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        List: Month dates of every rebalancing event.

    Warning:
        Empty for a passive run.
    """
    return [
        rebalance_event.month_date
        for rebalance_event in simulation_result.rebalance_events_list
    ]


def collect_pause_dates_list(
    simulation_result: SimulationResult,
) -> list:
    """List the months in which no instalment was made.

    Brief:
        Detected from the series itself, so it needs no access to
        the pause settings. Months before the very first
        instalment are ignored, since nothing was paused yet.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        List: Month dates that received no contribution.

    Warning:
        A plan that legitimately stops contributing at the end
        will also be shaded.
    """
    snapshot_list = simulation_result.monthly_snapshots_list
    has_started_bool = False
    pause_dates_list = []
    for snapshot in snapshot_list:
        if snapshot.monthly_sip_float > 0.0:
            has_started_bool = True
            continue
        if has_started_bool:
            pause_dates_list.append(
                pd.Timestamp(snapshot.month_date)
            )
    return pause_dates_list


def build_dashboard_run(
    label_str: str,
    simulation_result: SimulationResult,
    figure_title_str: str,
    target_weight_dict: dict[str, float] | None = None,
    sip_at_month_start_bool: bool = True,
    is_dark_mode_bool: bool = False,
    currency: Currency | None = None,
) -> DashboardRun:
    """Derive tables, figure and summary lines from one result.

    Brief:
        Central place where a raw result becomes presentable, so
        screen and exports always show identical numbers.

    Arguments:
        label_str (str): Run label such as Nominal or Real.
        simulation_result (SimulationResult): Completed run.
        figure_title_str (str): Headline of the figure.
        target_weight_dict (Optional[Dict[str, float]]): Targets.
        sip_at_month_start_bool (bool): Instalment timing, needed
            to date the cash flows the money-weighted return uses.
        is_dark_mode_bool (bool): Colour the fund traces for a
            dark surface instead of a light one.
        currency (Optional[Currency]): Currency every amount
            is in, for the tables, figures and summary.

    Returns:
        DashboardRun: Bundle of result, tables and figures.

    Warning:
        Building the figures is the most expensive step here.
    """
    return _assemble_dashboard_run(
        label_str,
        simulation_result,
        figure_title_str,
        target_weight_dict,
        (
            build_monthly_series_dataframe(simulation_result),
            build_fund_summary_dataframe(simulation_result),
            build_fund_history_dataframe(simulation_result),
        ),
        sip_at_month_start_bool,
        is_dark_mode_bool,
        currency,
    )


def _assemble_dashboard_run(
    label_str: str,
    simulation_result: SimulationResult,
    figure_title_str: str,
    target_weight_dict: dict[str, float] | None,
    dataframe_tuple: tuple,
    sip_at_month_start_bool: bool = True,
    is_dark_mode_bool: bool = False,
    currency: Currency | None = None,
) -> DashboardRun:
    """Build every figure and pack the bundle.

    Arguments:
        label_str (str): Run label.
        simulation_result (SimulationResult): Completed run.
        figure_title_str (str): Headline of the figure.
        target_weight_dict (Optional[Dict[str, float]]): Targets.
        dataframe_tuple (tuple): Series, summary and history.
        sip_at_month_start_bool (bool): Instalment timing.
        is_dark_mode_bool (bool): Dark surface flag.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        DashboardRun: Fully populated bundle.
    """
    series_frame, summary_frame, history_frame = dataframe_tuple
    return DashboardRun(
        label_str=label_str,
        result=simulation_result,
        monthly_series_dataframe=series_frame,
        fund_summary_dataframe=summary_frame,
        fund_history_dataframe=history_frame,
        **_build_figure_dict(
            simulation_result,
            figure_title_str,
            target_weight_dict,
            dataframe_tuple,
            is_dark_mode_bool,
            currency,
        ),
        summary_lines_list=build_summary_lines_list(
            simulation_result, label_str, currency
        ),
        **_build_money_weighted_dict(
            simulation_result, sip_at_month_start_bool
        ),
        currency=currency,
    )


def _build_figure_dict(
    simulation_result: SimulationResult,
    figure_title_str: str,
    target_weight_dict: dict[str, float] | None,
    dataframe_tuple: tuple,
    is_dark_mode_bool: bool = False,
    currency: Currency | None = None,
) -> dict[str, go.Figure]:
    """Build every figure of one run.

    Brief:
        Split from the bundle assembler because drawing figures is
        the expensive half and keeping it separate keeps both
        functions inside the house length limit.

    Arguments:
        simulation_result (SimulationResult): Completed run.
        figure_title_str (str): Headline of the growth figure.
        target_weight_dict (Optional[Dict[str, float]]): Targets.
        dataframe_tuple (tuple): Series, summary and history.
        is_dark_mode_bool (bool): Dark surface flag.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        Dict[str, go.Figure]: Figures keyed to the bundle fields.

    Warning:
        Tuple order must match the bundle assembler.
    """
    series_frame, summary_frame, history_frame = dataframe_tuple
    return {
        "figure": build_dashboard_figure(
            series_frame,
            summary_frame,
            figure_title_str,
            collect_rebalance_dates_list(simulation_result),
            collect_pause_dates_list(simulation_result),
            currency,
        ),
        "drawdown_figure": build_drawdown_figure(series_frame),
        "fund_history_figure": build_fund_history_figure(
            history_frame, is_dark_mode_bool, currency
        ),
        "allocation_figure": build_allocation_figure(
            history_frame, target_weight_dict, is_dark_mode_bool
        ),
    }


def _build_money_weighted_dict(
    simulation_result: SimulationResult,
    sip_at_month_start_bool: bool,
) -> dict[str, float | None]:
    """Solve both money-weighted returns for one run.

    Brief:
        Computed once here rather than in the view, so the screen,
        the Excel export and the PDF can never disagree.

    Arguments:
        simulation_result (SimulationResult): Completed run.
        sip_at_month_start_bool (bool): Instalment timing.

    Returns:
        Dict[str, Optional[float]]: Both rates, keyed to match the
            bundle's field names.

    Warning:
        Either value is None when the plan never both paid in and
        took out, which callers must render as unavailable.
    """
    return {
        "pre_tax_xirr_percent_float": (
            calculate_pre_tax_xirr_percent_float(
                simulation_result, sip_at_month_start_bool
            )
        ),
        "post_tax_xirr_percent_float": (
            calculate_post_tax_xirr_percent_float(
                simulation_result, sip_at_month_start_bool
            )
        ),
    }


def build_figure_title_str(
    headline_label_str: str,
    simulation_result: SimulationResult,
    currency: Currency | None = None,
) -> str:
    """Compose the headline printed above a dashboard figure.

    Brief:
        Repeats the four headline totals so an exported image is
        readable without its surrounding page.

    Arguments:
        headline_label_str (str): Prefix such as Nominal or Real.
        simulation_result (SimulationResult): Completed run.
        currency (Optional[Currency]): Currency of totals.

    Returns:
        str: Single line headline for the figure.

    Warning:
        Long labels can wrap on narrow screens.
    """
    metric_pair_list = [
        ("End Value", simulation_result.ending_value_float),
        ("Invested", simulation_result.ending_invested_float),
        ("Withdrawn", simulation_result.ending_withdrawn_float),
        ("Tax Paid", simulation_result.ending_tax_paid_float),
    ]
    metric_text_list = [
        f"{metric_label_str}: "
        f"{format_money_amount_str(metric_value_float, currency)}"
        for metric_label_str, metric_value_float in metric_pair_list
    ]
    return f"{headline_label_str} | " + " | ".join(metric_text_list)


def simulate_nominal_run(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    is_dark_mode_bool: bool = False,
    currency: Currency | None = None,
) -> DashboardRun:
    """Simulate the plan in future rupees and bundle the output.

    Brief:
        This is the headline run shown at the top of the page.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio level rules.
        is_dark_mode_bool (bool): Dark surface flag.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        DashboardRun: Nominal run bundle.

    Warning:
        Nominal values ignore the erosion of purchasing power.
    """
    simulation_result = PortfolioSimulator(
        fund_configurations_list, settings
    ).run()
    return build_dashboard_run(
        NOMINAL_LABEL_STR,
        simulation_result,
        build_figure_title_str(
            NOMINAL_LABEL_STR, simulation_result, currency
        ),
        resolve_target_weight_dict(
            fund_configurations_list, settings.rebalance
        ),
        settings.sip_at_month_start_bool,
        is_dark_mode_bool,
        currency,
    )


def build_real_run(
    nominal_result: SimulationResult,
    inflation_percent_float: float,
    target_weight_dict: dict[str, float] | None = None,
    sip_at_month_start_bool: bool = True,
    is_dark_mode_bool: bool = False,
    currency: Currency | None = None,
) -> DashboardRun:
    """Restate a completed run in today's purchasing power.

    Brief:
        Deflates the nominal, after-tax result at the date of every
        cash flow instead of simulating a second time at a real
        rate, because tax law applies to nominal gains.

    Arguments:
        nominal_result (SimulationResult): Completed nominal run.
        inflation_percent_float (float): Annual inflation percent.
        target_weight_dict (Optional[Dict[str, float]]): Targets.
        sip_at_month_start_bool (bool): Instalment timing.
        is_dark_mode_bool (bool): Dark surface flag.
        currency (Optional[Currency]): Currency of amounts.

    Returns:
        DashboardRun: Inflation-adjusted run bundle.

    Warning:
        Realized gain classification stays nominal by design; only
        the purchasing power of each amount is restated.
    """
    real_result = build_real_result(
        nominal_result, inflation_percent_float
    )
    headline_label_str = (
        f"{REAL_LABEL_STR} | Inflation: "
        f"{inflation_percent_float:.2f}%"
    )
    return build_dashboard_run(
        REAL_LABEL_STR,
        real_result,
        build_figure_title_str(
            headline_label_str, real_result, currency
        ),
        target_weight_dict,
        sip_at_month_start_bool,
        is_dark_mode_bool,
        currency,
    )
