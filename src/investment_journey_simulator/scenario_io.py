"""Saving and reopening a whole scenario.

Version 2.1 saved what the classic dashboard knew: a settings tree
and a fund table. It had no concept of an event, because the rail
did not exist when it was written. Version 3 saves a `PlanScenario`,
which is everything.

A file written by the old build must still open. The migration below
is explicit and tested against a fixture rather than assumed to work,
because a scenario someone saved a year ago is the one piece of this
program a reader cannot regenerate.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from typing import Any

from investment_journey_simulator.models import (
    FundConfiguration,
    TaxSettings,
)
from investment_journey_simulator.plan_policy import PlanPolicy
from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_AUTO_STR,
    UNSET_INFLATION_FLOAT,
    PlanScenario,
    PresentationPreferences,
)
from investment_journey_simulator.scenario_migration import (
    migrate_scenario_dict,
)
from investment_journey_simulator.timeline import (
    TimelineEvent,
    TimelinePlan,
)

SCENARIO_VERSION_STR: str = "3.0"
LEGACY_VERSION_PREFIX_STR: str = "2"
VERSION_KEY_STR: str = "scenario_version"
SCENARIO_FILE_NAME_STR: str = "plan_scenario.json"
SCENARIO_MIME_TYPE_STR: str = "application/json"

PLAN_KEY_STR: str = "plan"
POLICY_KEY_STR: str = "policy"
FUNDS_KEY_STR: str = "funds"
TAX_KEY_STR: str = "tax"
PRESENTATION_KEY_STR: str = "presentation"
INFLATION_KEY_STR: str = "inflation_percent"
NAME_KEY_STR: str = "name"
AMOUNTS_SOURCE_KEY_STR: str = "amounts_source"

LEGACY_SETTINGS_KEY_STR: str = "settings"
LEGACY_FUNDS_KEY_STR: str = "funds"
LEGACY_INFLATION_KEY_STR: str = "inflation_percent"


def encode_date_str(value_date: date) -> str:
    """Write a date as an ISO string."""
    return value_date.isoformat()


def decode_date(value_str: Any, fallback_date: date) -> date:
    """Read an ISO string back into a date.

    Brief:
        A missing or malformed date falls back rather than raising,
        so one bad field cannot cost a reader a whole saved plan.

    Arguments:
        value_str (Any): Value read from the document.
        fallback_date (date): Date to use when unreadable.

    Returns:
        date: Parsed date, or the fallback.

    Warning:
        Silently accepts the fallback; callers wanting strictness
        must check the value themselves.
    """
    if not isinstance(value_str, str):
        return fallback_date
    try:
        return date.fromisoformat(value_str)
    except ValueError:
        return fallback_date


def encode_event_dict(event: TimelineEvent) -> dict[str, Any]:
    """Write one timeline event as plain JSON values."""
    return {
        "type": event.event_type_str,
        "date": encode_date_str(event.event_date),
        "amount": float(event.amount_float),
        "percent": float(event.percent_float),
        "note": event.note_str,
        "fund": event.fund_name_str,
    }


def decode_event(
    event_dict: dict[str, Any],
    fallback_date: date,
) -> TimelineEvent:
    """Read one timeline event back."""
    return TimelineEvent(
        event_type_str=str(event_dict.get("type", "")),
        event_date=decode_date(
            event_dict.get("date"), fallback_date
        ),
        amount_float=float(event_dict.get("amount", 0.0)),
        percent_float=float(event_dict.get("percent", 0.0)),
        note_str=str(event_dict.get("note", "")),
        fund_name_str=str(event_dict.get("fund", "")),
    )


def encode_plan_dict(plan: TimelinePlan) -> dict[str, Any]:
    """Write a timeline plan as plain JSON values.

    Brief:
        Events are written in calendar order so that saving the
        same plan twice produces identical bytes and a saved plan
        can be diffed in version control.

    Arguments:
        plan (TimelinePlan): Plan being written.

    Returns:
        Dict[str, Any]: JSON-serialisable plan.

    Warning:
        Ordering on write means a reopened plan holds its events
        sorted even if they were added out of sequence. The sort is
        stable, and every compiler path already reads events in
        calendar order, so this cannot change what the plan is
        worth - `normalise_scenario` and its tests hold that line.
    """
    return {
        "start_date": encode_date_str(plan.start_date),
        "horizon_years": int(plan.horizon_years_int),
        "events": [
            encode_event_dict(event)
            for event in plan.ordered_event_list
        ],
    }


def normalise_scenario(scenario: PlanScenario) -> PlanScenario:
    """Put a scenario into the exact form a save produces.

    Brief:
        Saving orders the events. Reopening therefore returns a
        scenario equal to this, not to the original object, and
        stating that plainly is better than a round-trip test that
        quietly compares something weaker than it appears to.

    Arguments:
        scenario (PlanScenario): Scenario to normalise.

    Returns:
        PlanScenario: Copy with its events in calendar order.

    Warning:
        Meaning-preserving by construction, and tested as such: a
        normalised scenario must compile to identical settings.
    """
    return replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=list(scenario.plan.ordered_event_list),
        ),
    )


def decode_plan(plan_dict: dict[str, Any]) -> TimelinePlan:
    """Read a timeline plan back."""
    start_date = decode_date(
        plan_dict.get("start_date"), date.today()
    )
    return TimelinePlan(
        start_date=start_date,
        horizon_years_int=int(plan_dict.get("horizon_years", 0)),
        event_list=[
            decode_event(event_dict, start_date)
            for event_dict in plan_dict.get("events", [])
        ],
    )


def encode_dataclass_dict(instance: Any) -> dict[str, Any]:
    """Write a flat dataclass as plain JSON values.

    Brief:
        Used for the settings objects whose fields are all scalars,
        strings or sequences of those. Dates and nested dataclasses
        are handled by their own encoders.

    Arguments:
        instance (Any): Dataclass instance to encode.

    Returns:
        Dict[str, Any]: JSON-serialisable field mapping.

    Warning:
        Tuples become lists, so decoders must restore them.
    """
    encoded_dict: dict[str, Any] = {}
    for field_name_str, value_object in vars(instance).items():
        if isinstance(value_object, tuple):
            encoded_dict[field_name_str] = [
                list(item) if isinstance(item, tuple) else item
                for item in value_object
            ]
        elif isinstance(value_object, list):
            encoded_dict[field_name_str] = list(value_object)
        else:
            encoded_dict[field_name_str] = value_object
    return encoded_dict


def decode_into(
    instance_class: Any,
    encoded_dict: dict[str, Any],
    tuple_field_set: set,
) -> Any:
    """Rebuild a flat dataclass, ignoring fields it no longer has.

    Brief:
        A file written by a later build may carry fields this one
        has never heard of. Dropping them beats refusing to open
        the plan.

    Arguments:
        instance_class (Any): Dataclass to build.
        encoded_dict (Dict[str, Any]): Values read from the file.
        tuple_field_set (set): Fields to restore as tuples.

    Returns:
        Any: Instance of the given class.

    Warning:
        Unknown fields are discarded silently.
    """
    known_field_set = set(
        instance_class.__dataclass_fields__.keys()
    )
    accepted_dict = {
        key_str: value_object
        for key_str, value_object in encoded_dict.items()
        if key_str in known_field_set
    }
    for field_name_str in tuple_field_set:
        if field_name_str in accepted_dict:
            accepted_dict[field_name_str] = tuple(
                tuple(item) if isinstance(item, list) else item
                for item in accepted_dict[field_name_str]
            )
    return instance_class(**accepted_dict)


def encode_fund_dict(
    fund_configuration: FundConfiguration,
) -> dict[str, Any]:
    """Write one fund, with its start date as a string."""
    encoded_dict = encode_dataclass_dict(fund_configuration)
    encoded_dict["start_date"] = encode_date_str(
        fund_configuration.start_date
    )
    return encoded_dict


def decode_fund(
    fund_dict: dict[str, Any],
    fallback_date: date,
) -> FundConfiguration:
    """Read one fund back."""
    working_dict = dict(fund_dict)
    working_dict["start_date"] = decode_date(
        working_dict.get("start_date"), fallback_date
    )
    return decode_into(FundConfiguration, working_dict, set())


def encode_scenario_dict(
    scenario: PlanScenario,
) -> dict[str, Any]:
    """Capture a whole scenario as JSON-serialisable values.

    Brief:
        Inputs only. A result is never saved, because a result is
        always reproducible from the inputs that made it.

    Arguments:
        scenario (PlanScenario): Scenario to capture.

    Returns:
        Dict[str, Any]: The scenario, ready to serialise.

    Warning:
        Events are written in calendar order, so two saves of the
        same plan produce identical bytes.
    """
    return {
        VERSION_KEY_STR: SCENARIO_VERSION_STR,
        NAME_KEY_STR: scenario.name_str,
        PLAN_KEY_STR: encode_plan_dict(scenario.plan),
        POLICY_KEY_STR: encode_dataclass_dict(scenario.policy),
        FUNDS_KEY_STR: [
            encode_fund_dict(fund_configuration)
            for fund_configuration in scenario.fund_list
        ],
        TAX_KEY_STR: encode_dataclass_dict(scenario.tax),
        PRESENTATION_KEY_STR: encode_dataclass_dict(
            scenario.presentation
        ),
        INFLATION_KEY_STR: float(scenario.inflation_percent_float),
        AMOUNTS_SOURCE_KEY_STR: scenario.amounts_source_str,
    }


def decode_scenario(
    scenario_dict: dict[str, Any],
) -> PlanScenario:
    """Rebuild a scenario from a parsed document.

    Brief:
        Accepts version 3 directly and migrates anything older
        first, so callers never branch on the version themselves.

    Arguments:
        scenario_dict (Dict[str, Any]): Parsed document.

    Returns:
        PlanScenario: The reopened scenario.

    Warning:
        Fields absent from the document take their defaults rather
        than raising, so a partial file still opens.
    """
    upgraded_dict = migrate_scenario_dict(scenario_dict)
    plan = decode_plan(upgraded_dict.get(PLAN_KEY_STR, {}))
    return PlanScenario(
        plan=plan,
        fund_list=[
            decode_fund(fund_dict, plan.start_date)
            for fund_dict in upgraded_dict.get(FUNDS_KEY_STR, [])
        ],
        policy=_decode_policy(upgraded_dict),
        tax=decode_into(
            TaxSettings,
            upgraded_dict.get(TAX_KEY_STR, {}),
            {"income_by_year_tuple"},
        ),
        presentation=decode_into(
            PresentationPreferences,
            upgraded_dict.get(PRESENTATION_KEY_STR, {}),
            set(),
        ),
        inflation_percent_float=float(
            upgraded_dict.get(
                INFLATION_KEY_STR, UNSET_INFLATION_FLOAT
            )
        ),
        name_str=str(upgraded_dict.get(NAME_KEY_STR, "My plan")),
        amounts_source_str=str(
            upgraded_dict.get(
                AMOUNTS_SOURCE_KEY_STR, AMOUNTS_SOURCE_AUTO_STR
            )
        ),
    )


def _decode_policy(upgraded_dict: dict[str, Any]) -> PlanPolicy:
    """Read the standing rules back, restoring their tuples."""
    return decode_into(
        PlanPolicy,
        upgraded_dict.get(POLICY_KEY_STR, {}),
        {
            "withdrawal_schedule_tuple",
            "withdrawal_change_percent_tuple",
        },
    )


def build_scenario_json_bytes(scenario: PlanScenario) -> bytes:
    """Serialise a scenario into downloadable bytes."""
    return json.dumps(
        encode_scenario_dict(scenario), indent=2, ensure_ascii=False
    ).encode("utf-8")


def parse_scenario_bytes(uploaded_bytes: bytes) -> PlanScenario:
    """Read an uploaded file back into a scenario.

    Brief:
        The one entry point a screen should use. Version checking
        and migration happen inside.

    Arguments:
        uploaded_bytes (bytes): Uploaded JSON document.

    Returns:
        PlanScenario: The reopened scenario.

    Warning:
        Raises ValueError when the document is not a saved
        scenario at all, which is worth failing loudly on.
    """
    scenario_dict = json.loads(uploaded_bytes.decode("utf-8"))
    if VERSION_KEY_STR not in scenario_dict:
        raise ValueError(
            "This file does not look like a saved scenario."
        )
    return decode_scenario(scenario_dict)
