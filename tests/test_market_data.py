"""Real market history loading, calibration and backtesting."""

from __future__ import annotations

import random
from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.backtest import (
    replay_history,
    run_rolling_backtest_list,
    summarise_rolling_outcomes_dict,
)
from investment_journey_simulator.market_data import (
    MarketHistory,
    calculate_annualised_return_percent_float,
    calculate_annualised_volatility_percent_float,
    describe_coverage_str,
    load_bundled_market_history,
    load_market_history,
)
from investment_journey_simulator.stochastic import (
    build_bootstrap_path_builder,
    build_lognormal_path_builder,
)

# The history is package data now, so a test that pointed at a
# repository folder would pass here and prove nothing about an
# installed copy.


@pytest.fixture(scope="module")
def loaded_history() -> MarketHistory:
    """Load the bundled index history once for the module.

    REFERENCE: harness only. Resolved from this file rather than
    the working directory, so the suite passes wherever it runs.
    """
    history = load_bundled_market_history()
    if history is None:
        pytest.skip("bundled index history is not present")
    return history


def test_a_missing_directory_loads_nothing() -> None:
    """An absent history folder must not raise.

    REFERENCE: G4-SYNTHETIC. Guard branch; the package has to work
    for a user who never downloaded any history.
    """
    assert load_market_history("no_such_directory_here") is None


def test_the_bundled_history_parses(
    loaded_history: MarketHistory,
) -> None:
    """The shipped CSVs load into a usable monthly series.

    REFERENCE: G3-CROSSCHECK. The exchange files carry a
    byte-order mark, pad their headers with spaces and list newest
    first; all three must be handled or the series comes out empty
    or reversed.
    """
    assert loaded_history.month_count_int > 0
    assert len(loaded_history.month_end_close_list) == (
        loaded_history.month_count_int + 1
    )
    assert loaded_history.month_end_date_list == sorted(
        loaded_history.month_end_date_list
    )
    assert all(
        close_float > 0.0
        for close_float in loaded_history.month_end_close_list
    )


def test_month_ends_are_one_per_calendar_month(
    loaded_history: MarketHistory,
) -> None:
    """Each month contributes exactly one observation.

    REFERENCE: G4-SYNTHETIC. Overlapping files would otherwise
    double count a month and invent a zero-percent return.
    """
    month_key_list = [
        (observation_date.year, observation_date.month)
        for observation_date in loaded_history.month_end_date_list
    ]
    assert len(month_key_list) == len(set(month_key_list))


def test_monthly_returns_reconstruct_the_index(
    loaded_history: MarketHistory,
) -> None:
    """Compounding the returns must rebuild the closing level.

    REFERENCE: G1-ANALYTIC. If the return series did not compound
    back to the index, every backtest built on it would be wrong.
    """
    rebuilt_float = loaded_history.month_end_close_list[0]
    for monthly_return_float in loaded_history.monthly_return_list:
        rebuilt_float *= 1.0 + monthly_return_float
    assert rebuilt_float == pytest.approx(
        loaded_history.month_end_close_list[-1], rel=1e-9
    )


def test_calibration_statistics_are_sane(
    loaded_history: MarketHistory,
) -> None:
    """Measured return and volatility must be plausible.

    REFERENCE: G5-PLAUSIBILITY. Not asserting a specific value,
    because the file contents may be replaced; asserting only that
    the statistics are finite and in a range a real equity index
    could occupy.
    """
    return_percent_float = (
        calculate_annualised_return_percent_float(loaded_history)
    )
    volatility_percent_float = (
        calculate_annualised_volatility_percent_float(
            loaded_history
        )
    )
    assert -50.0 < return_percent_float < 60.0
    assert 0.0 < volatility_percent_float < 60.0


def test_coverage_warning_names_the_limits(
    loaded_history: MarketHistory,
) -> None:
    """The coverage note must state what the history cannot do.

    REFERENCE: G4-SYNTHETIC. A bootstrap is only as honest as its
    source. Three years of data cannot speak to a thirty-year
    plan, and the note has to say so rather than let the reader
    assume otherwise.
    """
    coverage_str = describe_coverage_str(loaded_history)
    assert "volatility" in coverage_str
    assert "thin for resampling" in coverage_str
    assert "severe crash" in coverage_str


def test_empty_history_describes_itself_safely() -> None:
    """A history with no rows must not crash the description.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    empty_history = MarketHistory("Nothing", [], [])
    assert empty_history.month_count_int == 0
    assert calculate_annualised_return_percent_float(
        empty_history
    ) == pytest.approx(0.0)
    assert "No usable history" in describe_coverage_str(
        empty_history
    )


# ------------------------------------------------------------------
# Backtesting against the real series
# ------------------------------------------------------------------
def test_replay_matches_an_independent_unit_calculation(
    loaded_history: MarketHistory,
) -> None:
    """The engine replay equals a naive unit-buying simulation.

    REFERENCE: G1-ANALYTIC and G3-CROSSCHECK. Buying units at each
    month-end close and valuing them at the final close is the
    definition of a SIP, worked out here without touching engine
    code. Agreement proves the return path feeds the lot book
    correctly.
    """
    close_list = loaded_history.month_end_close_list
    month_count_int = loaded_history.month_count_int
    units_float = sum(
        10000.0 / close_list[month_index_int]
        for month_index_int in range(month_count_int)
    )
    expected_float = units_float * close_list[month_count_int]
    outcome = replay_history(
        [
            build_test_fund(
                "Index", 10000.0, 12.0, 0.0, date(2023, 8, 1)
            )
        ],
        build_test_settings(
            horizon_years_int=month_count_int // 12,
            portfolio_start_date=date(2023, 8, 1),
        ),
        loaded_history.monthly_return_list,
    )
    assert outcome is not None
    assert outcome.ending_value_float == pytest.approx(
        expected_float, rel=1e-9
    )


def test_replay_stops_at_the_end_of_the_history(
    loaded_history: MarketHistory,
) -> None:
    """A plan longer than the data must not repeat the data.

    REFERENCE: G4-SYNTHETIC. Silently looping the history would
    manufacture returns the market never produced.
    """
    outcome = replay_history(
        [
            build_test_fund(
                "Index", 10000.0, 12.0, 0.0, date(2023, 8, 1)
            )
        ],
        build_test_settings(
            horizon_years_int=40,
            portfolio_start_date=date(2023, 8, 1),
        ),
        loaded_history.monthly_return_list,
    )
    assert outcome is not None
    assert outcome.months_simulated_int == (
        loaded_history.month_count_int
    )


def test_replay_past_the_end_returns_nothing(
    loaded_history: MarketHistory,
) -> None:
    """A start month beyond the data has nothing to replay.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert (
        replay_history(
            [
                build_test_fund(
                    "Index", 10000.0, 12.0, 0.0, date(2023, 8, 1)
                )
            ],
            build_test_settings(horizon_years_int=1),
            loaded_history.monthly_return_list,
            start_month_index_int=10_000,
        )
        is None
    )


def test_rolling_backtest_covers_every_viable_start(
    loaded_history: MarketHistory,
) -> None:
    """Every window long enough to run the horizon is used.

    REFERENCE: G4-SYNTHETIC. With N monthly returns and a horizon
    of H months there are exactly N - H + 1 comparable windows.
    """
    settings = build_test_settings(
        horizon_years_int=1, portfolio_start_date=date(2023, 8, 1)
    )
    outcome_list = run_rolling_backtest_list(
        [
            build_test_fund(
                "Index", 10000.0, 12.0, 0.0, date(2023, 8, 1)
            )
        ],
        settings,
        loaded_history,
    )
    assert len(outcome_list) == (
        loaded_history.month_count_int
        - settings.total_months_int
        + 1
    )
    assert all(
        outcome.months_simulated_int == settings.total_months_int
        for outcome in outcome_list
    )


def test_rolling_backtest_shows_start_date_matters(
    loaded_history: MarketHistory,
) -> None:
    """Identical plans started a month apart end differently.

    REFERENCE: G4-SYNTHETIC. This is sequence-of-returns risk
    measured on real data rather than simulated: the only thing
    that differs between these windows is when the plan began.
    """
    summary_dict = summarise_rolling_outcomes_dict(
        run_rolling_backtest_list(
            [
                build_test_fund(
                    "Index", 10000.0, 12.0, 0.0, date(2023, 8, 1)
                )
            ],
            build_test_settings(
                horizon_years_int=1,
                portfolio_start_date=date(2023, 8, 1),
            ),
            loaded_history,
        )
    )
    assert summary_dict["window_count"] > 1
    assert summary_dict["best_value"] > summary_dict["worst_value"]
    assert summary_dict["best_return"] > summary_dict[
        "worst_return"
    ]


def test_a_horizon_longer_than_the_history_has_no_windows(
    loaded_history: MarketHistory,
) -> None:
    """No comparable window exists for an over-long horizon.

    REFERENCE: G4-SYNTHETIC. Guard branch; returning a partial
    window would compare plans of different lengths.
    """
    assert (
        run_rolling_backtest_list(
            [
                build_test_fund(
                    "Index", 10000.0, 12.0, 0.0, date(2023, 8, 1)
                )
            ],
            build_test_settings(horizon_years_int=40),
            loaded_history,
        )
        == []
    )


def test_summarising_nothing_yields_nothing() -> None:
    """An empty outcome list summarises to an empty mapping.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert summarise_rolling_outcomes_dict([]) == {}


# ------------------------------------------------------------------
# Feeding real history to the bootstrap
# ------------------------------------------------------------------
def test_bootstrap_from_real_history_emits_only_real_returns(
    loaded_history: MarketHistory,
) -> None:
    """Resampled paths contain only months the index really had.

    REFERENCE: G4-SYNTHETIC. This is the whole claim of using real
    history: every simulated month is one the market delivered.
    """
    builder = build_bootstrap_path_builder(
        loaded_history.monthly_return_list,
        120,
        12,
        random.Random(1),
    )
    path_list = builder(
        build_test_fund("Index", 1000.0, 12.0, 0.0, date(2026, 1, 1))
    )
    assert len(path_list) == 120
    assert set(path_list).issubset(
        set(loaded_history.monthly_return_list)
    )


def test_real_history_paths_differ_from_a_bell_curve(
    loaded_history: MarketHistory,
) -> None:
    """The two sources must not quietly produce the same thing.

    REFERENCE: G4-SYNTHETIC. If resampling and the bell curve
    agreed, the source choice would be decorative.
    """
    fund = build_test_fund(
        "Index", 1000.0, 12.0, 0.0, date(2026, 1, 1)
    )
    bootstrap_list = build_bootstrap_path_builder(
        loaded_history.monthly_return_list, 60, 12, random.Random(3)
    )(fund)
    lognormal_list = build_lognormal_path_builder(
        14.0, 60, random.Random(3)
    )(fund)
    assert bootstrap_list != lognormal_list
