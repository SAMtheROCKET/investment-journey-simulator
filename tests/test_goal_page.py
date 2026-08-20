"""The Goal Planner, and the solver fix underneath it.

The solver was written when every plan carried its money on the
funds. A plan built on the event rail carries it in dated instalment
overrides instead, and scaling only the funds scaled nothing - so
the screen reported that no contribution on earth reached the
target. These tests hold that shut.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_test_fund
from investment_journey_simulator.goal_seek import (
    read_base_monthly_amount_float,
    solve_required_horizon_years_int,
    solve_required_monthly_sip_float,
    solve_required_return_percent_float,
)
from investment_journey_simulator.pages import goal_page
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import SCENARIO_STATE_KEY_STR
from investment_journey_simulator.scenario_set import run_journey_outcome
from investment_journey_simulator.timeline import (
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 600
PLAN_START_DATE: date = date(2026, 1, 1)
MONTHLY_AMOUNT_FLOAT: float = 25000.0


def build_rail_journey() -> PlanScenario:
    """A plan whose money lives in events, as the rail builds it."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=20,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    PLAN_START_DATE,
                    MONTHLY_AMOUNT_FLOAT,
                )
            ],
        ),
        fund_list=[build_test_fund(name_str="Equity")],
        name_str="Steady",
    )


def build_form_journey() -> PlanScenario:
    """A plan whose money lives on its funds, as the form builds it."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE, horizon_years_int=20
        ),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                monthly_sip_float=MONTHLY_AMOUNT_FLOAT,
            )
        ],
        name_str="Steady form plan",
    )


def build_target_float(scenario: PlanScenario) -> float:
    """Twice what the plan currently reaches."""
    return run_journey_outcome(scenario).final_value_float * 2.0


# --- The solver, on both plan shapes ------------------------------


@pytest.mark.parametrize(
    "build_journey",
    [build_rail_journey, build_form_journey],
    ids=["rail plan", "form plan"],
)
def test_the_opening_amount_is_read_from_either_shape(
    build_journey,
):
    """The solver must recognise money wherever a plan keeps it."""
    compiled = compile_scenario(build_journey())
    assert (
        read_base_monthly_amount_float(
            compiled.fund_list, compiled.settings
        )
        == MONTHLY_AMOUNT_FLOAT
    )


@pytest.mark.parametrize(
    "build_journey",
    [build_rail_journey, build_form_journey],
    ids=["rail plan", "form plan"],
)
def test_a_reachable_target_is_solved_on_either_shape(
    build_journey,
):
    """The bug this fixes: a rail plan used to answer 'impossible'."""
    scenario = build_journey()
    compiled = compile_scenario(scenario)
    solved_float = solve_required_monthly_sip_float(
        compiled.fund_list,
        compiled.settings,
        build_target_float(scenario),
    )
    assert solved_float is not None
    assert solved_float > MONTHLY_AMOUNT_FLOAT


def test_doubling_the_target_roughly_doubles_the_instalment():
    """A plain SIP is linear in its contribution."""
    scenario = build_rail_journey()
    compiled = compile_scenario(scenario)
    solved_float = solve_required_monthly_sip_float(
        compiled.fund_list,
        compiled.settings,
        build_target_float(scenario),
    )
    assert solved_float == pytest.approx(
        MONTHLY_AMOUNT_FLOAT * 2.0, rel=0.01
    )


def test_a_plan_investing_nothing_cannot_be_scaled():
    """There is no mix to preserve, so the answer is honest.

    Both sources must be empty: a fund carrying a standing
    instalment is scalable even with nothing on the timeline.
    """
    empty = PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE, horizon_years_int=20
        ),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                monthly_sip_float=0.0,
                initial_investment_float=0.0,
            )
        ],
    )
    compiled = compile_scenario(empty)
    assert (
        read_base_monthly_amount_float(
            compiled.fund_list, compiled.settings
        )
        == 0.0
    )
    assert (
        solve_required_monthly_sip_float(
            compiled.fund_list, compiled.settings, 1000000.0
        )
        is None
    )


def test_the_return_solver_answers_in_points_not_a_rate():
    """The distinction the page got wrong the first time.

    A multi-fund plan needs a *shift* so the spread between an
    equity fund and a debt fund survives. Reading that shift as an
    absolute rate reports 5.63% where the answer is 17.63%.
    """
    scenario = build_rail_journey()
    compiled = compile_scenario(scenario)
    shift_float = solve_required_return_percent_float(
        compiled.fund_list,
        compiled.settings,
        build_target_float(scenario),
    )
    base_float = compiled.fund_list[
        0
    ].gross_return_percent_float
    assert shift_float is not None
    assert shift_float < base_float
    assert goal_page.solve_required_absolute_return_float(
        compiled, build_target_float(scenario)
    ) == pytest.approx(base_float + shift_float)


def test_the_required_return_exceeds_the_one_assumed():
    """Reaching more than the plan reaches needs more than it earns."""
    scenario = build_rail_journey()
    compiled = compile_scenario(scenario)
    solved_float = goal_page.solve_required_absolute_return_float(
        compiled, build_target_float(scenario)
    )
    assert solved_float > (
        compiled.fund_list[0].gross_return_percent_float
    )


def test_a_longer_horizon_is_needed_for_a_bigger_target():
    """The cheapest lever, and it must point the right way."""
    scenario = build_rail_journey()
    compiled = compile_scenario(scenario)
    solved_int = solve_required_horizon_years_int(
        compiled.fund_list,
        compiled.settings,
        build_target_float(scenario),
    )
    assert solved_int is not None
    assert solved_int > scenario.plan.horizon_years_int


# --- The page -----------------------------------------------------


def run_goal_page(scenario=None) -> AppTest:
    """Render the Goal Planner on its own.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import goal_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    )
    if scenario is not None:
        app_test.session_state[SCENARIO_STATE_KEY_STR] = scenario
    return app_test.run()


def test_the_page_asks_for_a_plan_before_a_goal():
    """A goal needs something to measure against."""
    app_test = run_goal_page()
    assert not app_test.exception
    assert any(
        "Nothing is being invested" in info.value
        for info in app_test.info
    )


def test_the_page_offers_all_three_levers():
    """Money, time, and the one that is not a lever at all."""
    app_test = run_goal_page(build_rail_journey())
    assert not app_test.exception
    assert [metric.label for metric in app_test.metric] == [
        "Monthly instalment needed",
        "Years needed",
        "Gross annual return needed",
    ]


def test_the_instalment_answer_appears_for_a_rail_plan():
    """The regression that prompted the solver fix."""
    app_test = run_goal_page(build_rail_journey())
    instalment_metric = app_test.metric[0]
    assert instalment_metric.value
    assert "0" in instalment_metric.value


def test_the_return_answer_is_hedged_not_recommended():
    """A required return is a diagnosis, not a shopping list."""
    app_test = run_goal_page(build_rail_journey())
    caption_str = " ".join(
        element.value for element in app_test.caption
    )
    assert "not a lever you control" in caption_str
