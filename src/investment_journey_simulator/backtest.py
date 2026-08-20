"""Replaying a plan over returns the market actually delivered.

This is the one part of the package that is not a projection. It
takes the real month-end levels of a real index and runs the whole
engine over them - the same FIFO lot book, the same tax, the same
exit load and STT - so the answer is what a plan started on a given
date would genuinely have produced.

Three things are offered, in increasing order of usefulness:

    replay          one plan over the whole history, once
    rolling         the same plan started in every possible month,
                    which shows how much the *start date* mattered
    bootstrap feed  the real monthly returns handed to the block
                    bootstrap, so simulated paths inherit the
                    shape of real history instead of a bell curve

A rolling backtest is the honest way to answer "was I unlucky?".
A single replay tells you what happened once; the spread across
start dates tells you how much of that was timing.

**The bundled history is three years long.** That is enough to show
start-date sensitivity over short horizons and to calibrate
volatility. It is not enough to say anything about a thirty-year
plan, and it contains no severe crash. See `market_data` for the
coverage warning that should travel with every number from here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.market_data import MarketHistory
from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationSettings,
)
from investment_journey_simulator.money_weighted import (
    calculate_post_tax_xirr_percent_float,
    calculate_pre_tax_xirr_percent_float,
)


@dataclass(frozen=True)
class BacktestOutcome:
    """Result of replaying one plan over real market returns."""

    start_month_index_int: int
    months_simulated_int: int
    invested_float: float
    ending_value_float: float
    post_tax_ending_value_float: float
    pre_tax_xirr_percent_float: float | None
    post_tax_xirr_percent_float: float | None

    @property
    def gain_float(self) -> float:
        """Money made over and above the principal.

        Brief:
            Measured before exit tax, matching the gross corpus.

        Arguments:
            None.

        Returns:
            float: Gain over principal, negative at a loss.

        Warning:
            Ignores the exit cost; use the post-tax value for what
            is actually spendable.
        """
        return self.ending_value_float - self.invested_float


def _apply_history_path_list(
    fund_configurations_list: list[FundConfiguration],
    monthly_return_list: list[float],
) -> list[FundConfiguration]:
    """Give every fund the same real return path.

    Brief:
        A single index history drives every fund, which is right
        for a portfolio of equity funds tracking the same market
        and wrong for a mixed equity-and-debt plan.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        monthly_return_list (List[float]): Real monthly returns.

    Returns:
        List[FundConfiguration]: Copies carrying the real path.

    Warning:
        A debt fund driven by an equity index is nonsense. Backtest
        equity-only plans, or accept that the debt leg is modelled
        as if it were equity.
    """
    return [
        replace(
            fund_configuration,
            monthly_rate_path_list=list(monthly_return_list),
        )
        for fund_configuration in fund_configurations_list
    ]


def replay_history(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    monthly_return_list: list[float],
    start_month_index_int: int = 0,
) -> BacktestOutcome | None:
    """Run one plan over a slice of real monthly returns.

    Brief:
        The horizon is capped by the history available from the
        chosen start month, so a plan never runs past the end of
        the data and silently repeats it.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        monthly_return_list (List[float]): Real monthly returns.
        start_month_index_int (int): First month of the slice.

    Returns:
        Optional[BacktestOutcome]: Outcome, or None when the slice
            is shorter than one month.

    Warning:
        Uses the *settings* horizon when the history is longer, so
        a short plan is not stretched to fill the window.
    """
    available_list = monthly_return_list[start_month_index_int:]
    months_int = min(
        settings.total_months_int, len(available_list)
    )
    if months_int <= 0:
        return None
    result = PortfolioSimulator(
        _apply_history_path_list(
            fund_configurations_list, available_list[:months_int]
        ),
        settings,
    ).run()
    return _build_outcome(
        result, settings, start_month_index_int, months_int
    )


def _build_outcome(
    result,
    settings: SimulationSettings,
    start_month_index_int: int,
    months_int: int,
) -> BacktestOutcome:
    """Read one completed replay into a comparable record.

    Brief:
        Both money-weighted returns are solved here so a rolling
        backtest can be ranked by what the investor kept, not just
        by the corpus.

    Arguments:
        result: Completed simulation result.
        settings (SimulationSettings): Rules used for the run.
        start_month_index_int (int): Month the slice began at.
        months_int (int): Months actually simulated.

    Returns:
        BacktestOutcome: One comparable backtest record.

    Warning:
        Either return is None when the plan never both paid in and
        took out.
    """
    return BacktestOutcome(
        start_month_index_int=int(start_month_index_int),
        months_simulated_int=months_int,
        invested_float=result.ending_invested_float,
        ending_value_float=result.ending_value_float,
        post_tax_ending_value_float=(
            result.post_tax_ending_value_float
        ),
        pre_tax_xirr_percent_float=(
            calculate_pre_tax_xirr_percent_float(
                result, settings.sip_at_month_start_bool
            )
        ),
        post_tax_xirr_percent_float=(
            calculate_post_tax_xirr_percent_float(
                result, settings.sip_at_month_start_bool
            )
        ),
    )


def run_rolling_backtest_list(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    history: MarketHistory,
) -> list[BacktestOutcome]:
    """Start the same plan in every month the history allows.

    Brief:
        Only windows long enough to run the full horizon are kept,
        so every outcome in the list is comparable with every
        other. That is what makes the spread meaningful.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        history (MarketHistory): Real monthly history.

    Returns:
        List[BacktestOutcome]: One outcome per viable start month,
            empty when the history is shorter than the horizon.

    Warning:
        Windows overlap heavily, so the outcomes are not
        independent samples and their spread understates the true
        uncertainty.
    """
    monthly_return_list = history.monthly_return_list
    window_count_int = (
        len(monthly_return_list) - settings.total_months_int + 1
    )
    if window_count_int <= 0:
        return []
    outcome_list: list[BacktestOutcome] = []
    for start_index_int in range(window_count_int):
        outcome = replay_history(
            fund_configurations_list,
            settings,
            monthly_return_list,
            start_index_int,
        )
        if outcome is not None:
            outcome_list.append(outcome)
    return outcome_list


def summarise_rolling_outcomes_dict(
    outcome_list: list[BacktestOutcome],
) -> dict[str, float]:
    """Reduce rolling outcomes to the numbers worth reporting.

    Brief:
        The spread between the best and worst start month is the
        headline: it is the cost of timing, measured rather than
        argued about.

    Arguments:
        outcome_list (List[BacktestOutcome]): Rolling outcomes.

    Returns:
        Dict[str, float]: Best, worst, median and mean corpus, and
            the same for the post-tax money-weighted return. An
            empty mapping when there were no viable windows.

    Warning:
        Overlapping windows make these statistics correlated; read
        them as a range, not as a distribution.
    """
    if not outcome_list:
        return {}
    value_list = sorted(
        outcome.post_tax_ending_value_float
        for outcome in outcome_list
    )
    summary_dict = {
        "window_count": float(len(outcome_list)),
        "worst_value": value_list[0],
        "median_value": value_list[len(value_list) // 2],
        "best_value": value_list[-1],
        "mean_value": sum(value_list) / len(value_list),
    }
    summary_dict.update(_summarise_return_dict(outcome_list))
    return summary_dict


def _summarise_return_dict(
    outcome_list: list[BacktestOutcome],
) -> dict[str, float]:
    """Reduce the post-tax money-weighted returns to a range.

    Brief:
        Reported alongside the corpus because a corpus depends on
        how much was paid in, while a rate is comparable across
        plans of different sizes.

    Arguments:
        outcome_list (List[BacktestOutcome]): Rolling outcomes.

    Returns:
        Dict[str, float]: Worst, median and best return, or an
            empty mapping when no window produced a rate.

    Warning:
        Windows overlap, so these are a range, not a distribution.
    """
    return_list = sorted(
        outcome.post_tax_xirr_percent_float
        for outcome in outcome_list
        if outcome.post_tax_xirr_percent_float is not None
    )
    if not return_list:
        return {}
    return {
        "worst_return": return_list[0],
        "median_return": return_list[len(return_list) // 2],
        "best_return": return_list[-1],
    }
