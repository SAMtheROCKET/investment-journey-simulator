"""Conversion of nominal results into present-day purchasing power.

Every rupee is deflated at the date it actually occurred, which is
the only correct way to express a multi-year cash-flow stream in
today's money. Taxes stay computed on nominal gains, because that is
how tax law works; only their purchasing power is restated here.
"""

from __future__ import annotations

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
)
from investment_journey_simulator.models import (
    FundMonthlyState,
    FundOutcome,
    MonthlySnapshot,
    RebalanceEvent,
    SimulationResult,
)


def calculate_deflation_factor_float(
    inflation_percent_float: float,
    elapsed_months_int: int,
) -> float:
    """Compute the price level after a number of months.

    Brief:
        Dividing a future rupee amount by this factor restates it
        in the purchasing power of the portfolio start date.

    Arguments:
        inflation_percent_float (float): Annual inflation percent.
        elapsed_months_int (int): Months since the start date.

    Returns:
        float: Price level factor, one at the start date.

    Warning:
        Inflation at or below minus one hundred percent is not
        meaningful and is clamped to keep the power defined.
    """
    inflation_rate_float = max(
        -0.9999,
        float(inflation_percent_float) / PERCENT_TOTAL_FLOAT,
    )
    elapsed_years_float = (
        max(0, int(elapsed_months_int)) / MONTHS_IN_YEAR_INT
    )
    return (1.0 + inflation_rate_float) ** elapsed_years_float


def _compound_segment_float(
    inflation_percent_float: float,
    months_int: int,
) -> float:
    """Grow the price level across one stretch of one rate.

    Brief:
        The building block of a varying series: each stretch
        compounds at its own rate for its own length.

    Arguments:
        inflation_percent_float (float): Annual percent in force.
        months_int (int): Length of the stretch in months.

    Returns:
        float: Price level multiplier for that stretch.

    Warning:
        A non-positive length contributes nothing.
    """
    if int(months_int) <= 0:
        return 1.0
    inflation_rate_float = max(
        -0.9999,
        float(inflation_percent_float) / PERCENT_TOTAL_FLOAT,
    )
    return (1.0 + inflation_rate_float) ** (
        int(months_int) / MONTHS_IN_YEAR_INT
    )


def calculate_varying_deflation_factor_float(
    inflation_schedule_tuple: tuple,
    elapsed_months_int: int,
    base_inflation_percent_float: float = 0.0,
) -> float:
    """Price level when inflation itself changes over time.

    Brief:
        Inflation is not one number for thirty years. Each entry
        names the month a new rate takes effect, and the price
        level compounds through each stretch at the rate that was
        actually in force - so a spike in one decade does not
        silently reprice the others.

    Arguments:
        inflation_schedule_tuple (tuple): Pairs of month index and
            annual percent, in any order.
        elapsed_months_int (int): Months since the start date.
        base_inflation_percent_float (float): Rate before the first
            entry takes effect.

    Returns:
        float: Price level factor, one at the start date.

    Warning:
        Entries dated after the month asked about are ignored, so a
        future spike never reprices the present. With an empty
        schedule this reduces exactly to the flat-rate factor.
    """
    horizon_months_int = max(0, int(elapsed_months_int))
    factor_float = 1.0
    cursor_month_int = 0
    rate_percent_float = float(base_inflation_percent_float)
    for month_int, percent_float in sorted(
        inflation_schedule_tuple
    ):
        change_month_int = max(0, int(month_int))
        if change_month_int >= horizon_months_int:
            break
        factor_float *= _compound_segment_float(
            rate_percent_float,
            change_month_int - cursor_month_int,
        )
        cursor_month_int = change_month_int
        rate_percent_float = float(percent_float)
    return factor_float * _compound_segment_float(
        rate_percent_float, horizon_months_int - cursor_month_int
    )


def deflate_amount_float(
    nominal_amount_float: float,
    inflation_percent_float: float,
    elapsed_months_int: int,
) -> float:
    """Restate one nominal amount in start-date rupees.

    Brief:
        Used for both stock values and individual cash flows.

    Arguments:
        nominal_amount_float (float): Amount in future rupees.
        inflation_percent_float (float): Annual inflation percent.
        elapsed_months_int (int): Months since the start date.

    Returns:
        float: Amount expressed in start-date purchasing power.

    Warning:
        Deflating a cumulative total by the final factor is wrong;
        deflate each flow at its own date and then accumulate.
    """
    return float(nominal_amount_float) / (
        calculate_deflation_factor_float(
            inflation_percent_float, elapsed_months_int
        )
    )


def build_real_fund_state_list(
    fund_state_list: list[FundMonthlyState],
    deflation_factor_float: float,
) -> list[FundMonthlyState]:
    """Deflate every per-fund figure of one month.

    Brief:
        Values, cost basis and the month's flows all share the same
        price level, so one factor deflates them all.

    Arguments:
        fund_state_list (List[FundMonthlyState]): Nominal states.
        deflation_factor_float (float): Price level of the month.

    Returns:
        List[FundMonthlyState]: States in start-date rupees.

    Warning:
        The factor must belong to the same month as the states.
    """
    return [
        FundMonthlyState(
            name_str=fund_state.name_str,
            value_float=(
                fund_state.value_float / deflation_factor_float
            ),
            cost_basis_float=(
                fund_state.cost_basis_float / deflation_factor_float
            ),
            contributed_float=(
                fund_state.contributed_float / deflation_factor_float
            ),
            withdrawn_float=(
                fund_state.withdrawn_float / deflation_factor_float
            ),
            tax_float=(
                fund_state.tax_float / deflation_factor_float
            ),
            charges_float=(
                fund_state.charges_float / deflation_factor_float
            ),
        )
        for fund_state in fund_state_list
    ]


def build_real_snapshots_list(
    monthly_snapshots_list: list[MonthlySnapshot],
    inflation_percent_float: float,
) -> list[MonthlySnapshot]:
    """Restate a whole monthly series in start-date rupees.

    Brief:
        Stocks deflate at their own month; cumulative totals are
        rebuilt by accumulating individually deflated flows.

    Arguments:
        monthly_snapshots_list (List[MonthlySnapshot]): Nominal.
        inflation_percent_float (float): Annual inflation.

    Returns:
        List[MonthlySnapshot]: Deflated monthly series.

    Warning:
        Snapshots must be in chronological order.
    """
    real_snapshot_list: list[MonthlySnapshot] = []
    cumulative_dict = {
        "invested": 0.0, "withdrawn": 0.0, "tax": 0.0,
    }
    for month_index_int, snapshot in enumerate(
        monthly_snapshots_list
    ):
        factor_float = calculate_deflation_factor_float(
            inflation_percent_float, month_index_int + 1
        )
        cumulative_dict = _accumulate_deflated_flows_dict(
            cumulative_dict, snapshot, factor_float
        )
        real_snapshot_list.append(
            _build_real_snapshot(
                snapshot, factor_float, cumulative_dict
            )
        )
    return real_snapshot_list


def _accumulate_deflated_flows_dict(
    cumulative_dict: dict,
    snapshot: MonthlySnapshot,
    factor_float: float,
) -> dict:
    """Add one month's deflated flows to the running totals.

    Brief:
        Deflating each flow before adding it is what makes the
        cumulative figures correct in real terms.

    Arguments:
        cumulative_dict (dict): Totals so far.
        snapshot (MonthlySnapshot): Month being added.
        factor_float (float): Price level of that month.

    Returns:
        dict: Updated running totals.

    Warning:
        Returns a new mapping; the input is not mutated.
    """
    return {
        "invested": cumulative_dict["invested"]
        + snapshot.monthly_sip_float / factor_float,
        "withdrawn": cumulative_dict["withdrawn"]
        + snapshot.monthly_withdrawal_float / factor_float,
        "tax": cumulative_dict["tax"]
        + snapshot.monthly_tax_float / factor_float,
    }


def _build_real_snapshot(
    snapshot: MonthlySnapshot,
    factor_float: float,
    cumulative_dict: dict,
) -> MonthlySnapshot:
    """Deflate one month and attach its cumulative totals.

    Brief:
        Cumulative figures come from the caller because they must
        accumulate already deflated flows.

    Arguments:
        snapshot (MonthlySnapshot): Nominal month.
        factor_float (float): Price level of that month.
        cumulative_dict (dict): Deflated running totals.

    Returns:
        MonthlySnapshot: Month in start-date rupees.

    Warning:
        The factor must belong to this month.
    """
    return MonthlySnapshot(
        month_date=snapshot.month_date,
        portfolio_value_float=(
            snapshot.portfolio_value_float / factor_float
        ),
        invested_amount_float=cumulative_dict["invested"],
        withdrawn_amount_float=cumulative_dict["withdrawn"],
        tax_paid_float=cumulative_dict["tax"],
        monthly_sip_float=(
            snapshot.monthly_sip_float / factor_float
        ),
        monthly_withdrawal_float=(
            snapshot.monthly_withdrawal_float / factor_float
        ),
        requested_withdrawal_float=(
            snapshot.requested_withdrawal_float / factor_float
        ),
        unmet_withdrawal_float=(
            snapshot.unmet_withdrawal_float / factor_float
        ),
        monthly_tax_float=(
            snapshot.monthly_tax_float / factor_float
        ),
        fund_states_list=build_real_fund_state_list(
            snapshot.fund_states_list, factor_float
        ),
    )


def build_real_fund_outcomes_list(
    simulation_result: SimulationResult,
    real_snapshots_list: list[MonthlySnapshot],
    inflation_percent_float: float,
) -> list[FundOutcome]:
    """Restate every per-fund outcome in start-date rupees.

    Brief:
        Closing stocks use the horizon price level, while invested,
        withdrawn and tax accumulate their deflated monthly flows.

    Arguments:
        simulation_result (SimulationResult): Nominal run.
        real_snapshots_list (List[MonthlySnapshot]): Deflated
            monthly series of the same run.
        inflation_percent_float (float): Annual inflation percent.

    Returns:
        List[FundOutcome]: Inflation-adjusted per-fund outcomes.

    Warning:
        Realized short and long term gains stay nominal, because
        their classification and taxation are legal quantities
        defined on nominal amounts.
    """
    horizon_factor_float = calculate_deflation_factor_float(
        inflation_percent_float, len(real_snapshots_list)
    )
    flow_total_dict = _build_real_flow_total_dict(real_snapshots_list)
    return [
        _build_real_fund_outcome(
            fund_outcome,
            horizon_factor_float,
            flow_total_dict.get(
                fund_outcome.name_str,
                {"invested": 0.0, "withdrawn": 0.0, "tax": 0.0},
            ),
        )
        for fund_outcome in simulation_result.fund_outcomes_list
    ]


def _build_real_fund_outcome(
    fund_outcome: FundOutcome,
    horizon_factor_float: float,
    flow_dict: dict,
) -> FundOutcome:
    """Restate one fund outcome in start-date rupees.

    Brief:
        Stocks divide by the horizon price level; flows arrive
        pre-deflated from the monthly series.

    Arguments:
        fund_outcome (FundOutcome): Nominal outcome.
        horizon_factor_float (float): Price level at the horizon.
        flow_dict (dict): Deflated flow totals for this fund.

    Returns:
        FundOutcome: Outcome in start-date purchasing power.

    Warning:
        Realized gain classification is left nominal on purpose.
    """
    return FundOutcome(
        name_str=fund_outcome.name_str,
        preset_str=fund_outcome.preset_str,
        start_date=fund_outcome.start_date,
        net_return_percent_float=(
            fund_outcome.net_return_percent_float
        ),
        invested_amount_float=flow_dict["invested"],
        withdrawn_amount_float=flow_dict["withdrawn"],
        ending_value_float=(
            fund_outcome.ending_value_float / horizon_factor_float
        ),
        tax_paid_float=flow_dict["tax"],
        short_term_gain_float=fund_outcome.short_term_gain_float,
        long_term_gain_float=fund_outcome.long_term_gain_float,
        **_build_real_cost_fields_dict(
            fund_outcome, horizon_factor_float
        ),
    )


def _build_real_cost_fields_dict(
    fund_outcome: FundOutcome,
    horizon_factor_float: float,
) -> dict:
    """Deflate the cost and charge fields of one outcome.

    Brief:
        Basis, exit costs and charges are all stocks measured at
        the horizon, so one factor deflates them.

    Arguments:
        fund_outcome (FundOutcome): Nominal outcome.
        horizon_factor_float (float): Price level at the horizon.

    Returns:
        dict: Keyword arguments for the real outcome.

    Warning:
        Realized loss is a legal quantity and stays nominal.
    """
    return {
        "cost_basis_float": (
            fund_outcome.cost_basis_float / horizon_factor_float
        ),
        "final_liquidation_tax_float": (
            fund_outcome.final_liquidation_tax_float
            / horizon_factor_float
        ),
        "final_liquidation_charges_float": (
            fund_outcome.final_liquidation_charges_float
            / horizon_factor_float
        ),
        "realized_loss_float": fund_outcome.realized_loss_float,
        "charges_paid_float": (
            fund_outcome.charges_paid_float / horizon_factor_float
        ),
    }


def _build_real_flow_total_dict(
    real_snapshots_list: list[MonthlySnapshot],
) -> dict:
    """Accumulate deflated per-fund flows across the horizon.

    Brief:
        Contributions, withdrawals and tax must be summed after
        deflation, never deflated after summing.

    Arguments:
        real_snapshots_list (List[MonthlySnapshot]): Deflated
            monthly series.

    Returns:
        dict: Fund name to accumulated flow totals.

    Warning:
        Funds absent from the series are absent from the mapping.
    """
    flow_total_dict: dict = {}
    for snapshot in real_snapshots_list:
        for fund_state in snapshot.fund_states_list:
            totals_dict = flow_total_dict.setdefault(
                fund_state.name_str,
                {"invested": 0.0, "withdrawn": 0.0, "tax": 0.0},
            )
            totals_dict["invested"] += fund_state.contributed_float
            totals_dict["withdrawn"] += fund_state.withdrawn_float
            totals_dict["tax"] += fund_state.tax_float
    return flow_total_dict


def build_real_result(
    simulation_result: SimulationResult,
    inflation_percent_float: float,
) -> SimulationResult:
    """Restate a whole simulation in start-date purchasing power.

    Brief:
        Produces the inflation-adjusted twin of a nominal run
        without simulating anything a second time.

    Arguments:
        simulation_result (SimulationResult): Nominal run.
        inflation_percent_float (float): Annual inflation percent.

    Returns:
        SimulationResult: The same run, expressed in real rupees.

    Warning:
        Rebalancing ledger amounts are deflated at their own event
        dates, but their weight percentages are left untouched
        because ratios are unaffected by inflation.
    """
    real_snapshots_list = build_real_snapshots_list(
        simulation_result.monthly_snapshots_list,
        inflation_percent_float,
    )
    return SimulationResult(
        monthly_snapshots_list=real_snapshots_list,
        fund_outcomes_list=build_real_fund_outcomes_list(
            simulation_result,
            real_snapshots_list,
            inflation_percent_float,
        ),
        rebalance_events_list=_build_real_event_list(
            simulation_result, inflation_percent_float
        ),
    )


def _build_real_event_list(
    simulation_result: SimulationResult,
    inflation_percent_float: float,
) -> list[RebalanceEvent]:
    """Deflate the rupee amounts of every rebalancing event.

    Brief:
        Each event is deflated at its own month.

    Arguments:
        simulation_result (SimulationResult): Nominal run.
        inflation_percent_float (float): Annual inflation.

    Returns:
        List[RebalanceEvent]: Events in start-date rupees.

    Warning:
        Weights are ratios and are copied unchanged.
    """
    month_index_by_date_dict = {
        snapshot.month_date: month_index_int
        for month_index_int, snapshot in enumerate(
            simulation_result.monthly_snapshots_list
        )
    }
    return [
        _build_real_event(
            rebalance_event,
            calculate_deflation_factor_float(
                inflation_percent_float,
                month_index_by_date_dict.get(
                    rebalance_event.month_date, 0
                )
                + 1,
            ),
        )
        for rebalance_event in simulation_result.rebalance_events_list
    ]


def _build_real_event(
    rebalance_event: RebalanceEvent,
    factor_float: float,
) -> RebalanceEvent:
    """Deflate the rupee amounts of one rebalancing event.

    Brief:
        Weights are ratios, so only the amounts are restated.

    Arguments:
        rebalance_event (RebalanceEvent): Nominal event.
        factor_float (float): Price level of its month.

    Returns:
        RebalanceEvent: Event in start-date rupees.

    Warning:
        The factor must belong to the event's own month.
    """
    return RebalanceEvent(
        month_date=rebalance_event.month_date,
        value_before_float=(
            rebalance_event.value_before_float / factor_float
        ),
        value_after_float=(
            rebalance_event.value_after_float / factor_float
        ),
        tax_amount_float=(
            rebalance_event.tax_amount_float / factor_float
        ),
        weights_before_dict=rebalance_event.weights_before_dict,
        weights_after_dict=rebalance_event.weights_after_dict,
        trigger_reason_str=rebalance_event.trigger_reason_str,
    )
