"""The Guided Journey screen and the bridge underneath it.

The rail keeps its plan in its own session-state keys. These tests
are about the sync: a plan built elsewhere must appear here, edits
made here must be visible elsewhere, and the seed must not fight
the reader while they are typing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH
from investment_journey_simulator.pages import guided_page
from investment_journey_simulator.portal_state import (
    SCENARIO_STATE_KEY_STR,
    build_default_scenario,
)
from investment_journey_simulator.scenario_bridge import (
    BRIDGE_MARKER_KEY_STR,
    build_marker_str,
    needs_seeding_bool,
)
from investment_journey_simulator.scenario_edits import (
    set_horizon_years,
    set_monthly_contribution,
)
from investment_journey_simulator.timeline import (
    EVENT_START_SIP_STR,
    TimelineEvent,
)
from investment_journey_simulator.timeline_app import EVENT_STATE_KEY_STR

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 300


def build_guided_app(scenario=None) -> AppTest:
    """Prepare the Guided page, optionally with a plan loaded.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import guided_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    )
    if scenario is not None:
        app_test.session_state[SCENARIO_STATE_KEY_STR] = scenario
    return app_test


def build_arrived_scenario():
    """A plan as it would arrive from the Quick screen."""
    return set_horizon_years(
        set_monthly_contribution(
            build_default_scenario(), 25000.0
        ),
        30,
    )


# --- The page -----------------------------------------------------


def test_the_page_opens_on_an_empty_plan():
    """A reader may arrive here first, with nothing entered."""
    app_test = build_guided_app().run()
    assert not app_test.exception
    assert app_test.title[0].value == guided_page.TITLE_STR


def test_the_page_asks_the_questions_it_can_answer():
    """A blank rail does not say what to put on it."""
    app_test = build_guided_app().run()
    markdown_str = " ".join(
        element.value for element in app_test.markdown
    )
    assert "raise the amount" in markdown_str
    assert "pause" in markdown_str


# --- Carrying a plan in ------------------------------------------


def test_a_plan_built_elsewhere_appears_on_the_rail():
    """The promise: you do not type it twice."""
    app_test = build_guided_app(build_arrived_scenario()).run()
    assert not app_test.exception
    assert len(app_test.session_state[EVENT_STATE_KEY_STR]) == 1
    assert (
        app_test.session_state[EVENT_STATE_KEY_STR][0].amount_float
        == 25000.0
    )


def test_the_assumptions_carry_across_too():
    """A horizon set on another screen is not silently reset."""
    app_test = build_guided_app(build_arrived_scenario()).run()
    scenario = app_test.session_state[SCENARIO_STATE_KEY_STR]
    assert scenario.plan.horizon_years_int == 30


def test_the_events_survive_the_round_trip():
    """Rendering must not drop what it was given."""
    app_test = build_guided_app(build_arrived_scenario()).run()
    scenario = app_test.session_state[SCENARIO_STATE_KEY_STR]
    assert [
        event.event_type_str
        for event in scenario.plan.event_list
    ] == [EVENT_START_SIP_STR]


def test_the_rail_takes_ownership_of_the_amounts():
    """Every rupee a rail plan invests arrives as an event."""
    app_test = build_guided_app(build_arrived_scenario()).run()
    scenario = app_test.session_state[SCENARIO_STATE_KEY_STR]
    assert scenario.timeline_owns_amounts_bool is True


# --- The seeding rule --------------------------------------------


def test_a_first_visit_seeds():
    """Nothing has been published, so the rail must be loaded."""
    assert needs_seeding_bool(build_arrived_scenario()) is True


def test_an_unchanged_scenario_does_not_reseed(monkeypatch):
    """Otherwise the seed would overwrite every keystroke."""
    import streamlit as st

    scenario = build_arrived_scenario()
    state_dict = {
        BRIDGE_MARKER_KEY_STR: build_marker_str(scenario)
    }
    monkeypatch.setattr(st, "session_state", state_dict)
    assert needs_seeding_bool(scenario) is False


def test_a_scenario_changed_elsewhere_reseeds(monkeypatch):
    """Editing on another screen must reload this one."""
    import streamlit as st

    scenario = build_arrived_scenario()
    state_dict = {
        BRIDGE_MARKER_KEY_STR: build_marker_str(scenario)
    }
    monkeypatch.setattr(st, "session_state", state_dict)
    changed = set_horizon_years(scenario, 40)
    assert needs_seeding_bool(changed) is True


def test_the_marker_ignores_event_order():
    """Two plans differing only in insertion order are one plan."""
    scenario = build_arrived_scenario()
    extra_event = TimelineEvent(
        "Note to self", date(2030, 1, 1), note_str="house"
    )
    forward = replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=[*scenario.plan.event_list, extra_event],
        ),
    )
    backward = replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=[extra_event, *scenario.plan.event_list],
        ),
    )
    assert build_marker_str(forward) == build_marker_str(backward)


def test_the_marker_notices_a_real_change():
    """A fingerprint that never changes would be useless."""
    scenario = build_arrived_scenario()
    assert build_marker_str(scenario) != build_marker_str(
        set_horizon_years(scenario, 31)
    )
