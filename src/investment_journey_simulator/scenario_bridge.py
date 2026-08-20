"""Keeping the event rail and the shared scenario in step.

The rail is two thousand lines of interaction that works - clicking
a month, arming an event type, dragging the horizon. It keeps its
plan in its own session-state keys, because that is what Streamlit
requires and what it was built to do.

Rather than rewrite all of it, this module syncs those keys with the
shared `PlanScenario` in both directions:

* **Seed** - when a reader arrives from another screen, push the
  shared scenario into the rail's keys so their plan is already
  there.
* **Publish** - after the rail has rendered, read its keys back and
  write the result into the shared scenario so the next screen sees
  the edits.

The subtlety is knowing *when* to seed. Seeding on every rerun would
overwrite each edit the moment it was made. So the bridge remembers
what it last published, and re-seeds only when the shared scenario
has changed underneath it - which happens exactly when another
screen edited the plan.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import streamlit as st

from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_TIMELINE_STR,
    PlanScenario,
)
from investment_journey_simulator.scenario_io import encode_scenario_dict

BRIDGE_MARKER_KEY_STR: str = "rail_bridge_published_marker"


def build_marker_str(scenario: PlanScenario) -> str:
    """Build a stable fingerprint of a scenario.

    Brief:
        Used only to notice that the shared scenario changed while
        this screen was not looking. Encoding is already stable and
        order-independent, so it makes a serviceable fingerprint.

    Arguments:
        scenario (PlanScenario): Scenario to fingerprint.

    Returns:
        str: Fingerprint of the scenario's inputs.

    Warning:
        Not a hash and not a security boundary. Two scenarios that
        differ only in a field the encoder drops would collide, and
        the encoder drops nothing today.
    """
    return repr(encode_scenario_dict(scenario))


def needs_seeding_bool(scenario: PlanScenario) -> bool:
    """Whether the rail should be reloaded from the scenario.

    Brief:
        True on first arrival, and true again whenever another
        screen has changed the plan since this one last published.

    Arguments:
        scenario (PlanScenario): The shared scenario.

    Returns:
        bool: True when the rail's keys are out of date.

    Warning:
        False while the reader is editing on this screen, which is
        what stops the seed from fighting every keystroke.
    """
    if BRIDGE_MARKER_KEY_STR not in st.session_state:
        return True
    return st.session_state[
        BRIDGE_MARKER_KEY_STR
    ] != build_marker_str(scenario)


def mark_published(scenario: PlanScenario) -> None:
    """Record what this screen just published."""
    st.session_state[BRIDGE_MARKER_KEY_STR] = build_marker_str(
        scenario
    )


def seed_rail_state(scenario: PlanScenario) -> None:
    """Push the shared scenario into the rail's own keys.

    Brief:
        Called before any of the rail's widgets render, because
        Streamlit refuses to let a widget's key be written once the
        widget exists.

    Arguments:
        scenario (PlanScenario): Scenario to load onto the rail.

    Returns:
        None: Session state is updated.

    Warning:
        Must run before the rail's controls, never after.
    """
    from investment_journey_simulator import timeline_app

    st.session_state[timeline_app.EVENT_STATE_KEY_STR] = list(
        scenario.plan.event_list
    )
    _seed_assumption_state(scenario)


def _seed_assumption_state(scenario: PlanScenario) -> None:
    """Push the non-event assumptions onto the rail's controls."""
    from investment_journey_simulator import timeline_app

    st.session_state[timeline_app.HORIZON_STATE_KEY_STR] = int(
        scenario.plan.horizon_years_int
    )
    if scenario.fund_list:
        st.session_state[timeline_app.RETURN_STATE_KEY_STR] = (
            float(scenario.fund_list[0].gross_return_percent_float)
        )
        st.session_state[timeline_app.EXPENSE_STATE_KEY_STR] = (
            float(scenario.fund_list[0].expense_percent_float)
        )
    st.session_state[timeline_app.CURRENCY_STATE_KEY_STR] = (
        scenario.presentation.currency_code_str
    )
    st.session_state[timeline_app.REGIME_STATE_KEY_STR] = (
        scenario.presentation.regime_code_str
    )
    st.session_state[timeline_app.INFLATION_STATE_KEY_STR] = float(
        scenario.resolved_inflation_percent_float
    )


def publish_rail_scenario(
    scenario: PlanScenario,
    horizon_years_int: int,
    return_percent_float: float,
    expense_percent_float: float,
    currency_code_str: str,
    inflation_percent_float: float,
    start_date: date | None = None,
) -> PlanScenario:
    """Read the rail back into the shared scenario.

    The events come from the rail's own state; the assumptions come
    from the controls beside it, which the caller has already
    collected.

    Arguments:
        scenario (PlanScenario): Scenario being updated.
        horizon_years_int (int): Horizon from the controls.
        return_percent_float (float): Gross return.
        expense_percent_float (float): Expense ratio.
        currency_code_str (str): Currency to display in.
        inflation_percent_float (float): Inflation rate.
        start_date (Optional[date]): Month the timeline opens in.
            None keeps what the scenario already had.

    Returns:
        PlanScenario: The shared scenario, brought up to date.

    Warning:
        Hands the amounts to the timeline, because every rupee a
        rail plan invests arrives as a dated event.
    """
    return replace(
        scenario,
        plan=_rebuild_plan(scenario, horizon_years_int, start_date),
        fund_list=_apply_fund_assumptions(
            scenario, return_percent_float, expense_percent_float
        ),
        presentation=replace(
            scenario.presentation,
            currency_code_str=currency_code_str,
        ),
        inflation_percent_float=float(inflation_percent_float),
        amounts_source_str=AMOUNTS_SOURCE_TIMELINE_STR,
    )


def _rebuild_plan(
    scenario: PlanScenario,
    horizon_years_int: int,
    start_date: date | None,
):
    """Rebuild the plan from the rail's state and the controls."""
    return replace(
        scenario.plan,
        start_date=(
            start_date
            if start_date is not None
            else scenario.plan.start_date
        ),
        horizon_years_int=int(horizon_years_int),
        event_list=_read_rail_event_list(scenario),
    )


def _read_rail_event_list(scenario: PlanScenario) -> list:
    """Read the rail's events, falling back to the scenario's."""
    from investment_journey_simulator import timeline_app

    if timeline_app.EVENT_STATE_KEY_STR not in st.session_state:
        return list(scenario.plan.event_list)
    return list(
        st.session_state[timeline_app.EVENT_STATE_KEY_STR]
    )


def _apply_fund_assumptions(
    scenario: PlanScenario,
    return_percent_float: float,
    expense_percent_float: float,
) -> list:
    """Put the rail's return and fee onto every fund."""
    return [
        replace(
            fund_configuration,
            gross_return_percent_float=float(
                return_percent_float
            ),
            expense_percent_float=float(expense_percent_float),
        )
        for fund_configuration in scenario.fund_list
    ]
