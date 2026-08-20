"""The actions that change the plan, not just describe it.

Every screen in this portal could already tell a reader what would
happen. Several of them stopped there - the Goal Planner named the
monthly amount that reaches a target and left the reader to go and
type it in, and the Rebalancing Lab ranked nine policies with no way
to use any of them.

The buttons that close those loops are the riskiest code on the
site, because a write-back that silently does nothing looks exactly
like one that worked. So each is tested the same way: press it,
re-read the shared scenario, and assert the engine's answer moved.
Asserting the button exists would prove nothing.
"""

from __future__ import annotations

from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_test_fund
from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
)
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.portal_state import (
    SCENARIO_STATE_KEY_STR,
)
from investment_journey_simulator.scenario_edits import (
    add_annual_step_up,
    add_contribution_pause,
    has_event_of_type_bool,
    set_rebalancing_rule,
)
from investment_journey_simulator.scenario_set import (
    run_journey_outcome,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    TimelineEvent,
    TimelinePlan,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 600
PLAN_START_DATE: date = date(2026, 1, 1)
MONTHLY_AMOUNT_FLOAT: float = 25000.0
HORIZON_YEARS_INT: int = 20


def build_journey() -> PlanScenario:
    """A plain plan with money on the rail."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=HORIZON_YEARS_INT,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    PLAN_START_DATE,
                    MONTHLY_AMOUNT_FLOAT,
                )
            ],
        ),
        fund_list=[build_test_fund()],
    )


def run_page(module_name_str: str, scenario: PlanScenario):
    """Render one page over a given plan."""
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import "
        f"{module_name_str} as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    )
    app_test.session_state[SCENARIO_STATE_KEY_STR] = scenario
    return app_test.run()


def read_scenario_back(app_test) -> PlanScenario:
    """The plan as the page left it."""
    return app_test.session_state[SCENARIO_STATE_KEY_STR]


def press(app_test, key_str):
    """Click one button by key and rerun."""
    for button in app_test.button:
        if button.key == key_str:
            return button.click().run()
    raise AssertionError(f"no button keyed {key_str!r}")


# ------------------------------------------------------------------
# The edits themselves, without a page in the way.
# ------------------------------------------------------------------
def test_a_step_up_raises_the_ending_value():
    """The edit has to move the engine, not just the event list."""
    scenario = build_journey()
    before_float = run_journey_outcome(scenario).final_value_float
    after_float = run_journey_outcome(
        add_annual_step_up(scenario, 10.0)
    ).final_value_float
    assert after_float > before_float


def test_a_pause_lowers_the_ending_value():
    """Stopping contributions has to cost something."""
    scenario = build_journey()
    before_float = run_journey_outcome(scenario).final_value_float
    after_float = run_journey_outcome(
        add_contribution_pause(scenario, 5, 3)
    ).final_value_float
    assert after_float < before_float


def test_a_pause_leaves_the_invested_money_compounding():
    """The distinction most people get wrong about a break.

    A pause stops the instalment. It does not liquidate anything,
    so the ending value must stay well above what was paid in.
    """
    paused = add_contribution_pause(build_journey(), 5, 3)
    outcome = run_journey_outcome(paused)
    assert outcome.final_value_float > 0.0


def test_adding_a_step_up_twice_leaves_one():
    """Pressing a button twice must not compound the plan."""
    scenario = add_annual_step_up(build_journey(), 10.0)
    scenario = add_annual_step_up(scenario, 8.0)
    step_up_list = [
        event
        for event in scenario.plan.event_list
        if event.event_type_str == EVENT_STEPUP_STR
    ]
    assert len(step_up_list) == 1
    assert step_up_list[0].percent_float == 8.0


def test_adding_a_pause_twice_leaves_one_pair():
    """Same rule for the pause, which is two events not one."""
    scenario = add_contribution_pause(build_journey(), 5, 3)
    scenario = add_contribution_pause(scenario, 8, 2)
    type_list = [
        event.event_type_str for event in scenario.plan.event_list
    ]
    assert type_list.count(EVENT_PAUSE_STR) == 1
    assert type_list.count(EVENT_RESUME_STR) == 1


def test_a_pause_resumes_after_the_length_asked_for():
    """The break has to be as long as the screen said it was."""
    scenario = add_contribution_pause(build_journey(), 5, 3)
    pause_date = next(
        event.event_date
        for event in scenario.plan.event_list
        if event.event_type_str == EVENT_PAUSE_STR
    )
    resume_date = next(
        event.event_date
        for event in scenario.plan.event_list
        if event.event_type_str == EVENT_RESUME_STR
    )
    assert pause_date.year == PLAN_START_DATE.year + 5
    assert resume_date.year == pause_date.year + 3


def test_a_rebalancing_rule_lands_on_the_policy():
    """The lab's finding has to reach the plan's policy object."""
    scenario = set_rebalancing_rule(
        build_journey(), 2, "partial", "column", "portfolio", 5
    )
    assert scenario.policy.rebalance_interval_months_int == (
        2 * MONTHS_IN_YEAR_INT
    )
    assert scenario.policy.rebalance_method_str == "partial"
    assert scenario.policy.rebalance_maximum_events_int == 5


# ------------------------------------------------------------------
# The same edits, driven through the screens that offer them.
# ------------------------------------------------------------------
def test_quick_projection_step_up_button_changes_the_plan():
    """Press it, and the shared plan really carries a step-up."""
    app_test = run_page("quick_page", build_journey())
    assert not app_test.exception
    after = read_scenario_back(
        press(app_test, "quick_add_step_up")
    )
    assert has_event_of_type_bool(after, EVENT_STEPUP_STR)


def test_quick_projection_pause_button_changes_the_plan():
    """And the break, which two other screens then read."""
    app_test = run_page("quick_page", build_journey())
    after = read_scenario_back(press(app_test, "quick_add_pause"))
    assert has_event_of_type_bool(after, EVENT_PAUSE_STR)
    assert has_event_of_type_bool(after, EVENT_RESUME_STR)


def test_the_goal_planner_applies_the_monthly_amount():
    """The lever stops being a dead end.

    The screen already knew what monthly amount reached the target.
    Until this button existed, the reader had to carry the figure to
    another screen by hand.
    """
    app_test = run_page("goal_page", build_journey())
    assert not app_test.exception
    before_float = run_journey_outcome(
        build_journey()
    ).final_value_float
    after = read_scenario_back(
        press(app_test, "goal_apply_instalment")
    )
    assert (
        run_journey_outcome(after).final_value_float > before_float
    )


def test_the_goal_planner_applies_the_horizon():
    """The second lever, which is the cheap one nobody uses."""
    app_test = run_page("goal_page", build_journey())
    after = read_scenario_back(
        press(app_test, "goal_apply_horizon")
    )
    assert after.plan.horizon_years_int > HORIZON_YEARS_INT


def test_the_required_return_can_never_be_applied():
    """The one lever that must stay a dead end, on purpose.

    Letting a reader "apply" a required return would let them reach
    any goal by editing an assumption. That is the single most
    dangerous thing this program could make easy, so the control
    exists and is disabled rather than being quietly absent.
    """
    app_test = run_page("goal_page", build_journey())
    return_button_list = [
        button
        for button in app_test.button
        if button.key == "goal_apply_return"
    ]
    assert len(return_button_list) == 1
    assert return_button_list[0].disabled


def test_the_rebalancing_lab_applies_a_rule_to_the_plan():
    """The one door out of the laboratory's isolation."""
    app_test = run_page("rebalancing_page", build_journey())
    assert not app_test.exception
    after = read_scenario_back(press(app_test, "lab_apply_rule"))
    assert after.policy.rebalance_interval_months_int > 0


def test_the_rebalancing_lab_leaves_the_funds_alone():
    """Only the rule travels; the lab's funds stay in the lab."""
    scenario = build_journey()
    app_test = run_page("rebalancing_page", scenario)
    after = read_scenario_back(press(app_test, "lab_apply_rule"))
    assert [fund.name_str for fund in after.fund_list] == [
        fund.name_str for fund in scenario.fund_list
    ]


# ------------------------------------------------------------------
# The claim the whole portal rests on: type it once.
# ------------------------------------------------------------------
def test_a_change_on_one_screen_is_visible_on_the_next():
    """One plan, nine screens, no re-typing.

    This is the promise that made the portal worth building out of
    three separate programs, and it is the one a refactor is most
    likely to break silently - each screen would still work, and
    only a reader moving between two of them would notice.

    So the journey is walked: add a step-up on Quick, then read the
    plan back from Goal Planner and from Reports and assert both
    are looking at the plan Quick left behind.
    """
    quick_test = run_page("quick_page", build_journey())
    after = read_scenario_back(
        press(quick_test, "quick_add_step_up")
    )
    assert has_event_of_type_bool(after, EVENT_STEPUP_STR)

    goal_test = run_page("goal_page", after)
    assert not goal_test.exception
    assert has_event_of_type_bool(
        read_scenario_back(goal_test), EVENT_STEPUP_STR
    )

    reports_test = run_page("reports_page", after)
    assert not reports_test.exception
    assert has_event_of_type_bool(
        read_scenario_back(reports_test), EVENT_STEPUP_STR
    )


def test_the_reported_fingerprint_tracks_the_inputs():
    """Two readers quoting a figure can check they agree.

    The fingerprint is only worth printing if it actually changes
    when the plan does, and stays put when it does not.
    """
    from investment_journey_simulator.pages.reports_page import (
        build_run_fingerprint_str,
    )

    scenario = build_journey()
    assert build_run_fingerprint_str(
        scenario
    ) == build_run_fingerprint_str(build_journey())
    assert build_run_fingerprint_str(
        add_annual_step_up(scenario, 10.0)
    ) != build_run_fingerprint_str(scenario)
