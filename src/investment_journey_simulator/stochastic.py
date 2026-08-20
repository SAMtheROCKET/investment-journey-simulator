"""Return paths, so the engine can show risk and not just growth.

The deterministic engine answers "what if the return is exactly
twelve percent every single month?". No market does that, and the
difference is not cosmetic: a plan can hit its average return and
still fail, because *when* the bad months land matters as much as
how many there are. That is sequence-of-returns risk, and a single
constant rate cannot express it.

Two path generators are offered:

    lognormal   draws each month independently from a lognormal
                distribution calibrated to a mean and volatility.
                Simple, and wrong in one known way: real returns
                are not independent month to month.
    bootstrap   resamples *blocks* of real historical months, so
                whatever autocorrelation, fat tails and crash
                clustering the history contained survives into the
                simulated path. Preferred whenever a history is
                available.

Both feed `FundConfiguration.monthly_rate_path_list`, which the lot
book turns into a cumulative growth index. Everything downstream -
FIFO lots, tax, exit charges, rebalancing - is unchanged and keeps
working exactly as it does deterministically.

What this still does not do: it does not predict returns. A
distribution fitted to the past is an assumption about the future,
not knowledge of it. Percentile bands describe the model, not the
market.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationSettings,
)
from investment_journey_simulator.returns import (
    convert_annual_to_monthly_rate_float,
)

REPORTED_PERCENTILE_TUPLE: tuple = (5, 10, 25, 50, 75, 90, 95)


@dataclass(frozen=True)
class PathOutcomeSummary:
    """Distribution of one measure across many simulated paths."""

    trial_count_int: int
    percentile_dict: dict[int, float]
    mean_float: float
    worst_float: float
    best_float: float
    shortfall_probability_float: float


def build_lognormal_path_list(
    annual_return_percent_float: float,
    annual_volatility_percent_float: float,
    total_months_int: int,
    generator: random.Random,
) -> list[float]:
    """Draw a monthly return path from a lognormal distribution.

    Brief:
        Calibrated so that the *median* compounded outcome matches
        the requested annual return. Volatility is scaled by the
        square root of time, the standard convention for
        converting an annual figure to a monthly one.

    Arguments:
        annual_return_percent_float (float): Expected annual
            return in percent.
        annual_volatility_percent_float (float): Annual standard
            deviation of returns in percent.
        total_months_int (int): Months of path to generate.
        generator (random.Random): Seeded source of randomness.

    Returns:
        List[float]: One effective monthly rate per month.

    Warning:
        Successive months are independent, which real markets are
        not. Use the bootstrap when a history is available.
    """
    monthly_drift_float = math.log(
        1.0
        + convert_annual_to_monthly_rate_float(
            annual_return_percent_float
        )
    )
    monthly_sigma_float = (
        float(annual_volatility_percent_float)
        / PERCENT_TOTAL_FLOAT
    ) / math.sqrt(MONTHS_IN_YEAR_INT)
    return [
        math.exp(
            generator.gauss(monthly_drift_float, monthly_sigma_float)
        )
        - 1.0
        for _month_index_int in range(max(0, int(total_months_int)))
    ]


def build_block_bootstrap_path_list(
    historical_monthly_rate_list: list[float],
    total_months_int: int,
    block_months_int: int,
    generator: random.Random,
) -> list[float]:
    """Resample a real return history in contiguous blocks.

    Brief:
        Drawing whole blocks rather than single months preserves
        the shape of history: momentum, volatility clustering and
        the fact that crashes arrive as runs of bad months rather
        than as isolated ones.

    Arguments:
        historical_monthly_rate_list (List[float]): Observed
            monthly rates as decimal fractions.
        total_months_int (int): Months of path to generate.
        block_months_int (int): Length of each resampled block.
        generator (random.Random): Seeded source of randomness.

    Returns:
        List[float]: One monthly rate per simulated month.

    Warning:
        Resampling cannot invent a market state the history never
        contained. A history without a deep crash produces paths
        without one.
    """
    if not historical_monthly_rate_list:
        return []
    safe_block_int = max(1, int(block_months_int))
    path_list: list[float] = []
    while len(path_list) < int(total_months_int):
        start_index_int = generator.randrange(
            len(historical_monthly_rate_list)
        )
        for offset_int in range(safe_block_int):
            path_list.append(
                historical_monthly_rate_list[
                    (start_index_int + offset_int)
                    % len(historical_monthly_rate_list)
                ]
            )
    return path_list[: int(total_months_int)]


def _build_percentile_dict(
    ordered_list: list[float],
) -> dict[int, float]:
    """Read the reported percentiles off a sorted outcome list.

    Brief:
        Nearest-rank percentiles, which need no interpolation and
        so always report a value some path actually produced.

    Arguments:
        ordered_list (List[float]): Outcomes in ascending order.

    Returns:
        Dict[int, float]: Percentile to outcome mapping.

    Warning:
        The caller must have sorted the list already.
    """
    trial_count_int = len(ordered_list)
    return {
        percentile_int: ordered_list[
            min(
                trial_count_int - 1,
                int(percentile_int / 100.0 * trial_count_int),
            )
        ]
        for percentile_int in REPORTED_PERCENTILE_TUPLE
    }


def _summarise_outcome_list(
    outcome_list: list[float],
    target_corpus_float: float,
) -> PathOutcomeSummary:
    """Reduce many simulated outcomes to a readable summary.

    Brief:
        Percentiles rather than a mean, because the distribution
        of a compounded outcome is strongly right-skewed and its
        mean sits well above its median.

    Arguments:
        outcome_list (List[float]): One outcome per trial.
        target_corpus_float (float): Goal used for the shortfall
            probability; pass zero to disable it.

    Returns:
        PathOutcomeSummary: Percentiles and shortfall risk.

    Warning:
        The shortfall probability is the share of *simulated*
        paths that missed, which is a property of the model's
        assumptions and not a real-world probability.
    """
    ordered_list = sorted(outcome_list)
    trial_count_int = len(ordered_list)
    if trial_count_int == 0:
        return PathOutcomeSummary(0, {}, 0.0, 0.0, 0.0, 0.0)
    percentile_dict = _build_percentile_dict(ordered_list)
    shortfall_count_int = sum(
        1
        for outcome_float in ordered_list
        if outcome_float < float(target_corpus_float)
    )
    return PathOutcomeSummary(
        trial_count_int=trial_count_int,
        percentile_dict=percentile_dict,
        mean_float=sum(ordered_list) / trial_count_int,
        worst_float=ordered_list[0],
        best_float=ordered_list[-1],
        shortfall_probability_float=(
            shortfall_count_int / trial_count_int
        ),
    )


def _apply_path_to_funds_list(
    fund_configurations_list: list[FundConfiguration],
    build_path_for_fund,
) -> list[FundConfiguration]:
    """Attach a freshly drawn return path to every fund.

    Brief:
        Each fund draws its own path, so a two-asset portfolio
        sees its funds move independently. That understates the
        correlation real asset classes show in a crash, which is
        stated plainly rather than silently assumed away.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        build_path_for_fund: Callable taking a fund and returning
            its monthly rate path.

    Returns:
        List[FundConfiguration]: Copies carrying return paths.

    Warning:
        Independent draws make a diversified portfolio look safer
        than it is, because real correlations rise in a crash.
    """
    return [
        replace(
            fund,
            monthly_rate_path_list=build_path_for_fund(fund),
        )
        for fund in fund_configurations_list
    ]


def run_stochastic_trials(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    build_path_for_fund,
    trial_count_int: int,
    target_corpus_float: float = 0.0,
    use_post_tax_bool: bool = False,
) -> PathOutcomeSummary:
    """Simulate one plan many times over random return paths.

    Brief:
        Every trial runs the full engine, so tax, exit charges,
        FIFO lots and rebalancing all apply inside each path. That
        is what lets the rebalancing lab finally show rebalancing's
        *benefit* - volatility it harvests - alongside the tax and
        charges cost it has always shown.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        build_path_for_fund: Callable taking a fund and returning
            a monthly rate path for one trial.
        trial_count_int (int): Number of paths to simulate.
        target_corpus_float (float): Goal for shortfall risk.
        use_post_tax_bool (bool): Measure the spendable corpus.

    Returns:
        PathOutcomeSummary: Distribution across the trials.

    Warning:
        Cost is one full simulation per trial. A thousand trials
        over a thirty-year plan is three hundred and sixty
        thousand simulated months.
    """
    outcome_list: list[float] = []
    for _trial_index_int in range(max(0, int(trial_count_int))):
        result = PortfolioSimulator(
            _apply_path_to_funds_list(
                fund_configurations_list, build_path_for_fund
            ),
            settings,
        ).run()
        outcome_list.append(
            result.post_tax_ending_value_float
            if use_post_tax_bool
            else result.ending_value_float
        )
    return _summarise_outcome_list(
        outcome_list, target_corpus_float
    )


def build_bootstrap_path_builder(
    historical_monthly_rate_list: list[float],
    total_months_int: int,
    block_months_int: int,
    generator: random.Random,
):
    """Make a path builder that resamples real history.

    Brief:
        Preferred over the lognormal builder whenever a history is
        available, because it keeps the shape of real returns
        rather than assuming a bell curve.

    Arguments:
        historical_monthly_rate_list (List[float]): Real monthly
            returns to resample.
        total_months_int (int): Months each path must cover.
        block_months_int (int): Length of each resampled block.
        generator (random.Random): Seeded source of randomness.

    Returns:
        Callable: Builder mapping a fund to a return path.

    Warning:
        Every fund resamples the same history, so this models a
        portfolio of funds tracking one market. It cannot express
        an equity and debt mix.
    """

    def build_path_for_fund(
        _fund_configuration: FundConfiguration,
    ) -> list[float]:
        return build_block_bootstrap_path_list(
            historical_monthly_rate_list,
            total_months_int,
            block_months_int,
            generator,
        )

    return build_path_for_fund


def build_lognormal_path_builder(
    annual_volatility_percent_float: float,
    total_months_int: int,
    generator: random.Random,
):
    """Make a path builder that draws lognormal returns.

    Brief:
        Convenience wrapper so a caller can hand one callable to
        the trial runner without closing over the loop variables
        itself.

    Arguments:
        annual_volatility_percent_float (float): Annual standard
            deviation applied to every fund.
        total_months_int (int): Months each path must cover.
        generator (random.Random): Seeded source of randomness.

    Returns:
        Callable: Builder mapping a fund to a return path.

    Warning:
        Applies one volatility to every fund, so an equity fund
        and a debt fund are treated as equally risky unless the
        caller supplies its own builder instead.
    """

    def build_path_for_fund(
        fund_configuration: FundConfiguration,
    ) -> list[float]:
        return build_lognormal_path_list(
            fund_configuration.net_return_percent_float,
            annual_volatility_percent_float,
            total_months_int,
            generator,
        )

    return build_path_for_fund
