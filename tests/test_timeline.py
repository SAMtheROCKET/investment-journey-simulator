"""Timeline plan compilation and cross-checks against the engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
    REBALANCE_TRIGGER_DATED_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODE_OFF_STR,
    SURCHARGE_MODE_SLAB_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import (
    PauseRange,
    PauseSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.timeline import (
    EVENT_ANNOTATION_TUPLE,
    EVENT_CHANGE_SIP_STR,
    EVENT_EXPLANATION_DICT,
    EVENT_GROUP_TUPLE,
    EVENT_INCOME_STR,
    EVENT_LUMPSUM_STR,
    EVENT_NOTE_STR,
    EVENT_PAUSE_STR,
    EVENT_REBALANCE_STR,
    EVENT_RESUME_STR,
    EVENT_RETIRE_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_TYPE_TUPLE,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
    apply_plan_to_fund,
    compile_settings,
    resolve_monthly_amount_float,
    resolve_one_off_total_float,
)

START_DATE: date = date(2026, 1, 1)


def build_plan(
    event_list: list[TimelineEvent],
    horizon_years_int: int = 20,
) -> TimelinePlan:
    """Build a plan starting on the shared reference date.

    REFERENCE: harness only.
    """
    return TimelinePlan(START_DATE, horizon_years_int, event_list)


def run_timeline_plan(
    plan: TimelinePlan,
    expense_percent_float: float = 0.0,
):
    """Run a timeline plan and return the whole result.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(
        [
            apply_plan_to_fund(
                build_test_fund(
                    "Equity",
                    0.0,
                    12.0,
                    expense_percent_float,
                    START_DATE,
                ),
                plan,
            )
        ],
        compile_settings(plan),
    ).run()


def run_timeline_plan_float(
    plan: TimelinePlan,
    expense_percent_float: float = 0.0,
) -> float:
    """Value a timeline plan through the engine.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(
        [
            apply_plan_to_fund(
                build_test_fund(
                    "Equity",
                    0.0,
                    12.0,
                    expense_percent_float,
                    START_DATE,
                ),
                plan,
            )
        ],
        compile_settings(plan),
    ).run().ending_value_float


def test_every_event_type_explains_itself() -> None:
    """No event may be offered without an explanation.

    REFERENCE: G4-SYNTHETIC. The interface shows the explanation
    before the reader commits to an event, so a missing one would
    leave a silent option in the menu.
    """
    for event_type_str in EVENT_TYPE_TUPLE:
        assert event_type_str in EVENT_EXPLANATION_DICT
        assert len(EVENT_EXPLANATION_DICT[event_type_str]) > 20


def test_events_are_read_in_calendar_order() -> None:
    """Order of entry must not change the compiled plan.

    REFERENCE: G4-SYNTHETIC. Events are added by clicking, in
    whatever order the user thinks of them.
    """
    late_event = TimelineEvent(EVENT_PAUSE_STR, date(2030, 1, 1))
    early_event = TimelineEvent(
        EVENT_START_SIP_STR, START_DATE, amount_float=1000.0
    )
    forward_plan = build_plan([early_event, late_event])
    reversed_plan = build_plan([late_event, early_event])
    assert (
        forward_plan.ordered_event_list
        == reversed_plan.ordered_event_list
    )


def test_the_opening_amount_comes_from_the_first_event() -> None:
    """The instalment is whatever the first money event says.

    REFERENCE: G4-SYNTHETIC.
    """
    assert resolve_monthly_amount_float(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    START_DATE,
                    amount_float=7500.0,
                )
            ]
        )
    ) == pytest.approx(7500.0)


def test_a_plan_with_no_money_event_invests_nothing() -> None:
    """An empty timeline must not invent an instalment.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert resolve_monthly_amount_float(
        build_plan([])
    ) == pytest.approx(0.0)


def test_one_off_investments_are_totalled_for_display() -> None:
    """The reported total must cover every lump sum.

    REFERENCE: G4-SYNTHETIC. This figure is shown to the reader;
    the engine is given the dates, not the total.
    """
    assert resolve_one_off_total_float(
        build_plan(
            [
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    START_DATE,
                    amount_float=50000.0,
                ),
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    date(2028, 6, 1),
                    amount_float=25000.0,
                ),
            ]
        )
    ) == pytest.approx(75000.0)


def test_a_pause_and_resume_become_one_window() -> None:
    """A pause closed by a resume compiles to a bounded range.

    REFERENCE: G4-SYNTHETIC. This is the translation the whole
    timeline idea rests on, and the month it ends on is the whole
    subtlety. Both ends of a range are inclusive, so a pause in
    January 2029 resumed in January 2030 covers 2029 exactly: the
    resume month pays, and the twelve before it do not.

    Ending the range *on* the resume was the original reading. It
    made every gap a month too long, so every plan carrying one
    was a payment short - about a fifth of a per cent over twenty
    years, which looks like rounding and is not.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
                TimelineEvent(EVENT_RESUME_STR, date(2030, 1, 1)),
            ]
        )
    )
    assert settings.pauses.pause_ranges_list == [
        PauseRange(
            date(2029, 1, 1), date(2029, 12, 1), PAUSE_SCOPE_SIP_STR
        )
    ]


def test_a_pause_without_a_resume_runs_to_the_horizon() -> None:
    """Stopping and never restarting is a valid plan.

    REFERENCE: G4-SYNTHETIC. The window has to close somewhere,
    and the end of the plan is the only honest choice.
    """
    plan = build_plan(
        [TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1))],
        horizon_years_int=10,
    )
    pause_range_list = compile_settings(plan).pauses.pause_ranges_list
    assert len(pause_range_list) == 1
    assert pause_range_list[0].end_date == plan.end_date


def test_a_resume_with_no_pause_is_ignored() -> None:
    """An orphan resume must not create a window.

    REFERENCE: G4-SYNTHETIC. Guard branch; events can be added in
    any order and deleted in any order.
    """
    settings = compile_settings(
        build_plan(
            [TimelineEvent(EVENT_RESUME_STR, date(2029, 1, 1))]
        )
    )
    assert settings.pauses.pause_ranges_list == []


def test_a_step_up_event_becomes_a_step_up_rule() -> None:
    """The escalation starts in the month of its event.

    REFERENCE: G4-SYNTHETIC. A step-up added in year three must
    not silently backdate itself to the start.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_STEPUP_STR,
                    date(2029, 1, 1),
                    percent_float=10.0,
                )
            ]
        )
    )
    assert settings.stepup.mode_str == STEPUP_MODE_GLOBAL_STR
    assert settings.stepup.global_stepup_percent_float == 10.0
    assert settings.stepup.first_stepup_month_index_int == 36


def test_a_plan_without_a_step_up_has_none() -> None:
    """No step-up event means no escalation.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert (
        compile_settings(build_plan([])).stepup.mode_str
        == STEPUP_MODE_OFF_STR
    )


def test_retiring_both_pauses_and_withdraws() -> None:
    """Retirement is a pause and a withdrawal in one event.

    REFERENCE: G4-SYNTHETIC. Modelling it as a single event is
    the point: nobody thinks of retiring as two settings.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_RETIRE_STR,
                    date(2046, 1, 1),
                    amount_float=60000.0,
                )
            ]
        )
    )
    assert settings.withdrawal.is_enabled_bool is True
    assert settings.withdrawal.fixed_amount_float == 60000.0
    assert len(settings.pauses.pause_ranges_list) == 1


def test_an_event_before_the_start_clamps_to_month_zero() -> None:
    """A date earlier than the plan cannot fall off the grid.

    REFERENCE: G4-SYNTHETIC. Guard branch; a negative month index
    would silently corrupt the schedule.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_WITHDRAW_STR,
                    date(2020, 1, 1),
                    amount_float=1000.0,
                )
            ]
        )
    )
    assert settings.withdrawal.start_month_index_int == 0


def test_the_timeline_agrees_with_the_classic_dashboard() -> None:
    """Both front ends must value the same plan identically.

    REFERENCE: G1-ANALYTIC. This is the claim that justifies
    having two interfaces at all: the timeline is a translation
    layer, not a second implementation. A plain plan expressed as
    events must produce exactly the corpus the classic settings
    produce.
    """
    monthly_amount_float = 25000.0
    horizon_years_int = 15
    timeline_float = run_timeline_plan_float(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    START_DATE,
                    amount_float=monthly_amount_float,
                )
            ],
            horizon_years_int,
        ),
        0.5,
    )
    classic_float = PortfolioSimulator(
        [
            build_test_fund(
                "Equity",
                monthly_amount_float,
                12.0,
                0.5,
                START_DATE,
            )
        ],
        build_test_settings(
            horizon_years_int=horizon_years_int,
            portfolio_start_date=START_DATE,
        ),
    ).run().ending_value_float
    assert timeline_float == pytest.approx(classic_float)


def test_a_paused_timeline_matches_the_classic_pause() -> None:
    """A timeline pause equals the same pause typed as settings.

    REFERENCE: G1-ANALYTIC. Extends the agreement check to the
    one translation with real logic behind it.

    The two notations name the same window differently, and that
    is the translation being tested. Settings carry a range whose
    last month is silent. The timeline carries a *resume*, and a
    resume is the month money starts again - so it sits on the
    month after the range ends.
    """
    pause_start_date = date(2029, 1, 1)
    last_silent_date = date(2030, 12, 1)
    resume_date = date(2031, 1, 1)
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=10000.0
            ),
            TimelineEvent(EVENT_PAUSE_STR, pause_start_date),
            TimelineEvent(EVENT_RESUME_STR, resume_date),
        ],
        15,
    )
    timeline_float = run_timeline_plan_float(plan)
    classic_float = PortfolioSimulator(
        [
            build_test_fund(
                "Equity", 10000.0, 12.0, 0.0, START_DATE
            )
        ],
        build_test_settings(
            horizon_years_int=15,
            portfolio_start_date=START_DATE,
            pauses=PauseSettings(
                pause_ranges_list=[
                    PauseRange(
                        pause_start_date,
                        last_silent_date,
                        PAUSE_SCOPE_SIP_STR,
                    )
                ]
            ),
        ),
    ).run().ending_value_float
    assert timeline_float == pytest.approx(classic_float)


def test_unused_settings_default_to_off() -> None:
    """A bare timeline switches nothing on by accident.

    REFERENCE: G4-SYNTHETIC. Every optional feature must default
    off, or a simple plan would silently rebalance or withdraw.
    """
    settings = compile_settings(build_plan([]))
    assert settings.withdrawal == WithdrawalSettings()
    assert settings.stepup == StepUpSettings()
    assert settings.rebalance.is_enabled_bool is False


# ------------------------------------------------------------------
# Many events, anywhere on the timeline
# ------------------------------------------------------------------
def test_a_lump_sum_is_dated_not_collapsed_to_the_start() -> None:
    """A bonus in year eight must not compound from year zero.

    REFERENCE: G4-SYNTHETIC. The first version summed every lump
    sum into month zero, which silently overstated the corpus.
    This asserts the flaw cannot come back.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    date(2034, 1, 1),
                    amount_float=500000.0,
                )
            ]
        )
    )
    assert len(settings.one_off_contributions_list) == 1
    assert (
        settings.one_off_contributions_list[0].month_index_int == 96
    )


def test_a_dated_lump_sum_is_worth_less_than_an_opening_one(
) -> None:
    """The correction has to change the answer, not just the data.

    REFERENCE: G1-ANALYTIC. The same money invested eight years
    later must be worth exactly (1.12)^-8 of the opening version.
    """
    early_float = run_timeline_plan_float(
        build_plan(
            [
                TimelineEvent(
                    EVENT_LUMPSUM_STR, START_DATE, amount_float=1e6
                )
            ]
        )
    )
    late_float = run_timeline_plan_float(
        build_plan(
            [
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    date(2034, 1, 1),
                    amount_float=1e6,
                )
            ]
        )
    )
    assert late_float == pytest.approx(early_float / 1.12**8)


def test_every_instalment_change_becomes_its_own_override() -> None:
    """A plan may change its mind as often as a life does.

    REFERENCE: G4-SYNTHETIC. The first version read only the first
    money event and silently ignored every later one.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR, START_DATE, amount_float=1e4
                ),
                TimelineEvent(
                    EVENT_CHANGE_SIP_STR,
                    date(2029, 1, 1),
                    amount_float=2e4,
                ),
                TimelineEvent(
                    EVENT_CHANGE_SIP_STR,
                    date(2032, 1, 1),
                    amount_float=5e3,
                ),
            ]
        )
    )
    assert [
        (override.month_index_int, override.amount_float)
        for override in settings.instalment_override_list
    ] == [(0, 10000.0), (36, 20000.0), (72, 5000.0)]


def test_investing_starts_only_when_the_timeline_says_so() -> None:
    """Three empty years must really be three empty years.

    REFERENCE: G4-SYNTHETIC. A start event in year three means the
    first three years contribute nothing at all, so the principal
    is twelve years of instalments, not fifteen.
    """
    result = run_timeline_plan(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    date(2029, 1, 1),
                    amount_float=1000.0,
                )
            ],
            15,
        )
    )
    assert result.ending_invested_float == pytest.approx(144000.0)


def test_many_events_can_share_one_month() -> None:
    """Several things may happen in the same month of a life.

    REFERENCE: G4-SYNTHETIC. A raise, a bonus and a step-up all
    landing in one month must each be honoured.
    """
    same_month_date = date(2029, 1, 1)
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR, START_DATE, amount_float=1e4
                ),
                TimelineEvent(
                    EVENT_CHANGE_SIP_STR,
                    same_month_date,
                    amount_float=2e4,
                ),
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    same_month_date,
                    amount_float=1e5,
                ),
                TimelineEvent(
                    EVENT_STEPUP_STR,
                    same_month_date,
                    percent_float=10.0,
                ),
            ]
        )
    )
    assert len(settings.instalment_override_list) == 2
    assert len(settings.one_off_contributions_list) == 1
    assert settings.stepup.global_stepup_percent_float == 10.0


def test_a_salary_event_switches_the_surcharge_to_slab_mode(
) -> None:
    """Declaring an income must make the surcharge follow it.

    REFERENCE: G4-SYNTHETIC. Income is dated by financial year,
    which is the unit the Income-tax Act works in.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_INCOME_STR,
                    date(2030, 6, 1),
                    amount_float=6_000_000.0,
                )
            ]
        )
    )
    assert settings.tax.surcharge_mode_str == SURCHARGE_MODE_SLAB_STR
    assert settings.tax.income_by_year_tuple == (
        (2030, 6_000_000.0),
    )


def test_a_plan_without_salary_leaves_the_tax_rules_alone() -> None:
    """Not mentioning income must not switch anything on.

    REFERENCE: G4-SYNTHETIC. Guard branch; a plan that says
    nothing about salary must behave exactly as it did before.
    """
    original_settings = TaxSettings(cess_percent_float=4.0)
    assert (
        compile_settings(build_plan([]), original_settings).tax
        is original_settings
    )


def test_a_later_raise_restarts_the_step_up_clock() -> None:
    """Changing the amount must not re-apply old escalations.

    REFERENCE: G4-SYNTHETIC. A step-up starting in the same month
    as the instalment has no delay, so the escalation origin and
    the step-up month coincide and the offset is zero.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR, START_DATE, amount_float=1e4
                ),
                TimelineEvent(
                    EVENT_STEPUP_STR, START_DATE, percent_float=10.0
                ),
            ]
        )
    )
    assert settings.stepup.first_stepup_month_index_int == 0


# ------------------------------------------------------------------
# Rebalance events
# ------------------------------------------------------------------
def build_two_fund_list() -> list:
    """Build a drifting 50/50 equity and debt portfolio.

    REFERENCE: harness only. The two returns differ so the mix
    genuinely drifts and a rebalance has work to do.
    """
    return [
        build_test_fund(
            "Equity",
            0.0,
            14.0,
            0.0,
            START_DATE,
            target_allocation_percent_float=50.0,
        ),
        build_test_fund(
            "Debt",
            0.0,
            7.0,
            0.0,
            START_DATE,
            target_allocation_percent_float=50.0,
        ),
    ]


def run_two_fund_plan(plan: TimelinePlan):
    """Run a timeline across the drifting two-fund portfolio.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(
        [
            apply_plan_to_fund(fund, plan)
            for fund in build_two_fund_list()
        ],
        compile_settings(plan),
    ).run()


def test_a_plan_without_a_rebalance_event_never_trades() -> None:
    """Rebalancing must stay off unless it was asked for.

    REFERENCE: G4-SYNTHETIC. Guard branch; a simple plan must not
    silently start realising gains.
    """
    settings = compile_settings(build_plan([]))
    assert settings.rebalance.is_enabled_bool is False
    assert settings.rebalance.rebalance_month_index_tuple == ()


def test_rebalance_events_compile_to_the_months_they_sit_on(
) -> None:
    """A rebalance placed by hand happens then and only then.

    REFERENCE: G4-SYNTHETIC. It is not a rule with an interval, so
    the compiler names the months rather than a frequency.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2029, 1, 1)
                ),
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2033, 7, 1)
                ),
            ]
        )
    )
    assert settings.rebalance.is_enabled_bool is True
    assert settings.rebalance.trigger_str == (
        REBALANCE_TRIGGER_DATED_STR
    )
    assert settings.rebalance.rebalance_month_index_tuple == (
        36,
        90,
    )


def test_two_rebalances_in_one_month_count_once() -> None:
    """Placing the same trade twice must not trade twice.

    REFERENCE: G4-SYNTHETIC. The months are a set, so a duplicate
    dot cannot double the tax.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2029, 1, 1)
                ),
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2029, 1, 1)
                ),
            ]
        )
    )
    assert settings.rebalance.rebalance_month_index_tuple == (36,)


def test_a_rebalance_event_actually_executes_a_trade() -> None:
    """The event has to move money, not just set a flag.

    REFERENCE: G4-SYNTHETIC. Equity at 14% outgrows debt at 7%, so
    by year three the mix has drifted and a rebalance must fire in
    exactly the month it was placed.
    """
    result = run_two_fund_plan(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR, START_DATE, amount_float=1e4
                ),
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2029, 1, 1)
                ),
            ]
        )
    )
    assert len(result.rebalance_events_list) == 1
    rebalance_event = result.rebalance_events_list[0]
    assert rebalance_event.month_date == date(2029, 1, 1)
    assert rebalance_event.trigger_reason_str == (
        REBALANCE_TRIGGER_DATED_STR
    )


def test_a_rebalance_pulls_the_mix_back_towards_target() -> None:
    """A trade that does not restore the target is not a rebalance.

    REFERENCE: G4-SYNTHETIC. Equity drifts above its 50% target;
    afterwards it must sit closer to 50 than it did before.
    """
    result = run_two_fund_plan(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR, START_DATE, amount_float=1e4
                ),
                TimelineEvent(
                    EVENT_REBALANCE_STR, date(2033, 1, 1)
                ),
            ]
        )
    )
    rebalance_event = result.rebalance_events_list[0]
    drift_before_float = abs(
        rebalance_event.weights_before_dict["Equity"] - 50.0
    )
    drift_after_float = abs(
        rebalance_event.weights_after_dict["Equity"] - 50.0
    )
    assert drift_before_float > 0.0
    assert drift_after_float < drift_before_float


def test_rebalancing_realises_gains_and_therefore_costs_tax(
) -> None:
    """Selling to rebalance is a transfer, and transfers are taxed.

    REFERENCE: G2-STATUTORY. The trade sells the overweight fund,
    which realises a gain. A rebalance reported as free would
    understate what the decision actually costs.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(EVENT_REBALANCE_STR, date(2033, 1, 1)),
        ]
    )
    taxed_fund_list = [
        replace(
            fund,
            exemption_amount_float=0.0,
            long_term_tax_percent_float=12.5,
            short_term_tax_percent_float=20.0,
        )
        for fund in build_two_fund_list()
    ]
    result = PortfolioSimulator(
        [
            apply_plan_to_fund(fund, plan)
            for fund in taxed_fund_list
        ],
        compile_settings(plan),
    ).run()
    assert result.rebalance_events_list[0].tax_amount_float > 0.0


# ------------------------------------------------------------------
# Stopping a withdrawal, and markers that change nothing
# ------------------------------------------------------------------
def test_stopping_a_withdrawal_pauses_the_withdrawal_side(
) -> None:
    """Ending an income is a withdrawal pause, not a new mechanism.

    REFERENCE: G4-SYNTHETIC. Expressing it through the engine's
    existing pause scope means nothing new has to be trusted.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_WITHDRAW_STR, START_DATE, amount_float=5e4
            ),
            TimelineEvent(
                EVENT_STOP_WITHDRAW_STR, date(2031, 1, 1)
            ),
        ],
        10,
    )
    pause_range_list = compile_settings(plan).pauses.pause_ranges_list
    assert len(pause_range_list) == 1
    assert pause_range_list[0].scope_str == PAUSE_SCOPE_WITHDRAWAL_STR
    assert pause_range_list[0].start_date == date(2031, 1, 1)
    assert pause_range_list[0].end_date == plan.end_date


def test_stopping_a_withdrawal_leaves_more_money_behind() -> None:
    """The event has to change the corpus, not just the settings.

    REFERENCE: G4-SYNTHETIC. Drawing an income for five years
    instead of ten must leave strictly more at the end.
    """
    event_list = [
        TimelineEvent(
            EVENT_START_SIP_STR, START_DATE, amount_float=1e4
        ),
        TimelineEvent(
            EVENT_WITHDRAW_STR, date(2028, 1, 1), amount_float=2e4
        ),
    ]
    without_stop_float = run_timeline_plan_float(
        build_plan(event_list, 10)
    )
    with_stop_float = run_timeline_plan_float(
        build_plan(
            [
                *event_list,
                TimelineEvent(
                    EVENT_STOP_WITHDRAW_STR, date(2031, 1, 1)
                ),
            ],
            10,
        )
    )
    assert with_stop_float > without_stop_float


def test_a_note_changes_nothing_at_all() -> None:
    """A marker on the story must not touch the money.

    REFERENCE: G1-ANALYTIC. The same plan with and without a note
    must value identically to the paisa, or the marker is lying
    about being cosmetic.
    """
    event_list = [
        TimelineEvent(
            EVENT_START_SIP_STR, START_DATE, amount_float=1e4
        )
    ]
    plain_float = run_timeline_plan_float(build_plan(event_list))
    annotated_float = run_timeline_plan_float(
        build_plan(
            [
                *event_list,
                TimelineEvent(
                    EVENT_NOTE_STR,
                    date(2030, 6, 1),
                    note_str="bought a house",
                ),
            ]
        )
    )
    assert annotated_float == pytest.approx(plain_float)


def test_a_note_is_declared_as_an_annotation() -> None:
    """The interface must be able to say a marker is cosmetic.

    REFERENCE: G4-SYNTHETIC. Listing it explicitly stops a reader
    assuming a dot on the rail moved their money.
    """
    assert EVENT_NOTE_STR in EVENT_ANNOTATION_TUPLE
    assert EVENT_START_SIP_STR not in EVENT_ANNOTATION_TUPLE


def test_every_event_appears_in_exactly_one_dropdown_group(
) -> None:
    """A menu that hides an event makes it unreachable.

    REFERENCE: G4-SYNTHETIC. Every event the compiler understands
    must be offered, and offered once.
    """
    grouped_list = [
        event_type_str
        for _, event_tuple in EVENT_GROUP_TUPLE
        for event_type_str in event_tuple
    ]
    assert sorted(grouped_list) == sorted(EVENT_TYPE_TUPLE)
    assert len(grouped_list) == len(set(grouped_list))


def test_every_event_in_the_menu_explains_itself() -> None:
    """An option with no explanation cannot be chosen confidently.

    REFERENCE: G4-SYNTHETIC. The hover text is the whole point of
    the palette, so a missing entry is a defect.
    """
    for event_type_str in EVENT_TYPE_TUPLE:
        assert EVENT_EXPLANATION_DICT.get(event_type_str)


# --- The month a gap starts and the month it ends -----------------
#
# A reader draws a gap by placing two events. What matters is that
# the months between them are exactly the months they meant, and an
# off-by-one here is invisible: it passes every test that asks only
# whether a pause happened, and costs one instalment plus its
# compounding, which reads as a rounding difference and is not one.


def count_paying_months_int(event_list: list, years_int: int) -> int:
    """How many months of a plan actually pay an instalment."""
    settings = compile_settings(build_plan(event_list, years_int))
    result = PortfolioSimulator(
        [build_test_fund("Equity", 10000.0, 12.0, 0.0, START_DATE)],
        settings,
    ).run()
    return sum(
        1
        for snapshot in result.monthly_snapshots_list
        if snapshot.monthly_sip_float > 0.0
    )


def test_a_pause_month_stops_and_a_resume_month_pays() -> None:
    """The two boundaries, stated in one place.

    REFERENCE: G4-SYNTHETIC. A pause placed on a month silences
    that month; a resume placed on a month pays it.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    START_DATE,
                    amount_float=10000.0,
                ),
                TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
                TimelineEvent(EVENT_RESUME_STR, date(2030, 1, 1)),
            ],
            10,
        )
    )
    result = PortfolioSimulator(
        [build_test_fund("Equity", 10000.0, 12.0, 0.0, START_DATE)],
        settings,
    ).run()
    paid_dict = {
        snapshot.month_date: snapshot.monthly_sip_float
        for snapshot in result.monthly_snapshots_list
    }
    assert paid_dict[date(2028, 12, 1)] > 0.0
    assert paid_dict[date(2029, 1, 1)] == 0.0
    assert paid_dict[date(2029, 12, 1)] == 0.0
    assert paid_dict[date(2030, 1, 1)] > 0.0


def test_a_gap_is_exactly_as_long_as_it_was_drawn() -> None:
    """Count the months, do not merely check the direction.

    REFERENCE: G1-ANALYTIC. An off-by-one passes every test that
    asks whether a pause happened, so this asks how long it was.
    """
    start_event = TimelineEvent(
        EVENT_START_SIP_STR, START_DATE, amount_float=10000.0
    )
    horizon_years_int = 10
    total_months_int = horizon_years_int * 12
    assert (
        count_paying_months_int([start_event], horizon_years_int)
        == total_months_int
    )
    for gap_years_int, resume_date in (
        (1, date(2030, 1, 1)),
        (2, date(2031, 1, 1)),
        (3, date(2032, 1, 1)),
    ):
        paying_int = count_paying_months_int(
            [
                start_event,
                TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
                TimelineEvent(EVENT_RESUME_STR, resume_date),
            ],
            horizon_years_int,
        )
        assert paying_int == total_months_int - gap_years_int * 12


def test_a_resume_in_its_own_pause_month_stops_nothing() -> None:
    """Pausing and resuming in one month is not a pause.

    REFERENCE: G4-SYNTHETIC. The window would run backwards, and a
    backwards window covers nothing - which is the right answer.
    """
    assert count_paying_months_int(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=10000.0
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2029, 1, 1)),
        ],
        10,
    ) == 120


def test_stopping_withdrawals_then_starting_them_again() -> None:
    """A stop must not swallow the start that follows it.

    REFERENCE: G4-SYNTHETIC. A stop used to run to the horizon
    whatever came after, so a later "start withdrawing" was drawn
    on the rail and silently never paid out.
    """
    settings = compile_settings(
        build_plan(
            [
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    START_DATE,
                    amount_float=25000.0,
                ),
                TimelineEvent(
                    EVENT_WITHDRAW_STR,
                    date(2030, 1, 1),
                    amount_float=5000.0,
                ),
                TimelineEvent(
                    EVENT_STOP_WITHDRAW_STR, date(2032, 1, 1)
                ),
                TimelineEvent(
                    EVENT_WITHDRAW_STR,
                    date(2035, 1, 1),
                    amount_float=5000.0,
                ),
            ],
            15,
        )
    )
    result = PortfolioSimulator(
        [build_test_fund("Equity", 25000.0, 12.0, 0.0, START_DATE)],
        settings,
    ).run()
    paid_dict = {
        snapshot.month_date: snapshot.monthly_withdrawal_float
        for snapshot in result.monthly_snapshots_list
    }
    assert paid_dict[date(2031, 12, 1)] > 0.0
    assert paid_dict[date(2032, 1, 1)] == 0.0
    assert paid_dict[date(2034, 12, 1)] == 0.0
    assert paid_dict[date(2035, 1, 1)] > 0.0
