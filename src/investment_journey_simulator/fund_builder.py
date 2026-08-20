"""Translation between the fund editor table and fund objects."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pandas as pd

from investment_journey_simulator.asset_presets import (
    USE_SLAB_RATE_FLOAT,
    resolve_preset,
)
from investment_journey_simulator.constants import (
    COLUMN_EXEMPTION_AMOUNT_STR,
    COLUMN_EXEMPTION_SCOPE_STR,
    COLUMN_EXIT_LOAD_MONTHS_STR,
    COLUMN_EXIT_LOAD_STR,
    COLUMN_EXPENSE_STR,
    COLUMN_FUND_NAME_STR,
    COLUMN_FUND_START_STR,
    COLUMN_FUND_STEPUP_STR,
    COLUMN_GROSS_RETURN_STR,
    COLUMN_INITIAL_INVESTMENT_STR,
    COLUMN_LONG_TERM_MONTHS_STR,
    COLUMN_LONG_TERM_TAX_STR,
    COLUMN_MONTHLY_SIP_STR,
    COLUMN_OVERRIDE_PRESET_STR,
    COLUMN_PRESET_STR,
    COLUMN_SHORT_TERM_TAX_STR,
    COLUMN_TARGET_ALLOCATION_STR,
    COLUMN_TRANSACTION_TAX_STR,
    EQUITY_EXEMPTION_AMOUNT_FLOAT,
    EQUITY_EXEMPTION_SCOPE_STR,
    EQUITY_LONG_TERM_MONTHS_INT,
    EQUITY_LONG_TERM_PERCENT_FLOAT,
    EQUITY_REDEMPTION_STT_PERCENT_FLOAT,
    EQUITY_SHORT_TERM_PERCENT_FLOAT,
    EXPENSE_MODEL_SIMPLE_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.models import FundConfiguration

DEFAULT_FUND_NAMES_TUPLE: tuple = ("Fund-A", "Fund-B")
DEFAULT_MONTHLY_SIP_FLOAT: float = 2000.0
DEFAULT_GROSS_RETURN_PERCENT_TUPLE: tuple = (12.0, 9.0)
DEFAULT_EXPENSE_PERCENT_FLOAT: float = 0.20
DEFAULT_TARGET_ALLOCATION_FLOAT: float = 50.0
NEW_FUND_MONTHLY_SIP_FLOAT: float = 1000.0
NEW_FUND_EXPENSE_PERCENT_FLOAT: float = 0.50
NEW_FUND_GROSS_RETURN_FLOAT: float = 12.0
FALLBACK_FUND_NAME_STR: str = "Unnamed MF"


def build_fund_row_dict(
    fund_name_str: str,
    monthly_sip_float: float,
    gross_return_percent_float: float,
    expense_percent_float: float,
    start_date: date,
    target_allocation_percent_float: float,
    initial_investment_float: float = 0.0,
) -> dict:
    """Build one editor row pre-filled with equity tax defaults.

    Brief:
        Single place that defines the column set of the fund table
        so every caller stays schema compatible.

    Arguments:
        fund_name_str (str): Display name of the fund.
        monthly_sip_float (float): Instalment per month.
        gross_return_percent_float (float): Gross annual return.
        expense_percent_float (float): Annual expense ratio.
        start_date (date): First month this fund invests.
        target_allocation_percent_float (float): Target weight.
        initial_investment_float (float): Opening lump sum.

    Returns:
        dict: Row mapping column labels to default values.

    Warning:
        Tax fields follow the equity preset until overridden.
    """
    return {
        COLUMN_FUND_NAME_STR: fund_name_str,
        COLUMN_PRESET_STR: PRESET_EQUITY_STR,
        COLUMN_OVERRIDE_PRESET_STR: False,
        COLUMN_MONTHLY_SIP_STR: monthly_sip_float,
        COLUMN_INITIAL_INVESTMENT_STR: initial_investment_float,
        COLUMN_FUND_STEPUP_STR: 0.0,
        COLUMN_GROSS_RETURN_STR: gross_return_percent_float,
        COLUMN_EXPENSE_STR: expense_percent_float,
        COLUMN_FUND_START_STR: start_date,
        COLUMN_TARGET_ALLOCATION_STR: (
            target_allocation_percent_float
        ),
        **_build_default_tax_columns_dict(),
    }


def _build_default_tax_columns_dict() -> dict:
    """Build the equity tax and charge defaults of a new row.

    Brief:
        Applied to every new fund until the preset is changed.

    Arguments:
        None.

    Returns:
        dict: Tax and charge columns of one editor row.

    Warning:
        Exit load defaults to zero; index funds usually have none.
    """
    return {
        COLUMN_SHORT_TERM_TAX_STR: EQUITY_SHORT_TERM_PERCENT_FLOAT,
        COLUMN_LONG_TERM_TAX_STR: EQUITY_LONG_TERM_PERCENT_FLOAT,
        COLUMN_LONG_TERM_MONTHS_STR: EQUITY_LONG_TERM_MONTHS_INT,
        COLUMN_EXEMPTION_AMOUNT_STR: EQUITY_EXEMPTION_AMOUNT_FLOAT,
        COLUMN_EXEMPTION_SCOPE_STR: EQUITY_EXEMPTION_SCOPE_STR,
        COLUMN_EXIT_LOAD_STR: 0.0,
        COLUMN_EXIT_LOAD_MONTHS_STR: 0,
        COLUMN_TRANSACTION_TAX_STR: (
            EQUITY_REDEMPTION_STT_PERCENT_FLOAT
        ),
    }


def build_default_fund_dataframe(
    portfolio_start_date: date,
) -> pd.DataFrame:
    """Build the two-fund table shown on a first visit.

    Brief:
        A conservative and an aggressive fund make the effect of
        drift and rebalancing visible immediately.

    Arguments:
        portfolio_start_date (date): First simulated month.

    Returns:
        pd.DataFrame: Editable starter fund table.

    Warning:
        Values are illustrative and must be replaced with the real
        factsheet numbers before planning.
    """
    starter_row_list = [
        build_fund_row_dict(
            fund_name_str=fund_name_str,
            monthly_sip_float=DEFAULT_MONTHLY_SIP_FLOAT,
            gross_return_percent_float=gross_return_percent_float,
            expense_percent_float=DEFAULT_EXPENSE_PERCENT_FLOAT,
            start_date=portfolio_start_date,
            target_allocation_percent_float=(
                DEFAULT_TARGET_ALLOCATION_FLOAT
            ),
        )
        for fund_name_str, gross_return_percent_float in zip(
            DEFAULT_FUND_NAMES_TUPLE,
            DEFAULT_GROSS_RETURN_PERCENT_TUPLE,
            strict=True,
        )
    ]
    return pd.DataFrame(starter_row_list)


def build_additional_fund_row_dict(
    existing_fund_count_int: int,
    portfolio_start_date: date,
) -> dict:
    """Build the row appended when a new fund is added.

    Brief:
        Names the fund after its position so the table never has
        two blank rows with the same label.

    Arguments:
        existing_fund_count_int (int): Rows already in the table.
        portfolio_start_date (date): First simulated month.

    Returns:
        dict: Row mapping column labels to default values.

    Warning:
        The new fund starts with a zero target weight so it is
        ignored by rebalancing until a weight is typed in.
    """
    return build_fund_row_dict(
        fund_name_str=f"MF-{existing_fund_count_int + 1}",
        monthly_sip_float=NEW_FUND_MONTHLY_SIP_FLOAT,
        gross_return_percent_float=NEW_FUND_GROSS_RETURN_FLOAT,
        expense_percent_float=NEW_FUND_EXPENSE_PERCENT_FLOAT,
        start_date=portfolio_start_date,
        target_allocation_percent_float=0.0,
    )


def apply_tax_preset_to_row(
    fund_row: pd.Series,
    slab_rate_percent_float: float,
) -> pd.Series:
    """Overwrite the tax columns of one row from its preset.

    Brief:
        Presets keep the common cases correct while the override
        flag lets an expert type custom rates.

    Arguments:
        fund_row (pd.Series): Row of the fund editor table.
        slab_rate_percent_float (float): Investor slab rate.

    Returns:
        pd.Series: Row with preset-driven tax columns.

    Warning:
        Rows flagged as overridden are returned untouched.
    """
    if bool(fund_row.get(COLUMN_OVERRIDE_PRESET_STR, False)):
        return fund_row
    preset = resolve_preset(
        str(fund_row.get(COLUMN_PRESET_STR, PRESET_EQUITY_STR))
    )
    if preset is None:
        return fund_row
    short_term_float = preset.short_term_percent_float
    if short_term_float == USE_SLAB_RATE_FLOAT:
        short_term_float = float(slab_rate_percent_float)
    return _write_tax_columns(
        fund_row,
        short_term_float,
        preset.long_term_percent_float,
        preset.long_term_months_int,
        preset.exemption_amount_float,
        preset.exemption_scope_str,
    )


def _write_tax_columns(
    fund_row: pd.Series,
    short_term_percent_float: float,
    long_term_percent_float: float,
    long_term_months_int: int,
    exemption_amount_float: float,
    exemption_scope_str: str,
) -> pd.Series:
    """Write one preset's tax parameters into a table row.

    Brief:
        Shared writer so equity and debt presets stay symmetric.

    Arguments:
        fund_row (pd.Series): Row of the fund editor table.
        short_term_percent_float (float): Short term tax rate.
        long_term_percent_float (float): Long term tax rate.
        long_term_months_int (int): Long term holding threshold.
        exemption_amount_float (float): Yearly exemption cap.
        exemption_scope_str (str): Gains the exemption covers.

    Returns:
        pd.Series: The same row, mutated in place.

    Warning:
        Existing values in these columns are overwritten.
    """
    fund_row[COLUMN_SHORT_TERM_TAX_STR] = short_term_percent_float
    fund_row[COLUMN_LONG_TERM_TAX_STR] = long_term_percent_float
    fund_row[COLUMN_LONG_TERM_MONTHS_STR] = long_term_months_int
    fund_row[COLUMN_EXEMPTION_AMOUNT_STR] = exemption_amount_float
    fund_row[COLUMN_EXEMPTION_SCOPE_STR] = exemption_scope_str
    return fund_row


def apply_tax_presets_to_dataframe(
    fund_dataframe: pd.DataFrame,
    slab_rate_percent_float: float,
) -> pd.DataFrame:
    """Apply the tax presets to every row of the fund table.

    Brief:
        Runs before the table is rendered and again before the
        simulation so edits can never bypass the presets.

    Arguments:
        fund_dataframe (pd.DataFrame): Fund editor table.
        slab_rate_percent_float (float): Investor slab rate.

    Returns:
        pd.DataFrame: Copy with preset-driven tax columns.

    Warning:
        An empty table is returned unchanged.
    """
    if fund_dataframe.empty:
        return fund_dataframe.copy()
    return fund_dataframe.apply(
        lambda fund_row: apply_tax_preset_to_row(
            fund_row, slab_rate_percent_float
        ),
        axis=1,
    )


def read_float_value(cell_value: Any, fallback_float: float) -> float:
    """Read a numeric cell, falling back on blanks and errors.

    Brief:
        Editor cells can hold blanks or text, so every read must
        be defensive.

    Arguments:
        cell_value (Any): Raw cell value from the table.
        fallback_float (float): Value used when parsing fails.

    Returns:
        float: Parsed value or the supplied fallback.

    Warning:
        Silently swallows malformed input.
    """
    try:
        if cell_value is None or pd.isna(cell_value):
            return float(fallback_float)
        return float(cell_value)
    except (TypeError, ValueError):
        return float(fallback_float)


def read_date_value(cell_value: Any, fallback_date: date) -> date:
    """Read a date cell, falling back on blanks and errors.

    Brief:
        The editor may hand back timestamps, dates or blanks.

    Arguments:
        cell_value (Any): Raw cell value from the table.
        fallback_date (date): Value used when parsing fails.

    Returns:
        date: Parsed date or the supplied fallback.

    Warning:
        Any time component is discarded.
    """
    if isinstance(cell_value, pd.Timestamp):
        return cell_value.date()
    if isinstance(cell_value, date):
        return cell_value
    return fallback_date


def build_fund_configurations_list(
    fund_dataframe: pd.DataFrame,
    portfolio_start_date: date,
    expense_model_str: str = EXPENSE_MODEL_SIMPLE_STR,
) -> list[FundConfiguration]:
    """Convert the editor table into simulator fund objects.

    Brief:
        Boundary between the user interface and the engine, where
        every cell is validated once and typed.

    Arguments:
        fund_dataframe (pd.DataFrame): Fund editor table.
        portfolio_start_date (date): First simulated month.

    Returns:
        List[FundConfiguration]: One object per table row.

    Warning:
        Blank names become a placeholder label, so duplicate blank
        rows will share tax exemption bookkeeping.
    """
    fund_configurations_list = [
        build_single_fund_configuration(
            fund_row, portfolio_start_date, expense_model_str
        )
        for _, fund_row in fund_dataframe.iterrows()
    ]
    return deduplicate_fund_names_list(fund_configurations_list)


def deduplicate_fund_names_list(
    fund_configurations_list: list[FundConfiguration],
) -> list[FundConfiguration]:
    """Make every fund name unique within the portfolio.

    Brief:
        Fund names key the holdings, the target weights and the
        exemption ledger, so a duplicate would silently merge two
        different funds into one.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds
            possibly sharing a name.

    Returns:
        List[FundConfiguration]: Funds with unique names.

    Warning:
        Renaming is silent; surface a warning in the interface so
        the user notices the change.
    """
    seen_count_dict: dict = {}
    unique_fund_list: list[FundConfiguration] = []
    for fund_configuration in fund_configurations_list:
        base_name_str = fund_configuration.name_str
        seen_count_int = seen_count_dict.get(base_name_str, 0)
        seen_count_dict[base_name_str] = seen_count_int + 1
        if seen_count_int == 0:
            unique_fund_list.append(fund_configuration)
            continue
        unique_fund_list.append(
            replace(
                fund_configuration,
                name_str=(
                    f"{base_name_str} ({seen_count_int + 1})"
                ),
            )
        )
    return unique_fund_list


def build_single_fund_configuration(
    fund_row: pd.Series,
    portfolio_start_date: date,
    expense_model_str: str = EXPENSE_MODEL_SIMPLE_STR,
) -> FundConfiguration:
    """Convert one editor row into a simulator fund object.

    Brief:
        Reads every cell defensively so that partially filled rows
        still produce a usable fund.

    Arguments:
        fund_row (pd.Series): Row of the fund editor table.
        portfolio_start_date (date): First simulated month.

    Returns:
        FundConfiguration: Typed fund definition.

    Warning:
        Missing numeric cells default to zero, which silently
        disables that fund's contribution or tax.
    """
    return FundConfiguration(
        **_read_plan_fields_dict(fund_row, portfolio_start_date),
        **_read_tax_fields_dict(fund_row),
        expense_model_str=expense_model_str,
    )


def _read_plan_fields_dict(
    fund_row: pd.Series,
    portfolio_start_date: date,
) -> dict:
    """Read the investment fields of one editor row.

    Brief:
        Covers naming, instalment, escalation, returns and the
        rebalancing target of a single fund.

    Arguments:
        fund_row (pd.Series): Row of the fund editor table.
        portfolio_start_date (date): First simulated month.

    Returns:
        dict: Keyword arguments for the fund configuration.

    Warning:
        Blank names collapse into one placeholder label.
    """
    return {
        "name_str": str(
            fund_row.get(COLUMN_FUND_NAME_STR, "")
        ).strip() or FALLBACK_FUND_NAME_STR,
        "preset_str": str(
            fund_row.get(COLUMN_PRESET_STR, PRESET_EQUITY_STR)
        ),
        "monthly_sip_float": read_float_value(
            fund_row.get(COLUMN_MONTHLY_SIP_STR), 0.0
        ),
        "stepup_percent_float": read_float_value(
            fund_row.get(COLUMN_FUND_STEPUP_STR), 0.0
        ),
        "gross_return_percent_float": read_float_value(
            fund_row.get(COLUMN_GROSS_RETURN_STR), 0.0
        ),
        "expense_percent_float": read_float_value(
            fund_row.get(COLUMN_EXPENSE_STR), 0.0
        ),
        "start_date": read_date_value(
            fund_row.get(COLUMN_FUND_START_STR),
            portfolio_start_date,
        ),
        "target_allocation_percent_float": read_float_value(
            fund_row.get(COLUMN_TARGET_ALLOCATION_STR), 0.0
        ),
        "initial_investment_float": read_float_value(
            fund_row.get(COLUMN_INITIAL_INVESTMENT_STR), 0.0
        ),
    }


def _read_tax_fields_dict(fund_row: pd.Series) -> dict:
    """Read the taxation fields of one editor row.

    Brief:
        Covers both rates, the holding threshold, the exemption
        and the debt style always-short-term flag.

    Arguments:
        fund_row (pd.Series): Row of the fund editor table.

    Returns:
        dict: Keyword arguments for the fund configuration.

    Warning:
        Missing rates default to zero, which models a tax-free
        fund rather than raising an error.
    """
    preset_str = str(
        fund_row.get(COLUMN_PRESET_STR, PRESET_EQUITY_STR)
    )
    return {
        "short_term_tax_percent_float": read_float_value(
            fund_row.get(COLUMN_SHORT_TERM_TAX_STR), 0.0
        ),
        "long_term_tax_percent_float": read_float_value(
            fund_row.get(COLUMN_LONG_TERM_TAX_STR), 0.0
        ),
        "long_term_threshold_months_int": int(
            read_float_value(
                fund_row.get(COLUMN_LONG_TERM_MONTHS_STR),
                EQUITY_LONG_TERM_MONTHS_INT,
            )
        ),
        "exemption_amount_float": read_float_value(
            fund_row.get(COLUMN_EXEMPTION_AMOUNT_STR), 0.0
        ),
        "exemption_scope_str": str(
            fund_row.get(
                COLUMN_EXEMPTION_SCOPE_STR,
                EQUITY_EXEMPTION_SCOPE_STR,
            )
        ),
        "is_always_short_term_bool": _read_always_short_bool(
            preset_str
        ),
        **_read_charge_fields_dict(fund_row),
    }


def _read_charge_fields_dict(fund_row: pd.Series) -> dict:
    """Read the exit load and transaction tax of one row.

    Brief:
        Charges are not tax; they are deducted from redemption
        proceeds and reported separately.

    Arguments:
        fund_row (pd.Series): Row of the fund editor table.

    Returns:
        dict: Keyword arguments for the fund configuration.

    Warning:
        Missing values default to zero, meaning no charge.
    """
    return {
        "exit_load_percent_float": read_float_value(
            fund_row.get(COLUMN_EXIT_LOAD_STR), 0.0
        ),
        "exit_load_within_months_int": int(
            read_float_value(
                fund_row.get(COLUMN_EXIT_LOAD_MONTHS_STR), 0.0
            )
        ),
        "transaction_tax_percent_float": read_float_value(
            fund_row.get(COLUMN_TRANSACTION_TAX_STR), 0.0
        ),
    }


def _read_always_short_bool(preset_str: str) -> bool:
    """Whether this preset is taxed at slab whatever the wait.

    Brief:
        Used to be a comparison against the debt preset alone.
        Deposits behave the same way, and any later preset might,
        so the answer belongs to the preset rather than to a list
        of names kept here.

    Arguments:
        preset_str (str): Preset name from the editor row.

    Returns:
        bool: True when no long-term rate ever applies.

    Warning:
        A Custom row answers False, because its holding-period
        threshold is whatever the reader typed.
    """
    preset = resolve_preset(preset_str)
    return bool(preset and preset.is_always_short_term_bool)
