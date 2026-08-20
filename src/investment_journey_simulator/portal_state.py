"""One scenario, one owner, for the whole portal.

This module is what actually delivers the promise that a reader
never types anything twice. The navigation tree does not deliver it;
shared state does. Every page reads the scenario through
`read_scenario` and writes it through `write_scenario`, and no page
keeps a copy of any input of its own.

Streamlit re-runs a script top to bottom on every interaction, so
"state" here means `st.session_state` and nothing else. Keeping the
keys in one place, behind functions, is what stops nine pages from
inventing nine slightly different conventions.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from investment_journey_simulator.constants import (
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.models import FundConfiguration
from investment_journey_simulator.plan_modes import MODE_GUIDED_STR
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.timeline import TimelinePlan

SCENARIO_STATE_KEY_STR: str = "portal_scenario"
MODE_STATE_KEY_STR: str = "portal_mode"
COMPARISON_STATE_KEY_STR: str = "portal_comparison_list"

DEFAULT_HORIZON_YEARS_INT: int = 20
DEFAULT_FUND_NAME_STR: str = "Equity fund"
DEFAULT_RETURN_PERCENT_FLOAT: float = 12.0
DEFAULT_EXPENSE_PERCENT_FLOAT: float = 1.0
DEFAULT_SHORT_TERM_PERCENT_FLOAT: float = 20.0
DEFAULT_LONG_TERM_PERCENT_FLOAT: float = 12.5
DEFAULT_THRESHOLD_MONTHS_INT: int = 12
DEFAULT_EXEMPTION_FLOAT: float = 125000.0


def build_starting_month_date() -> date:
    """The month a new plan opens in.

    Brief:
        The first of the current month, because the engine works on
        a month grid and a mid-month start would be rounded anyway.

    Arguments:
        None.

    Returns:
        date: First day of the current month.

    Warning:
        Read at call time, so a session left open across a month
        boundary does not silently change an existing plan - only
        a newly created one.
    """
    today_date = date.today()
    return date(today_date.year, today_date.month, 1)


def build_default_fund() -> FundConfiguration:
    """Build the one fund a brand new plan starts with.

    Brief:
        A single equity fund at a plausible return. Every figure is
        a starting value the reader is expected to overwrite, and
        the interface says so rather than presenting them as
        recommendations.

    Arguments:
        None.

    Returns:
        FundConfiguration: One fund, ready to edit.

    Warning:
        The tax fields carry Indian equity rates because India is
        the one regime modelled in full. Choosing another regime
        replaces them.
    """
    return FundConfiguration(
        name_str=DEFAULT_FUND_NAME_STR,
        preset_str=PRESET_EQUITY_STR,
        monthly_sip_float=0.0,
        stepup_percent_float=0.0,
        gross_return_percent_float=DEFAULT_RETURN_PERCENT_FLOAT,
        expense_percent_float=DEFAULT_EXPENSE_PERCENT_FLOAT,
        start_date=build_starting_month_date(),
        target_allocation_percent_float=100.0,
        short_term_tax_percent_float=(
            DEFAULT_SHORT_TERM_PERCENT_FLOAT
        ),
        long_term_tax_percent_float=(
            DEFAULT_LONG_TERM_PERCENT_FLOAT
        ),
        long_term_threshold_months_int=(
            DEFAULT_THRESHOLD_MONTHS_INT
        ),
        exemption_amount_float=DEFAULT_EXEMPTION_FLOAT,
        exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
        is_always_short_term_bool=False,
        expense_model_str=EXPENSE_MODEL_SIMPLE_STR,
    )


def build_default_scenario() -> PlanScenario:
    """Build the empty plan a first-time reader starts from.

    Brief:
        Deliberately holds no events. A plan that invests nothing
        reports that it invests nothing, rather than inventing an
        instalment the reader never chose.

    Arguments:
        None.

    Returns:
        PlanScenario: An empty but valid scenario.

    Warning:
        Empty is a valid state every screen must render without
        falling over; that is what the empty states are for.
    """
    return PlanScenario(
        plan=TimelinePlan(
            start_date=build_starting_month_date(),
            horizon_years_int=DEFAULT_HORIZON_YEARS_INT,
        ),
        fund_list=[build_default_fund()],
    )


def read_scenario() -> PlanScenario:
    """Read the one scenario this session is working on.

    Brief:
        Creates the default on first read, so no page needs to
        check whether the session has been initialised.

    Arguments:
        None.

    Returns:
        PlanScenario: The session's scenario.

    Warning:
        Returns the stored object itself. It is frozen, so callers
        must write a modified copy back rather than mutating it.
    """
    if SCENARIO_STATE_KEY_STR not in st.session_state:
        st.session_state[SCENARIO_STATE_KEY_STR] = (
            build_default_scenario()
        )
    return st.session_state[SCENARIO_STATE_KEY_STR]


def write_scenario(scenario: PlanScenario) -> None:
    """Store the scenario every other page will now read.

    Brief:
        The only way a page changes the plan. Going through one
        function is what makes the shared state auditable.

    Arguments:
        scenario (PlanScenario): Scenario to store.

    Returns:
        None: The session is updated in place.

    Warning:
        Overwrites whatever was there. Callers editing one part of
        the plan must pass a full scenario, normally built with
        `dataclasses.replace`.
    """
    st.session_state[SCENARIO_STATE_KEY_STR] = scenario


def read_mode_str() -> str:
    """Read the experience level this reader has chosen."""
    if MODE_STATE_KEY_STR not in st.session_state:
        st.session_state[MODE_STATE_KEY_STR] = MODE_GUIDED_STR
    return st.session_state[MODE_STATE_KEY_STR]


def write_mode_str(mode_str: str) -> None:
    """Store the experience level for every later page."""
    st.session_state[MODE_STATE_KEY_STR] = mode_str


def reset_scenario() -> None:
    """Throw the current plan away and start again."""
    st.session_state[SCENARIO_STATE_KEY_STR] = (
        build_default_scenario()
    )


def read_comparison_list() -> list:
    """Read the named journeys held for comparison."""
    if COMPARISON_STATE_KEY_STR not in st.session_state:
        st.session_state[COMPARISON_STATE_KEY_STR] = []
    return st.session_state[COMPARISON_STATE_KEY_STR]


def write_comparison_list(comparison_list: list) -> None:
    """Store the named journeys held for comparison."""
    st.session_state[COMPARISON_STATE_KEY_STR] = list(
        comparison_list
    )
