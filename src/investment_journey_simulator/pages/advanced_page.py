"""Advanced Simulator: every control this program has.

The classic dashboard, moved onto the shared scenario. Its sidebar
and fund table are the originals - they have been right for a long
time and rewriting them would risk that for nothing - but what they
produce is now published into the one `PlanScenario` every other
screen reads. That is what makes "configure here, compare there"
work without typing anything twice.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.app import (
    NOMINAL_SECTION_HEADING_STR,
    REAL_SECTION_HEADING_STR,
    build_runs_pair,
    render_export_section,
)
from investment_journey_simulator.fund_builder import (
    build_fund_configurations_list,
)
from investment_journey_simulator.narrative import build_mode_description_str
from investment_journey_simulator.page_links import QUICK_PAGE_STR
from investment_journey_simulator.pages.page_shell import (
    open_page,
    render_page_link,
)
from investment_journey_simulator.portal_state import (
    read_scenario,
    write_scenario,
)
from investment_journey_simulator.scenario_adapter import (
    build_scenario_from_settings,
)
from investment_journey_simulator.ui.fund_inputs import (
    render_fund_table_dataframe,
)
from investment_journey_simulator.ui.plan_summary import (
    render_scenario_pulse,
)
from investment_journey_simulator.ui.result_view import (
    render_mode_description,
    render_notes_expander,
    render_run_section,
    render_summary_lines,
    render_validation_section,
)
from investment_journey_simulator.ui.risk_view import render_risk_section
from investment_journey_simulator.ui.sidebar_controls import (
    SidebarSelections,
    render_sidebar_selections,
)

TITLE_STR: str = "Advanced Simulator"
LEAD_STR: str = (
    "Every control this program has, including the ones that need "
    "explaining. What you set here becomes the plan every other "
    "screen works from."
)
NO_FUND_MESSAGE_STR: str = (
    "Add at least one fund below to run the plan."
)


def publish_scenario(
    sidebar_selections: SidebarSelections,
    fund_configurations_list: list,
) -> None:
    """Write what the sidebar built into the shared scenario.

    Brief:
        The step that makes this page part of the portal rather
        than a program of its own. Called on every rerun, so the
        moment a control moves, every other screen agrees.

    Arguments:
        sidebar_selections (SidebarSelections): Sidebar inputs.
        fund_configurations_list (list): Funds from the table.

    Returns:
        None: The shared scenario is updated.

    Warning:
        Overwrites the shared scenario wholesale. Anything a reader
        built on the rail is replaced by what this page shows,
        which is why the two are never edited side by side.
    """
    write_scenario(
        build_scenario_from_settings(
            sidebar_selections.settings,
            fund_configurations_list,
            sidebar_selections.inflation_percent_float,
            sidebar_selections.currency.code_str,
        )
    )


def render_inputs() -> tuple:
    """Render the sidebar and the fund table.

    Brief:
        Both are the classic dashboard's own, unchanged.

    Arguments:
        None.

    Returns:
        Tuple: Sidebar selections, fund frame and fund list.

    Warning:
        Returns an empty fund list when the table has no usable
        row; callers must check before simulating.
    """
    sidebar_selections = render_sidebar_selections()
    fund_table_dataframe = render_fund_table_dataframe(
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.slab_rate_percent_float,
        sidebar_selections.is_stagger_enabled_bool,
        sidebar_selections.currency,
    )
    fund_configurations_list = build_fund_configurations_list(
        fund_table_dataframe,
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.expense_model_str,
    )
    return (
        sidebar_selections,
        fund_table_dataframe,
        fund_configurations_list,
    )


def render_results(
    sidebar_selections: SidebarSelections,
    fund_table_dataframe,
    fund_configurations_list: list,
) -> None:
    """Simulate the plan and render every section of the answer."""
    nominal_run, real_run = build_runs_pair(
        fund_table_dataframe, sidebar_selections
    )
    render_mode_description(
        build_mode_description_str(
            sidebar_selections.settings,
            sidebar_selections.inflation_percent_float,
        )
    )
    render_summary_lines(nominal_run.summary_lines_list)
    render_run_section(nominal_run, NOMINAL_SECTION_HEADING_STR)
    render_validation_section(
        nominal_run, sidebar_selections.settings
    )
    render_risk_section(
        fund_configurations_list,
        sidebar_selections.settings,
        nominal_run.result.post_tax_ending_value_float,
        sidebar_selections.currency,
    )
    st.divider()
    render_summary_lines(real_run.summary_lines_list)
    render_run_section(real_run, REAL_SECTION_HEADING_STR)
    render_notes_expander()
    render_export_section(
        fund_table_dataframe, nominal_run, real_run
    )


def render() -> None:
    """Render the Advanced Simulator page."""
    open_page(TITLE_STR, LEAD_STR)
    (
        sidebar_selections,
        fund_table_dataframe,
        fund_configurations_list,
    ) = render_inputs()
    if not fund_configurations_list:
        st.warning(NO_FUND_MESSAGE_STR)
        render_page_link(
            QUICK_PAGE_STR, "Or start somewhere simpler", "⚡"
        )
        return
    publish_scenario(sidebar_selections, fund_configurations_list)
    # Published first, so the pulse below reports the plan as the
    # controls have just left it rather than as it was last rerun.
    render_scenario_pulse(
        read_scenario(), label_str="Where this plan stands"
    )
    render_results(
        sidebar_selections,
        fund_table_dataframe,
        fund_configurations_list,
    )
