"""Reports & Audit: every figure, and the working behind it.

A projection nobody can check is a number with a font. This screen
exists so that any figure the portal shows can be traced to the
inputs that produced it, exported, and argued with.

It also carries the save and reopen controls, because a plan you
cannot take away is a plan you have to rebuild next time.
"""

from __future__ import annotations

from hashlib import sha256

import streamlit as st

from investment_journey_simulator.dashboard_run import simulate_nominal_run
from investment_journey_simulator.ledgers import (
    build_annual_summary_dataframe,
    build_fund_history_dataframe,
    build_rebalance_ledger_dataframe,
    build_withdrawal_ledger_dataframe,
)
from investment_journey_simulator.narrative import (
    build_mode_description_str,
    build_notes_lines_list,
)
from investment_journey_simulator.page_links import QUICK_PAGE_STR
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
from investment_journey_simulator.portal_state import write_scenario
from investment_journey_simulator.scenario_io import (
    SCENARIO_FILE_NAME_STR,
    SCENARIO_MIME_TYPE_STR,
    SCENARIO_VERSION_STR,
    build_scenario_json_bytes,
    parse_scenario_bytes,
)
from investment_journey_simulator.ui.chrome import render_kicker
from investment_journey_simulator.ui.plan_summary import (
    render_scenario_pulse,
)
from investment_journey_simulator.ui.regime_notice import render_regime_notice

TITLE_STR: str = "Reports & Audit"
LEAD_STR: str = (
    "Every figure on every screen, traceable to the inputs that "
    "produced it - and portable, so you never rebuild a plan."
)
LEDGER_TAB_TUPLE: tuple = (
    ("Year by year", build_annual_summary_dataframe),
    ("Each fund", build_fund_history_dataframe),
    ("Rebalancing trades", build_rebalance_ledger_dataframe),
    ("Withdrawals", build_withdrawal_ledger_dataframe),
)


def render_save_and_open(scenario: PlanScenario) -> None:
    """Offer to take the plan away, and to bring one back.

    Brief:
        A saved plan is the one thing here a reader cannot
        regenerate, so reopening an older file is guaranteed to
        work and is tested against a frozen fixture.

    Arguments:
        scenario (PlanScenario): The plan currently loaded.

    Returns:
        None: The controls are rendered.

    Warning:
        Opening a file replaces the plan in this session outright.
    """
    st.subheader("Save or reopen this plan")
    save_column, open_column = st.columns(2)
    save_column.download_button(
        "Download this plan",
        data=build_scenario_json_bytes(scenario),
        file_name=SCENARIO_FILE_NAME_STR,
        mime=SCENARIO_MIME_TYPE_STR,
        width="stretch",
    )
    uploaded_file = open_column.file_uploader(
        "Open a saved plan", type=["json"]
    )
    if uploaded_file is not None:
        _apply_uploaded_plan(uploaded_file)
    st.caption(
        f"Saved as version {SCENARIO_VERSION_STR}. Files written "
        "by earlier builds are upgraded when opened, so nothing "
        "you have saved before is lost."
    )


def _apply_uploaded_plan(uploaded_file) -> None:
    """Load an uploaded plan, reporting a bad file plainly."""
    try:
        write_scenario(
            parse_scenario_bytes(uploaded_file.getvalue())
        )
    except (ValueError, KeyError) as error:
        st.error(f"That file could not be read: {error}")
        return
    st.success("Plan loaded. Every screen now uses it.")


def render_working(scenario: PlanScenario) -> None:
    """State in words what this run actually did."""
    compiled = compile_scenario(scenario)
    st.subheader("What this run did")
    render_regime_notice(compiled.regime)
    st.markdown(
        build_mode_description_str(
            compiled.settings, compiled.inflation_percent_float
        )
    )
    with st.expander("Notes and caveats", expanded=False):
        for line_str in build_notes_lines_list():
            st.markdown(f"- {line_str}")


def render_ledgers(scenario: PlanScenario) -> None:
    """Show the month-by-month working behind the headline."""
    compiled = compile_scenario(scenario)
    run = simulate_nominal_run(
        compiled.fund_list,
        compiled.settings,
        False,
        compiled.currency,
    )
    st.subheader("The working")
    tab_list = st.tabs(
        [label_str for label_str, _builder in LEDGER_TAB_TUPLE]
    )
    for tab, (_label_str, build_frame) in zip(
        tab_list, LEDGER_TAB_TUPLE, strict=True
    ):
        with tab:
            _render_ledger_frame(build_frame, run)


def _render_ledger_frame(build_frame, run) -> None:
    """Render one ledger, or say why it is empty."""
    frame = build_frame(run.result)
    if frame is None or frame.empty:
        st.caption(
            "Nothing to show - this plan has no entries of this "
            "kind."
        )
        return
    st.dataframe(frame, width="stretch")


def render_inputs_audit(scenario: PlanScenario) -> None:
    """List the inputs, so a figure can be argued with."""
    compiled = compile_scenario(scenario)
    with st.expander("Every input, as entered", expanded=False):
        st.markdown(
            f"**Horizon** {scenario.plan.horizon_years_int} years "
            f"from {scenario.plan.start_date:%B %Y}  \n"
            f"**Currency** {compiled.currency.name_str}  \n"
            f"**Tax rules** {compiled.regime.label_str}  \n"
            f"**Inflation** "
            f"{compiled.inflation_percent_float:g}% a year  \n"
            f"**Events on the timeline** "
            f"{len(scenario.plan.event_list)}"
        )
        for fund_configuration in scenario.fund_list:
            st.markdown(
                f"- **{fund_configuration.name_str}**: "
                f"{fund_configuration.gross_return_percent_float:g}"
                "% gross, "
                f"{fund_configuration.expense_percent_float:g}% "
                "expense ratio"
            )


def build_run_fingerprint_str(scenario: PlanScenario) -> str:
    """A short, stable identifier for one set of inputs.

    Brief:
        Two people looking at the same figure need a way to check
        they are looking at the same plan. A digest of the compiled
        inputs is that check: same inputs, same fingerprint, and
        any difference anywhere changes it.

    Arguments:
        scenario (PlanScenario): Plan being identified.

    Returns:
        str: Twelve hex characters.

    Warning:
        Identifies *inputs*, not results. It deliberately says
        nothing about whether the engine that ran them was the
        same version, which the build line beside it covers.
    """
    compiled = compile_scenario(scenario)
    material_str = repr(
        (
            scenario.plan.start_date,
            scenario.plan.horizon_years_int,
            sorted(
                (
                    event.event_type_str,
                    event.event_date,
                    event.amount_float,
                    event.percent_float,
                )
                for event in scenario.plan.event_list
            ),
            [
                (
                    fund.name_str,
                    fund.gross_return_percent_float,
                    fund.expense_percent_float,
                    fund.monthly_sip_float,
                )
                for fund in scenario.fund_list
            ],
            compiled.inflation_percent_float,
            compiled.currency.code_str,
            compiled.regime.label_str,
            scenario.policy,
        )
    )
    return sha256(material_str.encode("utf-8")).hexdigest()[:12]


def render_run_identity(scenario: PlanScenario) -> None:
    """Say exactly which plan produced the figures below.

    Brief:
        The proof layer's first obligation. Every other screen
        answers "what does this come to"; this one has to answer
        "and which inputs are you quoting".

    Arguments:
        scenario (PlanScenario): Plan being reported.

    Returns:
        None: The identity block is rendered.
    """
    render_kicker("Run identity")
    compiled = compile_scenario(scenario)
    first, second, third = st.columns(3)
    first.metric("Plan", scenario.name_str)
    second.metric(
        "Inputs fingerprint", build_run_fingerprint_str(scenario)
    )
    third.metric("Tax rules", compiled.regime.label_str)
    st.caption(
        "The fingerprint is a digest of every input above. Quote "
        "it alongside any figure from this page: if two of you "
        "have the same fingerprint, you are arguing about the same "
        "plan, and if you do not, that is the argument."
    )


def render() -> None:
    """Render the Reports & Audit page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    render_save_and_open(scenario)
    st.divider()
    if not has_investment_bool(scenario):
        render_empty_state(
            "Nothing is being invested yet",
            "There is no working to show until the plan puts "
            "money in. Set a monthly amount on Quick Projection "
            "or Guided Journey.",
        )
        render_page_link(
            QUICK_PAGE_STR, "Start a one-minute projection", "⚡"
        )
        return
    render_run_identity(scenario)
    render_scenario_pulse(scenario, label_str="Reported figures")
    render_working(scenario)
    render_inputs_audit(scenario)
    render_ledgers(scenario)
