"""Inverse solving: what input reaches a target corpus?

The engine answers "what will this plan be worth?". Every real
question is the other way round - "what instalment reaches two
crore in fifteen years?" - so this module drives the engine
backwards by bisection.

Bisection is used rather than a closed form on purpose. A closed
form exists only for the simplest plan; once step-ups, pauses,
withdrawals, rebalancing, expense ratios and tax are switched on
there is no formula, but the corpus is still monotone in each of
the three inputs solved here, which is all bisection needs.
"""

from __future__ import annotations

from dataclasses import replace

from investment_journey_simulator.constants import (
    GOAL_SEEK_MAXIMUM_ITERATIONS_INT,
    GOAL_SEEK_MAXIMUM_RETURN_PERCENT_FLOAT,
    GOAL_SEEK_MAXIMUM_SIP_FLOAT,
    GOAL_SEEK_MAXIMUM_YEARS_INT,
    GOAL_SEEK_TOLERANCE_FLOAT,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationSettings,
)


def _measure_corpus_float(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    use_post_tax_bool: bool,
) -> float:
    """Run the engine once and read the corpus it produces.

    Brief:
        The post-tax reading is what an investor can spend, so it
        is the honest target for a goal that must actually be met.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        use_post_tax_bool (bool): Read the corpus net of exit tax.

    Returns:
        float: Closing corpus of that plan.

    Warning:
        The post-tax reading is zero-effect unless the final
        liquidation switch is enabled in the settings.
    """
    result = PortfolioSimulator(
        fund_configurations_list, settings
    ).run()
    if use_post_tax_bool:
        return result.post_tax_ending_value_float
    return result.ending_value_float


def _bisect_input_float(
    measure_corpus_float,
    target_corpus_float: float,
    lower_bound_float: float,
    upper_bound_float: float,
) -> float | None:
    """Find the input value that reaches a target corpus.

    Brief:
        Assumes the corpus rises monotonically with the input,
        which holds for the instalment, the return and the
        horizon.

    Arguments:
        measure_corpus_float: Callable mapping input to corpus.
        target_corpus_float (float): Corpus to reach.
        lower_bound_float (float): Smallest input to consider.
        upper_bound_float (float): Largest input to consider.

    Returns:
        Optional[float]: Solved input, or None when even the
            largest input in range falls short of the target.

    Warning:
        Returns None rather than the upper bound when the goal is
        unreachable, so callers never present a bound as a result.
    """
    if measure_corpus_float(upper_bound_float) < target_corpus_float:
        return None
    if measure_corpus_float(lower_bound_float) >= target_corpus_float:
        return lower_bound_float
    for _iteration_int in range(GOAL_SEEK_MAXIMUM_ITERATIONS_INT):
        midpoint_float = (
            lower_bound_float + upper_bound_float
        ) / 2.0
        if measure_corpus_float(midpoint_float) < (
            target_corpus_float
        ):
            lower_bound_float = midpoint_float
        else:
            upper_bound_float = midpoint_float
        if (
            upper_bound_float - lower_bound_float
        ) < GOAL_SEEK_TOLERANCE_FLOAT:
            break
    return upper_bound_float


def _scale_instalments_list(
    fund_configurations_list: list[FundConfiguration],
    scale_float: float,
) -> list[FundConfiguration]:
    """Multiply every fund's instalment by one factor.

    Brief:
        Scaling uniformly preserves the plan's contribution mix,
        so only the overall size of the plan is being solved for.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        scale_float (float): Factor to apply to each instalment.

    Returns:
        List[FundConfiguration]: Rescaled copies of the funds.

    Warning:
        Returns copies; the caller's funds are left untouched.
    """
    return [
        replace(
            fund,
            monthly_sip_float=(
                fund.monthly_sip_float * scale_float
            ),
        )
        for fund in fund_configurations_list
    ]


def _scale_settings_instalments(
    settings: SimulationSettings,
    scale_float: float,
) -> SimulationSettings:
    """Multiply every dated instalment change by one factor.

    Brief:
        A plan built on the event rail carries no instalment on
        its funds at all: every rupee arrives as a dated override.
        Scaling only the funds would therefore scale nothing, and
        the solver would report that no contribution reaches the
        target however large it grew.

    Arguments:
        settings (SimulationSettings): Portfolio rules.
        scale_float (float): Factor to apply to each instalment.

    Returns:
        SimulationSettings: Copy with its instalments rescaled.

    Warning:
        One-off contributions are deliberately left alone. A bonus
        is not part of "how much do I invest each month", and
        scaling it would answer a question nobody asked.
    """
    if not settings.instalment_override_list:
        return settings
    return replace(
        settings,
        instalment_override_list=[
            replace(
                override,
                amount_float=override.amount_float * scale_float,
            )
            for override in settings.instalment_override_list
        ],
    )


def read_base_monthly_amount_float(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
) -> float:
    """The monthly contribution a plan opens with.

    Brief:
        Reads whichever source owns the amounts, so the solver can
        report a figure a reader recognises whether their plan came
        from the classic dashboard or the event rail.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.

    Returns:
        float: Opening monthly contribution across the portfolio.

    Warning:
        Reports the opening amount. A plan that steps up later
        contributes more than this in every year after the first.
    """
    fund_total_float = sum(
        fund.monthly_sip_float
        for fund in fund_configurations_list
    )
    if fund_total_float > 0.0:
        return fund_total_float
    opening_list = sorted(
        settings.instalment_override_list,
        key=lambda override: override.month_index_int,
    )
    return (
        float(opening_list[0].amount_float) if opening_list else 0.0
    )


def solve_required_monthly_sip_float(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    target_corpus_float: float,
    use_post_tax_bool: bool = False,
) -> float | None:
    """Find the instalment that reaches a target corpus.

    Brief:
        Every fund's instalment is scaled by the same factor, so
        the portfolio's contribution mix is preserved and only its
        overall size changes.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        target_corpus_float (float): Corpus to reach.
        use_post_tax_bool (bool): Target the post-tax corpus.

    Returns:
        Optional[float]: Total monthly instalment across all
            funds, or None when the target is out of reach.

    Warning:
        A plan investing nothing at all cannot be scaled and
        returns None, because there is no mix to preserve.
    """
    base_total_float = read_base_monthly_amount_float(
        fund_configurations_list, settings
    )
    if base_total_float <= 0.0:
        return None

    def measure_float(total_sip_float: float) -> float:
        scale_float = total_sip_float / base_total_float
        return _measure_corpus_float(
            _scale_instalments_list(
                fund_configurations_list, scale_float
            ),
            _scale_settings_instalments(settings, scale_float),
            use_post_tax_bool,
        )

    return _bisect_input_float(
        measure_float,
        target_corpus_float,
        0.0,
        GOAL_SEEK_MAXIMUM_SIP_FLOAT,
    )


def solve_required_return_percent_float(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    target_corpus_float: float,
    use_post_tax_bool: bool = False,
) -> float | None:
    """Find the gross return that reaches a target corpus.

    Brief:
        Shifts every fund's gross return by the same number of
        percentage points, preserving the spread between a growth
        fund and a debt fund.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        target_corpus_float (float): Corpus to reach.
        use_post_tax_bool (bool): Target the post-tax corpus.

    Returns:
        Optional[float]: Shift in percentage points to apply to
            every fund, or None when the target is out of reach.

    Warning:
        A required return is a diagnosis, not a plan. Nothing here
        makes a market deliver it.
    """

    def measure_float(shift_percent_float: float) -> float:
        return _measure_corpus_float(
            [
                replace(
                    fund,
                    gross_return_percent_float=(
                        fund.gross_return_percent_float
                        + shift_percent_float
                    ),
                )
                for fund in fund_configurations_list
            ],
            settings,
            use_post_tax_bool,
        )

    return _bisect_input_float(
        measure_float,
        target_corpus_float,
        0.0,
        GOAL_SEEK_MAXIMUM_RETURN_PERCENT_FLOAT,
    )


def solve_required_horizon_years_int(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    target_corpus_float: float,
    use_post_tax_bool: bool = False,
) -> int | None:
    """Find the shortest whole-year horizon reaching a target.

    Brief:
        Scans upward rather than bisecting because the horizon is
        an integer and the search range is small enough that a
        linear scan is both simpler and exact at the boundary.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        target_corpus_float (float): Corpus to reach.
        use_post_tax_bool (bool): Target the post-tax corpus.

    Returns:
        Optional[int]: Whole years needed, or None when the target
            is not reached inside the search limit.

    Warning:
        Rounds up to a whole year, so the solved plan overshoots
        the target slightly rather than falling short of it.
    """
    for horizon_years_int in range(
        1, GOAL_SEEK_MAXIMUM_YEARS_INT + 1
    ):
        corpus_float = _measure_corpus_float(
            fund_configurations_list,
            replace(
                settings, horizon_years_int=horizon_years_int
            ),
            use_post_tax_bool,
        )
        if corpus_float >= target_corpus_float:
            return horizon_years_int
    return None
