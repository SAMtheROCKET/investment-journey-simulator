"""Home: what this is, and where to start.

A reader arriving with no context must be able to answer "what is
this and what do I do first" without reading a manual and without
clicking anything.

The layout follows the bespoke concept: a two-column hero with the
argument on the left and the live Plan Pulse on the right, then the
four questions a reader might actually have arrived with, then the
strip saying what about this is inspectable.

Three things carried over from the prototype are worth naming,
because each is doing work rather than decorating:

*The pulse is live.* The concept mocked it with a fixed figure. Here
it is the engine's answer for the plan currently loaded, which is
what makes the first screen prove the program computes rather than
merely collects.

*The provenance chip is not a badge.* "Deterministic · nominal" is
the difference between this figure and the ones on the Risk Lab, and
a reader who cannot tell those apart has been misled.

*The goal meter appears only once a goal exists.* An empty progress
bar on a first visit would be a fake, and a fake figure is the one
thing this screen cannot afford.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.currency import format_money_str
from investment_journey_simulator.page_links import (
    COMPARE_PAGE_STR,
    GOAL_PAGE_STR,
    GUIDED_PAGE_STR,
    GUIDES_PAGE_STR,
    QUICK_PAGE_STR,
)
from investment_journey_simulator.pages.page_shell import (
    has_investment_bool,
    render_page_link,
)
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import read_scenario
from investment_journey_simulator.ui.chrome import (
    render_insight,
    render_kicker,
    render_plan_pulse,
    render_question_card,
    render_top_bar,
    render_trust_strip,
)
from investment_journey_simulator.ui.plan_summary import (
    PlanProjection,
    project_scenario,
    render_scenario_assumptions,
)

HERO_TITLE_STR: str = "Build the life around the money"
LEAD_STR: str = (
    "Work out what your investments could be worth, and - more "
    "usefully - how much the decisions along the way change that "
    "number."
)
PROVENANCE_STR: str = "deterministic · nominal"

# Routes lead with the *question a reader already has*, not with
# the name of the screen that answers it. Nobody arrives wanting a
# "simulator"; they arrive wanting to know whether they will have
# enough. The screen name goes underneath, where it becomes useful
# only once the question has been recognised.
ROUTE_TUPLE: tuple = (
    (
        "⚡",
        "Where might I reach?",
        "Quick Projection",
        "Four questions, an answer, and every assumption behind "
        "it - in under a minute.",
        QUICK_PAGE_STR,
    ),
    (
        "🎯",
        "What would my goal take?",
        "Goal Planner",
        "Name the figure you want. See the monthly amount, the "
        "horizon, or the return that would reach it.",
        GOAL_PAGE_STR,
    ),
    (
        "⚖️",
        "What does a decision cost?",
        "Compare Journeys",
        "Pause, step up, withdraw. Change one thing and see "
        "exactly what that one thing was worth.",
        COMPARE_PAGE_STR,
    ),
    (
        "🧭",
        "How does the money get there?",
        "Guides",
        "The route from a salary abroad into an investment, and "
        "the paperwork that gates each step.",
        GUIDES_PAGE_STR,
    ),
)
EXPERT_ROUTE_STR: str = (
    "Already know what a drift band is? **🎛 Advanced Simulator** "
    "has every control this program owns - tax, fees, "
    "rebalancing, exit loads and the lot."
)
EMPTY_PULSE_STR: str = (
    "Nothing entered yet. Pick a question below - whatever you "
    "enter carries across every screen, so you never type it "
    "twice."
)
TRUST_CLAIM_TUPLE: tuple = (
    "every assumption visible, never behind a click",
    "causes add up to the whole gap, exactly",
    "an audit layer with the working",
    "beginner-first, and still complete for a professional",
)


def render_hero_copy() -> None:
    """The left half: what this is, and the way in."""
    render_kicker("Investment journey simulator")
    st.title(HERO_TITLE_STR)
    st.markdown(f"#### {LEAD_STR}")
    st.markdown(
        "This is **not** a market forecast and does not try to be. "
        "You supply the assumptions - the return, the inflation, "
        "the contributions - and it works out, precisely, what "
        "those assumptions imply. That is a different and far more "
        "answerable question than *what will the market do*."
    )
    # Labelled with the screen name rather than a slogan. "Open the
    # timeline" reads better and tells a first-time reader nothing
    # about where they are being sent; the rail says "Guided
    # Journey" and the two have to agree.
    first_column, second_column = st.columns(2)
    with first_column:
        render_page_link(QUICK_PAGE_STR, "Quick Projection", "⚡")
    with second_column:
        render_page_link(GUIDED_PAGE_STR, "Guided Journey", "🧭")
    st.caption(
        "Four questions and an answer, or the whole timeline with "
        "the raises and breaks on it."
    )


def _goal_tuple(
    scenario: PlanScenario,
    projection: PlanProjection,
) -> tuple:
    """The goal meter's label and percentage, when a goal exists.

    Brief:
        Reads the target the Goal Planner last worked on, so the
        two screens agree without either owning the other. Absent
        until a reader has actually named a figure - an empty
        progress bar on a first visit would be a fake.

    Arguments:
        scenario (PlanScenario): The plan being measured.
        projection (PlanProjection): Its run.

    Returns:
        Tuple: `(label, percent)`, or empty when no goal is set.

    Warning:
        Imported inside the function to keep Home from importing
        the Goal Planner at module scope, which would make two
        sibling screens depend on each other's load order.
    """
    from investment_journey_simulator.pages.goal_page import (
        TARGET_STATE_KEY_STR,
    )
    from investment_journey_simulator.scenario_set import (
        run_journey_outcome,
    )

    target_float = float(
        st.session_state.get(TARGET_STATE_KEY_STR, 0.0) or 0.0
    )
    if target_float <= 0.0 or not projection.is_runnable_bool:
        return ()
    currency = compile_scenario(scenario).currency
    current_float = run_journey_outcome(scenario).final_value_float
    return (
        f"{format_money_str(target_float, currency)} target",
        100.0 * current_float / target_float,
    )


def render_hero_pulse() -> None:
    """The right half: what the plan currently comes to."""
    scenario = read_scenario()
    if not has_investment_bool(scenario):
        st.info(EMPTY_PULSE_STR)
        render_page_link(
            QUICK_PAGE_STR, "Start a one-minute projection", "⚡"
        )
        return
    projection = project_scenario(scenario)
    if not projection.is_runnable_bool:
        st.warning("This plan runs for no months at all.")
        return
    render_plan_pulse(
        projection.final_str,
        f"Projected value of {scenario.name_str} after "
        f"{scenario.plan.horizon_years_int} years.",
        (
            ("You pay in", projection.invested_str),
            ("Today's money", projection.real_str),
            (
                "Growth share",
                f"{projection.growth_share_float:.0f}%",
            ),
        ),
        provenance_str=PROVENANCE_STR,
        goal_tuple=_goal_tuple(scenario, projection),
    )
    render_scenario_assumptions(scenario)


def render_hero() -> None:
    """Draw the concept's two-column opening.

    Brief:
        The argument and the answer, side by side. A reader learns
        within one screen both what this program refuses to do and
        what it has already worked out for them.

    Arguments:
        None.

    Returns:
        None: The hero is rendered.

    Warning:
        Collapses to one column on a narrow viewport, which puts
        the copy above the figure. That is the right order to lose
        the split in - the figure means nothing unread.
    """
    copy_column, pulse_column = st.columns(
        [1.15, 0.85], gap="large"
    )
    with copy_column:
        render_hero_copy()
    with pulse_column:
        render_hero_pulse()


def render_routes() -> None:
    """Offer the four ways in, as questions rather than tools.

    Brief:
        A reader arrives with a question, not with a preference
        between simulators. Leading with the question is what lets
        them recognise their own situation before learning any of
        this program's vocabulary.

    Arguments:
        None.

    Returns:
        None: The routes are rendered.

    Warning:
        The screen names must stay in step with the navigation
        tree in `portal_app.py`; a test holds that shut.
    """
    st.subheader("Start with a question")
    st.caption(
        "Each one is a whole screen. The plan follows you between "
        "them."
    )
    column_list = st.columns(len(ROUTE_TUPLE), gap="medium")
    for column, route_tuple in zip(
        column_list, ROUTE_TUPLE, strict=True
    ):
        icon_str, question_str, screen_str, body_str, module_str = (
            route_tuple
        )
        with column:
            render_question_card(icon_str, question_str, body_str)
            render_page_link(module_str, screen_str, icon_str)
    st.caption(EXPERT_ROUTE_STR)


def render_honesty() -> None:
    """Say plainly what the program does and does not model."""
    render_insight(
        "Every figure in this program is arithmetic on assumptions "
        "you supplied. Change an assumption and the figure "
        "changes; that sensitivity is the answer, not a flaw in "
        "it.",
        title_str="How to read anything here",
    )
    with st.expander("What this does and does not do"):
        st.markdown(
            "**It models exactly:** monthly compounding on the "
            "convention you choose, FIFO lots, expense ratios, "
            "step-ups, pauses, withdrawals, rebalancing, and "
            "Indian capital gains tax in full - including the "
            "section 112A exemption, surcharge with marginal "
            "relief, grandfathering and loss carry-forward."
            "\n\n"
            "**It approximates:** capital gains outside India. "
            "Choosing another country fills in its headline rates "
            "as *starting values you can edit*. It does not teach "
            "the program that country's tax code, and the tax "
            "screen says so where you choose it."
            "\n\n"
            "**It does not attempt:** predicting returns, "
            "inflation or any market movement. Every rate here is "
            "one you supplied."
        )


def render() -> None:
    """Render the home page."""
    render_top_bar("Home", (("Start here", True),))
    render_hero()
    st.divider()
    render_routes()
    st.divider()
    render_trust_strip(TRUST_CLAIM_TUPLE)
    st.divider()
    render_honesty()
