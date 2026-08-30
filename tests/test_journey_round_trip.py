"""Saving, editing elsewhere, and saving again.

Every other page test drives one screen. This one drives two, in
the order a reader actually uses them, because the defect it was
written for lived precisely in the gap between them:

    Compare -> save as "A"
    Guided  -> change something
    Compare -> save as "B"

Each screen was correct on its own. The engine was correct. The
save made a genuine copy and the comparison ran each journey
separately. What went wrong was that the field labelled "How much
every month" belonged to the *add an event* composer, so typing in
it changed nothing until the event was placed - and the reader,
having changed a number and seen no complaint, saved the same plan
twice under two names and got a comparison of a plan with itself:
two identical curves, a spread of zero, and an attribution with
nothing in it.

That reads as an answer rather than as the mistake it is, which is
what makes it worth a file of its own.
"""

from __future__ import annotations

from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_test_fund
from investment_journey_simulator import timeline_app
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.portal_state import (
    COMPARISON_STATE_KEY_STR,
    SCENARIO_STATE_KEY_STR,
)
from investment_journey_simulator.scenario_edits import (
    build_named_copy,
)
from investment_journey_simulator.scenario_set import (
    ScenarioSet,
    find_duplicate_name_list,
    find_identical_journey_str,
    run_scenario_set,
)
from investment_journey_simulator.timeline import (
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 900
PLAN_START_DATE: date = date(2026, 1, 1)


def build_page_script_str(module_name_str: str) -> str:
    """A one-page app, so each screen can be driven on its own."""
    return (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import "
        f"{module_name_str}\n"
        f"{module_name_str}.render()\n"
    )


def build_scenario(amount_float: float) -> PlanScenario:
    """A plain twenty-year plan investing one amount."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=20,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    PLAN_START_DATE,
                    amount_float,
                )
            ],
        ),
        fund_list=[build_test_fund(name_str="Equity")],
        name_str="My plan",
    )


class Session:
    """One reader moving between screens.

    Streamlit's harness runs one page at a time, so the session
    has to be carried across by hand. Doing so is the whole point:
    a defect that only appears when two screens share state cannot
    be found by a harness that never shares any.
    """

    def __init__(self, scenario: PlanScenario) -> None:
        """Open a session on one plan."""
        self.state_dict: dict = {
            SCENARIO_STATE_KEY_STR: scenario
        }

    def visit(self, module_name_str: str, action=None) -> AppTest:
        """Render one page, optionally act, and keep the state."""
        app_test = AppTest.from_string(
            build_page_script_str(module_name_str),
            default_timeout=PAGE_TIMEOUT_SECONDS_INT,
        )
        for key_str, value in self.state_dict.items():
            app_test.session_state[key_str] = value
        app_test.run()
        if action is not None:
            action(app_test)
            app_test.run()
        for key_str in app_test.session_state.filtered_state:
            self.state_dict[key_str] = app_test.session_state[
                key_str
            ]
        return app_test

    @property
    def held_list(self) -> list:
        """The journeys currently saved for comparison."""
        return list(
            self.state_dict.get(COMPARISON_STATE_KEY_STR, [])
        )

    @property
    def live_scenario(self) -> PlanScenario:
        """The plan every screen is working on."""
        return self.state_dict[SCENARIO_STATE_KEY_STR]


def save_as(name_str: str):
    """An action that names the plan and saves it."""

    def action(app_test: AppTest) -> None:
        app_test.text_input[0].set_value(name_str)
        app_test.button[0].click()

    return action


def set_monthly_amount(amount_float: float):
    """An action that edits what the plan invests each month."""

    def action(app_test: AppTest) -> None:
        for widget in app_test.number_input:
            if widget.label.startswith("Invest each month"):
                widget.set_value(amount_float)
                return
        raise AssertionError(
            "the Guided page offers no way to change the monthly "
            "amount, which is the gap this file exists for"
        )

    return action


def read_starting_amount_list(scenario: PlanScenario) -> list:
    """Every opening instalment a plan carries."""
    return [
        event.amount_float
        for event in scenario.plan.event_list
        if event.event_type_str == EVENT_START_SIP_STR
    ]


# ------------------------------------------------------------------
# The round trip.
# ------------------------------------------------------------------
def test_editing_the_amount_between_saves_gives_two_journeys():
    """The reported defect, as an assertion.

    REFERENCE: G4-SYNTHETIC. Save, change the monthly amount on
    the timeline, save again. Two journeys, two answers.
    """
    session = Session(build_scenario(25000.0))
    session.visit("guided_page")
    session.visit("compare_page", save_as("A"))
    session.visit("guided_page", set_monthly_amount(60000.0))
    session.visit("compare_page", save_as("B"))

    held_list = session.held_list
    assert [held.name_str for held in held_list] == ["A", "B"]
    final_list = [
        outcome.final_value_float
        for outcome in run_scenario_set(ScenarioSet(held_list))
    ]
    assert final_list[0] != pytest.approx(final_list[1])


def test_the_amount_control_reaches_the_shared_scenario():
    """The edit has to survive leaving the page.

    REFERENCE: G4-SYNTHETIC.
    """
    session = Session(build_scenario(25000.0))
    session.visit("guided_page", set_monthly_amount(60000.0))
    assert read_starting_amount_list(session.live_scenario) == [
        60000.0
    ]


def test_the_rail_keeps_the_edited_amount():
    """The rail and the scenario must not disagree.

    REFERENCE: G4-SYNTHETIC. The rail is what the plan is
    republished from, so an edit reaching the scenario but not the
    rail would be undone by the very next render.
    """
    session = Session(build_scenario(25000.0))
    session.visit("guided_page", set_monthly_amount(60000.0))
    session.visit("guided_page")
    rail_list = session.state_dict[
        timeline_app.EVENT_STATE_KEY_STR
    ]
    assert [
        event.amount_float
        for event in rail_list
        if event.event_type_str == EVENT_START_SIP_STR
    ] == [60000.0]


# ------------------------------------------------------------------
# Saving the same plan twice.
# ------------------------------------------------------------------
def test_saving_an_unchanged_plan_under_a_new_name_is_refused():
    """A plan compared with itself is not a comparison.

    REFERENCE: G4-SYNTHETIC. The reader is told which journey it
    duplicates, rather than being handed two identical curves and
    left to work out why the difference is zero.
    """
    session = Session(build_scenario(25000.0))
    session.visit("guided_page")
    session.visit("compare_page", save_as("A"))
    app_test = session.visit("compare_page", save_as("B"))

    assert [held.name_str for held in session.held_list] == ["A"]
    warning_str = " ".join(
        warning.value for warning in app_test.warning
    )
    assert "same plan" in warning_str
    assert "A" in warning_str


def test_saving_under_an_existing_name_still_replaces_it():
    """Changing your mind about a journey must keep working.

    REFERENCE: G4-SYNTHETIC. The duplicate guard must not turn a
    replacement into a refusal.
    """
    session = Session(build_scenario(25000.0))
    session.visit("guided_page")
    session.visit("compare_page", save_as("A"))
    session.visit("guided_page", set_monthly_amount(60000.0))
    session.visit("compare_page", save_as("A"))

    held_list = session.held_list
    assert [held.name_str for held in held_list] == ["A"]
    assert read_starting_amount_list(held_list[0]) == [60000.0]


# ------------------------------------------------------------------
# The rules underneath, without a page in the way.
# ------------------------------------------------------------------
def test_two_plans_differing_only_in_name_are_identical():
    """REFERENCE: G4-SYNTHETIC."""
    scenario = build_scenario(25000.0)
    scenario_set = ScenarioSet([build_named_copy(scenario, "A")])
    assert (
        find_identical_journey_str(
            scenario_set, build_named_copy(scenario, "B")
        )
        == "A"
    )


def test_two_plans_differing_in_amount_are_not_identical():
    """REFERENCE: G4-SYNTHETIC."""
    scenario_set = ScenarioSet(
        [build_named_copy(build_scenario(25000.0), "A")]
    )
    assert (
        find_identical_journey_str(
            scenario_set,
            build_named_copy(build_scenario(60000.0), "B"),
        )
        == ""
    )


def test_a_set_holding_duplicates_names_all_of_them():
    """Which one is the copy is not a question the set can answer.

    REFERENCE: G4-SYNTHETIC.
    """
    scenario = build_scenario(25000.0)
    scenario_set = ScenarioSet(
        [
            build_named_copy(scenario, "A"),
            build_named_copy(build_scenario(60000.0), "B"),
            build_named_copy(scenario, "C"),
        ]
    )
    assert find_duplicate_name_list(scenario_set) == ["A", "C"]


def test_a_set_of_genuinely_different_plans_names_none():
    """REFERENCE: G4-SYNTHETIC."""
    scenario_set = ScenarioSet(
        [
            build_named_copy(build_scenario(25000.0), "A"),
            build_named_copy(build_scenario(60000.0), "B"),
        ]
    )
    assert find_duplicate_name_list(scenario_set) == []
