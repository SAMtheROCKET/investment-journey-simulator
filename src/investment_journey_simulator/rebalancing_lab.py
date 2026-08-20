"""Laboratory that compares rebalancing strategies side by side."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from investment_journey_simulator.constants import (
    EQUITY_EXEMPTION_AMOUNT_FLOAT,
    EQUITY_LONG_TERM_MONTHS_INT,
    EQUITY_LONG_TERM_PERCENT_FLOAT,
    EQUITY_SHORT_TERM_PERCENT_FLOAT,
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_SCOPE_LONG_TERM_STR,
    MONEY_TOLERANCE_FLOAT,
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
    PRESET_EQUITY_STR,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_METHOD_PARTIAL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    REBALANCE_TARGET_SIP_SPLIT_STR,
    TAX_FUNDING_OUTSIDE_STR,
    TAX_FUNDING_PORTFOLIO_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.formatting import format_money_amount_str
from investment_journey_simulator.models import (
    FundConfiguration,
    PauseSettings,
    RebalanceSettings,
    SimulationResult,
    SimulationSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)

COMPARISON_HORIZON_YEARS_TUPLE: tuple = (1, 2, 3, 5, 10, 11, 15, 25)
LAB_START_YEAR_INT: int = 2026
TOTAL_ROW_LABEL_STR: str = "TOTAL value"
INVESTED_ROW_LABEL_STR: str = "External principal"
GAIN_ROW_LABEL_STR: str = "Net gain over principal"
TAX_ROW_LABEL_STR: str = "Cumulative tax paid"
REBALANCE_TAX_ROW_LABEL_STR: str = "...of which rebalancing tax"
EVENT_COUNT_ROW_LABEL_STR: str = "Rebalance events so far"
SCENARIO_COLUMN_STR: str = "Scenario"
ROW_LABEL_COLUMN_STR: str = "Row"
UNLIMITED_EVENTS_INT: int = 0


@dataclass(frozen=True)
class LabFundSpecification:
    """Minimal description of one fund used by the laboratory."""

    name_str: str
    monthly_sip_float: float
    annual_return_percent_float: float
    target_weight_percent_float: float


@dataclass(frozen=True)
class RebalanceScenario:
    """One rebalancing policy to be compared against the others."""

    label_str: str
    is_enabled_bool: bool
    method_str: str = REBALANCE_METHOD_FULL_STR
    target_mode_str: str = REBALANCE_TARGET_SIP_SPLIT_STR
    tax_funding_str: str = TAX_FUNDING_OUTSIDE_STR


def build_default_scenario_list() -> list[RebalanceScenario]:
    """Build the nine policies compared in every report set.

    Brief:
        Covers doing nothing, both trading methods, both target
        bases and both treatments of rebalancing tax.

    Arguments:
        None.

    Returns:
        List[RebalanceScenario]: Policies in reporting order.

    Warning:
        Ignoring tax is a planning view only; the money is real.
    """
    scenario_list = [
        RebalanceScenario("A. No rebalancing", False),
    ]
    label_index_int = ord("B")
    for target_mode_str, target_label_str in (
        (REBALANCE_TARGET_SIP_SPLIT_STR, "initial SIP split"),
        (REBALANCE_TARGET_COLUMN_STR, "user target split"),
    ):
        for method_str, method_label_str in (
            (REBALANCE_METHOD_FULL_STR, "full liquidation"),
            (REBALANCE_METHOD_PARTIAL_STR, "sell overweight only"),
        ):
            for tax_funding_str, tax_label_str in (
                (TAX_FUNDING_OUTSIDE_STR, "tax paid from outside"),
                (
                    TAX_FUNDING_PORTFOLIO_STR,
                    "tax paid from portfolio",
                ),
            ):
                scenario_list.append(
                    RebalanceScenario(
                        label_str=(
                            f"{chr(label_index_int)}. "
                            f"{method_label_str} to "
                            f"{target_label_str} ({tax_label_str})"
                        ),
                        is_enabled_bool=True,
                        method_str=method_str,
                        target_mode_str=target_mode_str,
                        tax_funding_str=tax_funding_str,
                    )
                )
                label_index_int += 1
    return scenario_list


def build_lab_fund_list(
    fund_specification_list: list[LabFundSpecification],
) -> list[FundConfiguration]:
    """Turn laboratory fund specifications into engine funds.

    Brief:
        Applies the equity tax preset and a zero expense ratio so
        that the comparison isolates the rebalancing effect.

    Arguments:
        fund_specification_list (List[LabFundSpecification]): Funds.

    Returns:
        List[FundConfiguration]: Engine ready fund definitions.

    Warning:
        Returns are deterministic, so no volatility is modelled.
    """
    start_date = date(LAB_START_YEAR_INT, 1, 1)
    return [
        FundConfiguration(
            name_str=specification.name_str,
            preset_str=PRESET_EQUITY_STR,
            monthly_sip_float=specification.monthly_sip_float,
            stepup_percent_float=0.0,
            gross_return_percent_float=(
                specification.annual_return_percent_float
            ),
            expense_percent_float=0.0,
            start_date=start_date,
            target_allocation_percent_float=(
                specification.target_weight_percent_float
            ),
            short_term_tax_percent_float=(
                EQUITY_SHORT_TERM_PERCENT_FLOAT
            ),
            long_term_tax_percent_float=(
                EQUITY_LONG_TERM_PERCENT_FLOAT
            ),
            long_term_threshold_months_int=(
                EQUITY_LONG_TERM_MONTHS_INT
            ),
            exemption_amount_float=EQUITY_EXEMPTION_AMOUNT_FLOAT,
            exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
            is_always_short_term_bool=False,
        )
        for specification in fund_specification_list
    ]


def build_lab_settings(
    horizon_years_int: int,
    scenario: RebalanceScenario,
    interval_years_int: int,
    maximum_events_int: int,
) -> SimulationSettings:
    """Build engine settings for one scenario and one horizon.

    Brief:
        Only rebalancing varies between scenarios; contributions,
        timing and taxation stay identical.

    Arguments:
        horizon_years_int (int): Years to simulate.
        scenario (RebalanceScenario): Policy being measured.
        interval_years_int (int): Years between rebalances.
        maximum_events_int (int): Event cap, zero for unlimited.

    Returns:
        SimulationSettings: Settings for this comparison cell.

    Warning:
        Instalments are invested at the start of every month.
    """
    return SimulationSettings(
        horizon_years_int=horizon_years_int,
        portfolio_start_date=date(LAB_START_YEAR_INT, 1, 1),
        sip_at_month_start_bool=True,
        stepup=StepUpSettings(),
        withdrawal=WithdrawalSettings(),
        pauses=PauseSettings(),
        tax=TaxSettings(
            exemption_level_str=EXEMPTION_LEVEL_PORTFOLIO_STR,
            portfolio_exemption_amount_float=(
                EQUITY_EXEMPTION_AMOUNT_FLOAT
            ),
        ),
        rebalance=RebalanceSettings(
            is_enabled_bool=scenario.is_enabled_bool,
            interval_months_int=(
                interval_years_int * MONTHS_IN_YEAR_INT
            ),
            method_str=scenario.method_str,
            target_mode_str=scenario.target_mode_str,
            tax_funding_str=scenario.tax_funding_str,
            maximum_events_int=maximum_events_int,
        ),
    )


def run_scenario_result(
    fund_specification_list: list[LabFundSpecification],
    scenario: RebalanceScenario,
    horizon_years_int: int,
    interval_years_int: int,
    maximum_events_int: int,
) -> SimulationResult:
    """Simulate one policy for one horizon.

    Brief:
        Each reported horizon is an independent run that ends on
        that anniversary.

    Arguments:
        fund_specification_list (List[LabFundSpecification]): Funds.
        scenario (RebalanceScenario): Policy being measured.
        horizon_years_int (int): Years to simulate.
        interval_years_int (int): Years between rebalances.
        maximum_events_int (int): Event cap, zero for unlimited.

    Returns:
        SimulationResult: Completed run for that horizon.

    Warning:
        Longer horizons are not slices of one long run; they are
        separate simulations that end at that point.
    """
    return PortfolioSimulator(
        build_lab_fund_list(fund_specification_list),
        build_lab_settings(
            horizon_years_int,
            scenario,
            interval_years_int,
            maximum_events_int,
        ),
    ).run()


def format_value_with_share_str(
    amount_float: float,
    total_float: float,
) -> str:
    """Render an amount together with its portfolio share.

    Brief:
        Seeing the weight next to the rupee value is what makes
        allocation drift visible in the tables.

    Arguments:
        amount_float (float): Fund value in rupees.
        total_float (float): Portfolio value in rupees.

    Returns:
        str: Amount followed by its share in percent.

    Warning:
        An empty portfolio reports a zero share.
    """
    share_percent_float = 0.0
    if total_float > MONEY_TOLERANCE_FLOAT:
        share_percent_float = (
            PERCENT_TOTAL_FLOAT * amount_float / total_float
        )
    return (
        f"{format_money_amount_str(amount_float)} "
        f"({share_percent_float:.2f}%)"
    )


def build_scenario_column_dict(
    simulation_result: SimulationResult,
) -> dict[str, str]:
    """Summarise one completed run as a single report column.

    Brief:
        Per-fund values with shares first, then the portfolio
        totals, the gain, the tax and the event count.

    Arguments:
        simulation_result (SimulationResult): Completed run.

    Returns:
        Dict[str, str]: Row label to rendered value mapping.

    Warning:
        Tax is cumulative up to the reported horizon.
    """
    total_value_float = simulation_result.ending_value_float
    column_dict = {
        fund_outcome.name_str: format_value_with_share_str(
            fund_outcome.ending_value_float, total_value_float
        )
        for fund_outcome in simulation_result.fund_outcomes_list
    }
    invested_float = simulation_result.ending_invested_float
    column_dict[TOTAL_ROW_LABEL_STR] = (
        format_money_amount_str(total_value_float)
    )
    column_dict[INVESTED_ROW_LABEL_STR] = (
        format_money_amount_str(invested_float)
    )
    column_dict[GAIN_ROW_LABEL_STR] = format_money_amount_str(
        total_value_float - invested_float
    )
    column_dict[TAX_ROW_LABEL_STR] = format_money_amount_str(
        simulation_result.ending_tax_paid_float
    )
    column_dict[REBALANCE_TAX_ROW_LABEL_STR] = (
        format_money_amount_str(
            simulation_result.rebalance_tax_float
        )
    )
    column_dict[EVENT_COUNT_ROW_LABEL_STR] = str(
        len(simulation_result.rebalance_events_list)
    )
    return column_dict


def build_scenario_dataframe(
    fund_specification_list: list[LabFundSpecification],
    scenario: RebalanceScenario,
    interval_years_int: int,
    maximum_events_int: int,
    horizon_years_tuple: tuple = COMPARISON_HORIZON_YEARS_TUPLE,
) -> pd.DataFrame:
    """Build the horizon table of one rebalancing policy.

    Brief:
        Rows are the funds and the portfolio aggregates; columns
        are the requested horizons.

    Arguments:
        fund_specification_list (List[LabFundSpecification]): Funds.
        scenario (RebalanceScenario): Policy being measured.
        interval_years_int (int): Years between rebalances.
        maximum_events_int (int): Event cap, zero for unlimited.
        horizon_years_tuple (tuple): Horizons to report.

    Returns:
        pd.DataFrame: Table indexed by row label.

    Warning:
        One simulation runs per horizon, so wide tables are slow.
    """
    column_dict_by_horizon = {}
    for horizon_years_int in horizon_years_tuple:
        column_dict_by_horizon[f"T={horizon_years_int}Y"] = (
            build_scenario_column_dict(
                run_scenario_result(
                    fund_specification_list,
                    scenario,
                    horizon_years_int,
                    interval_years_int,
                    maximum_events_int,
                )
            )
        )
    scenario_dataframe = pd.DataFrame(column_dict_by_horizon)
    scenario_dataframe.index.name = ROW_LABEL_COLUMN_STR
    return scenario_dataframe.reset_index()


def build_all_scenario_dataframe_list(
    fund_specification_list: list[LabFundSpecification],
    interval_years_int: int,
    maximum_events_int: int,
    horizon_years_tuple: tuple = COMPARISON_HORIZON_YEARS_TUPLE,
) -> list[tuple[str, pd.DataFrame]]:
    """Build one horizon table for every compared policy.

    Brief:
        Produces the complete set of tables that a report page or
        a workbook sheet group needs.

    Arguments:
        fund_specification_list (List[LabFundSpecification]): Funds.
        interval_years_int (int): Years between rebalances.
        maximum_events_int (int): Event cap, zero for unlimited.
        horizon_years_tuple (tuple): Horizons to report.

    Returns:
        List[Tuple[str, pd.DataFrame]]: Policy label and its table.

    Warning:
        Runs one simulation per policy and horizon combination.
    """
    return [
        (
            scenario.label_str,
            build_scenario_dataframe(
                fund_specification_list,
                scenario,
                interval_years_int,
                maximum_events_int,
                horizon_years_tuple,
            ),
        )
        for scenario in build_default_scenario_list()
    ]


def build_headline_dataframe(
    fund_specification_list: list[LabFundSpecification],
    interval_years_int: int,
    maximum_events_int: int,
    horizon_years_tuple: tuple = COMPARISON_HORIZON_YEARS_TUPLE,
) -> pd.DataFrame:
    """Compare the ending value and tax of every policy at once.

    Brief:
        One row per policy, showing the closing portfolio value and
        the tax it cost, so policies rank at a glance.

    Arguments:
        fund_specification_list (List[LabFundSpecification]): Funds.
        interval_years_int (int): Years between rebalances.
        maximum_events_int (int): Event cap, zero for unlimited.
        horizon_years_tuple (tuple): Horizons to report.

    Returns:
        pd.DataFrame: Policy comparison of value and tax.

    Warning:
        Values are nominal and before any final redemption tax.
    """
    headline_row_list = []
    for scenario in build_default_scenario_list():
        headline_row_dict = {SCENARIO_COLUMN_STR: scenario.label_str}
        for horizon_years_int in horizon_years_tuple:
            simulation_result = run_scenario_result(
                fund_specification_list,
                scenario,
                horizon_years_int,
                interval_years_int,
                maximum_events_int,
            )
            headline_row_dict[f"T={horizon_years_int}Y value"] = (
                format_money_amount_str(
                    simulation_result.ending_value_float
                )
            )
            headline_row_dict[f"T={horizon_years_int}Y tax"] = (
                format_money_amount_str(
                    simulation_result.ending_tax_paid_float
                )
            )
        headline_row_list.append(headline_row_dict)
    return pd.DataFrame(headline_row_list)
