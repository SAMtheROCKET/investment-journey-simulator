"""No screen may be handed a value it refuses to display.

A reader solved a goal that needed fifty-two years, applied it,
opened Quick Projection, and the page died:

    StreamlitValueAboveMaxError: `value` 52 is greater than
    `max_value` 50

Nothing was wrong with fifty-two years. The goal solver searched to
sixty, the guided slider allowed sixty, the advanced sidebar
allowed sixty, and Quick Projection alone stopped at fifty. A limit
that lives in four places is not a limit; it is a disagreement
waiting for somebody to walk into it.

The same sweep found a second: a negative expected return is legal
on the timeline and was legal nowhere else, so a plan assuming a
fund loses money took Quick Projection down too.

Two rules come out of that, and this file holds both.

**One ceiling, named once.** Every control bounding the same
quantity reads the same constant, so a plan legal on one screen is
legal on all of them.

**A control clamps rather than dies.** Agreeing on a limit fixes
today's crash and not tomorrow's: a scenario loaded from a file, or
saved before a limit moved, can still arrive out of range. A widget
handed an impossible value should show the nearest possible one,
not take the page down.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH
from investment_journey_simulator.constants import (
    GOAL_SEEK_MAXIMUM_YEARS_INT,
    MAXIMUM_HORIZON_YEARS_INT,
    MAXIMUM_RETURN_PERCENT_FLOAT,
    MINIMUM_HORIZON_YEARS_INT,
    MINIMUM_RETURN_PERCENT_FLOAT,
)
from investment_journey_simulator.pages import quick_page
from investment_journey_simulator.portal_state import (
    SCENARIO_STATE_KEY_STR,
    build_default_scenario,
)
from investment_journey_simulator.timeline import (
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)
from investment_journey_simulator.ui import sidebar_controls

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 900
PAGE_NAME_TUPLE: tuple = (
    "quick_page",
    "guided_page",
    "goal_page",
    "advanced_page",
    "compare_page",
    "risk_page",
    "rebalancing_page",
    "reports_page",
)


def build_scenario(**override_dict):
    """A plain plan, with one field pushed to an extreme."""
    scenario = build_default_scenario()
    scenario = replace(
        scenario,
        plan=TimelinePlan(
            date(2026, 1, 1),
            20,
            [
                TimelineEvent(
                    EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
                )
            ],
        ),
    )
    return_percent_float = override_dict.pop(
        "return_percent_float", None
    )
    if return_percent_float is not None:
        scenario = replace(
            scenario,
            fund_list=[
                replace(
                    fund,
                    gross_return_percent_float=(
                        return_percent_float
                    ),
                )
                for fund in scenario.fund_list
            ],
        )
    horizon_years_int = override_dict.pop("horizon_years_int", None)
    if horizon_years_int is not None:
        scenario = replace(
            scenario,
            plan=replace(
                scenario.plan, horizon_years_int=horizon_years_int
            ),
        )
    return replace(scenario, **override_dict)


def render_page(page_name_str: str, scenario) -> AppTest:
    """Render one screen on a scenario and return the app."""
    app_test = AppTest.from_string(
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import "
        f"{page_name_str}\n"
        f"{page_name_str}.render()\n",
        default_timeout=PAGE_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[SCENARIO_STATE_KEY_STR] = scenario
    app_test.run()
    return app_test


# ------------------------------------------------------------------
# One ceiling, named once.
# ------------------------------------------------------------------
def test_every_screen_agrees_on_how_long_a_plan_may_run():
    """The disagreement that produced the crash.

    REFERENCE: G4-SYNTHETIC. Four places bounded the horizon and
    one of them was lower than the rest.
    """
    assert (
        quick_page.MAXIMUM_HORIZON_INT
        == sidebar_controls.MAXIMUM_HORIZON_YEARS_INT
        == GOAL_SEEK_MAXIMUM_YEARS_INT
        == MAXIMUM_HORIZON_YEARS_INT
    )
    assert (
        quick_page.MINIMUM_HORIZON_INT
        == sidebar_controls.MINIMUM_HORIZON_YEARS_INT
        == MINIMUM_HORIZON_YEARS_INT
    )


def test_the_goal_solver_cannot_propose_an_unshowable_plan():
    """A solver may not answer with a plan no screen can display.

    REFERENCE: G4-SYNTHETIC. This is the direction that bit: the
    solver wrote the value, and another screen refused it.
    """
    assert GOAL_SEEK_MAXIMUM_YEARS_INT <= MAXIMUM_HORIZON_YEARS_INT


def test_a_negative_return_is_allowed_everywhere_or_nowhere():
    """Assuming a fund loses money is a fair question to ask.

    REFERENCE: G4-SYNTHETIC. The timeline allowed it and Quick
    Projection did not, so a plan built on one died on the other.
    """
    assert MINIMUM_RETURN_PERCENT_FLOAT < 0.0
    assert MAXIMUM_RETURN_PERCENT_FLOAT > 0.0


# ------------------------------------------------------------------
# A control clamps rather than dies.
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "horizon_years_int", [0, 52, 75, 200, -5]
)
def test_quick_projection_survives_any_stored_horizon(
    horizon_years_int,
):
    """Including values no control could have produced.

    REFERENCE: G4-SYNTHETIC. A saved file is not obliged to
    respect a limit invented after it was written.
    """
    app_test = render_page(
        "quick_page",
        build_scenario(horizon_years_int=horizon_years_int),
    )
    assert not app_test.exception


@pytest.mark.parametrize(
    "return_percent_float", [-40.0, -5.0, 45.0, 120.0]
)
def test_quick_projection_survives_any_stored_return(
    return_percent_float,
):
    """REFERENCE: G4-SYNTHETIC."""
    app_test = render_page(
        "quick_page",
        build_scenario(return_percent_float=return_percent_float),
    )
    assert not app_test.exception


def test_clamping_leaves_a_value_already_in_range_alone():
    """The guard must not quietly move a sensible figure.

    REFERENCE: G4-SYNTHETIC.
    """
    assert quick_page.clamp_horizon_int(20) == 20
    assert quick_page.clamp_return_float(12.0) == 12.0
    assert quick_page.clamp_horizon_int(
        MAXIMUM_HORIZON_YEARS_INT
    ) == MAXIMUM_HORIZON_YEARS_INT
    assert quick_page.clamp_return_float(
        MINIMUM_RETURN_PERCENT_FLOAT
    ) == MINIMUM_RETURN_PERCENT_FLOAT


# ------------------------------------------------------------------
# The sweep, kept because one screen at a time is how this hid.
# ------------------------------------------------------------------
@pytest.mark.parametrize("page_name_str", PAGE_NAME_TUPLE)
def test_no_screen_dies_on_an_extreme_plan(page_name_str):
    """Every screen, against every value the others allow.

    REFERENCE: G4-SYNTHETIC. The failure only exists in the gap
    between two screens, so it has to be swept across all of them
    rather than checked on the one that happened to break.
    """
    for scenario in (
        build_scenario(horizon_years_int=60),
        build_scenario(return_percent_float=-5.0),
        build_scenario(return_percent_float=45.0),
        build_scenario(inflation_percent_float=35.0),
        build_scenario(inflation_percent_float=-8.0),
    ):
        app_test = render_page(page_name_str, scenario)
        assert not app_test.exception, (
            f"{page_name_str} died on "
            f"{app_test.exception[0].value[:120]}"
        )
