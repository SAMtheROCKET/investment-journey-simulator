"""Return path and distribution tests."""

from __future__ import annotations

import random
from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import FundConfiguration
from investment_journey_simulator.stochastic import (
    build_block_bootstrap_path_list,
    build_lognormal_path_builder,
    build_lognormal_path_list,
    run_stochastic_trials,
)

START_DATE: date = date(2026, 1, 1)


def run_with_path(path_list: list[float], horizon_years_int: int):
    """Simulate one fund over an explicit return path.

    REFERENCE: harness only.
    """
    fund = build_test_fund(
        "Fund-A", 10000.0, 12.0, 0.0, START_DATE
    )
    fund_with_path = FundConfiguration(
        **{
            **fund.__dict__,
            "monthly_rate_path_list": path_list,
        }
    )
    return PortfolioSimulator(
        [fund_with_path],
        build_test_settings(horizon_years_int=horizon_years_int),
    ).run()


def test_zero_volatility_reproduces_the_deterministic_run() -> None:
    """A path with no randomness must match the constant rate.

    REFERENCE: G1-ANALYTIC. This is the calibration check for the
    whole path machinery: if a flat path disagrees with the
    deterministic engine, every stochastic result is suspect.
    """
    fund_list = [
        build_test_fund("Fund-A", 10000.0, 12.0, 0.0, START_DATE)
    ]
    settings = build_test_settings(horizon_years_int=15)
    deterministic_float = PortfolioSimulator(
        fund_list, settings
    ).run().ending_value_float
    summary = run_stochastic_trials(
        fund_list,
        settings,
        build_lognormal_path_builder(
            0.0, 180, random.Random(7)
        ),
        3,
    )
    assert summary.percentile_dict[50] == pytest.approx(
        deterministic_float, rel=1e-9
    )


def test_the_order_of_returns_changes_the_outcome() -> None:
    """The same returns in a different order end differently.

    REFERENCE: G4-SYNTHETIC. This is sequence-of-returns risk, the
    single thing a constant-rate engine cannot express. An
    instalment plan buys more units when prices are low, so a bad
    decade followed by a good one beats the reverse even though
    both contain identical monthly returns.
    """
    good_month_list = [0.02] * 90
    bad_month_list = [-0.005] * 90
    bad_first_result = run_with_path(
        bad_month_list + good_month_list, 15
    )
    good_first_result = run_with_path(
        good_month_list + bad_month_list, 15
    )
    assert (
        bad_first_result.ending_value_float
        != pytest.approx(good_first_result.ending_value_float)
    )
    assert (
        bad_first_result.ending_value_float
        > good_first_result.ending_value_float
    )


def test_a_flat_path_equals_the_closed_form() -> None:
    """A constant path compounds like the annuity formula.

    REFERENCE: G1-ANALYTIC. With every monthly rate equal to one
    percent the corpus is the ordinary annuity-due closed form, so
    the cumulative index cannot be off by a month.
    """
    monthly_rate_float = 0.01
    total_months_int = 60
    result = run_with_path(
        [monthly_rate_float] * total_months_int, 5
    )
    expected_float = (
        10000.0
        * (
            (1 + monthly_rate_float) ** total_months_int - 1
        )
        / monthly_rate_float
        * (1 + monthly_rate_float)
    )
    assert result.ending_value_float == pytest.approx(
        expected_float, rel=1e-9
    )


def test_lognormal_paths_are_reproducible_from_a_seed() -> None:
    """The same seed must give the same path every time.

    REFERENCE: G4-SYNTHETIC. A result nobody can reproduce is not
    evidence; seeding is what makes a reported percentile band
    checkable by someone else.
    """
    first_list = build_lognormal_path_list(
        12.0, 18.0, 24, random.Random(11)
    )
    second_list = build_lognormal_path_list(
        12.0, 18.0, 24, random.Random(11)
    )
    assert first_list == second_list


def test_bootstrap_only_ever_emits_observed_returns() -> None:
    """Resampling must not invent a return history never saw.

    REFERENCE: G4-SYNTHETIC. The whole claim of a bootstrap is
    that its outputs came from the real record.
    """
    history_list = [0.01, -0.02, 0.03, 0.005, -0.04]
    path_list = build_block_bootstrap_path_list(
        history_list, 100, 6, random.Random(3)
    )
    assert len(path_list) == 100
    assert set(path_list).issubset(set(history_list))


def test_bootstrap_preserves_runs_of_months() -> None:
    """Block resampling keeps consecutive months together.

    REFERENCE: G4-SYNTHETIC. Drawing single months would destroy
    volatility clustering, which is the reason to bootstrap in
    blocks rather than one month at a time.
    """
    history_list = [float(index_int) for index_int in range(24)]
    path_list = build_block_bootstrap_path_list(
        history_list, 12, 12, random.Random(5)
    )
    difference_list = [
        (path_list[index_int + 1] - path_list[index_int]) % 24
        for index_int in range(len(path_list) - 1)
    ]
    assert difference_list == [1.0] * (len(path_list) - 1)


def test_an_empty_history_cannot_be_bootstrapped() -> None:
    """No history means no path, rather than a fabricated one.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert (
        build_block_bootstrap_path_list([], 12, 6, random.Random(1))
        == []
    )


def test_volatility_widens_the_distribution() -> None:
    """More volatility must spread the outcomes further apart.

    REFERENCE: G4-SYNTHETIC. Monotonicity check on the model: if
    raising volatility did not widen the band, the band would not
    be measuring risk.
    """
    fund_list = [
        build_test_fund("Fund-A", 10000.0, 12.0, 0.0, START_DATE)
    ]
    settings = build_test_settings(horizon_years_int=10)
    calm_summary = run_stochastic_trials(
        fund_list,
        settings,
        build_lognormal_path_builder(5.0, 120, random.Random(2)),
        120,
    )
    wild_summary = run_stochastic_trials(
        fund_list,
        settings,
        build_lognormal_path_builder(25.0, 120, random.Random(2)),
        120,
    )
    calm_spread_float = (
        calm_summary.percentile_dict[95]
        - calm_summary.percentile_dict[5]
    )
    wild_spread_float = (
        wild_summary.percentile_dict[95]
        - wild_summary.percentile_dict[5]
    )
    assert wild_spread_float > calm_spread_float


def test_shortfall_probability_counts_the_paths_that_missed(
) -> None:
    """Shortfall risk is the share of paths below the goal.

    REFERENCE: G4-SYNTHETIC. An impossible goal must be missed by
    every path and a trivial one by none, which pins both ends of
    the statistic.
    """
    fund_list = [
        build_test_fund("Fund-A", 10000.0, 12.0, 0.0, START_DATE)
    ]
    settings = build_test_settings(horizon_years_int=10)
    builder = build_lognormal_path_builder(
        15.0, 120, random.Random(4)
    )
    assert run_stochastic_trials(
        fund_list, settings, builder, 40, 1e15
    ).shortfall_probability_float == pytest.approx(1.0)
    assert run_stochastic_trials(
        fund_list, settings, builder, 40, 0.0
    ).shortfall_probability_float == pytest.approx(0.0)


def test_no_trials_produce_an_empty_summary() -> None:
    """Zero trials must not divide by zero.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    summary = run_stochastic_trials(
        [build_test_fund("Fund-A", 10000.0, 12.0, 0.0, START_DATE)],
        build_test_settings(horizon_years_int=5),
        build_lognormal_path_builder(10.0, 60, random.Random(1)),
        0,
    )
    assert summary.trial_count_int == 0
    assert summary.percentile_dict == {}
