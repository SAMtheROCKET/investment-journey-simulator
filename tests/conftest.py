"""Shared fixtures and builders for the simulator test suite."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

SOURCE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent / "src"
)
if str(SOURCE_DIRECTORY_PATH) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY_PATH))

from investment_journey_simulator.constants import (  # noqa: E402
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.models import (  # noqa: E402
    FundConfiguration,
    PauseSettings,
    RebalanceSettings,
    SimulationSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from reference_data import (  # noqa: E402
    STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT,
    STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT,
    STATUTORY_EQUITY_THRESHOLD_MONTHS_INT,
)

DEFAULT_START_DATE: date = date(2026, 1, 1)
STATUTORY_RATE_FIELDS_DICT: dict = {
    "short_term_tax_percent_float": (
        STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT
    ),
    "long_term_tax_percent_float": (
        STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT
    ),
}
MONEY_TOLERANCE_FLOAT: float = 1e-6
LOOSE_MONEY_TOLERANCE_FLOAT: float = 0.01


DEFAULT_FUND_FIELD_DICT: dict = {
    "preset_str": PRESET_EQUITY_STR,
    "stepup_percent_float": 0.0,
    "target_allocation_percent_float": 50.0,
    "exemption_amount_float": 0.0,
    "exemption_scope_str": EXEMPTION_SCOPE_LONG_TERM_STR,
    "is_always_short_term_bool": False,
    "expense_model_str": EXPENSE_MODEL_SIMPLE_STR,
    "initial_investment_float": 0.0,
    "long_term_threshold_months_int": (
        STATUTORY_EQUITY_THRESHOLD_MONTHS_INT
    ),
    **STATUTORY_RATE_FIELDS_DICT,
}


def build_test_fund(
    name_str: str = "Fund-A",
    monthly_sip_float: float = 1000.0,
    gross_return_percent_float: float = 12.0,
    expense_percent_float: float = 0.0,
    start_date: date = DEFAULT_START_DATE,
    **override_field_dict,
) -> FundConfiguration:
    """Build a fund with tax-free defaults for isolated testing.

    Brief:
        The exemption defaults to zero so growth tests are not
        altered by tax shelter; tax tests opt in by overriding.

    Arguments:
        name_str (str): Fund name.
        monthly_sip_float (float): Instalment per month.
        gross_return_percent_float (float): Gross annual return.
        expense_percent_float (float): Annual expense ratio.
        start_date (date): First month this fund invests.
        override_field_dict: Any other fund field to override.

    Returns:
        FundConfiguration: Fund ready for the engine.

    Warning:
        Statutory rates apply, but the exemption is off.
    """
    field_dict = dict(DEFAULT_FUND_FIELD_DICT)
    field_dict.update(override_field_dict)
    return FundConfiguration(
        name_str=name_str,
        monthly_sip_float=monthly_sip_float,
        gross_return_percent_float=gross_return_percent_float,
        expense_percent_float=expense_percent_float,
        start_date=start_date,
        **field_dict,
    )


def build_test_settings(
    horizon_years_int: int = 10,
    sip_at_month_start_bool: bool = True,
    stepup: StepUpSettings = None,
    withdrawal: WithdrawalSettings = None,
    pauses: PauseSettings = None,
    rebalance: RebalanceSettings = None,
    tax: TaxSettings = None,
    portfolio_start_date: date = DEFAULT_START_DATE,
    one_off_contributions_list: list = None,
    instalment_override_list: list = None,
) -> SimulationSettings:
    """Build settings with every optional feature switched off.

    Brief:
        Each test switches on exactly the feature it exercises, so
        failures point at one mechanism only.

    Arguments:
        horizon_years_int (int): Years to simulate.
        sip_at_month_start_bool (bool): Instalment timing.
        stepup (StepUpSettings): Escalation rules.
        withdrawal (WithdrawalSettings): Exit rules.
        pauses (PauseSettings): Pause rules.
        rebalance (RebalanceSettings): Rebalancing rules.
        tax (TaxSettings): Portfolio tax rules.
        portfolio_start_date (date): First simulated month.
        one_off_contributions_list (list): Dated extra investments.
        instalment_override_list (list): Dated instalment changes.

    Returns:
        SimulationSettings: Settings for one run.

    Warning:
        Defaults deliberately disable every optional feature.
    """
    return SimulationSettings(
        horizon_years_int=horizon_years_int,
        portfolio_start_date=portfolio_start_date,
        sip_at_month_start_bool=sip_at_month_start_bool,
        stepup=stepup or StepUpSettings(),
        withdrawal=withdrawal or WithdrawalSettings(),
        pauses=pauses or PauseSettings(),
        rebalance=rebalance or RebalanceSettings(),
        tax=tax or TaxSettings(),
        one_off_contributions_list=(
            one_off_contributions_list or []
        ),
        instalment_override_list=instalment_override_list or [],
    )


@pytest.fixture
def single_equity_fund_list() -> list[FundConfiguration]:
    """One tax-free equity fund investing a thousand a month.

    Brief:
        The baseline used by every growth and timing test.

    Arguments:
        None.

    Returns:
        List[FundConfiguration]: One-fund portfolio.

    Warning:
        Carries no exemption, so gains are fully taxable.
    """
    return [build_test_fund()]


@pytest.fixture
def two_fund_list() -> list[FundConfiguration]:
    """Two funds with different returns and an equal split.

    Brief:
        Used by drift, rebalancing and allocation tests.

    Arguments:
        None.

    Returns:
        List[FundConfiguration]: Two-fund portfolio.

    Warning:
        Returns differ, so the weights drift on purpose.
    """
    return [
        build_test_fund(
            "Fund-A", 1000.0, 14.0,
            target_allocation_percent_float=50.0,
        ),
        build_test_fund(
            "Fund-B", 1000.0, 8.0,
            target_allocation_percent_float=50.0,
        ),
    ]


def build_launch_script_str(module_name_str: str) -> str:
    """Build the script that boots one front end, headlessly.

    The three original launcher files were deleted when the portal
    became the only way in, so the suite builds the same four lines
    they contained rather than reading them off disk. Nothing about
    what these tests exercise changed; only where the entry point
    comes from.

    Arguments:
        module_name_str (str): Module whose `main` to run.

    Returns:
        str: A script `AppTest.from_string` can execute.
    """
    package_str = "investment_journey_simulator"
    line_list = [
        "import sys",
        f'sys.path.insert(0, r"{SOURCE_DIRECTORY_PATH}")',
        f"from {package_str}.{module_name_str} import main",
        "main()",
    ]
    return chr(10).join(line_list) + chr(10)
