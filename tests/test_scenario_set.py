"""Holding several journeys, and keeping the comparison honest.

The basis check is the point of this module. Four figures under
"same return, different behaviour" say nothing at all if the returns
were not in fact the same, so a comparison that cannot hold its
basis must say so.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    PresentationPreferences,
)
from investment_journey_simulator.scenario_set import (
    BASIS_HORIZON_STR,
    BASIS_RETURN_STR,
    MAXIMUM_JOURNEY_COUNT_INT,
    ScenarioSet,
    add_journey,
    find_basis_difference_list,
    find_spread_float,
    remove_journey,
    run_journey_outcome,
    run_scenario_set,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

PLAN_START_DATE: date = date(2026, 1, 1)


def build_journey(
    name_str: str,
    *event_tuple: TimelineEvent,
) -> PlanScenario:
    """Build a named twenty-year journey."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=20,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR, PLAN_START_DATE, 25000.0
                ),
                *event_tuple,
            ],
        ),
        fund_list=[build_test_fund(name_str="Equity")],
        name_str=name_str,
    )


def build_pair() -> ScenarioSet:
    """Two journeys differing only in a pause."""
    return ScenarioSet(
        [
            build_journey("Steady"),
            build_journey(
                "Paused",
                TimelineEvent(EVENT_PAUSE_STR, date(2030, 1, 1)),
                TimelineEvent(EVENT_RESUME_STR, date(2032, 12, 1)),
            ),
        ]
    )


# --- Holding journeys ---------------------------------------------


def test_one_journey_is_not_a_comparison():
    """There is nothing to compare a plan against but itself."""
    single = ScenarioSet([build_journey("Steady")])
    assert single.is_comparable_bool is False


def test_two_journeys_are():
    """The minimum for the screen to have anything to say."""
    assert build_pair().is_comparable_bool is True


def test_saving_under_the_same_name_replaces():
    """Saving twice means changing your mind, not duplicating."""
    scenario_set = ScenarioSet([build_journey("Steady")])
    updated = add_journey(
        scenario_set,
        build_journey(
            "Steady",
            TimelineEvent(EVENT_PAUSE_STR, date(2030, 1, 1)),
        ),
    )
    assert updated.name_str_list == ["Steady"]
    assert len(updated.scenario_list[0].plan.event_list) == 2


def test_the_set_is_capped_and_drops_the_oldest():
    """Seven curves on one axis read as noise."""
    scenario_set = ScenarioSet([])
    for index_int in range(MAXIMUM_JOURNEY_COUNT_INT + 2):
        scenario_set = add_journey(
            scenario_set, build_journey(f"Journey {index_int}")
        )
    assert (
        len(scenario_set.scenario_list)
        == MAXIMUM_JOURNEY_COUNT_INT
    )
    assert "Journey 0" not in scenario_set.name_str_list


def test_removing_a_journey_by_name():
    """A reader must be able to take one back out."""
    updated = remove_journey(build_pair(), "Paused")
    assert updated.name_str_list == ["Steady"]


def test_removing_an_absent_name_changes_nothing():
    """Idempotent, so a double click cannot misfire."""
    assert (
        remove_journey(build_pair(), "Nothing").name_str_list
        == build_pair().name_str_list
    )


# --- The basis check ----------------------------------------------


def test_journeys_differing_only_in_behaviour_share_a_basis():
    """The case where the headline claim is true."""
    assert find_basis_difference_list(build_pair()) == []


def test_a_different_return_is_reported():
    """The most misleading difference to leave unstated."""
    scenario_set = ScenarioSet(
        [
            build_journey("Steady"),
            replace(
                build_journey("Optimistic"),
                fund_list=[
                    replace(
                        build_test_fund(name_str="Equity"),
                        gross_return_percent_float=15.0,
                    )
                ],
            ),
        ]
    )
    difference_list = find_basis_difference_list(scenario_set)
    assert [
        difference.basis_str for difference in difference_list
    ] == [BASIS_RETURN_STR]


def test_a_different_horizon_is_reported():
    """A longer plan is not a better behaviour."""
    scenario_set = ScenarioSet(
        [
            build_journey("Twenty years"),
            replace(
                build_journey("Thirty years"),
                plan=replace(
                    build_journey("Thirty years").plan,
                    horizon_years_int=30,
                ),
            ),
        ]
    )
    assert BASIS_HORIZON_STR in [
        difference.basis_str
        for difference in find_basis_difference_list(scenario_set)
    ]


def test_a_different_currency_is_reported():
    """Two currencies on one axis compare nothing."""
    scenario_set = ScenarioSet(
        [
            build_journey("Rupees"),
            replace(
                build_journey("Dollars"),
                presentation=PresentationPreferences(
                    currency_code_str="USD"
                ),
            ),
        ]
    )
    assert find_basis_difference_list(scenario_set) != []


def test_a_basis_difference_explains_itself():
    """A warning nobody can act on is noise."""
    scenario_set = ScenarioSet(
        [
            build_journey("Steady"),
            replace(
                build_journey("Optimistic"),
                fund_list=[
                    replace(
                        build_test_fund(name_str="Equity"),
                        gross_return_percent_float=15.0,
                    )
                ],
            ),
        ]
    )
    sentence_str = find_basis_difference_list(scenario_set)[
        0
    ].sentence_str
    assert "not the same" in sentence_str
    assert "not caused by behaviour alone" in sentence_str


def test_a_single_journey_has_no_basis_to_check():
    """Nothing to hold constant against."""
    assert (
        find_basis_difference_list(
            ScenarioSet([build_journey("Steady")])
        )
        == []
    )


# --- Running ------------------------------------------------------


def test_running_a_journey_reports_its_outcome():
    """Everything the headline tiles need, and nothing more."""
    outcome = run_journey_outcome(build_journey("Steady"))
    assert outcome.name_str == "Steady"
    assert outcome.final_value_float > 0.0
    assert outcome.invested_float > 0.0
    assert outcome.growth_float == pytest.approx(
        outcome.final_value_float - outcome.invested_float
    )


def test_a_real_value_is_below_the_nominal_one():
    """Inflation only ever erodes."""
    outcome = run_journey_outcome(build_journey("Steady"))
    assert outcome.real_value_float < outcome.final_value_float


def test_running_a_set_keeps_the_order():
    """The tiles must line up with the names above them."""
    outcome_list = run_scenario_set(build_pair())
    assert [
        outcome.name_str for outcome in outcome_list
    ] == build_pair().name_str_list


def test_the_spread_is_best_minus_worst():
    """The headline figure of the whole screen."""
    outcome_list = run_scenario_set(build_pair())
    value_list = [
        outcome.final_value_float for outcome in outcome_list
    ]
    assert find_spread_float(outcome_list) == pytest.approx(
        max(value_list) - min(value_list)
    )


def test_pausing_really_does_cost_something():
    """If this were zero the whole screen would be pointless."""
    assert find_spread_float(run_scenario_set(build_pair())) > 0.0


def test_a_single_journey_has_no_spread():
    """Nothing to be apart from."""
    assert (
        find_spread_float(
            run_scenario_set(
                ScenarioSet([build_journey("Steady")])
            )
        )
        == 0.0
    )
