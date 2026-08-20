"""Conversion of simulation results into presentable tables."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from investment_journey_simulator.constants import (
    SERIES_INVESTED_STR,
    SERIES_MONTH_STR,
    SERIES_MONTHLY_CHARGES_STR,
    SERIES_MONTHLY_SIP_STR,
    SERIES_MONTHLY_TAX_STR,
    SERIES_MONTHLY_WITHDRAWAL_STR,
    SERIES_PORTFOLIO_VALUE_STR,
    SERIES_REQUESTED_WITHDRAWAL_STR,
    SERIES_TAX_PAID_STR,
    SERIES_UNMET_WITHDRAWAL_STR,
    SERIES_WITHDRAWN_STR,
    SUMMARY_CHARGES_STR,
    SUMMARY_ENDING_VALUE_STR,
    SUMMARY_EXIT_COST_STR,
    SUMMARY_FUND_NAME_STR,
    SUMMARY_GAIN_STR,
    SUMMARY_INVESTED_STR,
    SUMMARY_LONG_TERM_GAIN_STR,
    SUMMARY_NET_RETURN_STR,
    SUMMARY_PRESET_STR,
    SUMMARY_REALIZED_LOSS_STR,
    SUMMARY_SHORT_TERM_GAIN_STR,
    SUMMARY_START_STR,
    SUMMARY_TAX_PAID_STR,
    SUMMARY_UNREALIZED_GAIN_STR,
    SUMMARY_WEALTH_STR,
    SUMMARY_WITHDRAWN_STR,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.formatting import format_money_amount_str
from investment_journey_simulator.models import FundOutcome, SimulationResult


def build_monthly_series_dataframe(
    simulation_result: SimulationResult,
) -> pd.DataFrame:
    """Lay out the monthly snapshots as an export-ready table.

    Brief:
        One row per simulated month with cumulative totals and the
        cash flows of that month.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        pd.DataFrame: Monthly series with labelled columns.

    Warning:
        Amounts stay numeric here so that spreadsheets can chart
        them; formatting happens only in display helpers.
    """
    column_reader_dict = _build_series_reader_dict()
    return pd.DataFrame(
        {
            column_name_str: [
                read_value(snapshot)
                for snapshot in (
                    simulation_result.monthly_snapshots_list
                )
            ]
            for column_name_str, read_value in (
                column_reader_dict.items()
            )
        }
    )


def _build_series_reader_dict() -> dict:
    """Map every series column to the field it reads.

    Brief:
        Keeps the column set in one place so exports, charts and
        the workbook can never disagree about it.

    Arguments:
        None.

    Returns:
        dict: Column label to snapshot reader mapping.

    Warning:
        Adding a column here changes every export at once.
    """
    return {
        SERIES_MONTH_STR: lambda row: row.month_date,
        SERIES_PORTFOLIO_VALUE_STR: (
            lambda row: row.portfolio_value_float
        ),
        SERIES_INVESTED_STR: lambda row: row.invested_amount_float,
        SERIES_WITHDRAWN_STR: (
            lambda row: row.withdrawn_amount_float
        ),
        SERIES_TAX_PAID_STR: lambda row: row.tax_paid_float,
        SERIES_MONTHLY_SIP_STR: lambda row: row.monthly_sip_float,
        SERIES_MONTHLY_WITHDRAWAL_STR: (
            lambda row: row.monthly_withdrawal_float
        ),
        SERIES_REQUESTED_WITHDRAWAL_STR: (
            lambda row: row.requested_withdrawal_float
        ),
        SERIES_UNMET_WITHDRAWAL_STR: (
            lambda row: row.unmet_withdrawal_float
        ),
        SERIES_MONTHLY_TAX_STR: lambda row: row.monthly_tax_float,
        SERIES_MONTHLY_CHARGES_STR: (
            lambda row: row.monthly_charges_float
        ),
    }


def build_fund_summary_dataframe(
    simulation_result: SimulationResult,
) -> pd.DataFrame:
    """Lay out the per-fund outcomes as an export-ready table.

    Brief:
        One row per fund with invested principal, exits, closing
        value, realized tax and the gain classification split.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        pd.DataFrame: Per-fund summary with labelled columns.

    Warning:
        Gains are gross figures; the tax column is not netted off.
    """
    summary_row_list: list[dict] = [
        build_fund_summary_row_dict(fund_outcome)
        for fund_outcome in simulation_result.fund_outcomes_list
    ]
    return pd.DataFrame(summary_row_list)


def build_fund_summary_row_dict(fund_outcome: FundOutcome) -> dict:
    """Lay out one fund outcome as a labelled summary row.

    Brief:
        Keeps the column labels of the per-fund table in a single
        place shared by the screen and both exports.

    Arguments:
        fund_outcome (FundOutcome): End-of-horizon fund summary.

    Returns:
        dict: Column label to value mapping for one fund.

    Warning:
        Amounts stay numeric so that exports can format them.
    """
    return {
        SUMMARY_FUND_NAME_STR: fund_outcome.name_str,
        SUMMARY_PRESET_STR: fund_outcome.preset_str,
        SUMMARY_START_STR: fund_outcome.start_date.isoformat(),
        SUMMARY_NET_RETURN_STR: (
            fund_outcome.net_return_percent_float
        ),
        SUMMARY_INVESTED_STR: fund_outcome.invested_amount_float,
        SUMMARY_WITHDRAWN_STR: fund_outcome.withdrawn_amount_float,
        SUMMARY_ENDING_VALUE_STR: fund_outcome.ending_value_float,
        SUMMARY_WEALTH_STR: fund_outcome.wealth_generated_float,
        SUMMARY_GAIN_STR: fund_outcome.gain_amount_float,
        SUMMARY_TAX_PAID_STR: fund_outcome.tax_paid_float,
        SUMMARY_SHORT_TERM_GAIN_STR: (
            fund_outcome.short_term_gain_float
        ),
        SUMMARY_LONG_TERM_GAIN_STR: (
            fund_outcome.long_term_gain_float
        ),
        SUMMARY_REALIZED_LOSS_STR: fund_outcome.realized_loss_float,
        SUMMARY_UNREALIZED_GAIN_STR: (
            fund_outcome.unrealized_gain_float
        ),
        SUMMARY_CHARGES_STR: fund_outcome.charges_paid_float,
        SUMMARY_EXIT_COST_STR: (
            fund_outcome.final_liquidation_tax_float
            + fund_outcome.final_liquidation_charges_float
        ),
    }


def format_money_columns_dataframe(
    source_dataframe: pd.DataFrame,
    money_column_names_iterable: Iterable[str],
    currency: Currency | None = None,
) -> pd.DataFrame:
    """Render selected numeric columns as money strings.

    Brief:
        Produces a display copy so that the numeric table stays
        available for charts and exports.

    Arguments:
        source_dataframe (pd.DataFrame): Table to copy.
        money_column_names_iterable (Iterable[str]): Columns to
            convert into money strings.
        currency (Optional[Currency]): Currency to render in.

    Returns:
        pd.DataFrame: Copy with the chosen columns formatted.

    Warning:
        Columns absent from the table are skipped silently.
    """
    display_dataframe = source_dataframe.copy()
    for column_name_str in money_column_names_iterable:
        if column_name_str not in display_dataframe.columns:
            continue
        display_dataframe[column_name_str] = display_dataframe[
            column_name_str
        ].apply(
            lambda amount_float: format_money_amount_str(
                amount_float, currency
            )
        )
    return display_dataframe
