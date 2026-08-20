"""Generate the rebalancing comparison report.

Run:
    python tools/build_rebalancing_report.py

It writes docs/reports/rebalancing_comparison.md. This lives under
tools/ rather than src/ because it is a thing you run *at* the
project, like the house-style checker and the diagram renderer -
not a thing the project imports.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

PACKAGE_PARENT_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent / "src"
)
if str(PACKAGE_PARENT_DIRECTORY_PATH) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT_DIRECTORY_PATH))

import pandas as pd  # noqa: E402

from investment_journey_simulator.rebalancing_lab import (  # noqa: E402
    LabFundSpecification,
    build_all_scenario_dataframe_list,
    build_headline_dataframe,
)

REPORT_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent / "docs" / "reports"
)
REPORT_FILE_NAME_STR: str = "rebalancing_comparison.md"
EQUAL_TARGET_WEIGHT_FLOAT: float = 100.0 / 3.0
UNLIMITED_EVENTS_INT: int = 0
SINGLE_EVENT_INT: int = 1

SMALL_FUND_LIST: list[LabFundSpecification] = [
    LabFundSpecification("Fund A", 2.0, 12.0,
                         EQUAL_TARGET_WEIGHT_FLOAT),
    LabFundSpecification("Fund B", 7.0, 10.0,
                         EQUAL_TARGET_WEIGHT_FLOAT),
    LabFundSpecification("Fund C", 5.0, 14.0,
                         EQUAL_TARGET_WEIGHT_FLOAT),
]
LARGE_FUND_LIST: list[LabFundSpecification] = [
    LabFundSpecification("Fund A", 10000.0, 12.0,
                         EQUAL_TARGET_WEIGHT_FLOAT),
    LabFundSpecification("Fund B", 7000.0, 10.0,
                         EQUAL_TARGET_WEIGHT_FLOAT),
    LabFundSpecification("Fund C", 5000.0, 14.0,
                         EQUAL_TARGET_WEIGHT_FLOAT),
]


@dataclass(frozen=True)
class ReportSet:
    """One labelled block of tables inside the report."""

    title_str: str
    description_str: str
    fund_specification_list: list[LabFundSpecification]
    interval_years_int: int
    maximum_events_int: int


REPORT_SET_LIST: list[ReportSet] = [
    ReportSet(
        "Set 0 - tiny SIPs, one rebalance at T=10Y",
        "Fund A 2 at 12%, Fund B 7 at 10%, Fund C 5 at 14%. "
        "Shows why tax looked irrelevant at this scale.",
        SMALL_FUND_LIST, 10, SINGLE_EVENT_INT,
    ),
    ReportSet(
        "Set 1 - real SIPs, one rebalance at T=10Y",
        "Fund A 10,000 at 12%, Fund B 7,000 at 10%, "
        "Fund C 5,000 at 14%. Rebalances once, at year 10.",
        LARGE_FUND_LIST, 10, SINGLE_EVENT_INT,
    ),
    ReportSet(
        "Set 2 - real SIPs, rebalance every 5Y",
        "Same funds as Set 1, rebalanced at years 5, 10, 15, 20 "
        "and 25.",
        LARGE_FUND_LIST, 5, UNLIMITED_EVENTS_INT,
    ),
    ReportSet(
        "Set 3 - real SIPs, rebalance every 10Y",
        "Same funds as Set 1, rebalanced at years 10 and 20.",
        LARGE_FUND_LIST, 10, UNLIMITED_EVENTS_INT,
    ),
]


def render_markdown_table_str(table_dataframe: pd.DataFrame) -> str:
    """Render a table as a GitHub flavoured markdown table.

    Brief:
        Avoids an extra formatting dependency while keeping the
        report readable in any markdown viewer.

    Arguments:
        table_dataframe (pd.DataFrame): Table to render.

    Returns:
        str: Markdown table including its header separator.

    Warning:
        Pipe characters inside cell values are not escaped.
    """
    header_list = [str(column) for column in table_dataframe.columns]
    line_list = [
        "| " + " | ".join(header_list) + " |",
        "|" + "|".join(["---"] * len(header_list)) + "|",
    ]
    for row_tuple in table_dataframe.itertuples(index=False):
        line_list.append(
            "| "
            + " | ".join(str(value) for value in row_tuple)
            + " |"
        )
    return "\n".join(line_list)


def build_report_section_str(report_set: ReportSet) -> str:
    """Build the markdown block of one report set.

    Brief:
        Starts with the policy ranking, then prints the detailed
        per-fund table of every policy.

    Arguments:
        report_set (ReportSet): Set being rendered.

    Returns:
        str: Markdown section for that set.

    Warning:
        Building a section runs many simulations and is slow.
    """
    section_part_list = [
        f"## {report_set.title_str}",
        "",
        report_set.description_str,
        "",
        "### Ranking of every policy (value and cumulative tax)",
        "",
        render_markdown_table_str(
            build_headline_dataframe(
                report_set.fund_specification_list,
                report_set.interval_years_int,
                report_set.maximum_events_int,
            )
        ),
        "",
    ]
    scenario_table_list = build_all_scenario_dataframe_list(
        report_set.fund_specification_list,
        report_set.interval_years_int,
        report_set.maximum_events_int,
    )
    for scenario_label_str, scenario_dataframe in (
        scenario_table_list
    ):
        section_part_list.extend(
            [
                f"### {scenario_label_str}",
                "",
                render_markdown_table_str(scenario_dataframe),
                "",
            ]
        )
    return "\n".join(section_part_list)


def build_report_str() -> str:
    """Build the whole comparison report.

    Brief:
        Adds the assumption preamble in front of every set so the
        tables can never be read out of context.

    Arguments:
        None.

    Returns:
        str: Complete markdown report.

    Warning:
        Returns are deterministic, so this report cannot show the
        volatility benefit that motivates rebalancing in reality.
    """
    report_part_list = [
        "# Rebalancing comparison report",
        "",
        "Generated by `tools/build_rebalancing_report.py`.",
        "",
        "**Assumptions.** Instalments at the start of every month, "
        "smooth deterministic returns, zero expense ratio, no "
        "step-up, no withdrawals, no inflation. Equity taxation: "
        "STCG 20%, LTCG 12.5% beyond 12 months, exemption "
        "Rs.1,25,000 per taxpayer per financial year. The user target "
        "split is equal weight (33.33% each). Each horizon column "
        "is a separate simulation ending on that anniversary. No "
        "final redemption tax is applied at the horizon.",
        "",
    ]
    for report_set in REPORT_SET_LIST:
        report_part_list.append(build_report_section_str(report_set))
    return "\n".join(report_part_list)


def main() -> None:
    """Write the comparison report to the reports directory.

    Brief:
        Single entry point so the report can be regenerated after
        any change to the engine.

    Arguments:
        None.

    Returns:
        None: The report file is written to disk.

    Warning:
        Overwrites the existing report file.
    """
    REPORT_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    report_file_path = REPORT_DIRECTORY_PATH / REPORT_FILE_NAME_STR
    report_file_path.write_text(build_report_str(), encoding="utf-8")
    print(f"Report written to: {report_file_path}")


if __name__ == "__main__":
    main()
