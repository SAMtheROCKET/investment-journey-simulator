"""What the plan is doing, not what has happened to it.

An existence check asks "did a pause ever happen?" A state machine
asks "is the plan paused right now?" Every case in this file passed
the existence check and should not have: each one has the required
event somewhere in its history and is still impossible at the moment
it lands.

That difference is the whole reason `event_order.py` walks the
timeline instead of searching it.
"""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.event_order import (
    INVESTING_STR,
    NOT_INVESTING_STR,
    NOT_WITHDRAWING_STR,
    PAUSED_STR,
    WITHDRAWING_STR,
    describe_prospective_str,
    find_order_finding_list,
)
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_RETIRE_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
)


def at(year_int: int, event_type_str: str) -> TimelineEvent:
    """One event, in January of the given year."""
    return TimelineEvent(event_type_str, date(year_int, 1, 1))


def test_a_second_resume_after_resuming_is_reported():
    """The case that motivated the rewrite.

    Start, pause, resume, resume. The second resume has a pause
    behind it, so an existence check passes it - but contributions
    are already running by then and it does nothing.
    """
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2030, EVENT_PAUSE_STR),
            at(2032, EVENT_RESUME_STR),
            at(2034, EVENT_RESUME_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].event_date == date(2034, 1, 1)
    assert finding_list[0].state_str == INVESTING_STR


def test_a_second_pause_while_paused_is_reported():
    """Pausing what is already paused changes nothing."""
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2030, EVENT_PAUSE_STR),
            at(2032, EVENT_PAUSE_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].state_str == PAUSED_STR


def test_a_second_start_while_investing_is_reported():
    """Two starts is a change of amount, not a second start."""
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2030, EVENT_START_SIP_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].state_str == INVESTING_STR


def test_a_second_withdrawal_stop_is_reported():
    """The same hole on the withdrawal machine."""
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2040, EVENT_WITHDRAW_STR),
            at(2042, EVENT_STOP_WITHDRAW_STR),
            at(2044, EVENT_STOP_WITHDRAW_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].state_str == NOT_WITHDRAWING_STR


def test_starting_withdrawals_twice_is_reported():
    """Already withdrawing is not a state you can start from."""
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2040, EVENT_WITHDRAW_STR),
            at(2042, EVENT_WITHDRAW_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].state_str == WITHDRAWING_STR


def test_a_full_pause_cycle_is_silent():
    """The ordinary shape must stay quiet."""
    assert (
        find_order_finding_list(
            [
                at(2026, EVENT_START_SIP_STR),
                at(2030, EVENT_PAUSE_STR),
                at(2032, EVENT_RESUME_STR),
            ]
        )
        == []
    )


def test_withdrawals_may_stop_and_start_again():
    """Cycling a machine is not repeating a transition.

    Stop, then start again, is a real thing to plan. The state
    machine allows it where a "seen it already" check would have to
    special-case it.
    """
    assert (
        find_order_finding_list(
            [
                at(2026, EVENT_START_SIP_STR),
                at(2040, EVENT_WITHDRAW_STR),
                at(2042, EVENT_STOP_WITHDRAW_STR),
                at(2044, EVENT_WITHDRAW_STR),
            ]
        )
        == []
    )


def test_the_two_machines_do_not_interfere():
    """Contributions and withdrawals are independent.

    Withdrawing does not pause a SIP and pausing a SIP does not
    stop a withdrawal, so a plan doing both at once is fine.
    """
    assert (
        find_order_finding_list(
            [
                at(2026, EVENT_START_SIP_STR),
                at(2040, EVENT_WITHDRAW_STR),
                at(2042, EVENT_PAUSE_STR),
                at(2044, EVENT_RESUME_STR),
                at(2046, EVENT_STOP_WITHDRAW_STR),
            ]
        )
        == []
    )


def test_retiring_stops_contributions():
    """Retire leaves the contribution machine off.

    A pause placed after it has nothing to pause, which an
    existence check could never notice: the start is right there in
    the history.
    """
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2040, EVENT_RETIRE_STR),
            at(2042, EVENT_PAUSE_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].state_str == NOT_INVESTING_STR


def test_one_bad_event_does_not_blame_the_rest():
    """A single mistake must not cascade.

    The state is left alone when an event is refused, so everything
    after it is judged against the plan the reader meant.
    """
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2028, EVENT_RESUME_STR),
            at(2030, EVENT_PAUSE_STR),
            at(2032, EVENT_RESUME_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].event_date == date(2028, 1, 1)


def test_month_order_does_not_depend_on_typing_order():
    """Same month, either order, same verdict.

    Events that enter a state are applied before those that leave
    one, so a start and a step-up placed in the same month work
    whichever way round the reader added them.
    """
    for event_list in (
        [at(2026, EVENT_START_SIP_STR), at(2026, EVENT_STEPUP_STR)],
        [at(2026, EVENT_STEPUP_STR), at(2026, EVENT_START_SIP_STR)],
    ):
        assert find_order_finding_list(event_list) == []


def test_the_prospective_check_uses_the_state_too():
    """The warning before the button obeys the same machine."""
    running_list = [
        at(2026, EVENT_START_SIP_STR),
        at(2030, EVENT_PAUSE_STR),
        at(2032, EVENT_RESUME_STR),
    ]
    assert describe_prospective_str(
        at(2034, EVENT_RESUME_STR), running_list
    )
    assert (
        describe_prospective_str(
            at(2034, EVENT_PAUSE_STR), running_list
        )
        == ""
    )
