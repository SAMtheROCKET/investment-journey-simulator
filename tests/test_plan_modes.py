"""Three experience levels over one scenario.

The tests that matter here are the ones about *not* losing things.
A mode is allowed to hide a setting; it is never allowed to drop
one, and it is never allowed to hide one silently.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.constants import WITHDRAWAL_MODE_PERCENT_STR
from investment_journey_simulator.plan_modes import (
    EXPERT_PROJECTION,
    GUIDED_PROJECTION,
    MODE_EXPERT_STR,
    MODE_GUIDED_STR,
    MODE_ORDER_TUPLE,
    MODE_QUICK_STR,
    QUICK_PROJECTION,
    SCENARIO_SETTING_TUPLE,
    SETTING_PAUSE_STR,
    SETTING_REBALANCE_STR,
    SETTING_TIMING_STR,
    build_hidden_summary_str,
    describe_hidden_setting_list,
    resolve_projection,
)
from investment_journey_simulator.plan_policy import PlanPolicy
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_REBALANCE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

PLAN_START_DATE: date = date(2026, 1, 1)


def build_plain_scenario() -> PlanScenario:
    """A scenario a Quick reader could have produced."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=20,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    date(2026, 1, 1),
                    25000.0,
                )
            ],
        ),
        fund_list=[build_test_fund(name_str="Equity")],
    )


def build_expert_scenario() -> PlanScenario:
    """A scenario carrying configuration Quick cannot show."""
    plain = build_plain_scenario()
    return replace(
        plain,
        plan=replace(
            plain.plan,
            event_list=plain.plan.event_list
            + [
                TimelineEvent(EVENT_PAUSE_STR, date(2029, 4, 1)),
                TimelineEvent(EVENT_RESUME_STR, date(2030, 4, 1)),
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2031, 3, 1)
                ),
            ],
        ),
        policy=PlanPolicy(
            sip_at_month_start_bool=False,
            withdrawal_mode_str=WITHDRAWAL_MODE_PERCENT_STR,
            withdrawal_portfolio_percent_float=4.0,
        ),
        fund_list=[
            build_test_fund(name_str="Equity"),
            build_test_fund(name_str="Debt"),
        ],
    )


# --- Every setting must be reachable ------------------------------


def test_every_setting_is_shown_by_at_least_one_mode():
    """A field no mode can edit is a bug, not a feature."""
    reachable_set: set = set()
    for mode_str in MODE_ORDER_TUPLE:
        reachable_set |= set(
            resolve_projection(mode_str).setting_key_tuple
        )
    unreachable_list = [
        setting.key_str
        for setting in SCENARIO_SETTING_TUPLE
        if setting.key_str not in reachable_set
    ]
    assert unreachable_list == []


def test_expert_shows_everything():
    """Expert is the mode with nothing left out."""
    assert len(EXPERT_PROJECTION.setting_key_tuple) == len(
        SCENARIO_SETTING_TUPLE
    )


def test_the_modes_nest():
    """Each level adds to the one before rather than replacing it."""
    quick_set = set(QUICK_PROJECTION.setting_key_tuple)
    guided_set = set(GUIDED_PROJECTION.setting_key_tuple)
    expert_set = set(EXPERT_PROJECTION.setting_key_tuple)
    assert quick_set < guided_set < expert_set


def test_setting_keys_are_unique():
    """A duplicate key would silently shadow a whole control."""
    key_list = [
        setting.key_str for setting in SCENARIO_SETTING_TUPLE
    ]
    assert len(key_list) == len(set(key_list))


def test_an_unknown_mode_falls_back_to_guided():
    """A stale bookmark must not dump a beginner into Expert."""
    assert resolve_projection("NONSENSE") is GUIDED_PROJECTION


# --- Lossy in display, never in data ------------------------------


def test_switching_mode_does_not_touch_the_scenario():
    """Modes are declarations, not transformations."""
    scenario = build_expert_scenario()
    for mode_str in MODE_ORDER_TUPLE:
        describe_hidden_setting_list(scenario, mode_str)
        build_hidden_summary_str(scenario, mode_str)
    assert scenario == build_expert_scenario()


def test_a_round_trip_through_every_mode_preserves_everything():
    """Expert to Quick to Expert returns the identical object."""
    scenario = build_expert_scenario()
    first_expert_list = resolve_projection(
        MODE_EXPERT_STR
    ).setting_list
    for mode_str in (MODE_QUICK_STR, MODE_GUIDED_STR):
        assert resolve_projection(mode_str).setting_list
    assert scenario == build_expert_scenario()
    assert (
        resolve_projection(MODE_EXPERT_STR).setting_list
        == first_expert_list
    )
    assert compile_scenario(scenario) == compile_scenario(
        build_expert_scenario()
    )


def test_quick_still_runs_the_hidden_configuration():
    """Hidden means unshown, never ignored.

    The failure this guards: someone configures a plan in Expert,
    clicks Quick to check a number, and Quick answers a question
    they did not ask.
    """
    scenario = build_expert_scenario()
    compiled = compile_scenario(scenario)
    assert compiled.settings.sip_at_month_start_bool is False
    assert compiled.settings.rebalance.is_enabled_bool is True
    assert len(compiled.settings.pauses.pause_ranges_list) == 1


# --- The warning --------------------------------------------------


def test_quick_reports_the_settings_it_hides():
    """Hidden configuration is announced, not silent."""
    hidden_list = describe_hidden_setting_list(
        build_expert_scenario(), MODE_QUICK_STR
    )
    hidden_key_set = {hidden.key_str for hidden in hidden_list}
    assert SETTING_PAUSE_STR in hidden_key_set
    assert SETTING_REBALANCE_STR in hidden_key_set
    assert SETTING_TIMING_STR in hidden_key_set


def test_expert_hides_nothing():
    """The mode that shows everything warns about nothing."""
    assert (
        describe_hidden_setting_list(
            build_expert_scenario(), MODE_EXPERT_STR
        )
        == []
    )
    assert (
        build_hidden_summary_str(
            build_expert_scenario(), MODE_EXPERT_STR
        )
        == ""
    )


def test_a_plain_plan_hides_nothing_even_in_quick():
    """A setting nobody switched on is absent, not hidden."""
    assert (
        build_hidden_summary_str(
            build_plain_scenario(), MODE_QUICK_STR
        )
        == ""
    )


def test_the_summary_counts_what_it_lists():
    """The number in the sentence is the length of the list."""
    scenario = build_expert_scenario()
    hidden_list = describe_hidden_setting_list(
        scenario, MODE_QUICK_STR
    )
    summary_str = build_hidden_summary_str(
        scenario, MODE_QUICK_STR
    )
    assert str(len(hidden_list)) in summary_str


def test_the_summary_says_active_not_ignored():
    """Wording matters: the settings are still running."""
    summary_str = build_hidden_summary_str(
        build_expert_scenario(), MODE_QUICK_STR
    )
    assert "active" in summary_str
    assert "not shown" in summary_str
    assert "ignored" not in summary_str


def test_one_hidden_setting_reads_in_the_singular():
    """Counting is not an excuse for bad English."""
    scenario = replace(
        build_plain_scenario(),
        policy=PlanPolicy(sip_at_month_start_bool=False),
    )
    summary_str = build_hidden_summary_str(
        scenario, MODE_QUICK_STR
    )
    assert "1 advanced setting active" in summary_str


@pytest.mark.parametrize("mode_str", MODE_ORDER_TUPLE)
def test_every_hidden_setting_describes_its_value(mode_str):
    """A list of names without values would not help anyone."""
    for hidden in describe_hidden_setting_list(
        build_expert_scenario(), mode_str
    ):
        assert hidden.value_str
        assert hidden.label_str
        assert hidden.sentence_str.startswith(hidden.label_str)


def test_guided_hides_less_than_quick():
    """Each level up warns about less, because it shows more."""
    scenario = build_expert_scenario()
    assert len(
        describe_hidden_setting_list(scenario, MODE_GUIDED_STR)
    ) < len(describe_hidden_setting_list(scenario, MODE_QUICK_STR))
