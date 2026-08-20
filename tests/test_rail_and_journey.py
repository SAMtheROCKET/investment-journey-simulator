"""The rail input surface and the journey report it explains."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.inflation import (
    calculate_deflation_factor_float,
)
from investment_journey_simulator.journey import (
    build_milestone_list,
    summarise_milestone_str,
)
from investment_journey_simulator.timeline import (
    EVENT_INFLATION_STR,
    EVENT_LUMPSUM_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    TimelineEvent,
    TimelinePlan,
    apply_plan_to_fund,
    collect_inflation_schedule_tuple,
    compile_settings,
)
from investment_journey_simulator.ui.rail_view import (
    build_dot_order_list,
    build_month_date_list,
    build_rail_figure,
    needs_amount_bool,
    needs_percent_bool,
    read_clicked_month_index_int,
    resolve_clicked_event_index_int,
)

START_DATE: date = date(2026, 1, 1)
HORIZON_YEARS_INT: int = 10
MONTH_COUNT_INT: int = HORIZON_YEARS_INT * 12


def build_plan(event_list: list[TimelineEvent]) -> TimelinePlan:
    """Build a plan on the shared reference date.

    REFERENCE: harness only.
    """
    return TimelinePlan(START_DATE, HORIZON_YEARS_INT, event_list)


def build_selection_dict(
    point_index_int: int,
    curve_number_int: int = 0,
) -> dict:
    """Fake the payload a clicked chart returns.

    REFERENCE: harness only. Mirrors the shape Streamlit hands
    back from a plotly selection event.
    """
    return {
        "selection": {
            "points": [
                {
                    "curve_number": curve_number_int,
                    "point_index": point_index_int,
                }
            ]
        }
    }


# ------------------------------------------------------------------
# Reading a click on the rail
# ------------------------------------------------------------------
@pytest.mark.parametrize("point_index_int", [0, 1, 59, 119])
def test_a_click_on_the_rail_resolves_to_that_month(
    point_index_int: int,
) -> None:
    """Placing an event depends entirely on reading the click.

    REFERENCE: G4-SYNTHETIC. The hit layer carries one point per
    simulated month, so its point index *is* the month index.
    """
    assert (
        read_clicked_month_index_int(
            build_selection_dict(point_index_int), MONTH_COUNT_INT
        )
        == point_index_int
    )


def test_clicking_an_event_dot_places_nothing() -> None:
    """Inspecting an existing event must not stack a new one.

    REFERENCE: G4-SYNTHETIC. Only the hit layer, which is trace
    zero, is a placement target.
    """
    assert (
        read_clicked_month_index_int(
            build_selection_dict(10, curve_number_int=3),
            MONTH_COUNT_INT,
        )
        is None
    )


def test_a_click_beyond_the_horizon_is_refused() -> None:
    """A month the simulation does not have is not a month.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert (
        read_clicked_month_index_int(
            build_selection_dict(MONTH_COUNT_INT), MONTH_COUNT_INT
        )
        is None
    )


@pytest.mark.parametrize(
    "selection_result",
    [
        None,
        {},
        {"selection": None},
        {"selection": {}},
        {"selection": {"points": None}},
        {"selection": {"points": [{}]}},
    ],
)
def test_an_unusable_payload_never_raises(
    selection_result,
) -> None:
    """A page that crashes on an odd payload is worse than idle.

    REFERENCE: G4-SYNTHETIC. Every access into the payload is
    defensive because its shape is not a published contract.
    """
    assert (
        read_clicked_month_index_int(
            selection_result, MONTH_COUNT_INT
        )
        is None
    )


# ------------------------------------------------------------------
# Drawing the rail
# ------------------------------------------------------------------
def test_the_hit_layer_covers_every_month_and_comes_first() -> None:
    """The click reader identifies the hit layer by position.

    REFERENCE: G4-SYNTHETIC. If another trace were added first,
    every click would silently stop placing events.
    """
    figure = build_rail_figure(build_plan([]))
    assert len(figure.data[0].x) == MONTH_COUNT_INT
    assert len(build_month_date_list(build_plan([]))) == (
        MONTH_COUNT_INT
    )


def test_events_sharing_a_month_are_drawn_at_different_heights(
) -> None:
    """Two events in one month must not hide one another.

    REFERENCE: G4-SYNTHETIC. This is what "multiple events at any
    point of the timeline" has to look like to be usable.
    """
    same_month_date = date(2029, 1, 1)
    figure = build_rail_figure(
        build_plan(
            [
                TimelineEvent(
                    EVENT_STEPUP_STR,
                    same_month_date,
                    percent_float=10.0,
                ),
                TimelineEvent(
                    EVENT_LUMPSUM_STR,
                    same_month_date,
                    amount_float=1e5,
                ),
            ]
        )
    )
    dot_height_list = [
        trace.y[1]
        for trace in figure.data
        if trace.mode == "lines+markers"
    ]
    assert len(dot_height_list) == 2
    assert dot_height_list[0] != dot_height_list[1]


def test_a_pause_is_drawn_as_a_span_not_a_dot() -> None:
    """A pause lasts, so the rail has to show a window.

    REFERENCE: G4-SYNTHETIC. The span is read back out of the
    compiled settings, so it shows what the engine was told.
    """
    plan = build_plan(
        [
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2030, 1, 1)),
        ]
    )
    span_list = [
        (
            pause_range.start_date,
            pause_range.end_date,
            "Contributions paused",
        )
        for pause_range in compile_settings(
            plan
        ).pauses.pause_ranges_list
    ]
    figure = build_rail_figure(plan, span_list)
    span_trace_list = [
        trace
        for trace in figure.data
        if trace.mode == "lines" and trace.line.width == 9
    ]
    assert len(span_trace_list) == 1
    assert span_trace_list[0].x == (
        date(2029, 1, 1),
        date(2030, 1, 1),
    )


@pytest.mark.parametrize(
    ("event_type_str", "wants_amount_bool", "wants_percent_bool"),
    [
        (EVENT_START_SIP_STR, True, False),
        (EVENT_LUMPSUM_STR, True, False),
        (EVENT_STEPUP_STR, False, True),
        (EVENT_PAUSE_STR, False, False),
    ],
)
def test_each_event_asks_only_for_what_it_uses(
    event_type_str: str,
    wants_amount_bool: bool,
    wants_percent_bool: bool,
) -> None:
    """A form showing fields the event ignores is noise.

    REFERENCE: G4-SYNTHETIC. A pause needs neither input.
    """
    assert needs_amount_bool(event_type_str) is wants_amount_bool
    assert needs_percent_bool(event_type_str) is wants_percent_bool


# ------------------------------------------------------------------
# The journey report
# ------------------------------------------------------------------
def run_plan_for_report(plan: TimelinePlan):
    """Value a plan so its journey can be reported.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(
        [
            apply_plan_to_fund(
                build_test_fund("Equity", 0.0, 12.0, 0.0, START_DATE),
                plan,
            )
        ],
        compile_settings(plan),
    ).run()


def build_reported_plan() -> TimelinePlan:
    """Build a plan with three events worth narrating.

    REFERENCE: harness only.
    """
    return build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_LUMPSUM_STR,
                date(2029, 1, 1),
                amount_float=2e5,
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2032, 1, 1)),
        ]
    )


def test_the_report_has_one_milestone_per_event_in_order() -> None:
    """The story must follow the plan exactly.

    REFERENCE: G4-SYNTHETIC. Events are reported in calendar
    order however they were added.
    """
    plan = build_reported_plan()
    milestone_list = build_milestone_list(
        plan, run_plan_for_report(plan)
    )
    assert [
        milestone.month_index_int for milestone in milestone_list
    ] == [0, 36, 72]


def test_each_milestone_reports_the_corpus_of_its_own_month(
) -> None:
    """A milestone that misreads its month tells a false story.

    REFERENCE: G3-CROSSCHECK. Every figure must be readable
    straight out of the snapshot for that month.
    """
    plan = build_reported_plan()
    result = run_plan_for_report(plan)
    for milestone in build_milestone_list(plan, result):
        snapshot = result.monthly_snapshots_list[
            milestone.month_index_int
        ]
        assert milestone.portfolio_value_float == pytest.approx(
            snapshot.portfolio_value_float
        )
        assert milestone.invested_amount_float == pytest.approx(
            snapshot.invested_amount_float
        )
        assert milestone.month_date == snapshot.month_date


def test_the_gain_is_the_corpus_less_what_was_paid_in() -> None:
    """The gap between the two is the only part at risk of tax.

    REFERENCE: G1-ANALYTIC. Definitional.
    """
    plan = build_reported_plan()
    for milestone in build_milestone_list(
        plan, run_plan_for_report(plan)
    ):
        assert milestone.gain_float == pytest.approx(
            milestone.portfolio_value_float
            - milestone.invested_amount_float
        )


def test_the_real_value_is_deflated_at_the_event_date() -> None:
    """Restating in today's rupees must use the event's own month.

    REFERENCE: G1-ANALYTIC. Deflating everything by the final
    factor, or not at all, would misstate every early milestone.
    """
    plan = build_reported_plan()
    milestone_list = build_milestone_list(
        plan, run_plan_for_report(plan), 6.0
    )
    for milestone in milestone_list:
        assert milestone.real_value_float == pytest.approx(
            milestone.portfolio_value_float
            / calculate_deflation_factor_float(
                6.0, milestone.month_index_int
            )
        )


def test_zero_inflation_leaves_the_real_value_alone() -> None:
    """With no inflation the two figures must coincide.

    REFERENCE: G1-ANALYTIC. Guard branch.
    """
    plan = build_reported_plan()
    for milestone in build_milestone_list(
        plan, run_plan_for_report(plan), 0.0
    ):
        assert milestone.real_value_float == pytest.approx(
            milestone.portfolio_value_float
        )


def test_an_unsimulated_plan_reports_nothing() -> None:
    """A report against months that do not exist is a lie.

    REFERENCE: G4-SYNTHETIC. Guard branch for a zero horizon.
    """
    empty_plan = TimelinePlan(START_DATE, 0, [])
    assert (
        build_milestone_list(
            empty_plan, run_plan_for_report(empty_plan)
        )
        == []
    )


def test_an_event_past_the_horizon_clamps_to_the_last_month(
) -> None:
    """Every milestone needs a real month to report against.

    REFERENCE: G4-SYNTHETIC. Guard branch; the rail can hold an
    event that a later shortening of the horizon leaves outside.
    """
    plan = build_plan(
        [TimelineEvent(EVENT_PAUSE_STR, date(2099, 1, 1))]
    )
    milestone_list = build_milestone_list(
        plan, run_plan_for_report(plan)
    )
    assert milestone_list[0].month_index_int == MONTH_COUNT_INT - 1


def test_a_milestone_summarises_itself_in_one_line() -> None:
    """The table has a caption; the story needs a sentence.

    REFERENCE: G4-SYNTHETIC. Naming both the event and the corpus
    is what makes the line worth reading.
    """
    plan = build_reported_plan()
    summary_str = summarise_milestone_str(
        build_milestone_list(plan, run_plan_for_report(plan))[1]
    )
    assert EVENT_LUMPSUM_STR in summary_str
    assert "Jan 2029" in summary_str


# ------------------------------------------------------------------
# Inflation that changes on the rail
# ------------------------------------------------------------------
def test_inflation_events_compile_to_a_dated_schedule() -> None:
    """A rate change placed on the rail must be dated, not global.

    REFERENCE: G4-SYNTHETIC. Inflation is applied after the run, so
    the schedule is read straight off the plan.
    """
    assert collect_inflation_schedule_tuple(
        build_plan(
            [
                TimelineEvent(
                    EVENT_INFLATION_STR,
                    date(2031, 1, 1),
                    percent_float=9.0,
                ),
                TimelineEvent(
                    EVENT_INFLATION_STR,
                    date(2028, 1, 1),
                    percent_float=4.0,
                ),
            ]
        )
    ) == ((24, 4.0), (60, 9.0))


def test_a_plan_without_inflation_events_has_no_schedule() -> None:
    """Saying nothing about inflation must schedule nothing.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert collect_inflation_schedule_tuple(build_plan([])) == ()


def test_an_inflation_event_changes_the_reported_real_value(
) -> None:
    """The event has to move a number, not just be recorded.

    REFERENCE: G1-ANALYTIC. A milestone six years in, with the
    rate rising from 4% to 10% after five years, must be deflated
    by 1.04^5 x 1.10^1 rather than by 1.04^6.
    """
    plan = build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_INFLATION_STR,
                date(2031, 1, 1),
                percent_float=10.0,
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2032, 1, 1)),
        ]
    )
    result = run_plan_for_report(plan)
    milestone_list = build_milestone_list(
        plan, result, 4.0, collect_inflation_schedule_tuple(plan)
    )
    pause_milestone = milestone_list[-1]
    assert pause_milestone.month_index_int == 72
    assert pause_milestone.real_value_float == pytest.approx(
        pause_milestone.portfolio_value_float
        / (1.04**5 * 1.10)
    )


# ------------------------------------------------------------------
# The minus: clicking a placed dot takes it away
# ------------------------------------------------------------------
def build_dot_plan() -> TimelinePlan:
    """A plan whose dots sit in a known drawing order.

    REFERENCE: harness only. Two events share one month, so the
    stacking path is exercised as well as the ordering.
    """
    return build_plan(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, START_DATE, amount_float=1e4
            ),
            TimelineEvent(
                EVENT_LUMPSUM_STR, date(2029, 1, 1), amount_float=1e5
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
        ]
    )


def test_the_dot_order_covers_every_event_once() -> None:
    """A dot with no event behind it could remove the wrong one.

    REFERENCE: G4-SYNTHETIC. The order must be a permutation of
    the events, not a subset and not a repetition.
    """
    order_list = build_dot_order_list(build_dot_plan())
    assert sorted(order_list) == [0, 1, 2]


def test_the_dot_order_matches_the_traces_actually_drawn(
) -> None:
    """The mapping is positional, so it must not drift.

    REFERENCE: G4-SYNTHETIC. One dot trace per event, in the same
    order the order list reports.
    """
    plan = build_dot_plan()
    figure = build_rail_figure(plan)
    dot_trace_list = [
        trace
        for trace in figure.data
        if trace.mode == "lines+markers"
    ]
    assert len(dot_trace_list) == len(build_dot_order_list(plan))


@pytest.mark.parametrize("dot_index_int", [0, 1, 2])
def test_clicking_a_dot_identifies_its_own_event(
    dot_index_int: int,
) -> None:
    """Removing the wrong event would be worse than not removing.

    REFERENCE: G4-SYNTHETIC. The hit layer is trace zero and the
    rail line trace one, so with no spans the dots start at two.
    """
    plan = build_dot_plan()
    expected_int = build_dot_order_list(plan)[dot_index_int]
    assert (
        resolve_clicked_event_index_int(
            build_selection_dict(0, curve_number_int=2 + dot_index_int),
            plan,
            0,
        )
        == expected_int
    )


def test_spans_shift_where_the_dots_begin() -> None:
    """A pause draws a bar, which offsets every dot after it.

    REFERENCE: G4-SYNTHETIC. Getting this offset wrong would map
    a click onto the event next door.
    """
    plan = build_plan(
        [
            TimelineEvent(EVENT_PAUSE_STR, date(2029, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2031, 1, 1)),
        ]
    )
    assert (
        resolve_clicked_event_index_int(
            build_selection_dict(0, curve_number_int=3), plan, 1
        )
        == 0
    )


def test_clicking_the_rail_itself_removes_nothing() -> None:
    """Adding and removing must stay distinct gestures.

    REFERENCE: G4-SYNTHETIC. A click on the hit layer is an add,
    never a delete.
    """
    assert (
        resolve_clicked_event_index_int(
            build_selection_dict(10, curve_number_int=0),
            build_dot_plan(),
            0,
        )
        is None
    )


def test_an_unusable_payload_removes_nothing() -> None:
    """Silently deleting an event on a stray payload would be bad.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    plan = build_dot_plan()
    for selection_result in (None, {}, {"selection": {"points": []}}):
        assert (
            resolve_clicked_event_index_int(
                selection_result, plan, 0
            )
            is None
        )


def test_a_dot_hover_offers_to_remove_and_counts_its_month(
) -> None:
    """The affordance has to be visible before it is used.

    REFERENCE: G4-SYNTHETIC. Two events share January 2029, so
    both dots say so and both offer the minus.
    """
    figure = build_rail_figure(build_dot_plan())
    hover_list = [
        trace.hovertemplate
        for trace in figure.data
        if trace.mode == "lines+markers"
    ]
    assert all("click to remove" in hover for hover in hover_list)
    assert sum(
        "2 events this month" in hover for hover in hover_list
    ) == 2
