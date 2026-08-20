"""Reading a scenario back out of the classic dashboard.

One property matters more than everything else here: taking engine
settings into a scenario and compiling them out again must return
the settings you started with. If that ever fails, the Advanced
Simulator and every other screen are looking at different plans.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    PAUSE_SCOPE_SIP_STR,
    REBALANCE_METHOD_PARTIAL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    REBALANCE_TRIGGER_CALENDAR_STR,
    STEPUP_MODE_GLOBAL_STR,
    TAX_FUNDING_OUTSIDE_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
)
from investment_journey_simulator.models import (
    InstalmentOverride,
    OneOffContribution,
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_FUNDS_STR,
    compile_scenario,
)
from investment_journey_simulator.scenario_adapter import (
    build_scenario_from_settings,
    encode_settings_dict,
)

PLAN_START_DATE: date = date(2026, 1, 1)


def build_rich_stepup() -> StepUpSettings:
    """A step-up with every field away from its default."""
    return StepUpSettings(
        mode_str=STEPUP_MODE_GLOBAL_STR,
        global_stepup_percent_float=10.0,
        interval_months_int=6,
        first_stepup_month_index_int=12,
        fixed_increment_amount_float=1500.0,
    )


def build_rich_withdrawal() -> WithdrawalSettings:
    """A percent-of-corpus withdrawal that also escalates."""
    return WithdrawalSettings(
        is_enabled_bool=True,
        start_month_index_int=180,
        mode_str=WITHDRAWAL_MODE_PERCENT_STR,
        fixed_amount_float=40000.0,
        portfolio_percent_float=4.0,
        annual_change_percent_float=5.0,
    )


def build_rich_rebalance() -> RebalanceSettings:
    """A calendar rule with a band, steering and outside funding."""
    return RebalanceSettings(
        is_enabled_bool=True,
        interval_months_int=12,
        method_str=REBALANCE_METHOD_PARTIAL_STR,
        target_mode_str=REBALANCE_TARGET_COLUMN_STR,
        tax_funding_str=TAX_FUNDING_OUTSIDE_STR,
        trigger_str=REBALANCE_TRIGGER_CALENDAR_STR,
        drift_band_percent_float=5.0,
        use_contribution_steering_bool=True,
    )


def build_rich_settings():
    """Engine settings exercising every branch of the adapter."""
    return replace(
        build_test_settings(),
        horizon_years_int=20,
        portfolio_start_date=PLAN_START_DATE,
        sip_at_month_start_bool=False,
        stepup=build_rich_stepup(),
        withdrawal=build_rich_withdrawal(),
        pauses=PauseSettings(
            pause_ranges_list=[
                PauseRange(
                    date(2029, 4, 1),
                    date(2030, 3, 1),
                    PAUSE_SCOPE_SIP_STR,
                )
            ]
        ),
        rebalance=build_rich_rebalance(),
        tax=TaxSettings(
            surcharge_percent_float=10.0,
            cess_percent_float=4.0,
            total_income_float=2500000.0,
        ),
        one_off_contributions_list=[
            OneOffContribution(96, 500000.0)
        ],
        instalment_override_list=[
            InstalmentOverride(36, 30000.0)
        ],
    )


def build_scenario_from(settings):
    """Run the adapter on one settings tree."""
    return build_scenario_from_settings(
        settings,
        [build_test_fund(name_str="Equity")],
        6.0,
        "INR",
    )


# --- The property that matters ------------------------------------


def test_settings_survive_the_trip_through_a_scenario():
    """Take settings in, compile them out, get them back.

    This is the guarantee that the Advanced Simulator and every
    other screen are looking at the same plan.
    """
    settings = build_rich_settings()
    compiled = compile_scenario(build_scenario_from(settings))
    assert compiled.settings == settings


@pytest.mark.parametrize(
    "field_name_str",
    [
        "horizon_years_int",
        "portfolio_start_date",
        "sip_at_month_start_bool",
        "stepup",
        "withdrawal",
        "rebalance",
        "tax",
    ],
)
def test_each_part_of_the_settings_survives(field_name_str):
    """Named field by field, so a failure says which part broke."""
    settings = build_rich_settings()
    compiled = compile_scenario(build_scenario_from(settings))
    assert getattr(compiled.settings, field_name_str) == getattr(
        settings, field_name_str
    )


def test_plain_settings_survive_too():
    """The default plan is the one most readers will have."""
    settings = build_test_settings()
    compiled = compile_scenario(build_scenario_from(settings))
    assert compiled.settings == settings


# --- What the conversion produces ---------------------------------


def test_the_funds_keep_their_instalment():
    """A dashboard plan's money lives on its funds, not its events."""
    scenario = build_scenario_from(build_rich_settings())
    assert scenario.amounts_source_str == AMOUNTS_SOURCE_FUNDS_STR
    assert (
        compile_scenario(scenario).fund_list[0].monthly_sip_float
        > 0.0
    )


def test_the_dated_parts_become_events():
    """Which is what makes them visible on the rail."""
    scenario = build_scenario_from(build_rich_settings())
    assert len(scenario.plan.event_list) >= 5


def test_the_currency_and_inflation_are_carried():
    """Neither is expressible in engine settings alone."""
    scenario = build_scenario_from(build_rich_settings())
    assert scenario.presentation.currency_code_str == "INR"
    assert scenario.inflation_percent_float == 6.0


def test_a_named_plan_keeps_its_name():
    """Comparisons need something to call each journey."""
    scenario = build_scenario_from_settings(
        build_test_settings(),
        [build_test_fund(name_str="Equity")],
        6.0,
        "INR",
        "Retire at fifty",
    )
    assert scenario.name_str == "Retire at fifty"


# --- Encoding -----------------------------------------------------


def test_pause_dates_encode_as_strings():
    """A date two levels down is the one asdict cannot handle."""
    settings_dict = encode_settings_dict(build_rich_settings())
    range_dict = settings_dict["pauses"]["pause_ranges_list"][0]
    assert range_dict["start_date"] == "2029-04-01"
    assert range_dict["end_date"] == "2030-03-01"


def test_the_start_date_encodes_as_a_string():
    """The migration parses it back from ISO."""
    settings_dict = encode_settings_dict(build_rich_settings())
    assert settings_dict["portfolio_start_date"] == "2026-01-01"


def test_encoding_does_not_mutate_the_settings():
    """The caller's settings are theirs."""
    settings = build_rich_settings()
    encode_settings_dict(settings)
    assert settings == build_rich_settings()
