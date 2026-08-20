"""Guided Journey: plan by placing what happens, when.

The event rail, moved onto the shared scenario. A reader who has
already answered Quick's four questions arrives to find their plan
on the timeline; anything they add here is waiting for them on
Compare, Goals and Reports.

The rail's own interaction - arming an event, clicking a month,
reading the journey back - is untouched. `scenario_bridge.py` keeps
its session state and the shared scenario in step in both
directions.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.constants import MONTHS_IN_YEAR_INT
from investment_journey_simulator.page_links import (
    ADVANCED_PAGE_STR,
    COMPARE_PAGE_STR,
)
from investment_journey_simulator.pages.page_shell import (
    open_page,
    render_page_link,
)
from investment_journey_simulator.plan_modes import MODE_EXPERT_STR
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.portal_state import (
    read_mode_str,
    read_scenario,
    write_scenario,
)
from investment_journey_simulator.scenario_bridge import (
    mark_published,
    needs_seeding_bool,
    publish_rail_scenario,
    seed_rail_state,
)
from investment_journey_simulator.timeline import TimelinePlan
from investment_journey_simulator.timeline_app import (
    VIEW_PLAN_STR,
    build_fund_list,
    render_allocation_control,
    render_assumption_controls,
    render_currency_control,
    render_event_composer,
    render_event_list,
    render_inflation_control,
    render_rail_panel,
    render_regime_control,
    render_result_view,
    render_start_month_control,
    render_view_toggle,
    run_plan,
)
from investment_journey_simulator.ui.chrome import (
    render_insight,
    render_kicker,
)
from investment_journey_simulator.ui.plan_summary import (
    render_scenario_pulse,
)
from investment_journey_simulator.ui.rail_view import render_rail_style
from investment_journey_simulator.ui.timeline_view import render_page_style
from investment_journey_simulator.ui.value_input import (
    render_input_mode_control,
)

TITLE_STR: str = "Guided Journey"
LEAD_STR: str = (
    "Plan the way a life actually runs - you start, you get a "
    "raise, you pause for a wedding, you buy a house, you retire. "
    "Place each one on the timeline and read the plan back."
)
QUESTION_TUPLE: tuple = (
    "Will you raise the amount as your salary grows?",
    "Are there years you expect to pause?",
    "Will you take money out for a house, education or travel?",
    "When do you want to stop investing and start drawing?",
)


def render_questions() -> None:
    """Ask, in words, what the rail is for.

    Brief:
        A blank timeline does not tell a reader what to put on it.
        These four questions are the ones the rail can answer, in
        the language a reader would use to ask them.

    Arguments:
        None.

    Returns:
        None: The prompts are rendered.

    Warning:
        Prompts only. Each is answered by placing an event, not by
        filling in a box here.
    """
    with st.expander(
        "What this screen is for", expanded=False
    ):
        st.markdown(
            "Every one of these changes the final number, often by "
            "more than the return you assumed:"
        )
        for question_str in QUESTION_TUPLE:
            st.markdown(f"- {question_str}")
        st.caption(
            "Answer them by adding events to the timeline below. "
            "Nothing is compulsory - an empty year is a year "
            "nothing happened."
        )


def render_sidebar_controls() -> tuple:
    """Collect the assumptions that are not events.

    Brief:
        A horizon and a return are not things that happen on a
        date, so they stay as plain controls rather than being
        forced onto the axis.

    Arguments:
        None.

    Returns:
        Tuple: Horizon, return, expense, equity share, currency,
            inflation and the month the timeline opens in.

    Warning:
        Must run after the bridge has seeded, because these are
        widgets and Streamlit will not let a widget's key be
        written once it exists.
    """
    with st.sidebar:
        st.markdown("### Plan settings")
        start_date = render_start_month_control(
            read_scenario().plan.start_date
        )
        render_input_mode_control()
        currency = render_currency_control()
        render_regime_control()
        (
            horizon_years_int,
            return_percent_float,
            expense_percent_float,
        ) = render_assumption_controls()
        equity_percent_float = render_allocation_control()
        inflation_percent_float = render_inflation_control(currency)
    return (
        horizon_years_int,
        return_percent_float,
        expense_percent_float,
        equity_percent_float,
        currency,
        inflation_percent_float,
        start_date,
    )


def render_plan_view(plan: TimelinePlan) -> None:
    """Draw the rail and the tools for adding to it.

    Brief:
        `render_rail_panel` draws the event palette itself, so this
        must not draw one too - two palettes would collide on the
        same widget keys and take the page down.

    Arguments:
        plan (TimelinePlan): Plan being edited.

    Returns:
        None: The rail and its tools are rendered.

    Warning:
        Order matters: the rail is drawn before the composer so a
        month clicked on the rail is already armed when the
        composer reads it.
    """
    render_rail_panel(plan)
    render_event_composer(plan.start_date)
    render_event_list(plan.event_list)


def render_expert_panel(scenario: PlanScenario) -> None:
    """Show the deep settings, and where they are edited.

    Choosing Expert used to widen the promise without widening the
    screen: the level said it showed tax, fees and rebalancing, and
    this page showed none of them. It still cannot host every one -
    the fund table and the tax model belong to the Advanced
    Simulator - so it states what each is currently set to and
    sends the reader to the one screen that can change it.

    Arguments:
        scenario (PlanScenario): The plan being examined.

    Returns:
        None: The panel is rendered, or nothing is when the level
            is not Expert.
    """
    if read_mode_str() != MODE_EXPERT_STR:
        return
    with st.container(border=True):
        render_kicker("Expert - what the deep settings are set to")
        _render_expert_metrics(scenario)
        st.caption(
            "These are read-only here. The Advanced Simulator "
            "edits every one of them, plus the tax model, exit "
            "loads and the fund table."
        )
        render_page_link(
            ADVANCED_PAGE_STR, "Open the full controls", "🎛"
        )


def _render_expert_metrics(scenario: PlanScenario) -> None:
    """The three deep settings this screen can report."""
    interval_int = scenario.policy.rebalance_interval_months_int
    first, second, third = st.columns(3)
    first.metric(
        "Expense ratio",
        f"{scenario.fund_list[0].expense_percent_float:g}%"
        if scenario.fund_list
        else "no fund",
        help="Charged yearly, deducted from the fund value.",
    )
    second.metric(
        "Rebalancing",
        f"every {interval_int // MONTHS_IN_YEAR_INT} yr"
        if interval_int
        else "off",
        help=(
            "How often the plan is brought back to its target "
            "split. Off means it drifts."
        ),
    )
    third.metric(
        "Instalment timing",
        "month start"
        if scenario.policy.sip_at_month_start_bool
        else "month end",
        help=(
            "Whether an instalment earns a return in the month it "
            "is paid."
        ),
    )


def render_timeline_reading(plan: TimelinePlan) -> None:
    """Say what the rail currently amounts to, in one sentence.

    Brief:
        A rail with events on it is a picture; a reader still has
        to be told what the picture means. Empty is the case worth
        naming - a plan with no events is not broken, it is a plan
        nobody has told anything about their life yet.

    Arguments:
        plan (TimelinePlan): The plan as the rail has it.

    Returns:
        None: The reading is rendered.
    """
    if not plan.event_list:
        render_insight(
            "Nothing is on the rail yet, so this plan assumes a "
            "life with no raises, no breaks and no withdrawals in "
            "it. Add the ones you expect - that is the difference "
            "between a projection and a plan.",
            title_str="An empty rail is an assumption",
        )
        render_page_link(
            COMPARE_PAGE_STR, "Then see what each one cost", "⚖"
        )
        return
    render_insight(
        f"{len(plan.event_list)} event"
        f"{'' if len(plan.event_list) == 1 else 's'} on the rail. "
        "Save this as a journey and change one of them to see "
        "exactly what that single decision was worth.",
        title_str="What to do with this",
    )
    render_page_link(
        COMPARE_PAGE_STR, "Compare it against a variant", "⚖"
    )


def render() -> None:
    """Render the Guided Journey page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    render_page_style()
    render_rail_style()
    if needs_seeding_bool(scenario):
        seed_rail_state(scenario)
    render_questions()
    (
        horizon_years_int,
        return_percent_float,
        expense_percent_float,
        equity_percent_float,
        currency,
        inflation_percent_float,
        start_date,
    ) = render_sidebar_controls()
    updated = publish_rail_scenario(
        scenario,
        horizon_years_int,
        return_percent_float,
        expense_percent_float,
        currency.code_str,
        inflation_percent_float,
        start_date,
    )
    write_scenario(updated)
    mark_published(updated)
    render_scenario_pulse(updated, label_str="This plan, so far")
    render_expert_panel(updated)
    plan = TimelinePlan(
        updated.plan.start_date,
        horizon_years_int,
        list(updated.plan.event_list),
    )
    if render_view_toggle() == VIEW_PLAN_STR:
        render_plan_view(plan)
        render_timeline_reading(plan)
        return
    result, settings = run_plan(
        plan,
        build_fund_list(
            equity_percent_float,
            return_percent_float,
            expense_percent_float,
        ),
    )
    render_result_view(plan, result, settings)
