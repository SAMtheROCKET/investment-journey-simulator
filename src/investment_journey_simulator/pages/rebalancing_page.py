"""Rebalancing Lab: what each policy costs and saves.

Rebalancing is sold as free risk control. It is not free: selling
what has grown realises a gain, and a realised gain is taxed. This
screen measures both sides of that trade across nine policies at
once - doing nothing, both trading methods, both target bases, and
both treatments of the tax the trade creates.

The laboratory deliberately runs on its own funds at a zero expense
ratio rather than on the shared scenario, so that what it measures
is the rebalancing policy and nothing else. The page says so, out
loud, because every other screen here works the opposite way.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.page_links import ADVANCED_PAGE_STR
from investment_journey_simulator.pages.page_shell import (
    open_page,
    render_page_link,
)
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import write_scenario
from investment_journey_simulator.rebalancing_lab import (
    COMPARISON_HORIZON_YEARS_TUPLE,
    LabFundSpecification,
    build_default_scenario_list,
    build_headline_dataframe,
)
from investment_journey_simulator.scenario_edits import (
    set_rebalancing_rule,
)
from investment_journey_simulator.ui.chrome import render_insight

TITLE_STR: str = "Rebalancing Lab"
LEAD_STR: str = (
    "Rebalancing is not free. Selling what has grown realises a "
    "gain, and a realised gain is taxed. This is what nine "
    "different policies actually cost."
)
ONLY_THE_RULE_TRAVELS_STR: str = (
    "Only the rule travels. Your own funds, returns and "
    "contributions stay exactly as they are, so your plan's "
    "ending value will not match any row above."
)
DEFAULT_INTERVAL_YEARS_INT: int = 1
DEFAULT_MAXIMUM_EVENTS_INT: int = 0
DEFAULT_FUND_TUPLE: tuple = (
    ("Equity", 20000.0, 13.0, 60.0),
    ("Debt", 10000.0, 7.0, 40.0),
)

HELP_WHAT_THIS_FUND_RECEIVES_STR: str = (
    "What this fund receives each month in the experiment."
)
HELP_THE_RETURN_ASSUMED_FOR_STR: str = (
    "The return assumed for this fund. Your assumption, not a "
    "forecast."
)
HELP_THE_SHARE_OF_THE_STR: str = (
    "The share of the portfolio this fund is rebalanced back to."
)
HELP_HOW_OFTEN_EACH_POLICY_STR: str = (
    "How often each policy trims back to its target split."
)
HELP_CAPS_HOW_MANY_TIMES_STR: str = (
    "Caps how many times a policy may trade. Zero means no cap."
)
HELP_THE_RULE_YOU_WOULD_STR: str = (
    "The rule you would carry to your own plan. Only the rule "
    "travels, never these funds."
)
HELP_THE_NUMBER_OF_YEARS_STR: str = (
    "The number of years each policy is judged over. A policy "
    "that wins at ten years can lose at twenty-five."
)


def render_isolation_note() -> None:
    """Explain why this screen ignores the shared plan."""
    st.info(
        "**This screen runs its own controlled experiment.** Every "
        "policy below uses identical funds, identical "
        "contributions and a zero expense ratio, so the only "
        "thing that differs between the rows is the rebalancing "
        "rule. Mixing in your own plan would confound exactly the "
        "effect this is meant to isolate."
    )


def render_fund_controls() -> list[LabFundSpecification]:
    """Collect the two funds the experiment runs on."""
    specification_list = []
    column_list = st.columns(len(DEFAULT_FUND_TUPLE))
    for column, fund_tuple in zip(
        column_list, DEFAULT_FUND_TUPLE, strict=True
    ):
        (
            name_str,
            sip_float,
            return_float,
            weight_float,
        ) = fund_tuple
        with column:
            st.markdown(f"**{name_str}**")
            monthly_float = st.number_input(
                "Monthly amount",
                help=HELP_WHAT_THIS_FUND_RECEIVES_STR,
                min_value=0.0,
                value=sip_float,
                step=1000.0,
                key=f"lab_sip_{name_str}",
            )
            annual_float = st.number_input(
                "Annual return %",
                help=HELP_THE_RETURN_ASSUMED_FOR_STR,
                min_value=0.0,
                max_value=40.0,
                value=return_float,
                step=0.5,
                key=f"lab_return_{name_str}",
            )
            target_float = st.number_input(
                "Target weight %",
                help=HELP_THE_SHARE_OF_THE_STR,
                min_value=0.0,
                max_value=100.0,
                value=weight_float,
                step=5.0,
                key=f"lab_weight_{name_str}",
            )
        specification_list.append(
            LabFundSpecification(
                name_str,
                float(monthly_float),
                float(annual_float),
                float(target_float),
            )
        )
    return specification_list


def render_rule_controls() -> tuple[int, int]:
    """Collect how often the policies rebalance."""
    first_column, second_column = st.columns(2)
    interval_int = first_column.number_input(
        "Years between rebalances",
        help=HELP_HOW_OFTEN_EACH_POLICY_STR,
        min_value=1,
        max_value=10,
        value=DEFAULT_INTERVAL_YEARS_INT,
        step=1,
    )
    maximum_int = second_column.number_input(
        "Maximum rebalances (0 for no limit)",
        help=HELP_CAPS_HOW_MANY_TIMES_STR,
        min_value=0,
        max_value=50,
        value=DEFAULT_MAXIMUM_EVENTS_INT,
        step=1,
    )
    return int(interval_int), int(maximum_int)


def render_comparison(
    specification_list: list[LabFundSpecification],
    interval_years_int: int,
    maximum_events_int: int,
    horizon_years_int: int,
) -> None:
    """Rank every policy at the chosen horizon."""
    headline_frame = build_headline_dataframe(
        specification_list,
        interval_years_int,
        maximum_events_int,
        (horizon_years_int,),
    )
    st.subheader(
        f"Every policy at {horizon_years_int} years"
    )
    st.dataframe(headline_frame, width="stretch")
    st.caption(
        "Read the value column against the tax column. A policy "
        "that ends higher *after* paying more tax has earned its "
        "keep; one that ends lower has not."
    )


def render_reading_note() -> None:
    """Say what the table is for, and what it is not."""
    with st.expander("How to read this", expanded=False):
        st.markdown(
            "- **Doing nothing** is row A, and it is the row "
            "every other policy has to beat.\n"
            "- **Funding the tax from outside** the portfolio "
            "flatters a policy: the money is real and comes from "
            "somewhere, it simply is not shown here.\n"
            "- **Full liquidation** rebalances exactly to target "
            "and realises the most gain doing it. **Partial** "
            "sells only what is overweight, which realises the "
            "smallest gain that still restores the target.\n"
            "- A policy that wins at ten years may lose at "
            "twenty-five. Change the horizon and watch the order "
            "change - that instability is the finding, not a bug."
        )


def render_apply_controls(
    scenario: PlanScenario,
    interval_years_int: int,
    maximum_events_int: int,
) -> None:
    """Carry one rule out of the laboratory and onto the plan.

    Carries the *rule* across and leaves the lab's funds behind,
    so your plan's ending value will not match any row above.

    Arguments:
        scenario (PlanScenario): The plan to change.
        interval_years_int (int): Years between rebalances.
        maximum_events_int (int): Cap on rebalances, zero for none.

    Returns:
        None: The controls are rendered.
    """
    st.subheader("Use one of these rules on my own plan")
    option_list = [
        option
        for option in build_default_scenario_list()
        if option.is_enabled_bool
    ]
    choice_str = st.selectbox(
        "Which policy",
        help=HELP_THE_RULE_YOU_WOULD_STR,
        options=[option.label_str for option in option_list],
        key="lab_apply_policy",
    )
    st.caption(ONLY_THE_RULE_TRAVELS_STR)
    if not st.button(
        "Apply this rule to my plan",
        key="lab_apply_rule",
        width="stretch",
    ):
        return
    _apply_chosen_rule(
        scenario,
        next(
            option
            for option in option_list
            if option.label_str == choice_str
        ),
        interval_years_int,
        maximum_events_int,
    )


def _apply_chosen_rule(
    scenario: PlanScenario,
    chosen,
    interval_years_int: int,
    maximum_events_int: int,
) -> None:
    """Write one lab policy onto the shared plan."""
    write_scenario(
        set_rebalancing_rule(
            scenario,
            interval_years_int,
            chosen.method_str,
            chosen.target_mode_str,
            chosen.tax_funding_str,
            maximum_events_int,
        )
    )
    st.success(
        f"**{chosen.label_str}** is now the standing rule on your "
        "plan."
    )
    render_page_link(
        ADVANCED_PAGE_STR, "See it in the full simulator", "🎛"
    )


def render() -> None:
    """Render the Rebalancing Lab page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    render_isolation_note()
    specification_list = render_fund_controls()
    interval_years_int, maximum_events_int = render_rule_controls()
    horizon_years_int = st.select_slider(
        "Horizon",
        help=HELP_THE_NUMBER_OF_YEARS_STR,
        options=list(COMPARISON_HORIZON_YEARS_TUPLE),
        value=_resolve_default_horizon_int(scenario),
    )
    st.divider()
    render_comparison(
        specification_list,
        interval_years_int,
        maximum_events_int,
        int(horizon_years_int),
    )
    render_insight(
        "Row A is doing nothing, and it is the row every other "
        "policy has to beat after tax rather than before it. A "
        "policy that ends higher having realised more gain has "
        "earned its keep; one that ends lower has bought you "
        "tidiness and charged you for it.",
        title_str="What the table is saying",
    )
    render_reading_note()
    st.divider()
    render_apply_controls(
        scenario, interval_years_int, maximum_events_int
    )


def _resolve_default_horizon_int(scenario) -> int:
    """Open on the horizon nearest the reader's own plan."""
    wanted_int = compile_scenario(
        scenario
    ).settings.horizon_years_int
    return min(
        COMPARISON_HORIZON_YEARS_TUPLE,
        key=lambda years_int: abs(years_int - wanted_int),
    )
