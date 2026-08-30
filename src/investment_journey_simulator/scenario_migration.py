"""Reopening a plan saved by an older build.

Version 2.1 predates the event rail. It stored a settings tree whose
dated parts - pauses, lump sums, instalment changes, the month a
step-up or a withdrawal began - had nowhere to live except as month
indices inside that tree. Version 3 stores them as events, which is
what makes them visible and editable on a timeline.

Turning one into the other is this module's whole job. It is written
out longhand, field by field, because a scenario someone saved a year
ago is the one thing in this program a reader cannot regenerate, and
a clever generic converter would fail quietly.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

import pandas as pd

from investment_journey_simulator.constants import (
    COLUMN_FUND_NAME_STR,
    COLUMN_FUND_START_STR,
    COLUMN_FUND_STEPUP_STR,
    COLUMN_PRESET_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    MONTHS_IN_YEAR_INT,
    REBALANCE_TRIGGER_DATED_STR,
    STEPUP_MODE_OFF_STR,
)
from investment_journey_simulator.fund_builder import (
    build_fund_configurations_list,
)
from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_FUNDS_STR,
    UNSET_INFLATION_FLOAT,
)
from investment_journey_simulator.time_utils import (
    build_month_start_dates_list,
)
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_LUMPSUM_STR,
    EVENT_PAUSE_STR,
    EVENT_REBALANCE_STR,
    EVENT_RESUME_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_STR,
)

TARGET_VERSION_STR: str = "3.0"
VERSION_KEY_STR: str = "scenario_version"
LEGACY_SETTINGS_KEY_STR: str = "settings"
FIELD_NAMED_MARKER_STR: str = "name_str"

# Version 2.1 saved its funds as `dataframe.to_dict("records")`, so
# the keys are the *editor's column captions*, not field names. Any
# caption that has since been reworded therefore has to be mapped
# back, or a file saved before the rename stops loading.
#
# This map only ever grows. Removing an entry orphans every file
# saved while that caption was current.
LEGACY_COLUMN_ALIAS_DICT: dict[str, str] = {
    "MF Name": COLUMN_FUND_NAME_STR,
    "Fund Type Preset": COLUMN_PRESET_STR,
    "Fund Step-up %": COLUMN_FUND_STEPUP_STR,
    "Fund Start": COLUMN_FUND_START_STR,
}


def resolve_month_date(start_date: date, month_index_int: int) -> str:
    """Turn a month index back into a dated ISO string.

    Brief:
        Version 2.1 counted months from the portfolio start. The
        rail needs the date that index landed on.

    Arguments:
        start_date (date): Month zero of the plan.
        month_index_int (int): Offset in whole months.

    Returns:
        str: ISO date of that month, first day.

    Warning:
        A negative index clamps to month zero rather than running
        backwards off the plan.
    """
    safe_index_int = max(0, int(month_index_int))
    return build_month_start_dates_list(
        start_date, safe_index_int + 1
    )[safe_index_int].isoformat()


def build_event_dict(
    event_type_str: str,
    date_str: str,
    amount_float: float = 0.0,
    percent_float: float = 0.0,
) -> dict[str, Any]:
    """Build one version 3 event record."""
    return {
        "type": event_type_str,
        "date": date_str,
        "amount": float(amount_float),
        "percent": float(percent_float),
        "note": "",
        "fund": "",
    }


def migrate_stepup_event_list(
    settings_dict: dict[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    """Turn a step-up rule into the event that starts it."""
    stepup_dict = settings_dict.get("stepup") or {}
    mode_str = str(stepup_dict.get("mode_str", STEPUP_MODE_OFF_STR))
    if mode_str == STEPUP_MODE_OFF_STR:
        return []
    return [
        build_event_dict(
            EVENT_STEPUP_STR,
            resolve_month_date(
                start_date,
                int(
                    stepup_dict.get(
                        "first_stepup_month_index_int", 0
                    )
                ),
            ),
            percent_float=float(
                stepup_dict.get("global_stepup_percent_float", 0.0)
            ),
        )
    ]


def migrate_withdrawal_event_list(
    settings_dict: dict[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    """Turn a withdrawal rule into the event that starts it."""
    withdrawal_dict = settings_dict.get("withdrawal") or {}
    if not withdrawal_dict.get("is_enabled_bool", False):
        return []
    return [
        build_event_dict(
            EVENT_WITHDRAW_STR,
            resolve_month_date(
                start_date,
                int(
                    withdrawal_dict.get("start_month_index_int", 0)
                ),
            ),
            amount_float=float(
                withdrawal_dict.get("fixed_amount_float", 0.0)
            ),
        )
    ]


def migrate_pause_event_list(
    settings_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turn every pause window into a pause and a resume.

    Brief:
        A range becomes the two events that bracket it, which is
        how the rail expresses the same idea.

    Arguments:
        settings_dict (Dict[str, Any]): Legacy settings tree.

    Returns:
        List[Dict[str, Any]]: Pause and resume event records.

    Warning:
        The resume is placed on the month **after** the range
        ends, because that is the month contributions start again
        and "resume" is an event rather than a boundary.

        It used to be placed on the range's last month, to match a
        compiler that read a resume date as the inclusive end of
        the window it closed. Both halves of that were wrong
        together and right in combination: an old plan round
        tripped, and a resume the reader placed by hand cost them
        a month's instalment. The compiler now ends a pause the
        month before its resume, so this has to move by one month
        for a migrated plan to keep exactly the months it had.
    """
    pauses_dict = settings_dict.get("pauses") or {}
    event_list: list[dict[str, Any]] = []
    for range_dict in pauses_dict.get("pause_ranges_list", []):
        start_str = str(range_dict.get("start_date", ""))
        end_str = str(range_dict.get("end_date", ""))
        if not start_str or not end_str:
            continue
        event_list.append(
            build_event_dict(EVENT_PAUSE_STR, start_str)
        )
        event_list.append(
            build_event_dict(
                EVENT_RESUME_STR, _shift_month_str(end_str, 1)
            )
        )
    return event_list


def _shift_month_str(date_str: str, offset_int: int) -> str:
    """Move an ISO month-start date by whole months."""
    anchor_date = date.fromisoformat(date_str)
    zero_based_int = (
        anchor_date.year * MONTHS_IN_YEAR_INT
        + anchor_date.month
        - 1
        + int(offset_int)
    )
    year_int, month_int = divmod(
        zero_based_int, MONTHS_IN_YEAR_INT
    )
    return date(year_int, month_int + 1, 1).isoformat()


def migrate_contribution_event_list(
    settings_dict: dict[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    """Turn dated lump sums and instalment changes into events."""
    event_list: list[dict[str, Any]] = []
    for one_off_dict in settings_dict.get(
        "one_off_contributions_list", []
    ):
        event_list.append(
            build_event_dict(
                EVENT_LUMPSUM_STR,
                resolve_month_date(
                    start_date,
                    int(one_off_dict.get("month_index_int", 0)),
                ),
                amount_float=float(
                    one_off_dict.get("amount_float", 0.0)
                ),
            )
        )
    for override_dict in settings_dict.get(
        "instalment_override_list", []
    ):
        event_list.append(
            build_event_dict(
                EVENT_CHANGE_SIP_STR,
                resolve_month_date(
                    start_date,
                    int(override_dict.get("month_index_int", 0)),
                ),
                amount_float=float(
                    override_dict.get("amount_float", 0.0)
                ),
            )
        )
    return event_list


def migrate_rebalance_event_list(
    settings_dict: dict[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    """Turn hand-dated rebalances into events.

    Brief:
        Only a dated trigger produces events. A calendar or drift
        rule stays a rule and moves to the policy instead.

    Arguments:
        settings_dict (Dict[str, Any]): Legacy settings tree.
        start_date (date): Month zero of the plan.

    Returns:
        List[Dict[str, Any]]: Rebalance event records.

    Warning:
        Returns nothing when rebalancing was off, which is not the
        same as an empty month list on an enabled dated trigger.
    """
    rebalance_dict = settings_dict.get("rebalance") or {}
    if not rebalance_dict.get("is_enabled_bool", False):
        return []
    if (
        str(rebalance_dict.get("trigger_str", ""))
        != REBALANCE_TRIGGER_DATED_STR
    ):
        return []
    return [
        build_event_dict(
            EVENT_REBALANCE_STR,
            resolve_month_date(start_date, int(month_index_int)),
        )
        for month_index_int in rebalance_dict.get(
            "rebalance_month_index_tuple", []
        )
    ]


def build_policy_dict(
    settings_dict: dict[str, Any],
) -> dict[str, Any]:
    """Lift every rule shape out of the legacy settings tree."""
    stepup_dict = settings_dict.get("stepup") or {}
    withdrawal_dict = settings_dict.get("withdrawal") or {}
    rebalance_dict = settings_dict.get("rebalance") or {}
    return {
        "sip_at_month_start_bool": bool(
            settings_dict.get("sip_at_month_start_bool", True)
        ),
        "stepup_interval_months_int": int(
            stepup_dict.get("interval_months_int", 12)
        ),
        "stepup_fixed_increment_float": float(
            stepup_dict.get("fixed_increment_amount_float", 0.0)
        ),
        "withdrawal_mode_str": str(
            withdrawal_dict.get("mode_str", "FIXED")
        ),
        "withdrawal_portfolio_percent_float": float(
            withdrawal_dict.get("portfolio_percent_float", 0.0)
        ),
        "withdrawal_annual_change_percent_float": float(
            withdrawal_dict.get("annual_change_percent_float", 0.0)
        ),
        "withdrawal_schedule_tuple": tuple(
            withdrawal_dict.get("monthly_schedule_list", [])
        ),
        "withdrawal_change_percent_tuple": tuple(
            withdrawal_dict.get("monthly_change_percent_list", [])
        ),
        **build_rebalance_policy_dict(rebalance_dict),
    }


def build_rebalance_policy_dict(
    rebalance_dict: dict[str, Any],
) -> dict[str, Any]:
    """Lift the rebalance rule shape out of its settings block."""
    return {
        "rebalance_trigger_str": str(
            rebalance_dict.get(
                "trigger_str", REBALANCE_TRIGGER_DATED_STR
            )
        ),
        "rebalance_interval_months_int": int(
            rebalance_dict.get("interval_months_int", 0)
        ),
        "rebalance_drift_band_percent_float": float(
            rebalance_dict.get("drift_band_percent_float", 0.0)
        ),
        "rebalance_method_str": str(
            rebalance_dict.get("method_str", "")
        ),
        "rebalance_target_mode_str": str(
            rebalance_dict.get("target_mode_str", "")
        ),
        "rebalance_tax_funding_str": str(
            rebalance_dict.get("tax_funding_str", "PORTFOLIO")
        ),
        "rebalance_maximum_events_int": int(
            rebalance_dict.get("maximum_events_int", 0)
        ),
        "use_contribution_steering_bool": bool(
            rebalance_dict.get(
                "use_contribution_steering_bool", False
            )
        ),
    }


def build_migrated_event_list(
    settings_dict: dict[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    """Gather every event the legacy settings implied."""
    return (
        migrate_stepup_event_list(settings_dict, start_date)
        + migrate_withdrawal_event_list(settings_dict, start_date)
        + migrate_pause_event_list(settings_dict)
        + migrate_contribution_event_list(settings_dict, start_date)
        + migrate_rebalance_event_list(settings_dict, start_date)
    )


def migrate_legacy_scenario_dict(
    scenario_dict: dict[str, Any],
) -> dict[str, Any]:
    """Upgrade a version 2.1 document to version 3.

    Brief:
        The dated parts of the old settings tree become events; the
        rule shapes become a policy; the funds keep their standing
        instalments, which is why the amounts source is stated
        outright rather than inferred.

    Arguments:
        scenario_dict (Dict[str, Any]): Parsed legacy document.

    Returns:
        Dict[str, Any]: Equivalent version 3 document.

    Warning:
        The legacy format had no currency or regime, so both take
        their defaults - rupees and the fully modelled Indian
        regime, which is what that build always assumed.
    """
    settings_dict = scenario_dict.get(LEGACY_SETTINGS_KEY_STR) or {}
    start_date = _resolve_legacy_start_date(settings_dict)
    return {
        VERSION_KEY_STR: TARGET_VERSION_STR,
        "name": "Reopened plan",
        "plan": {
            "start_date": start_date.isoformat(),
            "horizon_years": int(
                settings_dict.get("horizon_years_int", 0)
            ),
            "events": build_migrated_event_list(
                settings_dict, start_date
            ),
        },
        "policy": build_policy_dict(settings_dict),
        "funds": translate_legacy_fund_list(
            scenario_dict, start_date
        ),
        "tax": settings_dict.get("tax") or {},
        "presentation": {},
        "inflation_percent": float(
            scenario_dict.get(
                "inflation_percent", UNSET_INFLATION_FLOAT
            )
        ),
        "amounts_source": AMOUNTS_SOURCE_FUNDS_STR,
    }


def _resolve_legacy_start_date(
    settings_dict: dict[str, Any],
) -> date:
    """Read month zero out of a legacy settings tree."""
    return date.fromisoformat(
        str(
            settings_dict.get(
                "portfolio_start_date", date.today().isoformat()
            )
        )
    )


def is_field_named_fund_bool(fund_dict: dict[str, Any]) -> bool:
    """Whether a fund record already uses dataclass field names.

    Brief:
        Tells a genuinely old record - keyed by editor captions -
        apart from one this build wrote itself.

    Arguments:
        fund_dict (Dict[str, Any]): One saved fund record.

    Returns:
        bool: True when the record needs no translation.

    Warning:
        Keys on the presence of one field name. A record carrying
        both shapes would be treated as current, which is the
        safer of the two mistakes.
    """
    return FIELD_NAMED_MARKER_STR in fund_dict


def apply_column_aliases_dict(
    fund_dict: dict[str, Any],
) -> dict[str, Any]:
    """Rename any caption that has since been reworded."""
    return {
        LEGACY_COLUMN_ALIAS_DICT.get(key_str, key_str): value
        for key_str, value in fund_dict.items()
    }


def translate_legacy_fund_list(
    scenario_dict: dict[str, Any],
    start_date: date,
) -> list[dict[str, Any]]:
    """Turn caption-keyed fund rows into field-named records.

    Brief:
        Version 2.1 saved the fund table with
        `to_dict("records")`, so its keys are the editor's column
        captions, not the names `FundConfiguration` uses. The
        rows are rebuilt into a frame and handed to
        `build_fund_configurations_list`, which already knows how
        to read an editor row and is already tested for it.

    Arguments:
        scenario_dict (Dict[str, Any]): Parsed legacy document.
        start_date (date): Month zero of the plan.

    Returns:
        List[Dict[str, Any]]: Field-named fund records.

    Warning:
        Records already in field-named form pass through
        untouched, so this is safe to run on any document.
    """
    fund_row_list = scenario_dict.get("funds") or []
    if not fund_row_list:
        return []
    if is_field_named_fund_bool(fund_row_list[0]):
        return list(fund_row_list)
    return [
        _encode_fund_record_dict(fund_configuration)
        for fund_configuration in build_fund_configurations_list(
            pd.DataFrame(
                [
                    apply_column_aliases_dict(fund_dict)
                    for fund_dict in fund_row_list
                ]
            ),
            start_date,
            str(
                scenario_dict.get(
                    "expense_model", EXPENSE_MODEL_SIMPLE_STR
                )
            ),
        )
    ]


def _encode_fund_record_dict(fund_configuration) -> dict[str, Any]:
    """Write one fund as field names, with an ISO start date.

    Brief:
        Deliberately not imported from `scenario_io`, which reads
        this module - importing it back would make a cycle.

    Arguments:
        fund_configuration: Fund to encode.

    Returns:
        Dict[str, Any]: Field-named record.

    Warning:
        Only the start date needs special handling; every other
        field of a fund is already a scalar.
    """
    record_dict = asdict(fund_configuration)
    record_dict["start_date"] = (
        fund_configuration.start_date.isoformat()
    )
    return record_dict


def migrate_scenario_dict(
    scenario_dict: dict[str, Any],
) -> dict[str, Any]:
    """Bring any supported document up to the current version.

    Brief:
        The single entry point. A version 3 document passes
        straight through, so callers never branch on the version.

    Arguments:
        scenario_dict (Dict[str, Any]): Parsed document.

    Returns:
        Dict[str, Any]: Document at the current version.

    Warning:
        A version this build has never heard of is returned
        unchanged and decoded on a best-effort basis.
    """
    version_str = str(scenario_dict.get(VERSION_KEY_STR, ""))
    if version_str.startswith("2"):
        return migrate_legacy_scenario_dict(scenario_dict)
    return scenario_dict
