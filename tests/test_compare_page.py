"""The Compare Journeys screen, rendered for real.

This is the screen the whole program was worth building for, so the
tests check the claims it makes on screen: that the spread is
stated, that the gap is explained rather than merely shown, and that
a comparison which cannot hold its basis says so.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_test_fund
from investment_journey_simulator.pages import compare_page
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.portal_state import (
    COMPARISON_STATE_KEY_STR,
    SCENARIO_STATE_KEY_STR,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 600
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


def build_paused_journey() -> PlanScenario:
    """The same plan with three years off in the middle."""
    return build_journey(
        "Paused for three years",
        TimelineEvent(EVENT_PAUSE_STR, date(2030, 1, 1)),
        TimelineEvent(EVENT_RESUME_STR, date(2032, 12, 1)),
    )


def run_compare_page(journey_list=None) -> AppTest:
    """Render the Compare page with journeys already held.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import compare_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    )
    if journey_list is not None:
        app_test.session_state[COMPARISON_STATE_KEY_STR] = (
            journey_list
        )
        app_test.session_state[SCENARIO_STATE_KEY_STR] = (
            journey_list[0]
        )
    return app_test.run()


def read_markdown_str(app_test: AppTest) -> str:
    """Everything the page wrote as markdown, joined.

    REFERENCE: harness only.
    """
    return " ".join(
        element.value for element in app_test.markdown
    )


# --- Empty states -------------------------------------------------


def test_the_page_opens_with_nothing_saved():
    """A reader may arrive here before building anything."""
    app_test = run_compare_page()
    assert not app_test.exception
    assert app_test.title[0].value == compare_page.TITLE_STR


def test_one_journey_asks_for_a_second():
    """A comparison of one is not a comparison."""
    app_test = run_compare_page([build_journey("Steady")])
    assert not app_test.exception
    assert any(
        "at least two" in info.value for info in app_test.info
    )
    assert app_test.metric == []


# --- The comparison -----------------------------------------------


def test_two_journeys_produce_a_tile_each():
    """The four-up headline, with two."""
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    assert not app_test.exception
    assert [metric.label for metric in app_test.metric] == [
        "Steady",
        "Paused for three years",
    ]


def test_the_spread_is_stated_outright():
    """The headline figure of the whole screen.

    It leads the page rather than trailing the tiles, because the
    gap is the finding and a reader should never have to subtract
    two of the figures themselves to find it.
    """
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    markdown_str = read_markdown_str(app_test)
    assert "What the decisions cost" in markdown_str
    assert "price of the decisions alone" in markdown_str


def test_the_gap_is_explained_not_merely_shown():
    """The claim that makes this more than four curves."""
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    assert "Why the gap exists" in [
        heading.value for heading in app_test.subheader
    ]
    assert "Compounding lost to the pause" in read_markdown_str(
        app_test
    )


def test_the_pause_is_explained_in_words():
    """The counter-intuitive part needs saying, not just plotting."""
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    caption_str = " ".join(
        element.value for element in app_test.caption
    )
    assert "never earned anything" in caption_str


def test_a_shared_basis_is_confirmed_on_screen():
    """A reader should know the comparison is about behaviour."""
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    assert any(
        "caused by behaviour" in success.value
        for success in app_test.success
    )


def test_a_broken_basis_is_warned_about():
    """Four figures across two returns say nothing about decisions."""
    optimistic = replace(
        build_journey("Optimistic"),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                gross_return_percent_float=15.0,
            )
        ],
    )
    app_test = run_compare_page(
        [build_journey("Steady"), optimistic]
    )
    assert not app_test.exception
    assert any(
        "not caused by behaviour alone" in warning.value
        for warning in app_test.warning
    )


def test_no_unexplained_residual_is_reported():
    """The causes add up, so the page never has to apologise."""
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    assert not any(
        "unexplained" in warning.value.lower()
        for warning in app_test.warning
    )


def test_four_journeys_render():
    """The shape the posts will show."""
    journey_list = [
        build_journey("Steady"),
        build_paused_journey(),
        build_journey(
            "Paused twice",
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2030, 12, 1)),
            TimelineEvent(EVENT_PAUSE_STR, date(2035, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2036, 12, 1)),
        ),
        build_journey(
            "Stopped at fifteen years",
            TimelineEvent(EVENT_PAUSE_STR, date(2041, 1, 1)),
        ),
    ]
    app_test = run_compare_page(journey_list)
    assert not app_test.exception
    assert len(app_test.metric) == 4


def test_the_journeys_held_are_listed():
    """A reader must see what is being compared."""
    app_test = run_compare_page(
        [build_journey("Steady"), build_paused_journey()]
    )
    markdown_str = read_markdown_str(app_test)
    assert "Journeys held for comparison" in markdown_str
