"""Small, named edits to a scenario.

Quick asks for a monthly amount. Guided asks the same question in a
sentence. Both mean the same thing to the plan - set the instalment
the plan opens with - and both must produce the identical scenario,
or the two screens will disagree about what the reader said.

So the edits live here, once, rather than being spelled out twice on
two pages. Every function takes a scenario and returns a new one;
none of them mutates.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    REBALANCE_TRIGGER_DATED_STR,
)
from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_TIMELINE_STR,
    PlanScenario,
    PresentationPreferences,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_SETS_INSTALMENT_TUPLE,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    TimelineEvent,
    TimelinePlan,
)


def read_monthly_contribution_float(
    scenario: PlanScenario,
) -> float:
    """Read the instalment the plan opens with.

    Brief:
        Reads whichever source owns the amounts, so the same
        question can be asked of a rail plan and a form plan.

    Arguments:
        scenario (PlanScenario): Scenario being read.

    Returns:
        float: Opening monthly instalment, zero when none is set.

    Warning:
        Reports the opening amount only. A plan that changes its
        instalment later still answers with the first one.
    """
    for event in scenario.plan.ordered_event_list:
        if event.event_type_str in EVENT_SETS_INSTALMENT_TUPLE:
            return float(event.amount_float)
    return sum(
        float(fund.monthly_sip_float)
        for fund in scenario.fund_list
    )


def set_monthly_contribution(
    scenario: PlanScenario,
    amount_float: float,
) -> PlanScenario:
    """Set the instalment the plan opens with.

    Brief:
        Updates the opening instalment event when one exists and
        adds it when it does not, so asking the question twice
        never leaves two contradictory events on the rail.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        amount_float (float): New monthly instalment.

    Returns:
        PlanScenario: Copy carrying the new instalment.

    Warning:
        Takes ownership of the amounts for the timeline, because
        an instalment event and a standing fund instalment would
        otherwise both be counted.
    """
    remaining_list = [
        event
        for event in scenario.plan.ordered_event_list
        if not _is_opening_instalment_bool(scenario, event)
    ]
    opening_event = TimelineEvent(
        EVENT_START_SIP_STR,
        scenario.plan.start_date,
        float(amount_float),
    )
    return replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=[opening_event] + remaining_list,
        ),
        amounts_source_str=AMOUNTS_SOURCE_TIMELINE_STR,
    )


def _is_opening_instalment_bool(
    scenario: PlanScenario,
    event: TimelineEvent,
) -> bool:
    """Whether this event is the one that opens the plan."""
    if event.event_type_str not in EVENT_SETS_INSTALMENT_TUPLE:
        return False
    return event.event_date <= scenario.plan.start_date


def set_horizon_years(
    scenario: PlanScenario,
    horizon_years_int: int,
) -> PlanScenario:
    """Set how many years the plan runs for."""
    return replace(
        scenario,
        plan=replace(
            scenario.plan,
            horizon_years_int=max(1, int(horizon_years_int)),
        ),
    )


def set_start_date(
    scenario: PlanScenario,
    start_date: date,
) -> PlanScenario:
    """Move the month the plan opens in.

    Brief:
        Events keep their own dates, because a plan that starts a
        year later is not the same as a plan whose every event
        shifts a year.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        start_date (date): New opening month.

    Returns:
        PlanScenario: Copy opening in the new month.

    Warning:
        An event now falling before the start compiles to month
        zero rather than being dropped.
    """
    anchored_date = date(start_date.year, start_date.month, 1)
    return replace(
        scenario,
        plan=replace(scenario.plan, start_date=anchored_date),
    )


def read_expected_return_float(scenario: PlanScenario) -> float:
    """Read the return a one-return screen should show.

    Brief:
        The plain average across the funds rather than the first
        one's. Showing fund one's rate and then writing it to all
        of them is how a three-fund plan silently became a
        one-return plan: the screen displayed 14%, the reader
        changed nothing, and the other two funds were rewritten to
        14% anyway.

    Arguments:
        scenario (PlanScenario): Scenario being read.

    Returns:
        float: Average gross return, zero when there are no funds.

    Warning:
        An average is not what any single fund earns. It is what a
        one-box screen can honestly show, and `set_expected_return`
        moves every fund by the same amount so the average is what
        a reader actually controls.
    """
    if not scenario.fund_list:
        return 0.0
    return sum(
        float(fund.gross_return_percent_float)
        for fund in scenario.fund_list
    ) / len(scenario.fund_list)


def has_return_spread_bool(scenario: PlanScenario) -> bool:
    """Whether the funds differ in the return they assume."""
    return (
        len(
            {
                round(float(fund.gross_return_percent_float), 6)
                for fund in scenario.fund_list
            }
        )
        > 1
    )


def set_expected_return(
    scenario: PlanScenario,
    return_percent_float: float,
) -> PlanScenario:
    """Set the gross return on every fund in the plan.

    Moves every fund by the same number of percentage points, so
    the average becomes what was asked for and the spread between
    an equity fund and a debt one survives. Flattening them to one
    rate is what this used to do, and it destroyed the thing that
    makes a multi-fund plan worth modelling: with equal returns the
    ending split is forced to equal the invested split.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        return_percent_float (float): Gross annual return wanted,
            as the average across the funds.

    Returns:
        PlanScenario: Copy carrying the new average.

    Warning:
        A shift can drive a low-return fund below zero, so each is
        floored there. That does compress the spread at the bottom
        of the range, which is the one case where this cannot keep
        both promises.
    """
    if not scenario.fund_list:
        return scenario
    shift_float = float(return_percent_float) - (
        read_expected_return_float(scenario)
    )
    return replace(
        scenario,
        fund_list=[
            replace(
                fund_configuration,
                gross_return_percent_float=max(
                    0.0,
                    float(
                        fund_configuration.gross_return_percent_float
                    )
                    + shift_float,
                ),
            )
            for fund_configuration in scenario.fund_list
        ],
    )


def set_currency_code(
    scenario: PlanScenario,
    currency_code_str: str,
) -> PlanScenario:
    """Set the currency every figure is shown in.

    Brief:
        Presentation only. It changes no amount, and deliberately
        does not change the tax regime, because a reader living in
        one country may well hold a fund quoted in another.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        currency_code_str (str): Currency to display in.

    Returns:
        PlanScenario: Copy displayed in the new currency.

    Warning:
        No conversion happens. An amount typed as 25000 stays
        25000; only the symbol and the grouping change.
    """
    return replace(
        scenario,
        presentation=replace(
            scenario.presentation,
            currency_code_str=currency_code_str,
        ),
    )


def set_inflation_percent(
    scenario: PlanScenario,
    inflation_percent_float: float,
) -> PlanScenario:
    """Set the rate real values are reported against."""
    return replace(
        scenario,
        inflation_percent_float=float(inflation_percent_float),
    )


def set_scenario_name(
    scenario: PlanScenario,
    name_str: str,
) -> PlanScenario:
    """Name the plan, for comparisons and reports."""
    return replace(
        scenario, name_str=name_str or scenario.name_str
    )


def build_named_copy(
    scenario: PlanScenario,
    name_str: str,
) -> PlanScenario:
    """Copy a scenario under a new name, for comparison."""
    return replace(
        scenario,
        name_str=name_str,
        plan=TimelinePlan(
            start_date=scenario.plan.start_date,
            horizon_years_int=scenario.plan.horizon_years_int,
            event_list=list(scenario.plan.event_list),
        ),
        fund_list=list(scenario.fund_list),
    )


def reset_presentation(
    scenario: PlanScenario,
) -> PlanScenario:
    """Return display preferences to their defaults."""
    return replace(
        scenario, presentation=PresentationPreferences()
    )


def has_event_of_type_bool(
    scenario: PlanScenario,
    event_type_str: str,
) -> bool:
    """Whether the plan already carries an event of this kind.

    Brief:
        Lets a screen offer "add a step-up" once rather than
        letting a reader stack five of them by clicking twice.

    Arguments:
        scenario (PlanScenario): Scenario being inspected.
        event_type_str (str): Event type to look for.

    Returns:
        bool: True when at least one such event exists.
    """
    return any(
        event.event_type_str == event_type_str
        for event in scenario.plan.event_list
    )


def _shift_years_date(start_date: date, years_int: int) -> date:
    """The same month, a whole number of years later.

    Brief:
        Anchored to the first of the month, like every other date
        this program stores, because the engine's grid is monthly
        and a day-of-month would be a distinction without a
        difference that still broke equality checks.
    """
    return date(start_date.year + int(years_int), start_date.month, 1)


def add_annual_step_up(
    scenario: PlanScenario,
    percent_float: float,
) -> PlanScenario:
    """Make the instalment grow by a fixed percentage each year.

    Brief:
        The single most consequential thing a first-time reader can
        add to a plan, and the one most of them leave out. A flat
        instalment quietly assumes a salary that never rises.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        percent_float (float): Yearly increase, in percent.

    Returns:
        PlanScenario: Copy carrying exactly one step-up.

    Warning:
        Replaces any existing step-up rather than adding a second,
        because two step-up events on one rail compound in a way
        nobody intends and nothing on screen would explain.
    """
    remaining_list = [
        event
        for event in scenario.plan.ordered_event_list
        if event.event_type_str != EVENT_STEPUP_STR
    ]
    step_up_event = TimelineEvent(
        EVENT_STEPUP_STR,
        scenario.plan.start_date,
        percent_float=float(percent_float),
        note_str="Yearly increase in the amount invested",
    )
    return replace(
        scenario,
        plan=replace(
            scenario.plan,
            event_list=remaining_list + [step_up_event],
        ),
        amounts_source_str=AMOUNTS_SOURCE_TIMELINE_STR,
    )


def _build_break_event_list(
    pause_date: date,
    length_years_int: int,
) -> list:
    """The pair of events that open and close a break."""
    return [
        TimelineEvent(
            EVENT_PAUSE_STR,
            pause_date,
            note_str="A break from contributing",
        ),
        TimelineEvent(
            EVENT_RESUME_STR,
            _shift_years_date(pause_date, length_years_int),
            note_str="Back to the previous amount",
        ),
    ]


def add_contribution_pause(
    scenario: PlanScenario,
    from_year_int: int,
    length_years_int: int,
) -> PlanScenario:
    """Stop contributing for a while, then start again.

    Brief:
        A career break, a house deposit, a year of study. The money
        already invested keeps compounding; only the instalment
        stops, which is exactly the distinction most people get
        wrong when they guess at the cost of a break.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        from_year_int (int): Years after the start that it begins.
        length_years_int (int): How many years it lasts.

    Returns:
        PlanScenario: Copy carrying one pause and its resume.

    Warning:
        Replaces any existing pause and resume. A second pause is a
        real thing to want, but it belongs on the rail where a
        reader can see both, not behind a button producing two.
    """
    remaining_list = [
        event
        for event in scenario.plan.ordered_event_list
        if event.event_type_str
        not in (EVENT_PAUSE_STR, EVENT_RESUME_STR)
    ]
    break_list = _build_break_event_list(
        _shift_years_date(
            scenario.plan.start_date, max(1, int(from_year_int))
        ),
        max(1, int(length_years_int)),
    )
    return replace(
        scenario,
        plan=replace(
            scenario.plan, event_list=remaining_list + break_list
        ),
        amounts_source_str=AMOUNTS_SOURCE_TIMELINE_STR,
    )


def set_rebalancing_rule(
    scenario: PlanScenario,
    interval_years_int: int,
    method_str: str,
    target_mode_str: str,
    tax_funding_str: str,
    maximum_events_int: int = 0,
) -> PlanScenario:
    """Put a standing rebalancing rule on the plan.

    Brief:
        The Rebalancing Lab runs its own controlled experiment on
        its own funds, which is what makes its comparison honest.
        This is the one door out of that isolation: it carries the
        *rule* across without carrying the lab's funds with it.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        interval_years_int (int): Years between rebalances.
        method_str (str): Full liquidation or partial.
        target_mode_str (str): Which split is the target.
        tax_funding_str (str): Where the tax is paid from.
        maximum_events_int (int): Cap on rebalances, zero for none.

    Returns:
        PlanScenario: Copy carrying the standing rule.

    Warning:
        Sets a *dated-interval* rule rather than a drift band. The
        lab compares intervals, so importing its finding as a drift
        band would apply a policy nobody measured.
    """
    return replace(
        scenario,
        policy=replace(
            scenario.policy,
            rebalance_trigger_str=REBALANCE_TRIGGER_DATED_STR,
            rebalance_interval_months_int=(
                max(1, int(interval_years_int)) * MONTHS_IN_YEAR_INT
            ),
            rebalance_method_str=method_str,
            rebalance_target_mode_str=target_mode_str,
            rebalance_tax_funding_str=tax_funding_str,
            rebalance_maximum_events_int=max(
                0, int(maximum_events_int)
            ),
        ),
    )
