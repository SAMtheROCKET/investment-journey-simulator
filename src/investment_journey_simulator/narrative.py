"""Human readable summary, caution and how-to-use text blocks."""

from __future__ import annotations

from investment_journey_simulator.constants import (
    STEPUP_MODE_BOTH_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODE_PER_FUND_STR,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.formatting import (
    format_compact_money_str,
    format_money_amount_str,
)
from investment_journey_simulator.models import (
    SimulationResult,
    SimulationSettings,
)

METHOD_NOTE_STR: str = (
    "Notes: Net return uses net = gross - expense (planning "
    "approximation). The equity preset uses STCG 20%, LTCG 12.5%, "
    "a 12-month threshold and a 1.25 lakh exemption on long term "
    "gains only. The debt preset (post Apr 1, 2023) is modelled as "
    "always short term at the slab rate. This is a planning "
    "simulator, not a tax or financial guarantee."
)

CAUTION_LINES_TUPLE: tuple = (
    "Important cautions:",
    "- Returns are assumptions; real markets are volatile and the "
    "path is never this smooth.",
    "- The expense ratio is modelled as net = gross - expense, "
    "while real funds deduct it continuously.",
    "- Withdrawal and rebalancing taxes are realized immediately "
    "using lot-wise FIFO accounting.",
    "- Exit load, securities transaction tax, cess, surcharge, "
    "expense-ratio changes and payouts are not modelled.",
    "- The exemption is tracked per fund per financial year, "
    "whereas the law applies it per taxpayer.",
)

USAGE_LINES_TUPLE: tuple = (
    "How to use this dashboard efficiently:",
    "1) To see allocation drift, switch rebalancing off and give "
    "the funds different return assumptions.",
    "2) Prefer conservative return assumptions over optimistic "
    "ones when planning a goal.",
    "3) Copy expense ratios from the fund factsheet or the latest "
    "total expense ratio disclosure.",
    "4) Use the global step-up for a salary-linked increase and "
    "the per-fund step-up for a fund-specific plan.",
    "5) Rebalancing reallocates the whole current value, principal "
    "and gains together, to the target proportions.",
)


def build_mode_description_str(
    settings: SimulationSettings,
    inflation_percent_float: float,
) -> str:
    """Describe the active switches of the current run in a line.

    Brief:
        Reproduced at the top of the on-screen summary and inside
        both exported reports so results stay self-documenting.

    Arguments:
        settings (SimulationSettings): Portfolio level rules.
        inflation_percent_float (float): Annual inflation percent.

    Returns:
        str: Single line describing the run configuration.

    Warning:
        Purely descriptive; nothing here affects the simulation.
    """
    timing_label_str = (
        "Start of Month"
        if settings.sip_at_month_start_bool
        else "End of Month"
    )
    description_part_list = [
        f"Horizon: {settings.horizon_years_int}y",
        f"SIP timing: {timing_label_str}",
        f"Step-up: {settings.stepup.mode_str}",
        f"Inflation: {inflation_percent_float:.2f}%",
        _describe_rebalancing_str(settings),
        _describe_withdrawal_str(settings),
    ]
    if settings.stepup.mode_str in (
        STEPUP_MODE_GLOBAL_STR,
        STEPUP_MODE_BOTH_STR,
    ):
        description_part_list.insert(
            3,
            "Global step-up: "
            f"{settings.stepup.global_stepup_percent_float:.2f}%/yr",
        )
    if settings.stepup.mode_str in (
        STEPUP_MODE_PER_FUND_STR,
        STEPUP_MODE_BOTH_STR,
    ):
        description_part_list.insert(3, "Per-fund step-up enabled")
    return " | ".join(description_part_list)


def _describe_rebalancing_str(settings: SimulationSettings) -> str:
    """Summarise the rebalancing switches in one phrase.

    Brief:
        Keeps the mode description builder short and readable.

    Arguments:
        settings (SimulationSettings): Portfolio level rules.

    Returns:
        str: Phrase describing the rebalancing configuration.

    Warning:
        Returns a short OFF phrase when rebalancing is disabled.
    """
    rebalance_settings = settings.rebalance
    if not rebalance_settings.is_enabled_bool:
        if rebalance_settings.use_contribution_steering_bool:
            return "Rebalancing: OFF (new money steered)"
        return "Rebalancing: OFF"
    return (
        "Rebalancing: ON ("
        f"target {rebalance_settings.target_mode_str}, "
        f"{rebalance_settings.method_str}, trigger "
        f"{rebalance_settings.trigger_str}, every "
        f"{rebalance_settings.interval_months_int} months, tax paid "
        f"from {rebalance_settings.tax_funding_str})"
    )


def _describe_withdrawal_str(settings: SimulationSettings) -> str:
    """Summarise the withdrawal switches in one phrase.

    Brief:
        Keeps the mode description builder short and readable.

    Arguments:
        settings (SimulationSettings): Portfolio level rules.

    Returns:
        str: Phrase describing the withdrawal configuration.

    Warning:
        Returns a short OFF phrase when withdrawals are disabled.
    """
    withdrawal_settings = settings.withdrawal
    if not withdrawal_settings.is_enabled_bool:
        return "SWP: OFF"
    return (
        "SWP: ON ("
        f"{withdrawal_settings.mode_str}, starts at month "
        f"{withdrawal_settings.start_month_index_int + 1}, annual "
        f"change "
        f"{withdrawal_settings.annual_change_percent_float:.2f}%)"
    )


def build_summary_lines_list(
    simulation_result: SimulationResult,
    heading_prefix_str: str,
    currency: Currency | None = None,
) -> list[str]:
    """Turn the headline totals of a run into report lines.

    Brief:
        The same four totals feed the screen, the workbook and the
        printable report.

    Arguments:
        simulation_result (SimulationResult): Completed run.
        heading_prefix_str (str): Label such as Nominal or Real.
        currency (Optional[Currency]): Currency of the totals.

    Returns:
        List[str]: Rendered summary lines, one metric per line.

    Warning:
        Withdrawals are reported gross of tax.
    """
    metric_pair_list = [
        ("End Value", simulation_result.ending_value_float),
        (
            "Invested (Principal)",
            simulation_result.ending_invested_float,
        ),
        (
            "Withdrawn (Gross)",
            simulation_result.ending_withdrawn_float,
        ),
        (
            "Tax Paid (Realized)",
            simulation_result.ending_tax_paid_float,
        ),
    ]
    return [
        (
            f"{heading_prefix_str} {metric_label_str}: "
            f"{format_money_amount_str(metric_value_float, currency)}"
            " ("
            f"{format_compact_money_str(metric_value_float, currency)}"
            ")"
        )
        for metric_label_str, metric_value_float in metric_pair_list
    ]


def build_notes_lines_list() -> list[str]:
    """Collect the method note, cautions and usage guidance.

    Brief:
        One ordered block of text reused by every export path.

    Arguments:
        None.

    Returns:
        List[str]: Paragraph lines ready to render or export.

    Warning:
        Read the cautions before acting on any simulated number.
    """
    notes_lines_list: list[str] = [METHOD_NOTE_STR, ""]
    notes_lines_list.extend(CAUTION_LINES_TUPLE)
    notes_lines_list.append("")
    notes_lines_list.extend(USAGE_LINES_TUPLE)
    return notes_lines_list
