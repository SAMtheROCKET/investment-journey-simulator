"""Reading a `PlanScenario` back out of the classic dashboard.

The dashboard's sidebar is fourteen hundred lines of widgets that
have been correct for a long time. Rewriting them to read and write
a scenario field by field would risk every one of those behaviours
for no visible gain.

So the dashboard keeps its controls and this module converts what
they produced into the shared scenario, which is what the rest of
the portal then reads.

The conversion is not written twice. Turning a `SimulationSettings`
tree into events and a policy is exactly what the version 2.1
migration already does, so this feeds the same code. That is
deliberate: it makes it impossible for "reopen a saved file" and
"read the dashboard" to drift apart.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationSettings,
)
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.scenario_io import (
    decode_scenario,
    encode_date_str,
    encode_fund_dict,
)
from investment_journey_simulator.scenario_migration import (
    LEGACY_SETTINGS_KEY_STR,
    VERSION_KEY_STR,
)

LEGACY_VERSION_STR: str = "2.1"


def encode_settings_dict(
    settings: SimulationSettings,
) -> dict[str, Any]:
    """Write engine settings in the shape the migration reads.

    Brief:
        `asdict` produces the nested tree, and the only values it
        leaves unserialisable are the dates.

    Arguments:
        settings (SimulationSettings): Settings to encode.

    Returns:
        Dict[str, Any]: Legacy-shaped settings tree.

    Warning:
        Pause ranges carry dates two levels down, so they are
        converted explicitly rather than by a blanket sweep.
    """
    settings_dict = asdict(settings)
    settings_dict["portfolio_start_date"] = encode_date_str(
        settings.portfolio_start_date
    )
    settings_dict["pauses"]["pause_ranges_list"] = [
        {
            "start_date": encode_date_str(pause_range.start_date),
            "end_date": encode_date_str(pause_range.end_date),
            "scope_str": pause_range.scope_str,
        }
        for pause_range in settings.pauses.pause_ranges_list
    ]
    return settings_dict


def build_scenario_from_settings(
    settings: SimulationSettings,
    fund_list: list[FundConfiguration],
    inflation_percent_float: float,
    currency_code_str: str = "",
    name_str: str = "",
) -> PlanScenario:
    """Turn one dashboard run into the shared scenario.

    Brief:
        Routed through the version 2.1 migration, so the dated
        parts become events and the rule shapes become a policy by
        exactly the same code that reopens a saved file.

    Arguments:
        settings (SimulationSettings): What the sidebar built.
        fund_list (List[FundConfiguration]): The fund table.
        inflation_percent_float (float): Rate for real values.
        currency_code_str (str): Currency to display in.
        name_str (str): Name for the plan.

    Returns:
        PlanScenario: The same plan, as the portal sees it.

    Warning:
        The funds keep their standing instalments, so the amounts
        source is set to the funds rather than the timeline.
    """
    legacy_dict = {
        VERSION_KEY_STR: LEGACY_VERSION_STR,
        LEGACY_SETTINGS_KEY_STR: encode_settings_dict(settings),
        "funds": [
            encode_fund_dict(fund_configuration)
            for fund_configuration in fund_list
        ],
        "inflation_percent": float(inflation_percent_float),
    }
    scenario = decode_scenario(legacy_dict)
    return _apply_presentation(
        scenario, currency_code_str, name_str
    )


def _apply_presentation(
    scenario: PlanScenario,
    currency_code_str: str,
    name_str: str,
) -> PlanScenario:
    """Carry the currency and name the migration cannot know."""
    presentation = scenario.presentation
    if currency_code_str:
        presentation = replace(
            presentation, currency_code_str=currency_code_str
        )
    return replace(
        scenario,
        presentation=presentation,
        name_str=name_str or scenario.name_str,
    )
