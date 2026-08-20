"""Saving, reopening and migrating a whole scenario.

The migration tests matter more than the round-trip ones. A plan
someone saved a year ago is the only thing in this program a reader
cannot regenerate, so "it probably still opens" is not good enough.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from conftest import build_test_fund
from investment_journey_simulator.constants import (
    REBALANCE_TRIGGER_CALENDAR_STR,
    TAX_FUNDING_OUTSIDE_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
)
from investment_journey_simulator.plan_policy import PlanPolicy
from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_FUNDS_STR,
    PlanScenario,
    PresentationPreferences,
    compile_scenario,
)
from investment_journey_simulator.scenario_io import (
    SCENARIO_VERSION_STR,
    build_scenario_json_bytes,
    decode_scenario,
    encode_scenario_dict,
    normalise_scenario,
    parse_scenario_bytes,
)
from investment_journey_simulator.scenario_migration import (
    migrate_scenario_dict,
)
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_LUMPSUM_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
)

FIXTURE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent / "fixtures"
)
LEGACY_FIXTURE_PATH: Path = (
    FIXTURE_DIRECTORY_PATH / "scenario_v2_1.json"
)
PLAN_START_DATE: date = date(2026, 1, 1)


def build_rich_scenario() -> PlanScenario:
    """Build a scenario touching every part of the format."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=25,
            event_list=[
                TimelineEvent(
                    "Start investing", date(2026, 1, 1), 25000.0
                ),
                TimelineEvent(
                    EVENT_STEPUP_STR,
                    date(2027, 1, 1),
                    percent_float=10.0,
                ),
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    date(2031, 6, 1),
                    500000.0,
                    fund_name_str="Equity",
                ),
                TimelineEvent(
                    EVENT_PAUSE_STR,
                    date(2029, 4, 1),
                    note_str="wedding",
                ),
                TimelineEvent(EVENT_RESUME_STR, date(2030, 4, 1)),
            ],
        ),
        fund_list=[
            build_test_fund(name_str="Equity"),
            build_test_fund(name_str="Debt"),
        ],
        policy=PlanPolicy(
            sip_at_month_start_bool=False,
            stepup_interval_months_int=6,
            withdrawal_mode_str=WITHDRAWAL_MODE_PERCENT_STR,
            withdrawal_portfolio_percent_float=4.0,
            withdrawal_schedule_tuple=(1000.0, 2000.0),
            rebalance_drift_band_percent_float=5.0,
            default_fund_name_str="Equity",
        ),
        presentation=PresentationPreferences(
            currency_code_str="GBP",
            regime_code_str="GB",
            is_dark_mode_bool=True,
        ),
        inflation_percent_float=3.5,
        name_str="Retire at fifty",
    )


# --- Round trip ---------------------------------------------------


def test_a_scenario_survives_a_round_trip():
    """Encode then decode returns the saved form of the object."""
    scenario = build_rich_scenario()
    assert decode_scenario(
        encode_scenario_dict(scenario)
    ) == normalise_scenario(scenario)


def test_a_scenario_survives_the_bytes_round_trip():
    """The same holds through actual JSON bytes."""
    scenario = build_rich_scenario()
    reopened = parse_scenario_bytes(
        build_scenario_json_bytes(scenario)
    )
    assert reopened == normalise_scenario(scenario)


def test_normalising_cannot_change_what_a_plan_is_worth():
    """The licence to reorder on save rests entirely on this.

    If sorting the events could alter the compiled settings, then
    saving a plan would change it, and every round-trip guarantee
    above would be worthless.
    """
    scenario = build_rich_scenario()
    assert compile_scenario(
        normalise_scenario(scenario)
    ) == compile_scenario(scenario)


def test_normalising_is_idempotent():
    """A saved plan is already in its saved form."""
    once = normalise_scenario(build_rich_scenario())
    assert normalise_scenario(once) == once


def test_saving_the_same_plan_twice_gives_identical_bytes():
    """Events are ordered on write, so saves are diffable."""
    scenario = build_rich_scenario()
    shuffled = replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=list(reversed(scenario.plan.event_list)),
        ),
    )
    assert build_scenario_json_bytes(
        scenario
    ) == build_scenario_json_bytes(shuffled)


def test_an_empty_scenario_round_trips():
    """A plan with nothing in it is still a valid plan."""
    scenario = PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE, horizon_years_int=10
        )
    )
    assert decode_scenario(encode_scenario_dict(scenario)) == (
        scenario
    )


def test_tuples_survive_as_tuples():
    """A list where a tuple belongs would break hashing later."""
    scenario = build_rich_scenario()
    reopened = decode_scenario(encode_scenario_dict(scenario))
    assert isinstance(
        reopened.policy.withdrawal_schedule_tuple, tuple
    )
    assert isinstance(reopened.tax.income_by_year_tuple, tuple)


def test_a_document_from_a_later_build_still_opens():
    """An unknown field is dropped, not fatal."""
    scenario_dict = encode_scenario_dict(build_rich_scenario())
    scenario_dict["policy"]["invented_future_field"] = 42
    scenario_dict["a_whole_new_section"] = {"x": 1}
    assert decode_scenario(scenario_dict).policy is not None


def test_a_file_that_is_not_a_scenario_is_rejected():
    """Failing loudly beats opening a meaningless plan."""
    with pytest.raises(ValueError):
        parse_scenario_bytes(b'{"something": "else"}')


# --- Compile determinism ------------------------------------------


def test_a_reopened_scenario_compiles_identically():
    """Saving and reopening cannot change what a plan is worth."""
    scenario = build_rich_scenario()
    reopened = parse_scenario_bytes(
        build_scenario_json_bytes(scenario)
    )
    assert compile_scenario(reopened) == compile_scenario(scenario)


# --- Migration from version 2.1 -----------------------------------


def load_legacy_dict() -> dict:
    """Read the frozen version 2.1 fixture."""
    return json.loads(
        LEGACY_FIXTURE_PATH.read_text(encoding="utf-8")
    )


def test_the_legacy_fixture_exists_and_is_version_two():
    """The fixture is the whole point; guard it against deletion."""
    assert LEGACY_FIXTURE_PATH.exists()
    assert load_legacy_dict()["scenario_version"].startswith("2")


def test_the_fixture_is_keyed_the_way_the_editor_saves():
    """The fixture must be a real save, not a hand-written one.

    Version 2.1 stored the fund table with `to_dict("records")`,
    so its keys are the editor's column *captions*, not dataclass
    field names. A fixture written by hand in field-name form
    passes every migration test while proving nothing - which is
    exactly what happened, and hid a crash on every genuinely
    saved file.
    """
    fund_dict = load_legacy_dict()["funds"][0]
    assert "MF Name" in fund_dict
    assert "SIP / month" in fund_dict
    assert "name_str" not in fund_dict


def test_a_legacy_file_opens():
    """The headline promise: an old saved plan still loads."""
    scenario = decode_scenario(load_legacy_dict())
    assert scenario.plan.horizon_years_int == 20
    assert scenario.plan.start_date == PLAN_START_DATE
    assert [fund.name_str for fund in scenario.fund_list] == [
        "Fund-A",
        "Fund-B",
    ]


def test_migration_marks_the_document_as_current():
    """Reopening upgrades the version rather than leaving it."""
    upgraded = migrate_scenario_dict(load_legacy_dict())
    assert upgraded["scenario_version"] == SCENARIO_VERSION_STR


def test_the_funds_keep_their_own_instalment():
    """A dashboard plan's money stays on its funds.

    This is the failure the explicit amounts source exists to
    prevent: the legacy file also carries a dated lump sum, and
    inferring ownership from that would silently delete the SIP.
    """
    scenario = decode_scenario(load_legacy_dict())
    assert scenario.amounts_source_str == AMOUNTS_SOURCE_FUNDS_STR
    assert scenario.timeline_owns_amounts_bool is False
    compiled = compile_scenario(scenario)
    assert [
        fund.monthly_sip_float for fund in compiled.fund_list
    ] == [2000.0, 2000.0]
    assert compiled.settings.one_off_contributions_list


def test_dated_parts_become_events():
    """Pauses, lump sums and changes are now on the rail."""
    scenario = decode_scenario(load_legacy_dict())
    type_list = [
        event.event_type_str for event in scenario.plan.event_list
    ]
    assert EVENT_STEPUP_STR in type_list
    assert EVENT_WITHDRAW_STR in type_list
    assert EVENT_PAUSE_STR in type_list
    assert EVENT_RESUME_STR in type_list
    assert EVENT_LUMPSUM_STR in type_list
    assert EVENT_CHANGE_SIP_STR in type_list


def test_dated_parts_land_on_the_right_months():
    """A month index means the month it always meant."""
    scenario = decode_scenario(load_legacy_dict())
    by_type_dict = {
        event.event_type_str: event
        for event in scenario.plan.event_list
    }
    # month 96 from January 2026 is January 2034
    assert by_type_dict[EVENT_LUMPSUM_STR].event_date == date(
        2034, 1, 1
    )
    assert by_type_dict[EVENT_LUMPSUM_STR].amount_float == 500000.0
    # month 36 is January 2029
    assert by_type_dict[EVENT_CHANGE_SIP_STR].event_date == date(
        2029, 1, 1
    )
    # month 180 is January 2041
    assert by_type_dict[EVENT_WITHDRAW_STR].event_date == date(
        2041, 1, 1
    )


def test_a_migrated_pause_covers_exactly_its_old_months():
    """A pause window must not gain or lose a month in the upgrade.

    The rail reads a resume date as the *inclusive end* of the
    window it closes, so the resume is placed on the range's last
    month rather than the month after. Getting this wrong
    lengthens every migrated pause by one month, which changes
    what an old saved plan is worth.
    """
    scenario = decode_scenario(load_legacy_dict())
    resume_event = next(
        event
        for event in scenario.plan.event_list
        if event.event_type_str == EVENT_RESUME_STR
    )
    assert resume_event.event_date == date(2030, 3, 1)
    pause_range_list = compile_scenario(
        scenario
    ).settings.pauses.pause_ranges_list
    assert len(pause_range_list) == 1
    assert pause_range_list[0].start_date == date(2029, 4, 1)
    assert pause_range_list[0].end_date == date(2030, 3, 1)


def test_rule_shapes_become_the_policy():
    """Everything the timeline cannot express moves to the policy."""
    policy = decode_scenario(load_legacy_dict()).policy
    assert policy.sip_at_month_start_bool is False
    assert policy.stepup_interval_months_int == 6
    assert policy.stepup_fixed_increment_float == 1500.0
    assert policy.withdrawal_mode_str == WITHDRAWAL_MODE_PERCENT_STR
    assert policy.withdrawal_portfolio_percent_float == 4.0
    assert policy.withdrawal_annual_change_percent_float == 5.0
    assert (
        policy.rebalance_trigger_str
        == REBALANCE_TRIGGER_CALENDAR_STR
    )
    assert policy.rebalance_interval_months_int == 12
    assert policy.rebalance_drift_band_percent_float == 5.0
    assert (
        policy.rebalance_tax_funding_str == TAX_FUNDING_OUTSIDE_STR
    )
    assert policy.use_contribution_steering_bool is True


def test_the_tax_settings_survive_migration():
    """Surcharge, cess and income are not lost in the upgrade."""
    tax = decode_scenario(load_legacy_dict()).tax
    assert tax.surcharge_percent_float == 10.0
    assert tax.cess_percent_float == 4.0
    assert tax.total_income_float == 2500000.0
    assert tax.portfolio_exemption_amount_float == 125000.0


def test_the_inflation_rate_survives_migration():
    """The rate real values were reported against is preserved."""
    scenario = decode_scenario(load_legacy_dict())
    assert scenario.inflation_percent_float == 6.0
    assert scenario.resolved_inflation_percent_float == 6.0


def test_a_migrated_scenario_compiles():
    """The whole point: an old plan still produces a run."""
    compiled = compile_scenario(decode_scenario(load_legacy_dict()))
    assert compiled.settings.sip_at_month_start_bool is False
    assert compiled.settings.horizon_years_int == 20
    assert compiled.settings.withdrawal.is_enabled_bool is True
    assert (
        compiled.settings.withdrawal.portfolio_percent_float == 4.0
    )
    assert compiled.settings.rebalance.is_enabled_bool is True


def test_a_migrated_scenario_can_be_saved_again():
    """Reopening an old plan and saving it writes version 3."""
    scenario = decode_scenario(load_legacy_dict())
    reopened = parse_scenario_bytes(
        build_scenario_json_bytes(scenario)
    )
    assert reopened == normalise_scenario(scenario)
    assert compile_scenario(reopened) == compile_scenario(scenario)


def test_migrating_twice_changes_nothing_further():
    """Migration is idempotent once the document is current."""
    once_dict = migrate_scenario_dict(load_legacy_dict())
    assert migrate_scenario_dict(once_dict) == once_dict
