"""The plan as phases: what is running, and when.

The rail answers *when did things happen*. A Gantt answers a
different question - *what is in force right now* - and a plan has
several things running at once: contributions, an escalation, an
income being drawn, a salary, a rate of inflation.

Every bar here is derived from the **compiled settings**, not from
the raw events. That matters: it means the chart shows what the
engine was actually told, so a bar and the corpus curve can never
tell different stories. If the compiler translates a lone pause into
a window running to the horizon, the bar runs to the horizon too.

Nothing in this module computes finance. It reads a `TimelinePlan`
and the `SimulationSettings` compiled from it, and returns bars and
markers for a chart to draw.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    PAUSE_SCOPE_BOTH_STR,
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
)
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_STR,
    EVENT_NOTE_STR,
    EVENT_REBALANCE_STR,
    TimelinePlan,
    collect_inflation_schedule_tuple,
    compile_settings,
)

LANE_CONTRIBUTIONS_STR: str = "Contributions"
LANE_STEPUP_STR: str = "Yearly step-up"
LANE_WITHDRAWALS_STR: str = "Withdrawals"
LANE_SALARY_STR: str = "Salary"
LANE_INFLATION_STR: str = "Inflation"
LANE_EVENTS_STR: str = "One-off events"

LANE_ORDER_TUPLE: tuple = (
    LANE_CONTRIBUTIONS_STR,
    LANE_STEPUP_STR,
    LANE_WITHDRAWALS_STR,
    LANE_SALARY_STR,
    LANE_INFLATION_STR,
    LANE_EVENTS_STR,
)

KIND_ACTIVE_STR: str = "ACTIVE"
KIND_PAUSED_STR: str = "PAUSED"
KIND_CONTEXT_STR: str = "CONTEXT"


@dataclass(frozen=True)
class GanttBar:
    """One stretch of time during which something is in force."""

    lane_str: str
    start_date: date
    end_date: date
    label_str: str
    kind_str: str = KIND_ACTIVE_STR
    detail_str: str = ""

    @property
    def months_int(self) -> int:
        """Length of this stretch in whole months.

        Brief:
            Reported so the chart can label a bar with how long it
            lasts rather than only when it starts.

        Arguments:
            None.

        Returns:
            int: Months spanned, never negative.

        Warning:
            Counts calendar months, not days.
        """
        return max(
            0,
            (self.end_date.year - self.start_date.year)
            * MONTHS_IN_YEAR_INT
            + (self.end_date.month - self.start_date.month),
        )


@dataclass(frozen=True)
class GanttMarker:
    """One thing that happens at a point rather than over time."""

    lane_str: str
    marker_date: date
    label_str: str
    event_type_str: str
    detail_str: str = ""


def _add_months_date(origin_date: date, months_int: int) -> date:
    """Move a date forward by a number of whole months.

    Brief:
        Always lands on the first of the month, matching the grid
        the engine simulates on.

    Arguments:
        origin_date (date): Date to move from.
        months_int (int): Months to add, may be zero.

    Returns:
        date: First day of the resulting month.

    Warning:
        Negative offsets are allowed but clamp at the origin year.
    """
    zero_based_int = (
        origin_date.month - 1 + max(0, int(months_int))
    )
    return date(
        origin_date.year + zero_based_int // MONTHS_IN_YEAR_INT,
        zero_based_int % MONTHS_IN_YEAR_INT + 1,
        1,
    )


def _blocks_contributions_bool(pause_range) -> bool:
    """Say whether a pause window stops contributions.

    Brief:
        A withdrawal-scoped pause leaves the SIP running, so only
        SIP and BOTH scopes break the contribution lane.

    Arguments:
        pause_range (PauseRange): Window being classified.

    Returns:
        bool: True when contributions stop in this window.

    Warning:
        Unknown scopes are treated as not blocking.
    """
    return pause_range.scope_str in (
        PAUSE_SCOPE_SIP_STR,
        PAUSE_SCOPE_BOTH_STR,
    )


def _blocks_withdrawals_bool(pause_range) -> bool:
    """Say whether a pause window stops withdrawals.

    Brief:
        Mirrors the contribution rule for the income side.

    Arguments:
        pause_range (PauseRange): Window being classified.

    Returns:
        bool: True when withdrawals stop in this window.

    Warning:
        Unknown scopes are treated as not blocking.
    """
    return pause_range.scope_str in (
        PAUSE_SCOPE_WITHDRAWAL_STR,
        PAUSE_SCOPE_BOTH_STR,
    )


def _split_around_pauses(
    start_date: date,
    end_date: date,
    pause_range_list: list,
    lane_str: str,
    label_str: str,
) -> list[GanttBar]:
    """Break a running stretch wherever a pause interrupts it.

    A contribution lane is the stretches between its pauses, not
    one bar from start to finish; drawing it whole would hide the
    thing the reader came to see.

    Arguments:
        start_date (date): First month the activity runs.
        end_date (date): Month it would otherwise end.
        pause_range_list (list): Windows that interrupt it.
        lane_str (str): Lane the bars belong to.
        label_str (str): Label for running stretches.

    Returns:
        List[GanttBar]: Running and paused bars, in order.

    Warning:
        A range names its last silent month; a bar ends
        exclusively, so each widens by one here.
    """
    bar_list: list[GanttBar] = []
    cursor_date = start_date
    for pause_range in sorted(
        pause_range_list, key=lambda window: window.start_date
    ):
        window_tuple = _build_window_tuple(
            cursor_date, end_date, pause_range
        )
        if window_tuple is None:
            continue
        bar_list.extend(
            _build_interrupted_pair_list(
                lane_str, label_str, window_tuple
            )
        )
        cursor_date = window_tuple[2]
    if cursor_date < end_date:
        bar_list.append(
            GanttBar(lane_str, cursor_date, end_date, label_str)
        )
    return bar_list


def _build_window_tuple(
    cursor_date: date,
    end_date: date,
    pause_range,
) -> tuple | None:
    """Clip one pause to the stretch still being drawn.

    Brief:
        A range names its last silent month and a bar ends
        exclusively, so the window widens by one month here.

    Arguments:
        cursor_date (date): Where the lane has been drawn to.
        end_date (date): Where the lane stops.
        pause_range (PauseRange): Window interrupting it.

    Returns:
        Optional[tuple]: Cursor, window start and window end, or
            None when this pause leaves nothing to draw.
    """
    window_start_date = max(cursor_date, pause_range.start_date)
    window_end_date = min(
        end_date, _add_months_date(pause_range.end_date, 1)
    )
    if window_start_date >= window_end_date:
        return None
    return cursor_date, window_start_date, window_end_date


def _build_interrupted_pair_list(
    lane_str: str,
    label_str: str,
    date_tuple: tuple,
) -> list[GanttBar]:
    """Build the running stretch before a pause, then the pause.

    Brief:
        Split out so the walk above stays readable: one pause
        contributes at most a running bar and a paused bar.

    Arguments:
        lane_str (str): Lane the bars belong to.
        label_str (str): Label for the running stretch.
        date_tuple (tuple): Cursor, pause start and pause end.

    Returns:
        List[GanttBar]: One or two bars, in order.

    Warning:
        Emits no running bar when the pause starts immediately.
    """
    cursor_date, window_start_date, window_end_date = date_tuple
    bar_list: list[GanttBar] = []
    if cursor_date < window_start_date:
        bar_list.append(
            GanttBar(
                lane_str, cursor_date, window_start_date, label_str
            )
        )
    bar_list.append(
        GanttBar(
            lane_str,
            window_start_date,
            window_end_date,
            "Paused",
            KIND_PAUSED_STR,
        )
    )
    return bar_list


def _build_contribution_bar_list(
    plan: TimelinePlan,
    settings,
) -> list[GanttBar]:
    """Show when money is actually going in, and when it is not.

    Brief:
        Each instalment override opens a stretch that runs until
        the next one, labelled with the amount in force, and every
        stretch is broken wherever a pause interrupts it.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        settings: Settings compiled from that plan.

    Returns:
        List[GanttBar]: Contribution stretches and pauses.

    Warning:
        A plan with no instalment event contributes nothing, so it
        produces no bars rather than an empty full-width one.
    """
    override_list = list(settings.instalment_override_list)
    if not override_list:
        return []
    pause_range_list = [
        pause_range
        for pause_range in settings.pauses.pause_ranges_list
        if _blocks_contributions_bool(pause_range)
    ]
    bar_list: list[GanttBar] = []
    for override_index_int, override in enumerate(override_list):
        if override.amount_float <= 0.0:
            continue
        bar_list.extend(
            _split_around_pauses(
                _add_months_date(
                    plan.start_date, override.month_index_int
                ),
                _resolve_override_end_date(
                    plan, override_list, override_index_int
                ),
                pause_range_list,
                LANE_CONTRIBUTIONS_STR,
                f"{override.amount_float:,.0f} a month",
            )
        )
    return bar_list


def _resolve_override_end_date(
    plan: TimelinePlan,
    override_list: list,
    override_index_int: int,
) -> date:
    """Find where one instalment stretch gives way to the next.

    Brief:
        An amount holds until the next change replaces it, and the
        last one holds to the end of the plan.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        override_list (list): Instalment changes in order.
        override_index_int (int): Change being measured.

    Returns:
        date: Month this stretch ends.

    Warning:
        Assumes the list is already in calendar order.
    """
    if override_index_int + 1 >= len(override_list):
        return plan.end_date
    return _add_months_date(
        plan.start_date,
        override_list[override_index_int + 1].month_index_int,
    )


def _build_stepup_bar_list(
    plan: TimelinePlan,
    settings,
) -> list[GanttBar]:
    """Show the stretch over which the instalment escalates.

    Brief:
        Escalation runs from its first step to the end of the plan,
        because nothing in the engine turns it off again.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        settings: Settings compiled from that plan.

    Returns:
        List[GanttBar]: A single bar, or none when off.

    Warning:
        The start is measured from the most recent instalment
        change, which is the origin the engine escalates from.
    """
    stepup_settings = settings.stepup
    if stepup_settings.global_stepup_percent_float <= 0.0:
        return []
    first_override_month_int = (
        settings.instalment_override_list[0].month_index_int
        if settings.instalment_override_list
        else 0
    )
    start_date = _add_months_date(
        plan.start_date,
        first_override_month_int
        + stepup_settings.first_stepup_month_index_int,
    )
    return [
        GanttBar(
            LANE_STEPUP_STR,
            start_date,
            plan.end_date,
            f"+{stepup_settings.global_stepup_percent_float:.0f}%"
            " a year",
        )
    ]


def _build_withdrawal_bar_list(
    plan: TimelinePlan,
    settings,
) -> list[GanttBar]:
    """Show the stretch over which an income is being drawn.

    Brief:
        Runs from the withdrawal's start month to the horizon, cut
        short wherever a withdrawal-scoped pause stops it.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        settings: Settings compiled from that plan.

    Returns:
        List[GanttBar]: Withdrawal stretches, empty when off.

    Warning:
        A stop is modelled as a pause running to the horizon, so a
        stopped income simply produces no bar after it.
    """
    withdrawal_settings = settings.withdrawal
    if not withdrawal_settings.is_enabled_bool:
        return []
    return _split_around_pauses(
        _add_months_date(
            plan.start_date,
            withdrawal_settings.start_month_index_int,
        ),
        plan.end_date,
        [
            pause_range
            for pause_range in settings.pauses.pause_ranges_list
            if _blocks_withdrawals_bool(pause_range)
        ],
        LANE_WITHDRAWALS_STR,
        f"{withdrawal_settings.fixed_amount_float:,.0f} a month",
    )


def _build_schedule_bar_list(
    plan: TimelinePlan,
    schedule_tuple: tuple,
    lane_str: str,
    suffix_str: str,
) -> list[GanttBar]:
    """Turn a dated series into one bar per stretch of one value.

    Brief:
        Shared by salary and inflation, which are the same shape:
        a value that holds until the next entry replaces it.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        schedule_tuple (tuple): Pairs of month index and value.
        lane_str (str): Lane the bars belong to.
        suffix_str (str): Unit appended to each label.

    Returns:
        List[GanttBar]: One bar per stretch, in order.

    Warning:
        An empty schedule produces no bars at all.
    """
    entry_list = sorted(schedule_tuple)
    bar_list: list[GanttBar] = []
    for entry_index_int, (month_int, value_float) in enumerate(
        entry_list
    ):
        end_date = (
            _add_months_date(
                plan.start_date, entry_list[entry_index_int + 1][0]
            )
            if entry_index_int + 1 < len(entry_list)
            else plan.end_date
        )
        bar_list.append(
            GanttBar(
                lane_str,
                _add_months_date(plan.start_date, month_int),
                end_date,
                f"{value_float:,.0f}{suffix_str}",
                KIND_CONTEXT_STR,
            )
        )
    return bar_list


def _build_salary_schedule_tuple(
    plan: TimelinePlan,
    settings,
) -> tuple:
    """Restate the salary history on the plan's month grid.

    Brief:
        Income is dated by financial year for tax, but the chart
        works in months, so each year is placed at the month its
        financial year begins.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        settings: Settings compiled from that plan.

    Returns:
        tuple: Pairs of month index and annual income.

    Warning:
        Clamped to month zero for years before the plan starts.
    """
    return tuple(
        (
            max(
                0,
                (year_int - plan.start_date.year)
                * MONTHS_IN_YEAR_INT,
            ),
            income_float,
        )
        for year_int, income_float in (
            settings.tax.income_by_year_tuple
        )
    )


def build_bar_list(plan: TimelinePlan) -> list[GanttBar]:
    """Build every phase bar the plan implies.

    Brief:
        Compiles the plan first and reads the bars off the result,
        so the chart shows what the engine was told rather than a
        second interpretation of the same events.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        List[GanttBar]: Bars across every lane, in lane order.

    Warning:
        Recompiles on every call; cheap, but not free.
    """
    settings = compile_settings(plan)
    return [
        *_build_contribution_bar_list(plan, settings),
        *_build_stepup_bar_list(plan, settings),
        *_build_withdrawal_bar_list(plan, settings),
        *_build_schedule_bar_list(
            plan,
            _build_salary_schedule_tuple(plan, settings),
            LANE_SALARY_STR,
            " a year",
        ),
        *_build_schedule_bar_list(
            plan,
            collect_inflation_schedule_tuple(plan),
            LANE_INFLATION_STR,
            "% a year",
        ),
    ]


def build_marker_list(plan: TimelinePlan) -> list[GanttMarker]:
    """Build the point-in-time events the plan carries.

    Brief:
        Lump sums, rebalances and notes happen in a month rather
        than over a stretch, so they are drawn as points on their
        own lane instead of as bars.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        List[GanttMarker]: Markers in calendar order.

    Warning:
        A note carries no amount, because it changes no number.
    """
    marker_type_tuple = (
        EVENT_LUMPSUM_STR,
        EVENT_REBALANCE_STR,
        EVENT_NOTE_STR,
    )
    return [
        GanttMarker(
            LANE_EVENTS_STR,
            event.event_date,
            event.event_type_str,
            event.event_type_str,
            (
                f"{event.amount_float:,.0f}"
                if event.amount_float
                else event.note_str
            ),
        )
        for event in plan.ordered_event_list
        if event.event_type_str in marker_type_tuple
    ]


def build_active_lane_list(plan: TimelinePlan) -> list[str]:
    """List the lanes this plan actually uses, in order.

    Brief:
        A plan with no salary should not show an empty salary lane,
        so the chart only reserves rows for lanes that carry
        something.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        List[str]: Lane names in the canonical order.

    Warning:
        Returns an empty list for a plan with nothing in it.
    """
    used_lane_set = {bar.lane_str for bar in build_bar_list(plan)}
    used_lane_set.update(
        marker.lane_str for marker in build_marker_list(plan)
    )
    return [
        lane_str
        for lane_str in LANE_ORDER_TUPLE
        if lane_str in used_lane_set
    ]
