"""Money-weighted return (XIRR) over the simulated cash flows.

The engine reports the rate a fund *compounds* at, which is an input
assumption. Once step-ups, pauses, withdrawals or rebalancing are on,
the cash flow stream is irregular and only a money-weighted rate
describes what the investor actually earned. XIRR is also the figure
printed on an Indian consolidated account statement, so it is the
only number in this package a user can reconcile against a broker.

Sign convention, matching every spreadsheet XIRR():

    negative   money leaving the investor's pocket (instalments)
    positive   money reaching it (withdrawals, terminal corpus)

The engine records withdrawals *gross* and tracks tax and charges as
separate counters, so the post-tax series adds them back as outflows
in the month they were incurred rather than netting them off the
withdrawal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from investment_journey_simulator.constants import (
    DAYS_IN_YEAR_FLOAT,
    PERCENT_TOTAL_FLOAT,
    XIRR_BRACKET_MAXIMUM_FLOAT,
    XIRR_BRACKET_MINIMUM_FLOAT,
    XIRR_CONVERGENCE_TOLERANCE_FLOAT,
    XIRR_MAXIMUM_ITERATIONS_INT,
)
from investment_journey_simulator.models import (
    MonthlySnapshot,
    SimulationResult,
)
from investment_journey_simulator.time_utils import (
    build_month_start_dates_list,
)


@dataclass(frozen=True)
class CashFlow:
    """One dated movement of money in or out of the investor."""

    flow_date: date
    amount_float: float


def calculate_present_value_float(
    cash_flow_list: list[CashFlow],
    annual_rate_float: float,
) -> float:
    """Discount a dated cash flow series at a trial annual rate.

    Brief:
        Uses actual/365 day counting from the first flow, which is
        the convention spreadsheet XIRR() implements.

    Arguments:
        cash_flow_list (List[CashFlow]): Dated flows, any order.
        annual_rate_float (float): Trial annual rate as a fraction.

    Returns:
        float: Net present value of the series at that rate.

    Warning:
        Rates at or below minus one are undefined and are pushed
        just above the boundary instead of raising.
    """
    if not cash_flow_list:
        return 0.0
    safe_rate_float = max(-0.999999, float(annual_rate_float))
    base_date = cash_flow_list[0].flow_date
    present_value_float = 0.0
    for cash_flow in cash_flow_list:
        elapsed_years_float = (
            cash_flow.flow_date - base_date
        ).days / DAYS_IN_YEAR_FLOAT
        present_value_float += cash_flow.amount_float / (
            (1.0 + safe_rate_float) ** elapsed_years_float
        )
    return present_value_float


def _has_sign_change_bool(cash_flow_list: list[CashFlow]) -> bool:
    """Check that the series contains both an inflow and outflow.

    Brief:
        A series that never changes sign has no internal rate of
        return, so the solver must decline rather than diverge.

    Arguments:
        cash_flow_list (List[CashFlow]): Dated flows.

    Returns:
        bool: True when both signs are present.

    Warning:
        Exactly zero amounts count as neither sign.
    """
    has_negative_bool = any(
        flow.amount_float < 0.0 for flow in cash_flow_list
    )
    has_positive_bool = any(
        flow.amount_float > 0.0 for flow in cash_flow_list
    )
    return has_negative_bool and has_positive_bool


def _bracket_root_tuple(
    cash_flow_list: list[CashFlow],
) -> tuple[float, float] | None:
    """Find two rates whose present values straddle zero.

    Brief:
        Scans outward from the low bracket so that the bisection
        that follows is guaranteed to converge on a sign change.

    Arguments:
        cash_flow_list (List[CashFlow]): Dated flows.

    Returns:
        Optional[Tuple[float, float]]: Bracketing rates, or None
            when no sign change exists in the search range.

    Warning:
        Only the first bracket found is returned; series with
        multiple roots resolve to the lowest one.
    """
    step_float = 0.01
    lower_rate_float = XIRR_BRACKET_MINIMUM_FLOAT
    lower_value_float = calculate_present_value_float(
        cash_flow_list, lower_rate_float
    )
    while lower_rate_float < XIRR_BRACKET_MAXIMUM_FLOAT:
        upper_rate_float = min(
            lower_rate_float + step_float, XIRR_BRACKET_MAXIMUM_FLOAT
        )
        upper_value_float = calculate_present_value_float(
            cash_flow_list, upper_rate_float
        )
        if lower_value_float == 0.0:
            return lower_rate_float, lower_rate_float
        if lower_value_float * upper_value_float < 0.0:
            return lower_rate_float, upper_rate_float
        lower_rate_float = upper_rate_float
        lower_value_float = upper_value_float
        step_float = min(step_float * 1.5, 1.0)
    return None


def calculate_xirr_percent_float(
    cash_flow_list: list[CashFlow],
) -> float | None:
    """Solve the annual money-weighted return of a flow series.

    Brief:
        Brackets the root then bisects, which cannot diverge the
        way a bare Newton iteration does on the flat, near-zero
        gradients a long SIP series produces.

    Arguments:
        cash_flow_list (List[CashFlow]): Dated flows in any order.

    Returns:
        Optional[float]: Annual rate in percent, or None when the
            series has no sign change and therefore no rate.

    Warning:
        Returns None rather than a misleading zero when the series
        is degenerate; callers must render that as "not available".
    """
    if len(cash_flow_list) < 2:
        return None
    ordered_flow_list = sorted(
        cash_flow_list, key=lambda flow: flow.flow_date
    )
    if not _has_sign_change_bool(ordered_flow_list):
        return None
    bracket_tuple = _bracket_root_tuple(ordered_flow_list)
    if bracket_tuple is None:
        return None
    return (
        _bisect_root_float(ordered_flow_list, bracket_tuple)
        * PERCENT_TOTAL_FLOAT
    )


def _bisect_root_float(
    cash_flow_list: list[CashFlow],
    bracket_tuple: tuple[float, float],
) -> float:
    """Narrow a bracketed root by repeated halving.

    Brief:
        Bisection cannot diverge, which matters because the flat,
        near-zero gradients a long instalment series produces make
        a bare Newton iteration unreliable.

    Arguments:
        cash_flow_list (List[CashFlow]): Flows in date order.
        bracket_tuple (Tuple[float, float]): Straddling rates.

    Returns:
        float: Rate at which the present value is zero.

    Warning:
        Assumes the bracket really does straddle a sign change.
    """
    lower_rate_float, upper_rate_float = bracket_tuple
    for _iteration_int in range(XIRR_MAXIMUM_ITERATIONS_INT):
        midpoint_rate_float = (
            lower_rate_float + upper_rate_float
        ) / 2.0
        midpoint_value_float = calculate_present_value_float(
            cash_flow_list, midpoint_rate_float
        )
        if abs(midpoint_value_float) < (
            XIRR_CONVERGENCE_TOLERANCE_FLOAT
        ):
            return midpoint_rate_float
        lower_value_float = calculate_present_value_float(
            cash_flow_list, lower_rate_float
        )
        if lower_value_float * midpoint_value_float < 0.0:
            upper_rate_float = midpoint_rate_float
        else:
            lower_rate_float = midpoint_rate_float
    return (lower_rate_float + upper_rate_float) / 2.0


def _derive_month_close_date(month_date: date) -> date:
    """Return the settlement date of a month's closing balance.

    Brief:
        The engine values a month at its close, so a flow settled
        at month end is dated on the first day of the next month.
        Dating it at the month start instead compresses the elapsed
        time and inflates the solved rate.

    Arguments:
        month_date (date): First day of the simulated month.

    Returns:
        date: First day of the following month.

    Warning:
        December rolls the year over, so never add one to month.
    """
    return build_month_start_dates_list(month_date, 2)[1]


def _build_cash_flow_list(
    result: SimulationResult,
    terminal_value_float: float,
    sip_at_month_start_bool: bool,
    is_post_tax_bool: bool,
) -> list[CashFlow]:
    """Assemble the dated flow series of one simulation.

    Brief:
        Instalments are dated by their own timing switch, while
        withdrawals, levies and the closing corpus settle at month
        close because the engine grows the month first.

    Arguments:
        result (SimulationResult): Completed simulation.
        terminal_value_float (float): Closing corpus to append.
        sip_at_month_start_bool (bool): Instalment timing.
        is_post_tax_bool (bool): Subtract tax and charges.

    Returns:
        List[CashFlow]: Dated flows ready for the solver.

    Warning:
        Instalments and exits in the same month are separate flows
        on purpose; netting them would misdate one of the two.
    """
    cash_flow_list: list[CashFlow] = []
    for snapshot in result.monthly_snapshots_list:
        cash_flow_list.extend(
            _build_month_flow_list(
                snapshot, sip_at_month_start_bool, is_post_tax_bool
            )
        )
    if not result.monthly_snapshots_list:
        return cash_flow_list
    if float(terminal_value_float) == 0.0:
        return cash_flow_list
    final_close_date = _derive_month_close_date(
        result.monthly_snapshots_list[-1].month_date
    )
    cash_flow_list.append(
        CashFlow(final_close_date, float(terminal_value_float))
    )
    return cash_flow_list


def _build_month_flow_list(
    snapshot: MonthlySnapshot,
    sip_at_month_start_bool: bool,
    is_post_tax_bool: bool,
) -> list[CashFlow]:
    """Turn one month's flows into dated cash flows.

    Brief:
        The instalment and the exit are kept separate because they
        settle at different points inside the month.

    Arguments:
        snapshot (MonthlySnapshot): Month being converted.
        sip_at_month_start_bool (bool): Instalment timing.
        is_post_tax_bool (bool): Subtract tax and charges.

    Returns:
        List[CashFlow]: Zero, one or two dated flows.

    Warning:
        Zero-valued flows are dropped so the solver never sees a
        date that carries no money.
    """
    close_date = _derive_month_close_date(snapshot.month_date)
    month_flow_list: list[CashFlow] = []
    if snapshot.monthly_sip_float != 0.0:
        month_flow_list.append(
            CashFlow(
                snapshot.month_date
                if sip_at_month_start_bool
                else close_date,
                -snapshot.monthly_sip_float,
            )
        )
    exit_amount_float = snapshot.monthly_withdrawal_float
    if is_post_tax_bool:
        exit_amount_float -= (
            snapshot.monthly_tax_float
            + snapshot.monthly_charges_float
        )
    if exit_amount_float != 0.0:
        month_flow_list.append(
            CashFlow(close_date, exit_amount_float)
        )
    return month_flow_list


def build_pre_tax_cash_flow_list(
    result: SimulationResult,
    sip_at_month_start_bool: bool = True,
) -> list[CashFlow]:
    """Build the gross cash flow series of a simulation.

    Brief:
        Instalments leave the investor, gross withdrawals reach
        them, and the closing corpus is a terminal inflow. Tax and
        charges are excluded, so this is the headline rate.

    Arguments:
        result (SimulationResult): Completed simulation.
        sip_at_month_start_bool (bool): Instalment timing.

    Returns:
        List[CashFlow]: Dated flows ready for the solver.

    Warning:
        Ignores tax entirely; compare with the post-tax series to
        see what the levies actually cost.
    """
    return _build_cash_flow_list(
        result,
        result.ending_value_float,
        sip_at_month_start_bool,
        is_post_tax_bool=False,
    )


def build_post_tax_cash_flow_list(
    result: SimulationResult,
    sip_at_month_start_bool: bool = True,
) -> list[CashFlow]:
    """Build the cash flow series net of every levy.

    Brief:
        Adds realized tax and exit charges as outflows in the month
        they were incurred, and uses the post-tax corpus as the
        terminal inflow, so the rate is what the investor keeps.

    Arguments:
        result (SimulationResult): Completed simulation.
        sip_at_month_start_bool (bool): Instalment timing.

    Returns:
        List[CashFlow]: Dated flows ready for the solver.

    Warning:
        The terminal value only nets off exit tax when the final
        liquidation setting was enabled for the run.
    """
    return _build_cash_flow_list(
        result,
        result.post_tax_ending_value_float,
        sip_at_month_start_bool,
        is_post_tax_bool=True,
    )


def calculate_pre_tax_xirr_percent_float(
    result: SimulationResult,
    sip_at_month_start_bool: bool = True,
) -> float | None:
    """Money-weighted annual return before tax and charges.

    Brief:
        Convenience wrapper tying the gross series to the solver.

    Arguments:
        result (SimulationResult): Completed simulation.
        sip_at_month_start_bool (bool): Instalment timing.

    Returns:
        Optional[float]: Annual percent, or None when undefined.

    Warning:
        None means the plan never both paid in and took out.
    """
    return calculate_xirr_percent_float(
        build_pre_tax_cash_flow_list(
            result, sip_at_month_start_bool
        )
    )


def calculate_post_tax_xirr_percent_float(
    result: SimulationResult,
    sip_at_month_start_bool: bool = True,
) -> float | None:
    """Money-weighted annual return after tax and charges.

    Brief:
        The figure an investor can actually spend, and the one no
        mainstream Indian SIP calculator publishes.

    Arguments:
        result (SimulationResult): Completed simulation.
        sip_at_month_start_bool (bool): Instalment timing.

    Returns:
        Optional[float]: Annual percent, or None when undefined.

    Warning:
        Requires the final liquidation setting for the terminal
        corpus to be net of exit tax.
    """
    return calculate_xirr_percent_float(
        build_post_tax_cash_flow_list(
            result, sip_at_month_start_bool
        )
    )
