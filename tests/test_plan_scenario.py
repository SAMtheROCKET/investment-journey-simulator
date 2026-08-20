"""The shared scenario object and its single compile path."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from conftest import build_test_fund
from investment_journey_simulator.plan_policy import PlanPolicy
from investment_journey_simulator.plan_scenario import (
    UNSET_INFLATION_FLOAT,
    CompiledPlan,
    PlanScenario,
    PresentationPreferences,
    apply_regime_to_tax,
    build_scenario_fund_list,
    compile_scenario,
)
from investment_journey_simulator.regimes import REGIME_INDIA_STR
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_STR,
    EVENT_NOTE_STR,
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

PLAN_START_DATE: date = date(2026, 1, 1)

SOURCE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "investment_journey_simulator"
)

# The compiler itself, which is where engine settings are supposed
# to be built. Permanent.
COMPILER_FILE_SET: set = {"timeline.py"}

# Modules that build engine settings without going through
# PlanScenario. This set must only ever shrink; keeping it exact
# rather than generous is the point, since a spare entry would hide
# the very drift the ratchet exists to catch.
#
# `sidebar_controls.py` is a deliberate long-term member, not
# unfinished work. The Advanced Simulator keeps the classic
# dashboard's fourteen hundred lines of tested widgets and converts
# what they produce into a scenario via `scenario_adapter.py`.
# Rewriting those widgets to read and write scenario fields one by
# one would risk every behaviour they already get right, for
# nothing a reader would ever see.
LEGACY_SETTINGS_BUILDER_SET: set = {
    "studio_app.py",
    "sidebar_controls.py",
    "rebalancing_lab.py",
}


def build_scenario(*event_tuple: TimelineEvent) -> PlanScenario:
    """Build a scenario holding one equity fund and given events."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=20,
            event_list=list(event_tuple),
        ),
        fund_list=[build_test_fund(name_str="Equity")],
    )


# --- The single compile path --------------------------------------


def test_compiling_the_same_scenario_twice_agrees():
    """Two screens compiling one scenario cannot disagree."""
    scenario = build_scenario(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0)
    )
    assert compile_scenario(scenario) == compile_scenario(scenario)


def test_compile_returns_the_inflation_schedule_with_the_settings():
    """The schedule travels with the settings, not separately."""
    scenario = build_scenario(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0)
    )
    compiled = compile_scenario(scenario)
    assert isinstance(compiled, CompiledPlan)
    assert compiled.inflation_schedule_tuple == ()
    assert compiled.settings.horizon_years_int == 20


def test_compiling_does_not_mutate_the_scenario():
    """Compiling is free of side effects."""
    scenario = build_scenario(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0)
    )
    before_fund = replace(scenario.fund_list[0])
    compile_scenario(scenario)
    assert scenario.fund_list[0] == before_fund


def test_the_policy_reaches_the_compiled_settings():
    """A scenario's standing rules are honoured by the compiler."""
    scenario = replace(
        build_scenario(
            TimelineEvent(
                EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
            )
        ),
        policy=PlanPolicy(sip_at_month_start_bool=False),
    )
    compiled = compile_scenario(scenario)
    assert compiled.settings.sip_at_month_start_bool is False


# --- Who owns the money -------------------------------------------


def test_events_that_invest_take_ownership_of_the_amounts():
    """A rail plan strips the funds so no rupee is counted twice."""
    scenario = build_scenario(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0)
    )
    assert scenario.timeline_owns_amounts_bool is True
    fitted_list = build_scenario_fund_list(scenario)
    assert fitted_list[0].monthly_sip_float == 0.0
    assert fitted_list[0].initial_investment_float == 0.0


def test_a_lump_sum_alone_also_takes_ownership():
    """A plan whose only money is a lump sum still owns it."""
    scenario = build_scenario(
        TimelineEvent(EVENT_LUMPSUM_STR, date(2030, 6, 1), 500000.0)
    )
    assert scenario.timeline_owns_amounts_bool is True


def test_a_plan_with_no_money_events_leaves_the_funds_alone():
    """The classic dashboard's funds keep their own instalment."""
    scenario = build_scenario(
        TimelineEvent(EVENT_NOTE_STR, date(2030, 1, 1))
    )
    assert scenario.timeline_owns_amounts_bool is False
    fitted_list = build_scenario_fund_list(scenario)
    assert (
        fitted_list[0].monthly_sip_float
        == scenario.fund_list[0].monthly_sip_float
    )


def test_an_empty_plan_leaves_the_funds_alone():
    """No events at all is the classic dashboard's shape."""
    scenario = build_scenario()
    assert scenario.timeline_owns_amounts_bool is False
    assert build_scenario_fund_list(scenario) == scenario.fund_list


# --- Inflation ----------------------------------------------------


def test_inflation_falls_back_to_the_currency_default():
    """A sensible rate in Mumbai is not one in Tokyo."""
    rupee_scenario = build_scenario()
    yen_scenario = replace(
        rupee_scenario,
        presentation=PresentationPreferences(currency_code_str="JPY"),
    )
    assert (
        rupee_scenario.inflation_percent_float
        == UNSET_INFLATION_FLOAT
    )
    assert (
        rupee_scenario.resolved_inflation_percent_float
        != yen_scenario.resolved_inflation_percent_float
    )


@pytest.mark.parametrize("rate_float", [0.0, 3.5, 12.0])
def test_an_explicit_rate_is_always_honoured(rate_float):
    """Zero is a choice, not an absence of one."""
    scenario = replace(
        build_scenario(), inflation_percent_float=rate_float
    )
    assert (
        scenario.resolved_inflation_percent_float == rate_float
    )


# --- Presentation and regime --------------------------------------


def test_an_unknown_currency_falls_back_rather_than_raising():
    """A scenario saved with a retired currency still opens."""
    preferences = PresentationPreferences(
        currency_code_str="ZZZ", regime_code_str="ZZ"
    )
    assert preferences.currency is not None
    assert preferences.regime is not None


def test_adopting_a_regime_fills_in_its_opening_values():
    """Choosing a country fills the rates it publishes."""
    scenario = build_scenario()
    changed = apply_regime_to_tax(scenario, "GB")
    assert changed.presentation.regime_code_str == "GB"
    assert (
        changed.fund_list[0].long_term_tax_percent_float
        != scenario.fund_list[0].long_term_tax_percent_float
    )


def test_adopting_a_regime_does_not_mutate_the_original():
    """The scenario is frozen and its fund list is copied."""
    scenario = build_scenario()
    before_float = scenario.fund_list[0].long_term_tax_percent_float
    apply_regime_to_tax(scenario, "GB")
    assert (
        scenario.fund_list[0].long_term_tax_percent_float
        == before_float
    )


def test_india_remains_the_default_regime():
    """The one regime modelled in full is the one assumed."""
    assert (
        PresentationPreferences().regime_code_str
        == REGIME_INDIA_STR
    )


# --- The ratchet --------------------------------------------------


def find_settings_builder_file_list() -> list[str]:
    """Find modules constructing SimulationSettings by hand."""
    offender_list = []
    for file_path in sorted(SOURCE_DIRECTORY_PATH.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "SimulationSettings"
            ):
                offender_list.append(file_path.name)
                break
    return offender_list


def test_no_new_module_builds_settings_by_hand():
    """A new compile path is drift, and fails here immediately."""
    offender_set = set(find_settings_builder_file_list())
    permitted_set = (
        COMPILER_FILE_SET | LEGACY_SETTINGS_BUILDER_SET
    )
    assert offender_set <= permitted_set, (
        "new module builds SimulationSettings directly: "
        f"{sorted(offender_set - permitted_set)}"
    )


def test_the_legacy_allowlist_holds_no_dead_entries():
    """A stale entry would hide real drift, so it must not exist."""
    offender_set = set(find_settings_builder_file_list())
    assert offender_set >= LEGACY_SETTINGS_BUILDER_SET, (
        "allowlist names a module that no longer builds settings; "
        "delete it: "
        f"{sorted(LEGACY_SETTINGS_BUILDER_SET - offender_set)}"
    )
