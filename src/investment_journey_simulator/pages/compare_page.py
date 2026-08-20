"""Compare Journeys: the same person, different decisions.

The screen this whole program was worth building for. Four corpus
figures side by side make a point; an honest account of *why* they
differ makes it useful.

Everything here rests on two guarantees built underneath it:

* the comparison checks that what it claims to hold constant really
  is constant (`scenario_set.py`), and
* the split of the gap is exact and order-independent, so the bars
  really do add up to the difference (`attribution.py`).
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.attribution import attribute_gap
from investment_journey_simulator.compare_charts import (
    build_attribution_figure,
    build_overlay_figure,
)
from investment_journey_simulator.currency import format_money_str
from investment_journey_simulator.dashboard_run import simulate_nominal_run
from investment_journey_simulator.page_links import (
    GUIDED_PAGE_STR,
    QUICK_PAGE_STR,
)
from investment_journey_simulator.pages.page_shell import (
    has_investment_bool,
    open_page,
    render_empty_state,
    render_page_link,
)
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import (
    read_comparison_list,
    write_comparison_list,
)
from investment_journey_simulator.scenario_edits import build_named_copy
from investment_journey_simulator.scenario_set import (
    MAXIMUM_JOURNEY_COUNT_INT,
    ScenarioSet,
    add_journey,
    find_basis_difference_list,
    find_spread_float,
    remove_journey,
    run_scenario_set,
)
from investment_journey_simulator.ui.chrome import (
    render_insight,
    render_plan_pulse,
)
from investment_journey_simulator.ui.theme import (
    apply_page_figure_theme,
)

TITLE_STR: str = "Compare Journeys"
LEAD_STR: str = (
    "Same income, same return, same retirement age - different "
    "behaviour. This is what those differences are worth."
)


def read_scenario_set() -> ScenarioSet:
    """Read the journeys held for comparison."""
    return ScenarioSet(list(read_comparison_list()))


def write_scenario_set(scenario_set: ScenarioSet) -> None:
    """Store the journeys held for comparison."""
    write_comparison_list(scenario_set.scenario_list)


def render_capture_controls(scenario: PlanScenario) -> None:
    """Offer to save the current plan as a named journey.

    Brief:
        A comparison is built by naming plans, so the name is asked
        for at the moment of saving rather than invented later.

    Arguments:
        scenario (PlanScenario): The plan currently loaded.

    Returns:
        None: The controls are rendered.

    Warning:
        Saving under an existing name replaces that journey, which
        is what "I changed my mind about that one" means.
    """
    scenario_set = read_scenario_set()
    with st.form("capture_journey_form"):
        name_str = st.text_input(
            "Name this version of the plan",
            value=scenario.name_str,
            help=(
                "Describe the behaviour, not the number - "
                "'paused for three years' beats 'scenario 2'."
            ),
        )
        is_saved_bool = st.form_submit_button(
            "Save as a journey to compare",
            width="stretch",
        )
    if is_saved_bool:
        write_scenario_set(
            add_journey(
                scenario_set, build_named_copy(scenario, name_str)
            )
        )
        st.rerun()


def render_journey_list() -> None:
    """List the saved journeys, with a way to drop each one."""
    scenario_set = read_scenario_set()
    if not scenario_set.scenario_list:
        return
    st.markdown("**Journeys held for comparison**")
    for held in scenario_set.scenario_list:
        name_column, drop_column = st.columns([5, 1])
        name_column.markdown(f"- {held.name_str}")
        if drop_column.button(
            "Remove",
            key=f"drop_{held.name_str}",
            width="stretch",
        ):
            write_scenario_set(
                remove_journey(scenario_set, held.name_str)
            )
            st.rerun()
    st.caption(
        f"Up to {MAXIMUM_JOURNEY_COUNT_INT} journeys; the oldest "
        "drops off after that."
    )


def render_basis_warning(scenario_set: ScenarioSet) -> None:
    """Say so when the comparison is not purely about behaviour.

    Brief:
        The guard that keeps the headline honest. Four figures
        under "same return, different behaviour" are worthless if
        the returns were not in fact the same.

    Arguments:
        scenario_set (ScenarioSet): Journeys being compared.

    Returns:
        None: A warning is rendered when one is warranted.

    Warning:
        Warns rather than refuses. Comparing two returns on purpose
        is reasonable; being told it was behaviour is not.
    """
    difference_list = find_basis_difference_list(scenario_set)
    if not difference_list:
        st.success(
            "These journeys share every assumption. The whole "
            "difference below is caused by behaviour."
        )
        return
    for difference in difference_list:
        st.warning(difference.sentence_str)


def render_headline_tiles(scenario_set: ScenarioSet) -> list:
    """Show each journey's final corpus, side by side."""
    outcome_list = run_scenario_set(scenario_set)
    currency = compile_scenario(
        scenario_set.scenario_list[0]
    ).currency
    column_list = st.columns(len(outcome_list))
    best_float = max(
        outcome.final_value_float for outcome in outcome_list
    )
    for column, outcome in zip(
        column_list, outcome_list, strict=True
    ):
        shortfall_float = outcome.final_value_float - best_float
        column.metric(
            outcome.name_str,
            format_money_str(outcome.final_value_float, currency),
            delta=(
                None
                if shortfall_float == 0.0
                else format_money_str(shortfall_float, currency)
            ),
        )
    return outcome_list


def render_gap_hero(outcome_list: list, currency) -> None:
    """Lead with the gap, because the gap is the finding.

    Brief:
        This screen exists to answer one question - what did the
        decisions cost - and the answer is a single figure. Burying
        it under four equal tiles makes a reader do the subtraction
        that the program was built to do for them.

    Arguments:
        outcome_list (list): One outcome per journey.
        currency: Currency the figures are in.

    Returns:
        None: The hero plate is rendered.

    Warning:
        Draws nothing when every journey lands on the same figure,
        which is a real and informative outcome rather than a bug.
    """
    spread_float = find_spread_float(outcome_list)
    if spread_float <= 0.0:
        st.info(
            "Every journey here ends on the same figure. Whatever "
            "differs between them did not change the outcome."
        )
        return
    best = max(outcome_list, key=lambda o: o.final_value_float)
    worst = min(outcome_list, key=lambda o: o.final_value_float)
    render_plan_pulse(
        format_money_str(spread_float, currency),
        "The distance between the best and the worst of these "
        "journeys. Same money available, same market assumed - "
        "this is the price of the decisions alone.",
        (
            ("Best", f"{best.name_str}"),
            ("Worst", f"{worst.name_str}"),
            ("Journeys compared", str(len(outcome_list))),
        ),
        label_str="What the decisions cost",
    )


def render_overlay(scenario_set: ScenarioSet) -> None:
    """Draw every journey's corpus on one axis."""
    series_dict = {}
    month_date_list: list = []
    for held in scenario_set.scenario_list:
        compiled = compile_scenario(held)
        run = simulate_nominal_run(
            compiled.fund_list,
            compiled.settings,
            False,
            compiled.currency,
        )
        snapshot_list = run.result.monthly_snapshots_list
        series_dict[held.name_str] = [
            snapshot.portfolio_value_float
            for snapshot in snapshot_list
        ]
        if len(snapshot_list) > len(month_date_list):
            month_date_list = [
                snapshot.month_date for snapshot in snapshot_list
            ]
    st.plotly_chart(
        apply_page_figure_theme(
            build_overlay_figure(
                series_dict,
                month_date_list,
                compile_scenario(
                    scenario_set.scenario_list[0]
                ).currency,
            ),
        ),
        width="stretch",
    )


def render_attribution(scenario_set: ScenarioSet) -> None:
    """Explain the gap between the best and worst journeys.

    Brief:
        The part that makes this more than four curves. Every bar
        is a named cause, and the bars add up exactly.

    Arguments:
        scenario_set (ScenarioSet): Journeys being compared.

    Returns:
        None: The waterfall and its prose are rendered.

    Warning:
        Compares the extremes. With more than two journeys the
        middle ones are shown above but not decomposed, because a
        waterfall per pair would be unreadable.
    """
    outcome_list = run_scenario_set(scenario_set)
    best_index_int = max(
        range(len(outcome_list)),
        key=lambda index_int: outcome_list[
            index_int
        ].final_value_float,
    )
    worst_index_int = min(
        range(len(outcome_list)),
        key=lambda index_int: outcome_list[
            index_int
        ].final_value_float,
    )
    if best_index_int == worst_index_int:
        return
    baseline = scenario_set.scenario_list[best_index_int]
    variant = scenario_set.scenario_list[worst_index_int]
    st.subheader("Why the gap exists")
    attribution = attribute_gap(baseline, variant)
    currency = compile_scenario(baseline).currency
    st.plotly_chart(
        apply_page_figure_theme(
            build_attribution_figure(attribution, currency),
        ),
        width="stretch",
    )
    _render_cause_prose(attribution, currency)


def _render_cause_prose(attribution, currency) -> None:
    """Explain each cause in the order that it mattered."""
    if not attribution.cause_list:
        st.info(
            "These two journeys are identical, so there is "
            "nothing to explain."
        )
        return
    for cause in attribution.ranked_cause_list:
        st.markdown(
            f"**{cause.label_str}: "
            f"{format_money_str(cause.amount_float, currency)}**"
        )
        st.caption(cause.explanation_str)
    if round(attribution.residual_float, 2) != 0.0:
        st.warning(
            "Part of the gap is unexplained: "
            f"{format_money_str(attribution.residual_float, currency)}. "
            "Please report this - the causes are meant to add up "
            "exactly."
        )
        return
    _render_attribution_reading(attribution, currency)


def _render_attribution_reading(attribution, currency) -> None:
    """Say what the decomposition means, and where to act on it.

    Brief:
        The split is exact and order-independent, which is a strong
        claim and a useless one until somebody says what to do with
        it. The largest cause is the one worth naming, because it
        is the one worth changing.

    Arguments:
        attribution: The decomposed gap.
        currency: Currency the figures are in.

    Returns:
        None: The interpretation is rendered.
    """
    if not attribution.ranked_cause_list:
        return
    leading = attribution.ranked_cause_list[0]
    render_insight(
        f"Most of this gap - "
        f"{format_money_str(abs(leading.amount_float), currency)} "
        f"of it - comes from one thing: {leading.label_str.lower()}"
        ". The causes are split by Shapley value, so they are "
        "order-independent and add up to the whole gap exactly, "
        "with nothing absorbed into a remainder."
    )
    render_page_link(
        GUIDED_PAGE_STR, "Change it on the timeline", "🧭"
    )


def render() -> None:
    """Render the Compare Journeys page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    if has_investment_bool(scenario):
        render_capture_controls(scenario)
    else:
        render_empty_state(
            "No plan to save yet",
            "Build a plan on Quick Projection or Guided Journey "
            "first, then come back and save it as a journey.",
        )
        render_page_link(
            QUICK_PAGE_STR, "Start a one-minute projection", "⚡"
        )
    render_journey_list()
    scenario_set = read_scenario_set()
    if not scenario_set.is_comparable_bool:
        st.divider()
        render_empty_state(
            "Save at least two journeys",
            "Change something about your plan - pause for a "
            "couple of years, add a step-up, take money out - "
            "then save it under a new name. The comparison "
            "appears once there are two.",
        )
        render_page_link(
            GUIDED_PAGE_STR, "Change something on the timeline", "🧭"
        )
        return
    st.divider()
    render_basis_warning(scenario_set)
    currency = compile_scenario(
        scenario_set.scenario_list[0]
    ).currency
    render_gap_hero(run_scenario_set(scenario_set), currency)
    render_headline_tiles(scenario_set)
    render_overlay(scenario_set)
    render_attribution(scenario_set)
