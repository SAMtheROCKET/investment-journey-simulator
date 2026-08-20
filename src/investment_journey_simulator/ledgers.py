"""Audit ledgers that expose every event behind the headline."""

from __future__ import annotations

import pandas as pd

from investment_journey_simulator.constants import MONTHS_IN_YEAR_INT
from investment_journey_simulator.models import SimulationResult

EVENT_DATE_COLUMN_STR: str = "Date"
EVENT_TRIGGER_COLUMN_STR: str = "Trigger"
VALUE_BEFORE_COLUMN_STR: str = "Value before"
VALUE_AFTER_COLUMN_STR: str = "Value after"
TAX_COLUMN_STR: str = "Tax realized"
WEIGHTS_BEFORE_COLUMN_STR: str = "Weights before %"
WEIGHTS_AFTER_COLUMN_STR: str = "Weights after %"
MAXIMUM_DRIFT_COLUMN_STR: str = "Max gap vs after %"
YEAR_COLUMN_STR: str = "Year"
FUND_COLUMN_STR: str = "Fund"
OPENING_VALUE_COLUMN_STR: str = "Opening value"
CLOSING_VALUE_COLUMN_STR: str = "Closing value"
CONTRIBUTED_COLUMN_STR: str = "Contributed"
WITHDRAWN_COLUMN_STR: str = "Withdrawn"
REQUESTED_COLUMN_STR: str = "Requested"
UNMET_COLUMN_STR: str = "Unmet"
COST_BASIS_COLUMN_STR: str = "Cost basis"
UNREALIZED_COLUMN_STR: str = "Unrealized gain"
WEIGHT_COLUMN_STR: str = "Weight %"


def format_weight_dict_str(weight_dict: dict[str, float]) -> str:
    """Render a weight mapping as a compact readable string.

    Brief:
        Keeps the ledger tables narrow enough to print.

    Arguments:
        weight_dict (Dict[str, float]): Fund to weight percent.

    Returns:
        str: Comma separated name and weight pairs.

    Warning:
        Ordering follows the mapping, not the fund table.
    """
    return ", ".join(
        f"{fund_name_str} {weight_float:.2f}"
        for fund_name_str, weight_float in weight_dict.items()
    )


def build_rebalance_ledger_dataframe(
    simulation_result: SimulationResult,
) -> pd.DataFrame:
    """Tabulate every rebalancing trade of a run.

    Brief:
        Shows what was worth what before and after each trade, what
        it cost in tax and how exactly it hit its target.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        pd.DataFrame: One row per executed rebalancing event.

    Warning:
        An empty frame means no rebalance ever executed.
    """
    return pd.DataFrame(
        [
            _build_rebalance_ledger_row_dict(rebalance_event)
            for rebalance_event in (
                simulation_result.rebalance_events_list
            )
        ]
    )


def _build_rebalance_ledger_row_dict(rebalance_event) -> dict:
    """Lay out one rebalancing event as a ledger row.

    Brief:
        Includes how far the trade actually moved each weight,
        which is the audit trail for an exact rebalance.

    Arguments:
        rebalance_event: Event recorded by the engine.

    Returns:
        dict: Column label to value mapping for one event.

    Warning:
        Weight strings are display text, not parseable data.
    """
    maximum_drift_float = 0.0
    for fund_name_str, weight_float in (
        rebalance_event.weights_after_dict.items()
    ):
        maximum_drift_float = max(
            maximum_drift_float,
            abs(
                weight_float
                - rebalance_event.weights_before_dict.get(
                    fund_name_str, 0.0
                )
            ),
        )
    return {
        EVENT_DATE_COLUMN_STR: rebalance_event.month_date,
        EVENT_TRIGGER_COLUMN_STR: (
            rebalance_event.trigger_reason_str
        ),
        VALUE_BEFORE_COLUMN_STR: rebalance_event.value_before_float,
        VALUE_AFTER_COLUMN_STR: rebalance_event.value_after_float,
        TAX_COLUMN_STR: rebalance_event.tax_amount_float,
        WEIGHTS_BEFORE_COLUMN_STR: format_weight_dict_str(
            rebalance_event.weights_before_dict
        ),
        WEIGHTS_AFTER_COLUMN_STR: format_weight_dict_str(
            rebalance_event.weights_after_dict
        ),
        MAXIMUM_DRIFT_COLUMN_STR: maximum_drift_float,
    }


def build_withdrawal_ledger_dataframe(
    simulation_result: SimulationResult,
) -> pd.DataFrame:
    """Tabulate every month in which a withdrawal was requested.

    Brief:
        Exposes the difference between what was asked for and what
        the portfolio could actually pay.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        pd.DataFrame: One row per month with a requested exit.

    Warning:
        An empty frame means withdrawals were never switched on.
    """
    ledger_row_list = [
        {
            EVENT_DATE_COLUMN_STR: snapshot.month_date,
            REQUESTED_COLUMN_STR: (
                snapshot.requested_withdrawal_float
            ),
            WITHDRAWN_COLUMN_STR: (
                snapshot.monthly_withdrawal_float
            ),
            UNMET_COLUMN_STR: snapshot.unmet_withdrawal_float,
            TAX_COLUMN_STR: snapshot.monthly_tax_float,
            CLOSING_VALUE_COLUMN_STR: (
                snapshot.portfolio_value_float
            ),
        }
        for snapshot in simulation_result.monthly_snapshots_list
        if snapshot.requested_withdrawal_float > 0.0
    ]
    return pd.DataFrame(ledger_row_list)


def build_annual_summary_dataframe(
    simulation_result: SimulationResult,
) -> pd.DataFrame:
    """Summarise the portfolio year by year.

    Brief:
        Compresses the monthly series into twelve-month blocks.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        pd.DataFrame: One row per investment year.

    Warning:
        A partial final year becomes its own short row.
    """
    snapshot_list = simulation_result.monthly_snapshots_list
    summary_row_list: list[dict] = []
    for year_index_int in range(
        0, len(snapshot_list), MONTHS_IN_YEAR_INT
    ):
        block_list = snapshot_list[
            year_index_int:year_index_int + MONTHS_IN_YEAR_INT
        ]
        summary_row_list.append(
            _build_annual_row_dict(
                block_list,
                year_index_int // MONTHS_IN_YEAR_INT + 1,
                0.0
                if year_index_int == 0
                else snapshot_list[
                    year_index_int - 1
                ].portfolio_value_float,
            )
        )
    return pd.DataFrame(summary_row_list)


def _build_annual_row_dict(
    block_list: list,
    year_number_int: int,
    opening_value_float: float,
) -> dict:
    """Aggregate one twelve-month block into a summary row.

    Brief:
        Flows are summed over the block; the closing value is the
        value of its last month.

    Arguments:
        block_list (list): Snapshots of one investment year.
        year_number_int (int): One-based year number.
        opening_value_float (float): Value before the block.

    Returns:
        dict: Column label to value mapping for one year.

    Warning:
        An empty block would raise; callers must not pass one.
    """
    return {
        YEAR_COLUMN_STR: year_number_int,
        OPENING_VALUE_COLUMN_STR: opening_value_float,
        CONTRIBUTED_COLUMN_STR: sum(
            snapshot.monthly_sip_float for snapshot in block_list
        ),
        WITHDRAWN_COLUMN_STR: sum(
            snapshot.monthly_withdrawal_float
            for snapshot in block_list
        ),
        TAX_COLUMN_STR: sum(
            snapshot.monthly_tax_float for snapshot in block_list
        ),
        CLOSING_VALUE_COLUMN_STR: (
            block_list[-1].portfolio_value_float
        ),
    }


def build_fund_history_dataframe(
    simulation_result: SimulationResult,
) -> pd.DataFrame:
    """Tabulate the month-by-month history of every fund.

    Brief:
        Feeds per-fund value charts and target-versus-actual
        weight analysis.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        pd.DataFrame: One row per fund per month.

    Warning:
        Long horizons with many funds produce large frames.
    """
    history_row_list: list[dict] = []
    for snapshot in simulation_result.monthly_snapshots_list:
        for fund_state in snapshot.fund_states_list:
            history_row_list.append(
                _build_fund_history_row_dict(
                    snapshot.month_date,
                    fund_state,
                    snapshot.portfolio_value_float,
                )
            )
    return pd.DataFrame(history_row_list)


def _build_fund_history_row_dict(
    month_date,
    fund_state,
    total_value_float: float,
) -> dict:
    """Lay out one fund-month as a history row.

    Brief:
        Adds the weight and the unrealized gain that the raw state
        does not carry directly.

    Arguments:
        month_date: Month being described.
        fund_state: Per-fund state of that month.
        total_value_float (float): Portfolio value that month.

    Returns:
        dict: Column label to value mapping for one fund-month.

    Warning:
        Weight is zero while the portfolio is empty.
    """
    weight_float = 0.0
    if total_value_float > 0.0:
        weight_float = (
            100.0 * fund_state.value_float / total_value_float
        )
    return {
        EVENT_DATE_COLUMN_STR: month_date,
        FUND_COLUMN_STR: fund_state.name_str,
        CLOSING_VALUE_COLUMN_STR: fund_state.value_float,
        WEIGHT_COLUMN_STR: weight_float,
        COST_BASIS_COLUMN_STR: fund_state.cost_basis_float,
        UNREALIZED_COLUMN_STR: (
            fund_state.value_float - fund_state.cost_basis_float
        ),
        CONTRIBUTED_COLUMN_STR: fund_state.contributed_float,
        WITHDRAWN_COLUMN_STR: fund_state.withdrawn_float,
        TAX_COLUMN_STR: fund_state.tax_float,
    }
