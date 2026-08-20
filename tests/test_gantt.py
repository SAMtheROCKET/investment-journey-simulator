"""The plan drawn as phases: what is running, and when."""

from __future__ import annotations

from datetime import date

import pytest

from investment_journey_simulator.constants import PAUSE_SCOPE_WITHDRAWAL_STR
from investment_journey_simulator.gantt import (
    KIND_CONTEXT_STR,
    KIND_PAUSED_STR,
    LANE_CONTRIBUTIONS_STR,
    LANE_EVENTS_STR,
    LANE_INFLATION_STR,
    LANE_ORDER_TUPLE,
    LANE_SALARY_STR,
    LANE_STEPUP_STR,
    LANE_WITHDRAWALS_STR,
    build_active_lane_list,
    build_bar_list,
    build_marker_list,
)
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_INCOME_STR,
    EVENT_INFLATION_STR,
    EVENT_LUMPSUM_STR,
    EVENT_NOTE_STR,
    EVENT_PAUSE_STR,
    EVENT_REBALANCE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
    compile_settings,
)
from investment_journey_simulator.ui.gantt_view import build_gantt_figure

START_DATE: date = date(2026, 1, 1)
HORIZON_YEARS_INT: int = 20


def build_plan(event_list: list[TimelineEvent]) -> TimelinePlan:
    """Build a plan on the shared reference date.

    REFERENCE: harness only.
    """
    return TimelinePlan(START_DATE, HORIZON_YEARS_INT, event_list)


def lane_bar_list(plan: TimelinePlan, lane_str: str) -> list:
    """Bars belonging to one lane, in order.

    REFERENCE: harness only.
    """
    return [
        bar for bar in build_bar_list(plan) if bar.lane_str == lane_str
    ]


# ------------------------------------------------------------------
# Contributions
# ------------------------------------------------------------------
def test_an_empty_plan_has_no_phases_at_all() -> None:
    """A plan that does nothing must not draw a full-width bar.

    REFERENCE: G4-SYNTHETIC. Guard branch; an empty chart is
    honest, an empty bar is not.
    """
    plan = build_plan([])
    assert build_bar_list(plan) == []
    assert build_active_lane_list(plan) == []


def test_contributions_run_from_the_start_event_to_the_horizon(
) -> None:
    """A plain plan is one unbroken stretch of paying in.

    REFERENCE: G4-SYNTHETIC. The bar must begin at the event, not
    at the start of the chart.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2028, 1, 1), amount_float=1e4
            )
        ]
    )
    bar_list = lane_bar_list(plan, LANE_CONTRIBUTIONS_STR)
    assert len(bar_list) == 1
    assert bar_list[0].start_date == date(2028, 1, 1)
    assert bar_list[0].end_date == plan.end_date
    assert bar_list[0].months_int == 216


def test_a_pause_breaks_the_contribution_lane_in_three() -> None:
    """The gap is the whole point, so it must be drawn.

    REFERENCE: G4-SYNTHETIC. Running, paused, running - and the
    paused stretch is marked as such rather than left blank.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
        ]
    )
    bar_list = lane_bar_list(plan, LANE_CONTRIBUTIONS_STR)
    assert len(bar_list) == 3
    assert bar_list[1].kind_str == KIND_PAUSED_STR
    assert bar_list[1].start_date == date(2029, 1, 1)
    assert bar_list[1].end_date == date(2031, 1, 1)
    assert bar_list[1].months_int == 24


def test_each_change_of_amount_starts_its_own_bar() -> None:
    """A raise is a new phase, labelled with the new amount.

    REFERENCE: G4-SYNTHETIC. One bar per stretch of one amount.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_CHANGE_SIP_STR,
                date(2032, 1, 1),
                amount_float=3e4,
            ),
        ]
    )
    bar_list = lane_bar_list(plan, LANE_CONTRIBUTIONS_STR)
    assert len(bar_list) == 2
    assert "10,000" in bar_list[0].label_str
    assert "30,000" in bar_list[1].label_str
    assert bar_list[0].end_date == date(2032, 1, 1)


def test_setting_the_amount_to_zero_draws_no_bar() -> None:
    """Nothing is running, so nothing should be shown running.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_CHANGE_SIP_STR,
                date(2032, 1, 1),
                amount_float=0.0,
            ),
        ]
    )
    bar_list = lane_bar_list(plan, LANE_CONTRIBUTIONS_STR)
    assert len(bar_list) == 1
    assert bar_list[0].end_date == date(2032, 1, 1)


# ------------------------------------------------------------------
# The other lanes
# ------------------------------------------------------------------
def test_the_step_up_lane_starts_where_escalation_does() -> None:
    """Escalation is a phase, and it does not start at month zero.

    REFERENCE: G4-SYNTHETIC. The engine counts step-ups from the
    latest instalment change, so the bar must too.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_STEPUP_STR, date(2030, 1, 1), percent_float=8.0
            ),
        ]
    )
    bar_list = lane_bar_list(plan, LANE_STEPUP_STR)
    assert len(bar_list) == 1
    assert bar_list[0].start_date == date(2030, 1, 1)
    assert "+8%" in bar_list[0].label_str


def test_a_stopped_withdrawal_ends_its_bar() -> None:
    """An income that stops must stop being drawn.

    REFERENCE: G4-SYNTHETIC. The stop compiles to a withdrawal
    pause running to the horizon, so no bar survives after it.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_WITHDRAW_STR,
                date(2036, 1, 1),
                amount_float=5e4,
            ),
            TimelineEvent(
                EVENT_STOP_WITHDRAW_STR, date(2040, 1, 1)
            ),
        ]
    )
    running_bar_list = [
        bar
        for bar in lane_bar_list(plan, LANE_WITHDRAWALS_STR)
        if bar.kind_str != KIND_PAUSED_STR
    ]
    assert len(running_bar_list) == 1
    assert running_bar_list[0].start_date == date(2036, 1, 1)
    assert running_bar_list[0].end_date == date(2040, 1, 1)


def test_a_withdrawal_pause_does_not_break_contributions() -> None:
    """Scope matters: stopping income must not stop paying in.

    REFERENCE: G4-SYNTHETIC. Reading the scope wrongly would draw
    a contribution gap that the engine never simulates.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_WITHDRAW_STR,
                date(2030, 1, 1),
                amount_float=5e4,
            ),
            TimelineEvent(
                EVENT_STOP_WITHDRAW_STR, date(2034, 1, 1)
            ),
        ]
    )
    assert any(
        pause_range.scope_str == PAUSE_SCOPE_WITHDRAWAL_STR
        for pause_range in compile_settings(
            plan
        ).pauses.pause_ranges_list
    )
    contribution_bar_list = lane_bar_list(
        plan, LANE_CONTRIBUTIONS_STR
    )
    assert len(contribution_bar_list) == 1
    assert contribution_bar_list[0].kind_str != KIND_PAUSED_STR


def test_salary_and_inflation_are_drawn_as_context() -> None:
    """These shape the answer without being actions you take.

    REFERENCE: G4-SYNTHETIC. Marking them differently stops a
    reader mistaking a salary band for money being invested.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_INCOME_STR,
                date(2030, 6, 1),
                amount_float=6e6,
            ),
            TimelineEvent(
                EVENT_INFLATION_STR,
                date(2032, 1, 1),
                percent_float=7.0,
            ),
        ]
    )
    for lane_str in (LANE_SALARY_STR, LANE_INFLATION_STR):
        bar_list = lane_bar_list(plan, lane_str)
        assert len(bar_list) == 1
        assert bar_list[0].kind_str == KIND_CONTEXT_STR


def test_a_later_salary_ends_the_earlier_band() -> None:
    """A value holds only until the next one replaces it.

    REFERENCE: G4-SYNTHETIC. Overlapping bands would misreport
    which income the surcharge was judged against.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_INCOME_STR,
                date(2028, 6, 1),
                amount_float=4e6,
            ),
            TimelineEvent(
                EVENT_INCOME_STR,
                date(2034, 6, 1),
                amount_float=9e6,
            ),
        ]
    )
    bar_list = lane_bar_list(plan, LANE_SALARY_STR)
    assert len(bar_list) == 2
    assert bar_list[0].end_date == bar_list[1].start_date


# ------------------------------------------------------------------
# Markers and lanes
# ------------------------------------------------------------------
def test_point_events_become_markers_not_bars() -> None:
    """A lump sum happens in a month; it does not run for years.

    REFERENCE: G4-SYNTHETIC. Drawing it as a bar would imply a
    duration it does not have.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_LUMPSUM_STR,
                date(2030, 1, 1),
                amount_float=5e5,
            ),
            TimelineEvent(EVENT_REBALANCE_STR, date(2033, 1, 1)),
            TimelineEvent(
                EVENT_NOTE_STR,
                date(2035, 1, 1),
                note_str="bought a house",
            ),
        ]
    )
    marker_list = build_marker_list(plan)
    assert len(marker_list) == 3
    assert all(
        marker.lane_str == LANE_EVENTS_STR for marker in marker_list
    )
    assert [marker.marker_date for marker in marker_list] == [
        date(2030, 1, 1),
        date(2033, 1, 1),
        date(2035, 1, 1),
    ]


def test_a_note_carries_its_text_and_no_amount() -> None:
    """A marker that changes nothing must not display a rupee sum.

    REFERENCE: G4-SYNTHETIC. Showing an amount would contradict
    the promise that a note moves no money.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_NOTE_STR,
                date(2035, 1, 1),
                note_str="bought a house",
            )
        ]
    )
    assert build_marker_list(plan)[0].detail_str == "bought a house"


def test_only_lanes_that_carry_something_are_shown() -> None:
    """An empty lane is a row of nothing, so it is omitted.

    REFERENCE: G4-SYNTHETIC. The chart's height follows the plan.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            )
        ]
    )
    assert build_active_lane_list(plan) == [LANE_CONTRIBUTIONS_STR]


def test_lanes_always_appear_in_the_canonical_order() -> None:
    """Lane order must not depend on the order events were added.

    REFERENCE: G4-SYNTHETIC. A chart that reshuffles itself as you
    type is unreadable.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_INFLATION_STR,
                date(2032, 1, 1),
                percent_float=7.0,
            ),
            TimelineEvent(
                EVENT_LUMPSUM_STR, date(2030, 1, 1), amount_float=1e5
            ),
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
        ]
    )
    lane_list = build_active_lane_list(plan)
    assert lane_list == [
        lane_str
        for lane_str in LANE_ORDER_TUPLE
        if lane_str in set(lane_list)
    ]


# ------------------------------------------------------------------
# The rendered figure
# ------------------------------------------------------------------
def test_the_figure_is_serialisable_and_spans_the_horizon() -> None:
    """A chart Streamlit cannot serialise never reaches the page.

    REFERENCE: G4-SYNTHETIC. A bar length handed over as a
    timedelta looks natural and fails at serialisation, so the
    figure is round-tripped here to prove it does not.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
        ]
    )
    figure = build_gantt_figure(plan)
    assert figure.to_json()
    assert figure.layout.xaxis.range == (
        START_DATE,
        plan.end_date,
    )


def test_every_bar_has_a_non_negative_length() -> None:
    """A bar running backwards would silently vanish.

    REFERENCE: G4-SYNTHETIC. Guard over every lane at once.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
            TimelineEvent(
                EVENT_STEPUP_STR, date(2031, 1, 1), percent_float=8.0
            ),
            TimelineEvent(
                EVENT_WITHDRAW_STR,
                date(2040, 1, 1),
                amount_float=5e4,
            ),
        ]
    )
    for bar in build_bar_list(plan):
        assert bar.end_date >= bar.start_date
        assert bar.months_int >= 0


@pytest.mark.parametrize("horizon_years_int", [1, 5, 20, 50])
def test_the_chart_holds_together_at_any_horizon(
    horizon_years_int: int,
) -> None:
    """The plan's length is a slider, so every length must work.

    REFERENCE: G4-SYNTHETIC. Boundary sweep.
    """
    plan = TimelinePlan(
        START_DATE,
        horizon_years_int,
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            )
        ],
    )
    assert build_gantt_figure(plan).to_json()


# ------------------------------------------------------------------
# The pending-click marker on the rail
# ------------------------------------------------------------------
def test_an_unanswered_click_is_marked_on_the_rail() -> None:
    """A click asks a question; the rail must show where.

    REFERENCE: G4-SYNTHETIC. Without a mark the reader has to
    remember which month they hit, and the panel underneath reads
    as unrelated to the timeline they were looking at.
    """
    from datetime import date

    from investment_journey_simulator.timeline import (
        EVENT_START_SIP_STR,
        TimelineEvent,
        TimelinePlan,
    )
    from investment_journey_simulator.ui.rail_view import build_rail_figure

    plan = TimelinePlan(
        date(2026, 1, 1),
        10,
        [TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1))],
    )
    idle_figure = build_rail_figure(plan, [])
    pending_figure = build_rail_figure(plan, [], 30)
    assert len(pending_figure.data) == len(idle_figure.data) + 2
    assert pending_figure.data[-1].x == (date(2028, 7, 1),)


def test_the_pending_ring_is_hollow() -> None:
    """It must not read as an event that has been placed.

    REFERENCE: G4-SYNTHETIC. Nothing has been added yet, so a
    filled dot would claim something untrue.
    """
    from datetime import date

    from investment_journey_simulator.timeline import TimelinePlan
    from investment_journey_simulator.ui.rail_view import (
        TRANSPARENT_STR,
        build_rail_figure,
    )

    figure = build_rail_figure(
        TimelinePlan(date(2026, 1, 1), 10, []), [], 5
    )
    assert figure.data[-1].marker.color == TRANSPARENT_STR
    assert figure.data[-1].marker.line.width > 0


def test_the_hit_layer_stays_first_with_a_pending_mark() -> None:
    """Click reading depends on trace zero being the hit layer.

    REFERENCE: G4-SYNTHETIC. The marker is added last precisely so
    it cannot displace the layer every click is read from.
    """
    from datetime import date

    from investment_journey_simulator.timeline import TimelinePlan
    from investment_journey_simulator.ui.rail_view import (
        RAIL_HIT_SIZE_INT,
        build_rail_figure,
    )

    figure = build_rail_figure(
        TimelinePlan(date(2026, 1, 1), 10, []), [], 5
    )
    assert figure.data[0].marker.size == RAIL_HIT_SIZE_INT


def test_an_out_of_range_pending_month_is_ignored() -> None:
    """A stale index must not draw a mark off the axis.

    REFERENCE: G4-SYNTHETIC. Shortening the horizon can leave a
    pending click beyond the end of the plan.
    """
    from datetime import date

    from investment_journey_simulator.timeline import TimelinePlan
    from investment_journey_simulator.ui.rail_view import build_rail_figure

    plan = TimelinePlan(date(2026, 1, 1), 10, [])
    assert len(build_rail_figure(plan, [], 9999).data) == len(
        build_rail_figure(plan, []).data
    )


# ------------------------------------------------------------------
# The cash-flow band beneath the rail
# ------------------------------------------------------------------
def build_money_plan():
    """A plan with money going in and out.

    REFERENCE: harness only.
    """
    from datetime import date

    from investment_journey_simulator.timeline import (
        EVENT_LUMPSUM_STR,
        EVENT_PAUSE_STR,
        EVENT_START_SIP_STR,
        EVENT_WITHDRAW_STR,
        TimelineEvent,
        TimelinePlan,
    )

    return TimelinePlan(
        date(2026, 1, 1),
        20,
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
            ),
            TimelineEvent(
                EVENT_LUMPSUM_STR, date(2030, 6, 1), 500000.0
            ),
            TimelineEvent(
                EVENT_WITHDRAW_STR, date(2041, 1, 1), 50000.0
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2033, 1, 1)),
        ],
    )


def read_arrow_list(figure):
    """The cash-flow arrows in a rail figure.

    REFERENCE: harness only.
    """
    from investment_journey_simulator.ui.rail_view import MONEY_BASE_FLOAT

    return [
        trace
        for trace in figure.data
        if trace.mode == "lines"
        and trace.y
        and trace.y[0] == MONEY_BASE_FLOAT
    ]


def test_every_arrow_fits_inside_the_axis() -> None:
    """An arrow drawn past the axis is silently clipped.

    REFERENCE: G4-SYNTHETIC. Money-out arrows point downward, so a
    baseline sitting on the floor of the axis cut every withdrawal
    off - which looked like no withdrawal at all.
    """
    from investment_journey_simulator.ui.rail_view import (
        RAIL_Y_MAXIMUM_FLOAT,
        RAIL_Y_MINIMUM_FLOAT,
        build_rail_figure,
    )

    figure = build_rail_figure(build_money_plan(), [])
    arrow_list = read_arrow_list(figure)
    assert arrow_list
    for arrow in arrow_list:
        assert (
            RAIL_Y_MINIMUM_FLOAT <= arrow.y[1]
            <= RAIL_Y_MAXIMUM_FLOAT
        )


def test_money_in_and_out_point_opposite_ways() -> None:
    """Direction is the whole point of the band.

    REFERENCE: G4-SYNTHETIC.
    """
    from investment_journey_simulator.ui.rail_view import build_rail_figure

    figure = build_rail_figure(build_money_plan(), [])
    symbol_list = [
        trace.marker.symbol
        for trace in figure.data
        if trace.mode == "markers"
        and trace.marker.symbol
        in ("triangle-up", "triangle-down")
    ]
    assert "triangle-up" in symbol_list
    assert "triangle-down" in symbol_list


def test_an_instalment_is_sized_per_year_not_per_month() -> None:
    """Otherwise a lump sum dwarfs a far larger commitment.

    REFERENCE: G4-SYNTHETIC. Twenty-five thousand a month is three
    lakh a year, which is the figure comparable with a lump sum.
    """
    from datetime import date

    from investment_journey_simulator.timeline import (
        EVENT_LUMPSUM_STR,
        EVENT_START_SIP_STR,
        TimelineEvent,
    )
    from investment_journey_simulator.ui.rail_view import (
        build_yearly_amount_float,
    )

    instalment = TimelineEvent(
        EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
    )
    lump_sum = TimelineEvent(
        EVENT_LUMPSUM_STR, date(2026, 1, 1), 500000.0
    )
    assert build_yearly_amount_float(instalment) == 300000.0
    assert build_yearly_amount_float(lump_sum) == 500000.0


def test_an_event_that_moves_no_money_draws_no_arrow() -> None:
    """A pause is not a cash flow.

    REFERENCE: G4-SYNTHETIC.
    """
    from datetime import date

    from investment_journey_simulator.timeline import (
        EVENT_PAUSE_STR,
        TimelineEvent,
    )
    from investment_journey_simulator.ui.rail_view import (
        build_yearly_amount_float,
    )

    assert (
        build_yearly_amount_float(
            TimelineEvent(EVENT_PAUSE_STR, date(2030, 1, 1))
        )
        == 0.0
    )


def test_a_plan_with_no_money_draws_no_band() -> None:
    """An empty band must not reserve space for nothing.

    REFERENCE: G4-SYNTHETIC.
    """
    from datetime import date

    from investment_journey_simulator.timeline import TimelinePlan
    from investment_journey_simulator.ui.rail_view import build_rail_figure

    figure = build_rail_figure(
        TimelinePlan(date(2026, 1, 1), 10, []), []
    )
    assert read_arrow_list(figure) == []
