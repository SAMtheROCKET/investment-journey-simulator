"""What state the plan is in, and which events that state allows.

A timeline lets a reader place anything anywhere, and most of what
they can place is fine. A few combinations are not merely unusual
but impossible: stopping a SIP that never started, resuming
contributions that were never paused, ending withdrawals that never
began. The engine handles all of them without complaining, because
it compiles what it is given - a pause with no matching start simply
never fires - and a plan that quietly does nothing is far worse than
one that argues back.

Why this is a state machine and not a checklist
-----------------------------------------------
The first version of this module asked one question of each event:
*has a required event happened at some earlier date?* That catches
the obvious mistakes and misses a whole family of real ones, because
"has happened" is not the same as "is happening":

    Start -> Pause -> Resume -> Resume

The second Resume has a Pause before it, so an existence check
passes it. But contributions are already running by then; the plan
is not paused, and the second Resume does nothing. The same hole let
through a second Pause while already paused, a second Start while
already investing, and repeated withdrawal stops.

So the timeline is walked in date order through two independent
machines, and each event is judged against the state at the moment
it lands rather than against the history behind it:

    NOT INVESTING --start--> INVESTING --pause--> PAUSED
                                 ^                  |
                                 +------resume------+

    NOT WITHDRAWING --start--> WITHDRAWING --stop--> NOT WITHDRAWING

Two rules shape the reporting
-----------------------------
*Warn, do not forbid.* A reader may be building a plan out of order,
or may mean something the machine has not been taught. Every finding
here is a sentence, never a locked button.

*Say what state it was in.* "Invalid sequence" helps nobody. Each
finding names what the plan was doing at that month, because that is
what makes the fix obvious.

Kept free of Streamlit so the rules can be tested as arithmetic
rather than through a rendered page.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_RETIRE_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
)

# Contribution states.
NOT_INVESTING_STR: str = "not investing"
INVESTING_STR: str = "investing"
PAUSED_STR: str = "paused"

# Withdrawal states.
NOT_WITHDRAWING_STR: str = "not withdrawing"
WITHDRAWING_STR: str = "withdrawing"

CONTRIBUTION_MACHINE_STR: str = "contribution"
WITHDRAWAL_MACHINE_STR: str = "withdrawal"


@dataclass(frozen=True)
class PlanState:
    """What the plan is doing at one moment on the timeline."""

    contribution_str: str = NOT_INVESTING_STR
    withdrawal_str: str = NOT_WITHDRAWING_STR


@dataclass(frozen=True)
class Transition:
    """One event, the states it needs, and where it leads.

    Arguments:
        machine_str (str): Which machine the event drives.
        allowed_tuple (tuple): States it may be placed in.
        next_state_str (str): State it leaves behind. Empty means
            the event reads the state without changing it.
        needs_str (str): What is missing, in the reader's words.
    """

    machine_str: str
    allowed_tuple: tuple
    next_state_str: str
    needs_str: str


# Every event that cares what the plan is doing. Anything absent -
# a lump sum, a rebalance, a note, an inflation change - is valid
# whenever it is placed, and inventing a prerequisite for one of
# those would block the commonest ways a plan is built.
TRANSITION_DICT: dict = {
    EVENT_START_SIP_STR: Transition(
        CONTRIBUTION_MACHINE_STR,
        (NOT_INVESTING_STR,),
        INVESTING_STR,
        "money going in",
    ),
    EVENT_PAUSE_STR: Transition(
        CONTRIBUTION_MACHINE_STR,
        (INVESTING_STR,),
        PAUSED_STR,
        "money going in",
    ),
    EVENT_RESUME_STR: Transition(
        CONTRIBUTION_MACHINE_STR,
        (PAUSED_STR,),
        INVESTING_STR,
        "a pause",
    ),
    EVENT_RETIRE_STR: Transition(
        CONTRIBUTION_MACHINE_STR,
        (INVESTING_STR, PAUSED_STR),
        NOT_INVESTING_STR,
        "money going in",
    ),
    EVENT_CHANGE_SIP_STR: Transition(
        CONTRIBUTION_MACHINE_STR,
        (INVESTING_STR, PAUSED_STR),
        "",
        "money going in",
    ),
    EVENT_STEPUP_STR: Transition(
        CONTRIBUTION_MACHINE_STR,
        (INVESTING_STR, PAUSED_STR),
        "",
        "money going in",
    ),
    EVENT_WITHDRAW_STR: Transition(
        WITHDRAWAL_MACHINE_STR,
        (NOT_WITHDRAWING_STR,),
        WITHDRAWING_STR,
        "withdrawals",
    ),
    EVENT_STOP_WITHDRAW_STR: Transition(
        WITHDRAWAL_MACHINE_STR,
        (WITHDRAWING_STR,),
        NOT_WITHDRAWING_STR,
        "withdrawals",
    ),
}

# Within one month the order the reader typed events in should not
# decide whether the plan is coherent. Anything that enters a state
# is applied first, anything that leaves one last, so "start and
# step up in the same month" works whichever way round it was added.
ENTERS_STATE_INT: int = 0
NEUTRAL_INT: int = 1
LEAVES_STATE_INT: int = 2
PRECEDENCE_DICT: dict = {
    EVENT_START_SIP_STR: ENTERS_STATE_INT,
    EVENT_WITHDRAW_STR: ENTERS_STATE_INT,
    EVENT_RESUME_STR: ENTERS_STATE_INT,
    EVENT_PAUSE_STR: LEAVES_STATE_INT,
    EVENT_STOP_WITHDRAW_STR: LEAVES_STATE_INT,
    EVENT_RETIRE_STR: LEAVES_STATE_INT,
}


@dataclass(frozen=True)
class OrderFinding:
    """One thing about the order of events that will not work.

    Arguments:
        event_type_str (str): The event that cannot take effect.
        event_date (date): When it was placed.
        state_str (str): What the plan was doing at that moment.
        sentence_str (str): What is wrong and what would fix it.
    """

    event_type_str: str
    event_date: date
    state_str: str
    sentence_str: str


def _sort_key_tuple(event: TimelineEvent) -> tuple:
    """Date first, then whether the event enters or leaves a state."""
    return (
        event.event_date,
        PRECEDENCE_DICT.get(event.event_type_str, NEUTRAL_INT),
    )


def _read_state_str(state: PlanState, machine_str: str) -> str:
    """The current state of one machine."""
    if machine_str == WITHDRAWAL_MACHINE_STR:
        return state.withdrawal_str
    return state.contribution_str


def _apply_state(
    state: PlanState,
    transition: Transition,
) -> PlanState:
    """Move one machine on, leaving the other untouched."""
    if not transition.next_state_str:
        return state
    if transition.machine_str == WITHDRAWAL_MACHINE_STR:
        return replace(
            state, withdrawal_str=transition.next_state_str
        )
    return replace(
        state, contribution_str=transition.next_state_str
    )


def _build_sentence_str(
    event: TimelineEvent,
    transition: Transition,
    state_str: str,
) -> str:
    """Say what the plan was doing, and what would fix it."""
    if state_str in (INVESTING_STR, WITHDRAWING_STR, PAUSED_STR):
        return (
            f"**{event.event_type_str}** in "
            f"{event.event_date:%B %Y} cannot happen: by then the "
            f"plan is already {state_str}. Remove this one, or "
            "move it to a month where it makes a difference. Left "
            "as it is, it changes nothing."
        )
    return (
        f"**{event.event_type_str}** in "
        f"{event.event_date:%B %Y} has nothing to act on: the plan "
        f"is {state_str} by then, so there is no "
        f"{transition.needs_str} for it to change. Add that in an "
        "earlier month, or move this event later. Left as it is, "
        "this event changes nothing."
    )


def find_order_finding_list(
    event_list: list[TimelineEvent],
) -> list[OrderFinding]:
    """Walk the timeline and report every event the state forbids.

    Brief:
        One pass, in date order, through both machines at once. An
        event that cannot be applied is reported and the state is
        left alone, so one mistake does not cascade into a report
        blaming every event after it.

    Arguments:
        event_list (List[TimelineEvent]): The timeline.

    Returns:
        List[OrderFinding]: Findings, in date order. Empty when
            every event lands in a state that allows it.

    Warning:
        Reports rather than repairs. Nothing here edits a plan, and
        no caller may treat a finding as grounds for refusing one.
    """
    state = PlanState()
    finding_list: list[OrderFinding] = []
    for event in sorted(event_list, key=_sort_key_tuple):
        transition = TRANSITION_DICT.get(event.event_type_str)
        if transition is None:
            continue
        state_str = _read_state_str(state, transition.machine_str)
        if state_str in transition.allowed_tuple:
            state = _apply_state(state, transition)
            continue
        finding_list.append(
            OrderFinding(
                event.event_type_str,
                event.event_date,
                state_str,
                _build_sentence_str(event, transition, state_str),
            )
        )
    return finding_list


def describe_prospective_str(
    event: TimelineEvent,
    event_list: list[TimelineEvent],
) -> str:
    """Warn before an event is added, not after.

    Brief:
        Asks the same question of a plan that does not exist yet.
        Built by running the whole check over the timeline plus the
        candidate, so a reader learns the start is missing while
        they are still looking at the button.

    Arguments:
        event (TimelineEvent): Event about to be placed.
        event_list (List[TimelineEvent]): The timeline as it is.

    Returns:
        str: A warning sentence, or empty when the event is fine.

    Warning:
        Reports only on the candidate. An event already on the rail
        that the candidate happens to invalidate is left to the
        plan-wide check, which is what the rail renders.
    """
    for finding in find_order_finding_list(
        [*event_list, event]
    ):
        if (
            finding.event_type_str == event.event_type_str
            and finding.event_date == event.event_date
        ):
            return finding.sentence_str
    return ""
