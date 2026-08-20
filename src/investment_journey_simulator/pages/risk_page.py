"""Historical & Risk Lab: the part that changes conclusions.

Every other screen answers "what if the return is exactly what I
assumed". Nothing ever is. This screen asks two harder questions:

* **What actually happened?** The same plan, replayed over real
  index history, started in every month the data allows. The spread
  between the best and worst start month is the cost of timing -
  measured rather than argued about.
* **What does the order of returns do?** The same average return in
  a different sequence produces a different corpus, and near the end
  of a plan the difference is large. That is sequence-of-returns
  risk, and it is the single most under-appreciated thing here.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.backtest import (
    run_rolling_backtest_list,
    summarise_rolling_outcomes_dict,
)
from investment_journey_simulator.currency import format_money_str
from investment_journey_simulator.market_data import (
    calculate_annualised_return_percent_float,
    calculate_annualised_volatility_percent_float,
    describe_coverage_str,
    load_bundled_market_history,
)
from investment_journey_simulator.page_links import QUICK_PAGE_STR
from investment_journey_simulator.pages.page_shell import (
    has_investment_bool,
    open_page,
    render_empty_state,
    render_page_link,
)
from investment_journey_simulator.plan_scenario import (
    CompiledPlan,
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.scenario_set import run_journey_outcome
from investment_journey_simulator.ui.chrome import (
    render_insight,
    render_kicker,
)
from investment_journey_simulator.ui.plan_summary import (
    render_scenario_assumptions,
)
from investment_journey_simulator.ui.risk_view import render_risk_section

TITLE_STR: str = "Historical & Risk Lab"
LEAD_STR: str = (
    "Your plan assumes one steady return. No market has ever "
    "delivered one. This is what happens when you drop that "
    "assumption."
)
# Keys as `summarise_rolling_outcomes_dict` emits them. Named here
# rather than inline so a rename in the summariser breaks a test
# instead of quietly rendering an empty row of tiles.
BEST_VALUE_KEY_STR: str = "best_value"
MEDIAN_VALUE_KEY_STR: str = "median_value"
WORST_VALUE_KEY_STR: str = "worst_value"
SUMMARY_KEY_TUPLE: tuple = (
    (BEST_VALUE_KEY_STR, "Best start month"),
    (MEDIAN_VALUE_KEY_STR, "Median start month"),
    (WORST_VALUE_KEY_STR, "Worst start month"),
)


def render_history_summary(history) -> None:
    """Say what data is being replayed, before replaying it."""
    return_float = calculate_annualised_return_percent_float(
        history
    )
    volatility_float = (
        calculate_annualised_volatility_percent_float(history)
    )
    st.caption(
        f"{describe_coverage_str(history)} · annualised return "
        f"{return_float:.1f}% · annualised volatility "
        f"{volatility_float:.1f}%"
    )


def render_rolling_backtest(
    compiled: CompiledPlan,
    history,
) -> None:
    """Replay the plan from every start month the data allows.

    Brief:
        The headline is the spread: the same plan, the same
        contributions, the same length - and a different answer
        depending only on the month it happened to begin.

    Arguments:
        compiled (CompiledPlan): The plan being replayed.
        history: Monthly index history.

    Returns:
        None: The results are rendered.

    Warning:
        Windows overlap heavily, so these are a range rather than
        a distribution. The caption says so.
    """
    outcome_list = run_rolling_backtest_list(
        compiled.fund_list, compiled.settings, history
    )
    if not outcome_list:
        st.info(
            "The history available is shorter than this plan's "
            "horizon, so no full window can be replayed. Shorten "
            "the horizon to use this section."
        )
        return
    summary_dict = summarise_rolling_outcomes_dict(outcome_list)
    st.subheader("What actually happened")
    column_list = st.columns(len(SUMMARY_KEY_TUPLE))
    for column, (key_str, label_str) in zip(
        column_list, SUMMARY_KEY_TUPLE, strict=True
    ):
        if key_str in summary_dict:
            column.metric(
                label_str,
                format_money_str(
                    summary_dict[key_str], compiled.currency
                ),
            )
    _render_timing_note(summary_dict, compiled, len(outcome_list))


def _render_timing_note(
    summary_dict: dict,
    compiled: CompiledPlan,
    window_count_int: int,
) -> None:
    """State the cost of timing in one sentence."""
    if not {
        BEST_VALUE_KEY_STR,
        WORST_VALUE_KEY_STR,
    } <= set(summary_dict):
        return
    spread_float = (
        summary_dict[BEST_VALUE_KEY_STR]
        - summary_dict[WORST_VALUE_KEY_STR]
    )
    st.markdown(
        "**The month you happened to start was worth "
        f"{format_money_str(spread_float, compiled.currency)}.**"
    )
    st.caption(
        f"Across {window_count_int} overlapping start months, "
        "with identical contributions and an identical horizon. "
        "Read these as a range rather than a distribution - the "
        "windows share most of their history."
    )


def render_sequence_risk(compiled: CompiledPlan) -> None:
    """Explain the risk that only bites at the end of a plan."""
    with st.expander(
        "Why the *order* of returns matters", expanded=False
    ):
        st.markdown(
            "Two plans can earn the same average return over "
            "thirty years and end up far apart, because when the "
            "bad years land is not neutral.\n\n"
            "* A crash in **year two** costs you very little. "
            "There is not much invested yet, and every "
            "contribution afterwards buys in cheaply.\n"
            "* The same crash in **year twenty-eight** hits the "
            "whole balance, and there are almost no contributing "
            "years left to recover in.\n\n"
            "This is sequence-of-returns risk. It is why a single "
            "average return - the number every other screen here "
            "asks you for - flatters a plan near its end."
        )


HISTORY_TAB_STR: str = "What actually happened"
SIMULATION_TAB_STR: str = "What could happen"


def render_history_tab(compiled: CompiledPlan) -> None:
    """Replay the plan over real history, and label it as measured.

    Brief:
        Everything in this tab happened. Nothing in it is a
        probability, and the language is chosen so a reader cannot
        come away thinking otherwise.

    Arguments:
        compiled (CompiledPlan): The plan being replayed.

    Returns:
        None: The tab is rendered.
    """
    render_kicker("Measured · real index history")
    history = load_bundled_market_history()
    if history is None:
        st.info(
            "No index history is bundled with this build, so "
            "nothing can be replayed. The other tab does not need "
            "it - it simulates rather than replays."
        )
        return
    render_history_summary(history)
    render_rolling_backtest(compiled, history)
    render_insight(
        "Every figure in this tab is something that happened to a "
        "real index. None of it is a probability, and none of it "
        "is a forecast - it is the same plan, started in a "
        "different month.",
        title_str="How to read this tab",
    )
    render_sequence_risk(compiled)


def render_simulation_tab(
    scenario: PlanScenario,
    compiled: CompiledPlan,
) -> None:
    """Simulate the plan, and label it as modelled.

    Brief:
        The counterpart tab, kept separate on purpose. Merging
        measured history with modelled probability in one visual
        treatment is the single most misleading thing a risk
        screen can do, because a reader cannot then tell which
        numbers are evidence and which are assumption.

    Arguments:
        scenario (PlanScenario): The plan being simulated.
        compiled (CompiledPlan): Its compiled form.

    Returns:
        None: The tab is rendered.
    """
    render_kicker("Modelled · generated from your assumptions")
    render_insight(
        "Nothing in this tab happened. These paths are generated "
        "from the return and volatility you supplied, so they "
        "describe your assumptions rather than any market. Change "
        "the assumptions and every figure here changes with them.",
        title_str="How to read this tab",
    )
    render_risk_section(
        compiled.fund_list,
        compiled.settings,
        run_journey_outcome(scenario).final_value_float,
        compiled.currency,
    )


def render() -> None:
    """Render the Historical & Risk Lab page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    if not has_investment_bool(scenario):
        render_empty_state(
            "Nothing is being invested yet",
            "Risk is a property of a plan. Set a monthly amount "
            "on Quick Projection or Guided Journey first.",
        )
        render_page_link(
            QUICK_PAGE_STR, "Start a one-minute projection", "⚡"
        )
        return
    compiled = compile_scenario(scenario)
    render_scenario_assumptions(scenario)
    # Two tabs rather than two sections down one page. A divider is
    # not a strong enough signal to stop a reader carrying a
    # measured figure into a modelled one.
    history_tab, simulation_tab = st.tabs(
        [HISTORY_TAB_STR, SIMULATION_TAB_STR]
    )
    with history_tab:
        render_history_tab(compiled)
    with simulation_tab:
        render_simulation_tab(scenario, compiled)
