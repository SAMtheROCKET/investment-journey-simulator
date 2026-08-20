"""Which events can follow which.

The engine never complains about an impossible order. A pause with
no SIP to pause compiles perfectly and then does nothing, which is
the worst failure a planning tool has: the reader believes they
modelled a career break, and the figure they are shown is the figure
for a plan that never took one.

These hold that shut, and hold shut the opposite mistake too - the
checker must not invent problems, or a reader building a plan out of
order gets shouted at for no reason.
"""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.event_order import (
    INVESTING_STR,
    describe_prospective_str,
    find_order_finding_list,
)
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_STR,
    EVENT_NOTE_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
)

START_DATE: date = date(2026, 1, 1)


def at(year_int: int, event_type_str: str) -> TimelineEvent:
    """One event, in January of the given year."""
    return TimelineEvent(event_type_str, date(year_int, 1, 1))


def test_a_pause_with_no_sip_is_reported():
    """The case that started this: a break from nothing."""
    finding_list = find_order_finding_list(
        [at(2030, EVENT_PAUSE_STR)]
    )
    assert len(finding_list) == 1
    assert finding_list[0].event_type_str == EVENT_PAUSE_STR
    assert "money going in" in finding_list[0].sentence_str


def test_a_pause_after_a_sip_is_fine():
    """The ordinary case must stay silent."""
    assert (
        find_order_finding_list(
            [
                at(2026, EVENT_START_SIP_STR),
                at(2030, EVENT_PAUSE_STR),
            ]
        )
        == []
    )


def test_a_pause_before_its_sip_is_reported():
    """Order matters, not merely presence.

    A SIP starting in 2030 cannot be paused in 2028.
    """
    finding_list = find_order_finding_list(
        [
            at(2030, EVENT_START_SIP_STR),
            at(2028, EVENT_PAUSE_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].event_type_str == EVENT_PAUSE_STR


def test_stopping_withdrawals_that_never_started_is_reported():
    """The second case the reader named."""
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2040, EVENT_STOP_WITHDRAW_STR),
        ]
    )
    assert len(finding_list) == 1
    assert "withdrawals" in finding_list[0].sentence_str


def test_stopping_withdrawals_after_starting_them_is_fine():
    """And the same pair in the right order is silent."""
    assert (
        find_order_finding_list(
            [
                at(2026, EVENT_START_SIP_STR),
                at(2040, EVENT_WITHDRAW_STR),
                at(2045, EVENT_STOP_WITHDRAW_STR),
            ]
        )
        == []
    )


def test_resuming_without_a_pause_is_reported():
    """Resume means resume something.

    The finding names the state rather than the missing event,
    because contributions are running at that point: the problem is
    not that a pause is absent from the history but that the plan
    is not paused now.
    """
    finding_list = find_order_finding_list(
        [
            at(2026, EVENT_START_SIP_STR),
            at(2030, EVENT_RESUME_STR),
        ]
    )
    assert len(finding_list) == 1
    assert finding_list[0].state_str == INVESTING_STR
    assert "already investing" in finding_list[0].sentence_str


def test_a_step_up_needs_something_to_step_up():
    """Raising an instalment that does not exist does nothing."""
    assert find_order_finding_list([at(2026, EVENT_STEPUP_STR)])


def test_a_lump_sum_stands_on_its_own():
    """It requires nothing, and must never be flagged.

    Inventing a prerequisite here would block the commonest way a
    reader adds money to a plan.
    """
    assert (
        find_order_finding_list([at(2030, EVENT_LUMPSUM_STR)]) == []
    )


def test_a_note_is_never_flagged():
    """Annotations touch no money and gate nothing."""
    assert find_order_finding_list([at(2030, EVENT_NOTE_STR)]) == []


def test_an_empty_timeline_is_not_a_problem():
    """A plan nobody has built yet is not a broken plan."""
    assert find_order_finding_list([]) == []


def test_findings_come_back_in_date_order():
    """So the reader fixes the earliest cause first."""
    finding_list = find_order_finding_list(
        [
            at(2040, EVENT_STOP_WITHDRAW_STR),
            at(2030, EVENT_PAUSE_STR),
        ]
    )
    assert [finding.event_date for finding in finding_list] == [
        date(2030, 1, 1),
        date(2040, 1, 1),
    ]


def test_a_same_month_start_satisfies_the_event_that_needs_it():
    """Unusual is not impossible.

    Starting a SIP and stepping it up in the same month is odd, and
    this module warns about what cannot work rather than about what
    somebody would not normally do.
    """
    assert (
        find_order_finding_list(
            [
                at(2026, EVENT_START_SIP_STR),
                at(2026, EVENT_STEPUP_STR),
            ]
        )
        == []
    )


def test_the_prospective_check_warns_before_the_event_exists():
    """A reader learns while still looking at the button."""
    sentence_str = describe_prospective_str(
        at(2030, EVENT_PAUSE_STR), []
    )
    assert "money going in" in sentence_str


def test_the_prospective_check_stays_quiet_when_it_should():
    """No warning when the plan already supports the event."""
    assert (
        describe_prospective_str(
            at(2030, EVENT_PAUSE_STR),
            [at(2026, EVENT_START_SIP_STR)],
        )
        == ""
    )


def test_adding_the_missing_start_clears_the_finding():
    """The finding is about the plan, not about the click order.

    A reader who places the pause first and the start afterwards
    must end up with a clean timeline, without re-ordering by hand.
    """
    broken_list = [at(2030, EVENT_PAUSE_STR)]
    assert find_order_finding_list(broken_list)
    assert (
        find_order_finding_list(
            [*broken_list, at(2026, EVENT_START_SIP_STR)]
        )
        == []
    )
