"""Streamlit application wiring inputs, engine and reports."""

from __future__ import annotations

from typing import Literal

import pandas as pd
import streamlit as st

from investment_journey_simulator.constants import DASHBOARD_TITLE_STR
from investment_journey_simulator.dashboard_run import (
    DashboardRun,
    build_real_run,
    simulate_nominal_run,
)
from investment_journey_simulator.exports.excel_report import (
    build_excel_report_bytes,
)
from investment_journey_simulator.exports.pdf_report import (
    build_pdf_report_bytes,
)
from investment_journey_simulator.fund_builder import (
    build_fund_configurations_list,
)
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
from investment_journey_simulator.scenarios import render_scenario_controls
from investment_journey_simulator.ui.fund_inputs import (
    render_fund_table_dataframe,
)
from investment_journey_simulator.ui.result_view import (
    render_download_buttons,
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
from investment_journey_simulator.ui.theme import is_dark_mode_bool

PAGE_LAYOUT_STR: Literal["centered", "wide"] = "wide"
NOMINAL_SECTION_HEADING_STR: str = "Portfolio Summary (Nominal)"
REAL_SECTION_HEADING_STR: str = "Inflation-adjusted (Real Returns)"
EXPORT_SECTION_HEADING_STR: str = "Export / Save Results"
EXPORT_BUTTON_LABEL_STR: str = "Prepare downloads"
EXPORT_STATE_KEY_STR: str = "prepared_export_payload"
NO_FUND_MESSAGE_STR: str = (
    "Add at least one mutual fund to run the simulation."
)
EXPORT_HINT_STR: str = (
    "Exports are built on request, because rendering the report "
    "takes a few seconds."
)
FUNDS_SHEET_NAME_STR: str = "Funds"
SHEET_NAME_TEMPLATE_STR: str = "{label}_{table}"


def build_export_sheet_dict(
    fund_table_dataframe: pd.DataFrame,
    nominal_run: DashboardRun,
    real_run: DashboardRun,
) -> dict[str, pd.DataFrame]:
    """Collect every table that belongs in the workbook.

    Brief:
        Inputs first, then each run's summary, ledgers and series,
        so a reader can retrace any headline number.

    Arguments:
        fund_table_dataframe (pd.DataFrame): Fund inputs.
        nominal_run (DashboardRun): Nominal run bundle.
        real_run (DashboardRun): Inflation-adjusted run bundle.

    Returns:
        Dict[str, pd.DataFrame]: Sheet name to table mapping.

    Warning:
        Sheet names are truncated to the Excel limit on write.
    """
    sheet_dataframe_dict: dict[str, pd.DataFrame] = {
        FUNDS_SHEET_NAME_STR: fund_table_dataframe
    }
    for dashboard_run in (nominal_run, real_run):
        for table_label_str, table_frame in _build_run_table_dict(
            dashboard_run
        ).items():
            sheet_dataframe_dict[
                SHEET_NAME_TEMPLATE_STR.format(
                    label=dashboard_run.label_str,
                    table=table_label_str,
                )
            ] = table_frame
    return sheet_dataframe_dict


def _build_run_table_dict(
    dashboard_run: DashboardRun,
) -> dict[str, pd.DataFrame]:
    """List the exportable tables of one run.

    Brief:
        Same set for the nominal and the real run, so the workbook
        stays symmetric.

    Arguments:
        dashboard_run (DashboardRun): Run being exported.

    Returns:
        Dict[str, pd.DataFrame]: Table label to table mapping.

    Warning:
        Empty ledgers are still written, as empty sheets.
    """
    return {
        "Summary": dashboard_run.fund_summary_dataframe,
        "Series": dashboard_run.monthly_series_dataframe,
        "Annual": build_annual_summary_dataframe(
            dashboard_run.result
        ),
        "Rebalances": build_rebalance_ledger_dataframe(
            dashboard_run.result
        ),
        "Withdrawals": build_withdrawal_ledger_dataframe(
            dashboard_run.result
        ),
        "FundHistory": build_fund_history_dataframe(
            dashboard_run.result
        ),
    }


def build_pdf_payload(
    nominal_run: DashboardRun,
    real_run: DashboardRun,
    fund_table_dataframe: pd.DataFrame,
) -> tuple[bytes | None, str]:
    """Try to render the printable report and report failures.

    Brief:
        The report depends on optional packages, so a failure must
        degrade into a message instead of breaking the page.

    Arguments:
        nominal_run (DashboardRun): Nominal run bundle.
        real_run (DashboardRun): Inflation-adjusted run bundle.
        fund_table_dataframe (pd.DataFrame): Scenario appendix.

    Returns:
        Tuple[Optional[bytes], str]: Report payload and the error
            message when the payload could not be built.

    Warning:
        Image rendering can be slow for long horizons.
    """
    try:
        report_bytes = build_pdf_report_bytes(
            dashboard_title_str=DASHBOARD_TITLE_STR,
            nominal_summary_lines_list=(
                nominal_run.summary_lines_list
            ),
            real_summary_lines_list=real_run.summary_lines_list,
            notes_lines_list=build_notes_lines_list(),
            nominal_figure=nominal_run.figure,
            real_figure=real_run.figure,
            nominal_summary_dataframe=(
                nominal_run.fund_summary_dataframe
            ),
            real_summary_dataframe=real_run.fund_summary_dataframe,
            scenario_dataframe=fund_table_dataframe,
        )
        return report_bytes, ""
    except Exception as export_error:  # noqa: BLE001
        return None, str(export_error)


def build_export_payload_tuple(
    fund_table_dataframe: pd.DataFrame,
    nominal_run: DashboardRun,
    real_run: DashboardRun,
) -> tuple[bytes, bytes | None, str]:
    """Build both export payloads once.

    Brief:
        Called only when the user presses the prepare button, so a
        normal interaction never pays the rendering cost.

    Arguments:
        fund_table_dataframe (pd.DataFrame): Fund inputs.
        nominal_run (DashboardRun): Nominal run bundle.
        real_run (DashboardRun): Inflation-adjusted run bundle.

    Returns:
        Tuple[bytes, Optional[bytes], str]: Workbook, report and
            the report error message.

    Warning:
        Payloads reflect the settings at the moment of the press.
    """
    excel_report_bytes = build_excel_report_bytes(
        dashboard_title_str=DASHBOARD_TITLE_STR,
        nominal_summary_lines_list=nominal_run.summary_lines_list,
        real_summary_lines_list=real_run.summary_lines_list,
        notes_lines_list=build_notes_lines_list(),
        sheet_dataframe_dict=build_export_sheet_dict(
            fund_table_dataframe, nominal_run, real_run
        ),
    )
    pdf_report_bytes, pdf_error_message_str = build_pdf_payload(
        nominal_run, real_run, fund_table_dataframe
    )
    return (
        excel_report_bytes,
        pdf_report_bytes,
        pdf_error_message_str,
    )


def render_export_section(
    fund_table_dataframe: pd.DataFrame,
    nominal_run: DashboardRun,
    real_run: DashboardRun,
) -> None:
    """Offer, build and serve the downloadable exports.

    Brief:
        Building is gated behind a button so that editing an input
        never triggers a full report render.

    Arguments:
        fund_table_dataframe (pd.DataFrame): Fund inputs.
        nominal_run (DashboardRun): Nominal run bundle.
        real_run (DashboardRun): Inflation-adjusted run bundle.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Prepared payloads go stale if inputs change afterwards.
    """
    st.divider()
    st.subheader(EXPORT_SECTION_HEADING_STR)
    st.caption(EXPORT_HINT_STR)
    if st.button(EXPORT_BUTTON_LABEL_STR):
        st.session_state[EXPORT_STATE_KEY_STR] = (
            build_export_payload_tuple(
                fund_table_dataframe, nominal_run, real_run
            )
        )
    payload_tuple = st.session_state.get(EXPORT_STATE_KEY_STR)
    if payload_tuple is None:
        return
    render_download_buttons(*payload_tuple)


def build_runs_pair(
    fund_table_dataframe: pd.DataFrame,
    sidebar_selections: SidebarSelections,
) -> tuple[DashboardRun, DashboardRun]:
    """Simulate the plan in nominal and in real terms.

    Brief:
        Both runs share one fund list; the real run deflates the
        nominal result rather than simulating again.

    Arguments:
        fund_table_dataframe (pd.DataFrame): Fund inputs.
        sidebar_selections (SidebarSelections): Sidebar inputs.

    Returns:
        Tuple[DashboardRun, DashboardRun]: Nominal and real runs.

    Warning:
        Stops the script when no fund could be built.
    """
    fund_configurations_list = build_fund_configurations_list(
        fund_table_dataframe,
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.expense_model_str,
    )
    if not fund_configurations_list:
        st.warning(NO_FUND_MESSAGE_STR)
        st.stop()
    is_dark_bool = is_dark_mode_bool()
    nominal_run = simulate_nominal_run(
        fund_configurations_list,
        sidebar_selections.settings,
        is_dark_bool,
        sidebar_selections.currency,
    )
    real_run = build_real_run(
        nominal_run.result,
        sidebar_selections.inflation_percent_float,
        sip_at_month_start_bool=(
            sidebar_selections.settings.sip_at_month_start_bool
        ),
        is_dark_mode_bool=is_dark_bool,
        currency=sidebar_selections.currency,
    )
    return nominal_run, real_run


def main() -> None:
    """Run the dashboard from inputs through to the exports.

    Brief:
        Collects the sidebar and fund inputs, simulates the plan,
        renders the results and offers the downloads.

    Arguments:
        None.

    Returns:
        None: The Streamlit page is rendered.

    Warning:
        Streamlit re-executes this function on every interaction.
    """
    st.set_page_config(
        page_title=DASHBOARD_TITLE_STR, layout=PAGE_LAYOUT_STR
    )
    st.title(DASHBOARD_TITLE_STR)
    sidebar_selections = render_sidebar_selections()
    fund_table_dataframe = render_fund_table_dataframe(
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.slab_rate_percent_float,
        sidebar_selections.is_stagger_enabled_bool,
        sidebar_selections.currency,
    )
    render_scenario_controls(
        sidebar_selections, fund_table_dataframe
    )
    fund_configurations_list = build_fund_configurations_list(
        fund_table_dataframe,
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.expense_model_str,
    )
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


if __name__ == "__main__":
    main()
