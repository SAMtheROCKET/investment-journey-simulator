"""Two things happening in one month, counted.

Four boundary faults came out of this family in a single week: a
resume month that did not pay, a withdrawal stop that swallowed the
start after it, and two charts drawing a gap a month short. Each
had the same shape - an inclusive end read as an exclusive one, or
the reverse - and each passed every test that asked only whether
something happened rather than how much or how many.

So these count. A test that asserts a pause occurred cannot tell a
two-year pause from a two-year-and-one-month pause, and the second
is a missing instalment plus every rupee it would have earned.

Everything here is a convention rather than a truth, which is why
it is written down: a reader who disagrees should be able to find
the decision, and a change to it should break a test rather than
quietly move somebody's retirement figure.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_STR,
    EVENT_LUMPSUM_WITHDRAW_STR,
    EVENT_PAUSE_STR,
    EVENT_REBALANCE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_ALL_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
)
from investment_journey_simulator.timeline_app import build_fund_list

PLAN_START_DATE: date = date(2026, 1, 1)
HORIZON_YEARS_INT: int = 20
MONTHLY_FLOAT: float = 10000.0


def build_start_event() -> TimelineEvent:
    """Ten thousand a month from the first month."""
    return TimelineEvent(
        EVENT_START_SIP_STR, PLAN_START_DATE, MONTHLY_FLOAT
    )


def build_single_free_fund_list() -> list:
    """One fund, no tax, so an effect can be isolated."""
    return [
        build_test_fund(
            name_str="Equity",
            short_term_tax_percent_float=0.0,
            long_term_tax_percent_float=0.0,
            exemption_amount_float=0.0,
        )
    ]


def run_plan(event_list: list, fund_list: list | None = None):
    """Compile a timeline, run it, and index it by month."""
    scenario = PlanScenario(
        plan=TimelinePlan(
            PLAN_START_DATE, HORIZON_YEARS_INT, event_list
        ),
        fund_list=(
            fund_list
            if fund_list is not None
            else build_fund_list(60.0, 12.0, 0.0)
        ),
    )
    compiled = compile_scenario(scenario)
    result = PortfolioSimulator(
        compiled.fund_list, compiled.settings
    ).run()
    return result, {
        snapshot.month_date: snapshot
        for snapshot in result.monthly_snapshots_list
    }


# ------------------------------------------------------------------
# A step-up meeting a pause.
# ------------------------------------------------------------------
def test_the_escalation_clock_runs_through_a_pause():
    """A break does not reset what the instalment had grown to.

    REFERENCE: G1-ANALYTIC. Five anniversaries pass between the
    start and the resume, two of them while nothing is being paid.
    A step-up that paused with the money would quietly put the
    reader back on a smaller instalment for the rest of their life.
    """
    _result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(
                EVENT_STEPUP_STR,
                PLAN_START_DATE,
                percent_float=10.0,
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
        ]
    )
    assert month_dict[
        date(2031, 1, 1)
    ].monthly_sip_float == pytest.approx(
        MONTHLY_FLOAT * 1.1**5
    )


def test_a_step_up_placed_on_a_resume_month_raises_it_at_once():
    """The month a plan restarts can also change its shape.

    REFERENCE: G4-SYNTHETIC. A step-up event dates the *first*
    increase rather than starting a clock towards one, which is
    the same convention `test_delayed_first_stepup_holds_the
    _instalment` holds from the other side: a first step dated at
    month eighteen means a twelve-month run never escalates.

    So placing one on the resume month raises the instalment that
    month, and again a year later.
    """
    _result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
            TimelineEvent(
                EVENT_STEPUP_STR,
                date(2031, 1, 1),
                percent_float=10.0,
            ),
        ]
    )
    assert month_dict[
        date(2031, 1, 1)
    ].monthly_sip_float == pytest.approx(MONTHLY_FLOAT * 1.1)
    assert month_dict[
        date(2032, 1, 1)
    ].monthly_sip_float == pytest.approx(MONTHLY_FLOAT * 1.1**2)


def test_a_withdrawal_may_begin_the_month_a_pause_lifts():
    """Both flows can start in one month, in either direction.

    REFERENCE: G4-SYNTHETIC.
    """
    _result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
            TimelineEvent(
                EVENT_WITHDRAW_STR, date(2031, 1, 1), 5000.0
            ),
        ]
    )
    snapshot = month_dict[date(2031, 1, 1)]
    assert snapshot.monthly_sip_float > 0.0
    assert snapshot.monthly_withdrawal_float == pytest.approx(
        5000.0
    )


def test_a_fund_starting_inside_a_pause_stays_silent():
    """A pause is about the plan, not about one fund's calendar.

    REFERENCE: G4-SYNTHETIC. A fund whose own start date falls in
    a paused stretch waits like everything else.
    """
    fund_list = build_fund_list(60.0, 12.0, 0.0)
    fund_list[1] = replace(
        fund_list[1], start_date=date(2029, 6, 1)
    )
    _result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
        ],
        fund_list,
    )
    assert month_dict[date(2029, 6, 1)].monthly_sip_float == 0.0
    assert month_dict[date(2031, 1, 1)].monthly_sip_float > 0.0


# ------------------------------------------------------------------
# Money in and money out of one month.
# ------------------------------------------------------------------
def test_a_lump_in_and_out_of_one_month_keeps_that_month_growth():
    """Money invested for a month earns that month.

    REFERENCE: G1-ANALYTIC. Five lakh in and five lakh out of the
    same month is not a no-op: the money was in the fund while the
    month happened, so it earned the month, and the residue is
    exactly one month of growth compounded to the horizon.

    Worth stating because it looks at first like an error. It is
    the same rule that pays an instalment its first month, and the
    independently written simulator agrees to the paisa.

    Run on one fund, because with two the answer moves for a
    second reason worth knowing: money in with no fund named is
    split by *target weight*, money out with no fund named is
    taken *pro rata by value*. Both rules are sensible on their
    own, and together they nudge a drifted portfolio back toward
    its target - so an in-and-out can leave the mix, and the final
    figure, slightly different.
    """
    fund_list = build_single_free_fund_list()
    plain_result, _plain_dict = run_plan(
        [build_start_event()], fund_list
    )
    both_result, _both_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(
                EVENT_LUMPSUM_STR, date(2031, 1, 1), 500000.0
            ),
            TimelineEvent(
                EVENT_LUMPSUM_WITHDRAW_STR,
                date(2031, 1, 1),
                500000.0,
            ),
        ],
        fund_list,
    )
    monthly_rate_float = (1.12) ** (1.0 / 12.0) - 1.0
    remaining_months_int = 20 * 12 - 60 - 1
    expected_float = (
        500000.0
        * monthly_rate_float
        * (1.0 + monthly_rate_float) ** remaining_months_int
    )
    assert (
        both_result.ending_value_float
        - plain_result.ending_value_float
    ) == pytest.approx(expected_float, rel=1e-9)


def test_a_lump_withdrawal_on_a_rebalancing_month_is_paid():
    """Two sales in one month, from one corpus.

    REFERENCE: G4-SYNTHETIC. The rebalance sells and rebuys; the
    withdrawal sells and pays out. Neither may starve the other.
    """
    result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(EVENT_REBALANCE_STR, date(2032, 1, 1)),
            TimelineEvent(
                EVENT_LUMPSUM_WITHDRAW_STR,
                date(2032, 1, 1),
                200000.0,
            ),
        ]
    )
    snapshot = month_dict[date(2032, 1, 1)]
    assert snapshot.monthly_withdrawal_float == pytest.approx(
        200000.0
    )
    assert snapshot.unmet_withdrawal_float == pytest.approx(0.0)
    assert result.rebalance_events_list


# ------------------------------------------------------------------
# Closing on an awkward month.
# ------------------------------------------------------------------
def test_a_plan_closed_in_its_first_month_pays_that_month_in():
    """The instalment lands, then everything is sold.

    REFERENCE: G4-SYNTHETIC. The degenerate case: a plan that ends
    where it began still ran for one month.
    """
    _result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(
                EVENT_WITHDRAW_ALL_STR, PLAN_START_DATE
            ),
        ]
    )
    opening_snapshot = month_dict[PLAN_START_DATE]
    assert opening_snapshot.monthly_withdrawal_float > 0.0
    assert opening_snapshot.portfolio_value_float == 0.0
    assert (
        month_dict[date(2045, 12, 1)].portfolio_value_float == 0.0
    )


def test_a_plan_closed_on_its_last_month_still_sells():
    """Closing on the final month is not the same as not closing.

    REFERENCE: G4-SYNTHETIC. The corpus is realised rather than
    left standing, which is what makes the tax real.
    """
    result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(
                EVENT_WITHDRAW_ALL_STR, date(2045, 12, 1)
            ),
        ]
    )
    assert result.ending_value_float == 0.0
    assert (
        month_dict[date(2045, 12, 1)].monthly_withdrawal_float
        > 0.0
    )


def test_a_pause_and_a_closure_in_one_month():
    """The pause silences the month; the closure ends the plan.

    REFERENCE: G4-SYNTHETIC. Both apply, in that order, and the
    plan holds nothing afterwards.
    """
    _result, month_dict = run_plan(
        [
            build_start_event(),
            TimelineEvent(EVENT_PAUSE_STR, date(2036, 1, 1)),
            TimelineEvent(
                EVENT_WITHDRAW_ALL_STR, date(2036, 1, 1)
            ),
        ]
    )
    snapshot = month_dict[date(2036, 1, 1)]
    assert snapshot.monthly_sip_float == 0.0
    assert snapshot.monthly_withdrawal_float > 0.0
    assert snapshot.portfolio_value_float == 0.0
