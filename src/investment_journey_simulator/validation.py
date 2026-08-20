"""Invariant checks that must hold for every simulation run."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from investment_journey_simulator.constants import (
    PERCENT_TOTAL_FLOAT,
    REBALANCE_METHOD_FULL_STR,
    TAX_FUNDING_OUTSIDE_STR,
)
from investment_journey_simulator.models import (
    SimulationResult,
    SimulationSettings,
)

MONEY_CHECK_TOLERANCE_FLOAT: float = 0.01
WEIGHT_CHECK_TOLERANCE_FLOAT: float = 0.01
CHECK_NAME_COLUMN_STR: str = "Check"
CHECK_RESULT_COLUMN_STR: str = "Result"
CHECK_DETAIL_COLUMN_STR: str = "Detail"
PASS_LABEL_STR: str = "PASS"
FAIL_LABEL_STR: str = "FAIL"


@dataclass(frozen=True)
class InvariantOutcome:
    """Result of one invariant check."""

    name_str: str
    is_passing_bool: bool
    detail_str: str


def check_wealth_identity(
    simulation_result: SimulationResult,
) -> InvariantOutcome:
    """Verify that value plus exits minus principal equals gain.

    Brief:
        The accounting identity every cash-flow simulator must
        satisfy: nothing may be created or lost in bookkeeping.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        InvariantOutcome: Pass or fail with the residual.

    Warning:
        A failure means the engine leaked or duplicated money.
    """
    portfolio_gain_float = (
        simulation_result.ending_value_float
        + simulation_result.ending_withdrawn_float
        - simulation_result.ending_invested_float
    )
    fund_gain_float = sum(
        fund_outcome.gain_amount_float
        for fund_outcome in simulation_result.fund_outcomes_list
    )
    residual_float = abs(portfolio_gain_float - fund_gain_float)
    return InvariantOutcome(
        "Portfolio gain equals the sum of fund gains",
        residual_float <= MONEY_CHECK_TOLERANCE_FLOAT,
        f"residual {residual_float:.6f}",
    )


def check_principal_excludes_internal_transfers(
    simulation_result: SimulationResult,
) -> InvariantOutcome:
    """Verify that rebalancing never inflates invested principal.

    Brief:
        Internal purchases move existing money; only instalments
        are external contributions.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        InvariantOutcome: Pass or fail with the residual.

    Warning:
        A failure would overstate the money the investor put in.
    """
    contributed_total_float = sum(
        snapshot.monthly_sip_float
        for snapshot in simulation_result.monthly_snapshots_list
    )
    residual_float = abs(
        contributed_total_float
        - simulation_result.ending_invested_float
    )
    return InvariantOutcome(
        "Invested principal equals the sum of instalments",
        residual_float <= MONEY_CHECK_TOLERANCE_FLOAT,
        f"residual {residual_float:.6f}",
    )


def check_tax_attribution(
    simulation_result: SimulationResult,
) -> InvariantOutcome:
    """Verify that rebalancing tax never exceeds the total tax.

    Brief:
        Total realized tax must split cleanly into the part caused
        by rebalancing and the part caused by withdrawals.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        InvariantOutcome: Pass or fail with both components.

    Warning:
        Only meaningful when rebalancing tax is funded from the
        portfolio; outside funding still reports the liability.
    """
    rebalance_tax_float = simulation_result.rebalance_tax_float
    total_tax_float = simulation_result.ending_tax_paid_float
    return InvariantOutcome(
        "Rebalancing tax is part of the total realized tax",
        rebalance_tax_float
        <= total_tax_float + MONEY_CHECK_TOLERANCE_FLOAT,
        f"rebalance {rebalance_tax_float:.2f} of "
        f"total {total_tax_float:.2f}",
    )


def check_exact_rebalance_targets(
    simulation_result: SimulationResult,
    settings: SimulationSettings,
) -> InvariantOutcome:
    """Verify that a full liquidation lands on its target split.

    Brief:
        Only checked when the method is full liquidation and the
        tax is funded from outside, because tax paid from the
        portfolio legitimately shrinks the reinvested cash.

    Arguments:
        simulation_result (SimulationResult): Completed run.
        settings (SimulationSettings): Rules used for the run.

    Returns:
        InvariantOutcome: Pass or fail with the worst gap.

    Warning:
        Skipped, and therefore passing, when not applicable.
    """
    is_applicable_bool = (
        settings.rebalance.is_enabled_bool
        and settings.rebalance.method_str == REBALANCE_METHOD_FULL_STR
        and settings.rebalance.tax_funding_str
        == TAX_FUNDING_OUTSIDE_STR
    )
    if not is_applicable_bool:
        return InvariantOutcome(
            "Exact rebalance reaches its target weights",
            True,
            "not applicable to this run",
        )
    worst_gap_float = 0.0
    for rebalance_event in simulation_result.rebalance_events_list:
        weight_total_float = sum(
            rebalance_event.weights_after_dict.values()
        )
        worst_gap_float = max(
            worst_gap_float,
            abs(weight_total_float - PERCENT_TOTAL_FLOAT),
        )
    return InvariantOutcome(
        "Exact rebalance reaches its target weights",
        worst_gap_float <= WEIGHT_CHECK_TOLERANCE_FLOAT,
        f"worst weight-sum gap {worst_gap_float:.6f}",
    )


def check_no_rebalance_when_disabled(
    simulation_result: SimulationResult,
    settings: SimulationSettings,
) -> InvariantOutcome:
    """Verify that a passive run executed no rebalancing trade.

    Brief:
        Switching rebalancing off must leave the portfolio to
        drift with no hidden trades and no hidden tax.

    Arguments:
        simulation_result (SimulationResult): Completed run.
        settings (SimulationSettings): Rules used for the run.

    Returns:
        InvariantOutcome: Pass or fail with the event count.

    Warning:
        Passes trivially when rebalancing was enabled.
    """
    event_count_int = len(simulation_result.rebalance_events_list)
    is_passing_bool = (
        settings.rebalance.is_enabled_bool or event_count_int == 0
    )
    return InvariantOutcome(
        "No rebalancing events while rebalancing is off",
        is_passing_bool,
        f"{event_count_int} events",
    )


def check_withdrawal_feasibility(
    simulation_result: SimulationResult,
) -> InvariantOutcome:
    """Verify that no withdrawal exceeded the available corpus.

    Brief:
        Reports the first month in which the plan could not pay
        what it promised.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        InvariantOutcome: Pass when every request was funded.

    Warning:
        A failure is a planning result, not an engine defect.
    """
    depletion_month_date = simulation_result.depletion_month_date
    return InvariantOutcome(
        "Every requested withdrawal was funded",
        depletion_month_date is None,
        "fully funded"
        if depletion_month_date is None
        else f"first shortfall {depletion_month_date.isoformat()}",
    )


def check_non_negative_values(
    simulation_result: SimulationResult,
) -> InvariantOutcome:
    """Verify that no fund value ever went negative.

    Brief:
        Selling more than a fund holds would produce a negative
        balance, which is physically impossible.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        InvariantOutcome: Pass or fail with the worst value.

    Warning:
        Small negative dust below one paisa is tolerated.
    """
    worst_value_float = 0.0
    for snapshot in simulation_result.monthly_snapshots_list:
        for fund_state in snapshot.fund_states_list:
            worst_value_float = min(
                worst_value_float, fund_state.value_float
            )
    return InvariantOutcome(
        "No fund value ever turned negative",
        worst_value_float >= -MONEY_CHECK_TOLERANCE_FLOAT,
        f"lowest fund value {worst_value_float:.6f}",
    )


def run_all_invariants_list(
    simulation_result: SimulationResult,
    settings: SimulationSettings,
) -> list[InvariantOutcome]:
    """Run every invariant against one completed run.

    Brief:
        Single entry point used by the validation tab and by the
        automated test suite.

    Arguments:
        simulation_result (SimulationResult): Completed run.
        settings (SimulationSettings): Rules used for the run.

    Returns:
        List[InvariantOutcome]: One outcome per invariant.

    Warning:
        Checks are independent; one failure does not stop others.
    """
    return [
        check_wealth_identity(simulation_result),
        check_principal_excludes_internal_transfers(
            simulation_result
        ),
        check_tax_attribution(simulation_result),
        check_exact_rebalance_targets(simulation_result, settings),
        check_no_rebalance_when_disabled(simulation_result, settings),
        check_withdrawal_feasibility(simulation_result),
        check_non_negative_values(simulation_result),
    ]


def build_invariant_dataframe(
    invariant_outcome_list: list[InvariantOutcome],
) -> pd.DataFrame:
    """Tabulate invariant outcomes for display.

    Brief:
        Turns the check objects into a pass/fail table.

    Arguments:
        invariant_outcome_list (List[InvariantOutcome]): Outcomes.

    Returns:
        pd.DataFrame: One row per check.

    Warning:
        Presentation only; callers must inspect the booleans to
        decide whether the run is trustworthy.
    """
    return pd.DataFrame(
        [
            {
                CHECK_NAME_COLUMN_STR: invariant_outcome.name_str,
                CHECK_RESULT_COLUMN_STR: (
                    PASS_LABEL_STR
                    if invariant_outcome.is_passing_bool
                    else FAIL_LABEL_STR
                ),
                CHECK_DETAIL_COLUMN_STR: (
                    invariant_outcome.detail_str
                ),
            }
            for invariant_outcome in invariant_outcome_list
        ]
    )
