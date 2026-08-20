"""Widgets that present simulation results and downloads."""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.constants import (
    EXCEL_FILE_NAME_STR,
    EXCEL_MIME_TYPE_STR,
    MONTHS_IN_YEAR_INT,
    PDF_FILE_NAME_STR,
    PDF_MIME_TYPE_STR,
    SUMMARY_MONEY_COLUMNS_TUPLE,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.dashboard_run import DashboardRun
from investment_journey_simulator.formatting import format_money_amount_str
from investment_journey_simulator.ledgers import (
    build_annual_summary_dataframe,
    build_rebalance_ledger_dataframe,
    build_withdrawal_ledger_dataframe,
)
from investment_journey_simulator.models import SimulationSettings
from investment_journey_simulator.narrative import build_notes_lines_list
from investment_journey_simulator.tables import format_money_columns_dataframe
from investment_journey_simulator.ui.theme import (
    apply_page_figure_theme,
)
from investment_journey_simulator.validation import (
    build_invariant_dataframe,
    run_all_invariants_list,
)

METRIC_LABELS_TUPLE: tuple = (
    "End Value",
    "Invested (Principal)",
    "Withdrawn (Gross)",
    "Tax Paid (Realized)",
)
SECONDARY_METRIC_LABELS_TUPLE: tuple = (
    "Spendable after full exit",
    "Cost to exit today",
    "Exit load + STT paid",
    "Losses booked",
)
RETURN_METRIC_LABELS_TUPLE: tuple = (
    "XIRR (pre-tax)",
    "XIRR (post-tax)",
)
UNAVAILABLE_RETURN_STR: str = "n/a"
CAVEAT_TAIL_STR: str = (
    ", which it has never once done. Useful for comparing plans. "
    "Not a forecast. See the Risk section for what actually happens."
)
SINGLE_RATE_CAVEAT_TEMPLATE_STR: str = (
    "⚠️ This figure assumes the market returns exactly {rate} every "
    "single month for {years}" + CAVEAT_TAIL_STR
)
MANY_RATE_CAVEAT_TEMPLATE_STR: str = (
    "⚠️ This figure assumes every fund returns exactly the rate you "
    "typed, every single month for {years}" + CAVEAT_TAIL_STR
)
CHART_TAB_LABELS_TUPLE: tuple = (
    "Dashboard",
    "Value by fund",
    "Weights vs target",
    "Drawdown",
)
LEDGER_TAB_LABELS_TUPLE: tuple = (
    "Per-fund summary",
    "Rebalancing history",
    "Withdrawal history",
    "Year by year",
    "Monthly series",
)
EMPTY_LEDGER_MESSAGE_TUPLE: tuple = (
    "No funds configured.",
    "No rebalancing trade was executed in this run.",
    "No withdrawal was requested in this run.",
    "No completed year yet.",
    "No months simulated.",
)
VALIDATION_ELEMENT_NAME_STR: str = "validation"


def build_element_key_str(
    run_label_str: str,
    element_name_str: str,
) -> str:
    """Build a unique widget key for one run's element.

    Brief:
        Streamlit derives an element id from its parameters, so two
        runs that happen to render identical figures or identical
        empty tables would collide. Weight charts in particular are
        ratios, so the nominal and real versions are byte
        identical. Prefixing every key with the run label makes
        each element unambiguous.

    Arguments:
        run_label_str (str): Run label such as Nominal or Real.
        element_name_str (str): Name of the element inside the run.

    Returns:
        str: Lower case, underscore separated widget key.

    Warning:
        Keys must stay stable across reruns, so never build them
        from values that change with the inputs.
    """
    slug_str = f"{run_label_str}_{element_name_str}".lower()
    return "".join(
        character_str if character_str.isalnum() else "_"
        for character_str in slug_str
    )


def render_mode_description(mode_description_str: str) -> None:
    """Show the one-line description of the active settings.

    Brief:
        Keeps the reader aware of which switches produced the
        numbers on screen.

    Arguments:
        mode_description_str (str): Description of the settings.

    Returns:
        None: Text is written to the page.

    Warning:
        Purely informational; nothing here is recomputed.
    """
    st.markdown(f"**{mode_description_str}**")


def render_depletion_warning(dashboard_run: DashboardRun) -> None:
    """Warn when the plan could not pay a requested withdrawal.

    Brief:
        A shortfall means the corpus ran out; this is the single
        most important thing a withdrawal plan can tell you.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to inspect.

    Returns:
        None: A warning is written when relevant.

    Warning:
        Silence means every request was funded in full.
    """
    depletion_month_date = (
        dashboard_run.result.depletion_month_date
    )
    if depletion_month_date is None:
        return
    unmet_float = dashboard_run.result.total_unmet_withdrawal_float
    currency = dashboard_run.currency
    st.error(
        f"Portfolio exhausted: the first unpaid withdrawal falls in "
        f"{depletion_month_date.strftime('%b %Y')}. "
        f"Total shortfall over the horizon: "
        f"{format_money_amount_str(unmet_float, currency)}."
    )


def render_run_section(
    dashboard_run: DashboardRun,
    section_heading_str: str,
) -> None:
    """Render the metrics, charts and tables of one run.

    Brief:
        The nominal and inflation-adjusted runs share this layout
        so the two can be compared at a glance.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.
        section_heading_str (str): Heading above the section.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Very long horizons make the charts heavy to render.
    """
    st.subheader(section_heading_str)
    _render_metric_row(dashboard_run)
    _render_secondary_metric_row(dashboard_run)
    _render_return_metric_row(dashboard_run)
    render_constant_return_caveat(dashboard_run)
    render_depletion_warning(dashboard_run)
    _render_chart_tabs(dashboard_run)
    _render_ledger_tabs(dashboard_run)


def _render_chart_tabs(dashboard_run: DashboardRun) -> None:
    """Render every figure of a run in its own tab.

    Brief:
        Tabs keep the page short while still exposing the drawdown
        and allocation views that a single panel cannot show.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Each tab renders eagerly, so all figures are built.
    """
    figure_list = [
        dashboard_run.figure,
        dashboard_run.fund_history_figure,
        dashboard_run.allocation_figure,
        dashboard_run.drawdown_figure,
    ]
    tab_list = st.tabs(list(CHART_TAB_LABELS_TUPLE))
    for tab, figure, tab_label_str in zip(
        tab_list, figure_list, CHART_TAB_LABELS_TUPLE, strict=True
    ):
        with tab:
            st.plotly_chart(
                apply_page_figure_theme(
                    figure,
                ),
                width="stretch",
                key=build_element_key_str(
                    dashboard_run.label_str, tab_label_str
                ),
            )


def _render_ledger_tabs(dashboard_run: DashboardRun) -> None:
    """Render the audit tables of a run in tabs.

    Brief:
        Every headline number can be traced to the event that
        produced it.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Empty ledgers show an explanatory caption instead.
    """
    frame_list = _build_ledger_frame_list(dashboard_run)
    tab_list = st.tabs(list(LEDGER_TAB_LABELS_TUPLE))
    for tab, table_frame, message_str, tab_label_str in zip(
        tab_list,
        frame_list,
        EMPTY_LEDGER_MESSAGE_TUPLE,
        LEDGER_TAB_LABELS_TUPLE,
        strict=True,
    ):
        with tab:
            if table_frame.empty:
                st.caption(message_str)
                continue
            st.dataframe(
                table_frame,
                width="stretch",
                hide_index=True,
                key=build_element_key_str(
                    dashboard_run.label_str, tab_label_str
                ),
            )


def _build_ledger_frame_list(dashboard_run: DashboardRun) -> list:
    """Collect the tables shown in the ledger tabs.

    Brief:
        Kept in one place so the tab labels, the tables and the
        empty-state captions stay aligned.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.

    Returns:
        list: Tables in the same order as the tab labels.

    Warning:
        Order must match both label tuples exactly.
    """
    return [
        format_money_columns_dataframe(
            dashboard_run.fund_summary_dataframe,
            SUMMARY_MONEY_COLUMNS_TUPLE,
            dashboard_run.currency,
        ),
        build_rebalance_ledger_dataframe(dashboard_run.result),
        build_withdrawal_ledger_dataframe(dashboard_run.result),
        build_annual_summary_dataframe(dashboard_run.result),
        dashboard_run.monthly_series_dataframe,
    ]


def _render_metric_row(dashboard_run: DashboardRun) -> None:
    """Render the four headline totals as metric tiles.

    Brief:
        Gives an immediate read of corpus, cost, exits and tax.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Withdrawals are shown gross of tax.
    """
    metric_value_list = [
        dashboard_run.result.ending_value_float,
        dashboard_run.result.ending_invested_float,
        dashboard_run.result.ending_withdrawn_float,
        dashboard_run.result.ending_tax_paid_float,
    ]
    _render_metric_tiles(
        METRIC_LABELS_TUPLE,
        metric_value_list,
        dashboard_run.label_str,
        dashboard_run.currency,
    )


def _render_secondary_metric_row(
    dashboard_run: DashboardRun,
) -> None:
    """Render the exit cost and loss tiles.

    Brief:
        Surfaces the money that the headline corpus does not yet
        account for: the tax and charges of actually leaving.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Exit figures are zero when the exit-tax switch is off.
    """
    metric_value_list = [
        dashboard_run.result.post_tax_ending_value_float,
        dashboard_run.result.total_exit_cost_float,
        dashboard_run.result.charges_paid_float,
        dashboard_run.result.realized_loss_float,
    ]
    _render_metric_tiles(
        SECONDARY_METRIC_LABELS_TUPLE,
        metric_value_list,
        "",
        dashboard_run.currency,
    )


def _format_return_percent_str(
    return_percent_float: float | None,
) -> str:
    """Render a money-weighted return for a metric tile.

    Brief:
        A degenerate cash flow series has no rate at all, and that
        must read as unavailable rather than as zero percent.

    Arguments:
        return_percent_float (Optional[float]): Solved rate.

    Returns:
        str: Formatted percentage, or the unavailable marker.

    Warning:
        Never substitutes zero for an unsolvable series.
    """
    if return_percent_float is None:
        return UNAVAILABLE_RETURN_STR
    return f"{float(return_percent_float):.2f}%"


def _render_return_metric_row(dashboard_run: DashboardRun) -> None:
    """Render the money-weighted return tiles.

    Brief:
        XIRR is the only return figure comparable with a broker
        statement, and the post-tax figure is the one that says
        what the plan actually kept.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to display.

    Returns:
        None: Widgets are written to the page.

    Warning:
        The post-tax figure only nets exit tax when the final
        liquidation switch is on.
    """
    value_str_list = [
        _format_return_percent_str(
            dashboard_run.pre_tax_xirr_percent_float
        ),
        _format_return_percent_str(
            dashboard_run.post_tax_xirr_percent_float
        ),
    ]
    column_list = st.columns(len(RETURN_METRIC_LABELS_TUPLE))
    for column_index_int, label_str in enumerate(
        RETURN_METRIC_LABELS_TUPLE
    ):
        column_list[column_index_int].metric(
            label_str, value_str_list[column_index_int]
        )


def render_constant_return_caveat(
    dashboard_run: DashboardRun,
) -> None:
    """Warn that the headline figure assumes a constant return.

    Brief:
        Every number above this line comes from compounding one
        fixed rate every month, which no market has ever done. The
        caveat sits directly beneath the tiles so nobody reads the
        corpus without it.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to describe.

    Returns:
        None: A caption is written to the page.

    Warning:
        Says nothing when the run has no funds to describe.
    """
    outcome_list = dashboard_run.result.fund_outcomes_list
    if not outcome_list:
        return
    horizon_str = _describe_horizon_str(
        len(dashboard_run.result.monthly_snapshots_list)
    )
    rate_set = {
        round(outcome.net_return_percent_float, 2)
        for outcome in outcome_list
    }
    if len(rate_set) == 1:
        st.caption(
            SINGLE_RATE_CAVEAT_TEMPLATE_STR.format(
                rate=f"{rate_set.pop():.2f}%", years=horizon_str
            )
        )
        return
    st.caption(
        MANY_RATE_CAVEAT_TEMPLATE_STR.format(years=horizon_str)
    )


def _describe_horizon_str(month_count_int: int) -> str:
    """Phrase a month count as whole years where it divides evenly.

    Brief:
        "15 years" reads better than "180 months", but a partial
        year must not be rounded away.

    Arguments:
        month_count_int (int): Months simulated.

    Returns:
        str: Human phrase naming the horizon.

    Warning:
        Falls back to months whenever the horizon is not a whole
        number of years.
    """
    if month_count_int % MONTHS_IN_YEAR_INT == 0:
        year_count_int = month_count_int // MONTHS_IN_YEAR_INT
        return f"{year_count_int} years"
    return f"{month_count_int} months"


def _render_metric_tiles(
    label_tuple: tuple,
    value_list: list[float],
    prefix_str: str,
    currency: Currency | None = None,
) -> None:
    """Render one row of money metric tiles.

    Brief:
        Shared by both metric rows so spacing stays the same.

    Arguments:
        label_tuple (tuple): Tile labels.
        value_list (List[float]): Tile values.
        prefix_str (str): Optional label prefix.
        currency (Optional[Currency]): Display currency.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Label and value counts must match.
    """
    column_list = st.columns(len(label_tuple))
    for column_index_int, metric_label_str in enumerate(label_tuple):
        full_label_str = (
            f"{prefix_str} {metric_label_str}".strip()
            if prefix_str
            else metric_label_str
        )
        column_list[column_index_int].metric(
            full_label_str,
            format_money_amount_str(
                value_list[column_index_int], currency
            ),
        )


def render_validation_section(
    dashboard_run: DashboardRun,
    settings: SimulationSettings,
) -> None:
    """Render the pass or fail table of every invariant.

    Brief:
        Lets the reader confirm the engine's own accounting before
        trusting any number on the page.

    Arguments:
        dashboard_run (DashboardRun): Bundled run to check.
        settings (SimulationSettings): Rules used for the run.

    Returns:
        None: Widgets are written to the page.

    Warning:
        A failing withdrawal check is a planning result, not an
        engine defect.
    """
    outcome_list = run_all_invariants_list(
        dashboard_run.result, settings
    )
    failing_count_int = sum(
        1
        for outcome in outcome_list
        if not outcome.is_passing_bool
    )
    with st.expander(
        f"Validation: {len(outcome_list) - failing_count_int} of "
        f"{len(outcome_list)} checks passing",
        expanded=failing_count_int > 0,
    ):
        st.dataframe(
            build_invariant_dataframe(outcome_list),
            width="stretch",
            hide_index=True,
            key=build_element_key_str(
                dashboard_run.label_str, VALIDATION_ELEMENT_NAME_STR
            ),
        )


def render_notes_expander() -> None:
    """Render the method notes, cautions and usage guidance.

    Brief:
        Expanded by default so the assumptions are read before the
        numbers are trusted.

    Arguments:
        None.

    Returns:
        None: Widgets are written to the page.

    Warning:
        The listed caveats materially affect the projections.
    """
    with st.expander(
        "Notes, cautions and how to use this dashboard",
        expanded=False,
    ):
        for note_line_str in build_notes_lines_list():
            if note_line_str:
                st.markdown(note_line_str)


def render_download_buttons(
    excel_report_bytes: bytes,
    pdf_report_bytes: bytes | None,
    pdf_error_message_str: str,
) -> None:
    """Render the workbook and report download buttons.

    Brief:
        The report button is replaced by an explanation when the
        optional rendering toolchain is unavailable.

    Arguments:
        excel_report_bytes (bytes): Workbook payload.
        pdf_report_bytes (Optional[bytes]): Report payload, or
            None when the export failed.
        pdf_error_message_str (str): Reason the report failed.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Payloads are built only when the user asks for them.
    """
    excel_column, pdf_column = st.columns(2)
    with excel_column:
        st.download_button(
            label="Download Excel (tables, ledgers, series)",
            data=excel_report_bytes,
            file_name=EXCEL_FILE_NAME_STR,
            mime=EXCEL_MIME_TYPE_STR,
        )
    with pdf_column:
        if pdf_report_bytes is not None:
            st.download_button(
                label="Download PDF (snapshot)",
                data=pdf_report_bytes,
                file_name=PDF_FILE_NAME_STR,
                mime=PDF_MIME_TYPE_STR,
            )
        else:
            st.warning(
                "PDF export needs reportlab and kaleido. Install "
                "them with: pip install reportlab kaleido\n\n"
                f"Details: {pdf_error_message_str}"
            )


def render_summary_lines(summary_lines_list: list[str]) -> None:
    """Render pre-rendered summary lines as a bullet list.

    Brief:
        Used for the compact text summary above the charts.

    Arguments:
        summary_lines_list (List[str]): Lines to display.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Lines are printed verbatim without further formatting.
    """
    for summary_line_str in summary_lines_list:
        st.markdown(f"- {summary_line_str}")
