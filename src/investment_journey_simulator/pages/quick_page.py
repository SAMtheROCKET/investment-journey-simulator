"""Quick Projection: one number, fast.

Four questions and an answer. Everything else takes a default, and
every default is stated on screen rather than hidden - a projection
whose assumptions are invisible is worse than no projection.

The page writes into the same scenario every other screen reads, so
"try Guided next" costs the reader nothing.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.constants import (
    MAXIMUM_HORIZON_YEARS_INT,
    MAXIMUM_RETURN_PERCENT_FLOAT,
    MINIMUM_HORIZON_YEARS_INT,
    MINIMUM_RETURN_PERCENT_FLOAT,
)
from investment_journey_simulator.currency import (
    describe_money_str,
    format_money_str,
    list_currency_code_list,
)
from investment_journey_simulator.dashboard_run import simulate_nominal_run
from investment_journey_simulator.inflation import deflate_amount_float
from investment_journey_simulator.page_links import (
    COMPARE_PAGE_STR,
    GUIDED_PAGE_STR,
)
from investment_journey_simulator.pages.page_shell import (
    open_page,
    render_page_link,
)
from investment_journey_simulator.plan_scenario import (
    CompiledPlan,
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import write_scenario
from investment_journey_simulator.scenario_edits import (
    add_annual_step_up,
    add_contribution_pause,
    has_event_of_type_bool,
    read_expected_return_float,
    read_monthly_contribution_float,
    set_currency_code,
    set_expected_return,
    set_horizon_years,
    set_monthly_contribution,
)
from investment_journey_simulator.scenario_set import (
    run_journey_outcome,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_STEPUP_STR,
)
from investment_journey_simulator.ui.plan_summary import (
    render_scenario_assumptions,
)

TITLE_STR: str = "Quick Projection"
LEAD_STR: str = (
    "Four questions and an answer. Every other assumption is "
    "listed below the result, so you can see what was taken for "
    "granted."
)
# Both come from constants.py, so this screen can never
# disagree with the solver that writes to it again.
MINIMUM_HORIZON_INT: int = MINIMUM_HORIZON_YEARS_INT
MAXIMUM_HORIZON_INT: int = MAXIMUM_HORIZON_YEARS_INT

HELP_HOW_LONG_THE_MONEY_STR: str = (
    "How long the money stays invested. Longer horizons compound "
    "far harder than larger amounts."
)
HELP_THIS_IS_YOUR_ASSUMPTION_STR: str = (
    "This is your assumption, not a forecast. Nothing here "
    "predicts a market."
)
HELP_CHANGES_THE_SYMBOL_AND_STR: str = (
    "Changes the symbol and the grouping only. No amount is "
    "converted."
)


def clamp_horizon_int(horizon_years_int: int) -> int:
    """Bring a stored horizon inside what this control accepts.

    Brief:
        A widget handed a value outside its own range does not
        clip it - it raises, and the whole page dies with it. That
        is a poor way to react to a number the program itself
        wrote, and a worse one to react to a file somebody saved
        under an older limit.

    Arguments:
        horizon_years_int (int): Horizon the plan carries.

    Returns:
        int: The same horizon, or the nearest allowed value.

    Warning:
        Clamps quietly. The plan itself is left alone until the
        reader touches the control, so a scenario is never edited
        by being looked at - but the figure shown will differ from
        the figure stored until they do.
    """
    return max(
        MINIMUM_HORIZON_INT,
        min(MAXIMUM_HORIZON_INT, int(horizon_years_int)),
    )


def clamp_return_float(return_percent_float: float) -> float:
    """Bring a stored return inside what this control accepts.

    Brief:
        The same guard as the horizon, for the same reason. A plan
        may legitimately assume a fund loses money, and this
        screen has to be able to show that plan rather than die
        on it.

    Arguments:
        return_percent_float (float): Return the plan assumes.

    Returns:
        float: The same figure, or the nearest allowed one.
    """
    return max(
        MINIMUM_RETURN_PERCENT_FLOAT,
        min(MAXIMUM_RETURN_PERCENT_FLOAT, float(return_percent_float)),
    )


def render_inputs(scenario: PlanScenario) -> PlanScenario:
    """Ask the four questions and store every answer.

    Brief:
        Written back on every rerun rather than behind a button,
        so the figure on screen always matches the boxes above it.

    Arguments:
        scenario (PlanScenario): Scenario being edited.

    Returns:
        PlanScenario: Scenario carrying the answers.

    Warning:
        Writes to shared state, so leaving this page keeps every
        answer.
    """
    first_column, second_column = st.columns(2)
    with first_column:
        amount_float, horizon_int = _render_how_much_and_how_long(
            scenario
        )
    with second_column:
        return_float = _render_expected_return(scenario)
        currency_code_str = _render_currency_picker(scenario)
    updated = set_monthly_contribution(scenario, amount_float)
    updated = set_horizon_years(updated, int(horizon_int))
    updated = set_expected_return(updated, return_float)
    return set_currency_code(updated, currency_code_str)


def _render_how_much_and_how_long(
    scenario: PlanScenario,
) -> tuple[float, int]:
    """Ask the two questions that decide most of the answer."""
    amount_float = st.number_input(
        "How much will you invest each month?",
        min_value=0.0,
        value=read_monthly_contribution_float(scenario),
        step=1000.0,
        help="Leave at zero if you are only testing a lump sum.",
    )
    horizon_int = st.number_input(
        "For how many years?",
        help=HELP_HOW_LONG_THE_MONEY_STR,
        min_value=MINIMUM_HORIZON_INT,
        max_value=MAXIMUM_HORIZON_INT,
        value=clamp_horizon_int(scenario.plan.horizon_years_int),
        step=1,
    )
    return float(amount_float), int(horizon_int)


def _render_expected_return(scenario: PlanScenario) -> float:
    """Ask for the assumption the whole projection rests on."""
    return float(
        st.number_input(
            "What annual return do you expect, before costs?",
            min_value=MINIMUM_RETURN_PERCENT_FLOAT,
            max_value=MAXIMUM_RETURN_PERCENT_FLOAT,
            value=clamp_return_float(
                read_expected_return_float(scenario)
            ),
            step=0.5,
            help=HELP_THIS_IS_YOUR_ASSUMPTION_STR,
        )
    )


def _render_currency_picker(scenario: PlanScenario) -> str:
    """Offer every currency, opening on the one already chosen."""
    code_list = list_currency_code_list()
    current_str = scenario.presentation.currency_code_str
    return st.selectbox(
        "Currency",
        help=HELP_CHANGES_THE_SYMBOL_AND_STR,
        options=code_list,
        index=(
            code_list.index(current_str)
            if current_str in code_list
            else 0
        ),
    )


def render_answer(scenario: PlanScenario) -> None:
    """Run the plan and report what it comes to.

    Brief:
        Reports the nominal corpus, what it is worth in today's
        money, and what was actually paid in - because a corpus
        without its cost is only half an answer.

    Arguments:
        scenario (PlanScenario): Scenario to run.

    Returns:
        None: The answer is rendered.

    Warning:
        Runs on every rerun. The plans this page can express are
        small enough for that to be imperceptible.
    """
    compiled = compile_scenario(scenario)
    run = simulate_nominal_run(
        compiled.fund_list,
        compiled.settings,
        False,
        compiled.currency,
    )
    snapshot_list = run.result.monthly_snapshots_list
    if not snapshot_list:
        st.warning("This plan runs for no months at all.")
        return
    final_snapshot = snapshot_list[-1]
    final_float = final_snapshot.portfolio_value_float
    invested_float = final_snapshot.invested_amount_float
    real_float = deflate_amount_float(
        final_float,
        compiled.inflation_percent_float,
        scenario.plan.horizon_years_int * 12,
    )
    st.subheader("What that comes to")
    _render_headline_tiles(
        final_float, invested_float, real_float, compiled
    )
    _render_growth_note(final_float, invested_float, compiled)


def _render_headline_tiles(
    final_float: float,
    invested_float: float,
    real_float: float,
    compiled: CompiledPlan,
) -> None:
    """Show the three figures that answer the question."""
    first, second, third = st.columns(3)
    first.metric(
        "Value at the end",
        format_money_str(final_float, compiled.currency),
        help=describe_money_str(final_float, compiled.currency),
    )
    second.metric(
        "You will have paid in",
        format_money_str(invested_float, compiled.currency),
    )
    third.metric(
        "Worth in today's money",
        format_money_str(real_float, compiled.currency),
        help=(
            "The same value, restated at "
            f"{compiled.inflation_percent_float:g}% inflation."
        ),
    )


def _render_growth_note(
    final_float: float,
    invested_float: float,
    compiled: CompiledPlan,
) -> None:
    """Say how much of the corpus was growth rather than saving."""
    if final_float <= 0.0 or invested_float <= 0.0:
        return
    growth_float = final_float - invested_float
    share_float = 100.0 * growth_float / final_float
    st.caption(
        f"{format_money_str(growth_float, compiled.currency)} of "
        f"that - {share_float:.0f}% - is growth rather than money "
        "you paid in."
    )


def describe_step_up_str(scenario: PlanScenario) -> str:
    """Say whether the instalment grows, and by how much.

    Brief:
        Written from the plan rather than fixed, because this page
        can now add a step-up. A screen that says "no step-up"
        under a plan that has one is worse than saying nothing.

    Arguments:
        scenario (PlanScenario): Plan being described.

    Returns:
        str: One markdown bullet.
    """
    for event in scenario.plan.ordered_event_list:
        if event.event_type_str == EVENT_STEPUP_STR:
            return (
                f"**Step-up of {event.percent_float:g}% a year.** "
                "The amount rises every year from the start."
            )
    return (
        "**No step-up.** The amount never rises with your salary."
    )


def describe_pause_str(scenario: PlanScenario) -> str:
    """Say whether contributions stop for a while.

    Arguments:
        scenario (PlanScenario): Plan being described.

    Returns:
        str: One markdown bullet.
    """
    for event in scenario.plan.ordered_event_list:
        if event.event_type_str == EVENT_PAUSE_STR:
            return (
                "**A break from "
                f"{event.event_date:%B %Y}.** Contributions stop; "
                "what is already invested keeps compounding."
            )
    return "**No pauses.** You never stop contributing."


def render_assumptions(scenario: PlanScenario) -> None:
    """State every default this page took on the reader's behalf."""
    compiled = compile_scenario(scenario)
    with st.expander("What this assumed", expanded=False):
        st.markdown(
            f"- {describe_step_up_str(scenario)}\n"
            f"- {describe_pause_str(scenario)}\n"
            "- **No withdrawals.** Nothing comes out until the "
            "end.\n"
            f"- **Costs:** an expense ratio of "
            f"{scenario.fund_list[0].expense_percent_float:g}% a "
            "year is deducted.\n"
            f"- **Inflation:** "
            f"{compiled.inflation_percent_float:g}% a year, used "
            "only for the today's-money figure.\n"
            "- **Tax:** not applied to this figure, because "
            "nothing is sold until the end. The Advanced "
            "Simulator applies it in full."
        )
        st.caption(
            "Every one of these is a real choice, and each one "
            "moves the answer. **Guided Journey** asks about them "
            "in plain language."
        )


STEP_UP_PERCENT_FLOAT: float = 10.0
PAUSE_FROM_YEAR_INT: int = 5
PAUSE_LENGTH_YEARS_INT: int = 3


def _describe_delta_str(
    scenario: PlanScenario,
    changed: PlanScenario,
) -> str:
    """What one change would do to the ending value.

    Brief:
        The whole point of offering these buttons. A reader
        deciding whether a career break matters is helped by the
        figure, not by the invitation to go and find out.

    Arguments:
        scenario (PlanScenario): The plan as it stands.
        changed (PlanScenario): The plan with the change applied.

    Returns:
        str: A signed money amount, or an empty string when the
            plan cannot be run.
    """
    currency = compile_scenario(scenario).currency
    before_float = run_journey_outcome(scenario).final_value_float
    after_float = run_journey_outcome(changed).final_value_float
    difference_float = after_float - before_float
    if round(difference_float, 2) == 0.0:
        return ""
    sign_str = "+" if difference_float > 0 else "−"
    return (
        f"{sign_str}"
        f"{format_money_str(abs(difference_float), currency)}"
    )


def render_realism_actions(scenario: PlanScenario) -> None:
    """Offer the two changes that most plans are missing.

    Brief:
        Real life has raises in it and breaks in it, and a flat
        projection has neither. Each button says what it would be
        worth before it is pressed, and applies to the shared plan
        so every other screen sees it immediately.

    Arguments:
        scenario (PlanScenario): The plan as it stands.

    Returns:
        None: The actions are rendered.

    Warning:
        Writes the scenario and reruns. The edits replace rather
        than stack, so pressing a button twice is harmless.
    """
    st.subheader("Make this more like a real life")
    step_up_column, pause_column = st.columns(2)
    with step_up_column:
        _render_step_up_action(scenario)
    with pause_column:
        _render_pause_action(scenario)


def _render_step_up_action(scenario: PlanScenario) -> None:
    """Offer a yearly increase, priced before it is applied."""
    if has_event_of_type_bool(scenario, EVENT_STEPUP_STR):
        st.success(
            f"**Step-up applied.** The amount now rises "
            f"{STEP_UP_PERCENT_FLOAT:g}% a year."
        )
        return
    changed = add_annual_step_up(scenario, STEP_UP_PERCENT_FLOAT)
    delta_str = _describe_delta_str(scenario, changed)
    st.markdown(
        f"**Raise the amount {STEP_UP_PERCENT_FLOAT:g}% a year**"
    )
    st.caption(
        "Most salaries grow. A flat instalment quietly assumes "
        f"yours will not. Worth **{delta_str}** here."
        if delta_str
        else "Most salaries grow; a flat instalment assumes yours "
        "will not."
    )
    if st.button(
        "Add a yearly step-up",
        key="quick_add_step_up",
        width="stretch",
    ):
        write_scenario(changed)
        st.rerun()


def _render_pause_action(scenario: PlanScenario) -> None:
    """Offer a career break, priced before it is applied."""
    if has_event_of_type_bool(scenario, EVENT_PAUSE_STR):
        st.info(
            f"**A {PAUSE_LENGTH_YEARS_INT}-year break is in the "
            "plan.** Edit it on Guided Journey."
        )
        render_page_link(
            GUIDED_PAGE_STR, "Open the timeline", "🧭"
        )
        return
    changed = add_contribution_pause(
        scenario, PAUSE_FROM_YEAR_INT, PAUSE_LENGTH_YEARS_INT
    )
    delta_str = _describe_delta_str(scenario, changed)
    st.markdown(
        f"**Stop for {PAUSE_LENGTH_YEARS_INT} years from year "
        f"{PAUSE_FROM_YEAR_INT}**"
    )
    st.caption(
        "A career break, a house, a course. Costs "
        f"**{delta_str}** here - and what is already invested "
        "keeps compounding throughout."
        if delta_str
        else "A career break, a house deposit, a course."
    )
    if st.button(
        "Add a break",
        key="quick_add_pause",
        width="stretch",
    ):
        write_scenario(changed)
        st.rerun()


def render_next_steps() -> None:
    """Point at the routes onward, which carry the plan across."""
    st.divider()
    st.markdown("**Where next**")
    first_column, second_column = st.columns(2)
    with first_column:
        st.markdown(
            "🧭 **Guided Journey** - add the raises, the breaks "
            "and the withdrawals that a real life has in it."
        )
        render_page_link(GUIDED_PAGE_STR, "Guided Journey", "🧭")
    with second_column:
        st.markdown(
            "⚖️ **Compare Journeys** - see what each of those "
            "decisions actually costs over the whole horizon."
        )
        render_page_link(COMPARE_PAGE_STR, "Compare Journeys", "⚖")
    st.caption(
        "Everything you entered carries across - you will not be "
        "asked again."
    )


def render() -> None:
    """Render the Quick Projection page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    updated = render_inputs(scenario)
    if updated != scenario:
        write_scenario(updated)
    st.divider()
    if read_monthly_contribution_float(updated) <= 0.0:
        st.info(
            "**Enter a monthly amount above.** With nothing going "
            "in, there is nothing to project."
        )
        return
    render_answer(updated)
    render_scenario_assumptions(updated)
    render_assumptions(updated)
    st.divider()
    render_realism_actions(updated)
    render_next_steps()
