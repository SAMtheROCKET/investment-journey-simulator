"""The Historical & Risk Lab, rendered against real index history.

The summariser's key names are load-bearing: get one wrong and the
page renders a heading with no figures under it, which is exactly
what happened the first time. `test_the_summary_keys_are_real`
exists so a rename breaks a test rather than a screen.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_test_fund
from investment_journey_simulator.backtest import (
    run_rolling_backtest_list,
    summarise_rolling_outcomes_dict,
)
from investment_journey_simulator.market_data import (
    load_bundled_market_history,
)
from investment_journey_simulator.pages import risk_page
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import SCENARIO_STATE_KEY_STR
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


def build_short_journey(horizon_years_int: int = 2) -> PlanScenario:
    """A plan short enough to replay inside the bundled history."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=horizon_years_int,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR, PLAN_START_DATE, 25000.0
                )
            ],
        ),
        fund_list=[build_test_fund(name_str="Equity")],
        name_str="Steady",
    )


def run_risk_page(scenario=None) -> AppTest:
    """Render the risk page on its own.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import risk_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    )
    if scenario is not None:
        app_test.session_state[SCENARIO_STATE_KEY_STR] = scenario
    return app_test.run()


# --- The contract with the summariser -----------------------------


def test_the_summary_keys_are_real():
    """The page names keys the summariser actually emits.

    Getting one wrong renders a heading above an empty row, which
    no exception would ever catch.
    """
    history = load_bundled_market_history()
    assert history is not None
    compiled = compile_scenario(build_short_journey())
    summary_dict = summarise_rolling_outcomes_dict(
        run_rolling_backtest_list(
            compiled.fund_list, compiled.settings, history
        )
    )
    for key_str, _label_str in risk_page.SUMMARY_KEY_TUPLE:
        assert key_str in summary_dict


def test_the_bundled_history_loads():
    """The replay section is worthless without it."""
    history = load_bundled_market_history()
    assert history is not None
    assert len(history.month_end_close_list) > 12


# --- The page -----------------------------------------------------


def test_the_page_asks_for_a_plan_first():
    """Risk is a property of a plan, not of nothing."""
    app_test = run_risk_page()
    assert not app_test.exception
    assert any(
        "Nothing is being invested" in info.value
        for info in app_test.info
    )


def test_the_replay_reports_best_median_and_worst():
    """The three figures that show what timing was worth."""
    app_test = run_risk_page(build_short_journey())
    assert not app_test.exception
    label_list = [metric.label for metric in app_test.metric]
    assert "Best start month" in label_list
    assert "Median start month" in label_list
    assert "Worst start month" in label_list


def test_the_cost_of_timing_is_stated_outright():
    """The headline the replay exists to produce."""
    app_test = run_risk_page(build_short_journey())
    markdown_str = " ".join(
        element.value for element in app_test.markdown
    )
    assert "month you happened to start was worth" in markdown_str


def test_the_windows_are_called_a_range_not_a_distribution():
    """Overlapping windows are correlated, and the page says so."""
    app_test = run_risk_page(build_short_journey())
    caption_str = " ".join(
        element.value for element in app_test.caption
    )
    assert "range rather than a distribution" in caption_str


def test_sequence_risk_is_explained():
    """The most under-appreciated risk deserves words, not a chart."""
    app_test = run_risk_page(build_short_journey())
    markdown_str = " ".join(
        element.value for element in app_test.markdown
    )
    assert "year two" in markdown_str
    assert "year twenty-eight" in markdown_str


def test_a_horizon_longer_than_the_history_says_so():
    """Better to explain than to silently show nothing."""
    app_test = run_risk_page(build_short_journey(30))
    assert not app_test.exception
    assert any(
        "shorter than this plan" in info.value
        for info in app_test.info
    )


def test_the_simulated_risk_section_still_runs():
    """It does not depend on any bundled history."""
    app_test = run_risk_page(build_short_journey(30))
    assert "Risk: the fan of outcomes" in [
        heading.value for heading in app_test.subheader
    ]


def test_history_and_simulation_are_never_the_same_surface():
    """The firmest rule this screen has.

    Measured history and modelled probability answer different
    questions, and a reader who carries a figure from one into the
    other has been misled by the layout rather than by any number.
    Two tabs, each stating on its face which kind of thing it holds.
    """
    app_test = run_risk_page(build_short_journey(30))
    assert not app_test.exception
    label_list = [tab.label for tab in app_test.tabs]
    assert risk_page.HISTORY_TAB_STR in label_list
    assert risk_page.SIMULATION_TAB_STR in label_list
    markdown_str = " ".join(
        str(block.value) for block in app_test.markdown
    )
    assert "Measured · real index history" in markdown_str
    assert "Modelled · generated from your assumptions" in (
        markdown_str
    )


def test_a_pause_does_not_break_the_replay():
    """A realistic plan has events in it."""
    scenario = build_short_journey()
    scenario = replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=[
                *scenario.plan.event_list,
                TimelineEvent(
                    "Pause contributions", date(2026, 6, 1)
                ),
                TimelineEvent(
                    "Resume contributions", date(2026, 12, 1)
                ),
            ],
        ),
    )
    app_test = run_risk_page(scenario)
    assert not app_test.exception
