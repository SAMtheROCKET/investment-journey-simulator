"""The plan read back as a story, event by event.

A corpus figure at the end of thirty years answers *how much* but
never *how*. This module walks the simulated months alongside the
events that were placed on the rail and reports what the portfolio
was actually worth when each decision was taken - nominal, real, and
net of the tax paid up to that point.

It computes no finance of its own. Every figure is read out of a
`SimulationResult` the engine has already produced, which keeps this
module a reporting layer and nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from investment_journey_simulator.constants import MONTHS_IN_YEAR_INT
from investment_journey_simulator.inflation import (
    calculate_varying_deflation_factor_float,
)
from investment_journey_simulator.timeline import TimelineEvent, TimelinePlan


@dataclass(frozen=True)
class JourneyMilestone:
    """What the portfolio looked like when one event happened."""

    event: TimelineEvent
    month_index_int: int
    month_date: date
    portfolio_value_float: float
    invested_amount_float: float
    tax_paid_float: float
    real_value_float: float

    @property
    def gain_float(self) -> float:
        """Value above what was paid in by this point.

        Brief:
            Stated separately because the gap between corpus and
            principal is the only part of the corpus that is
            actually at risk of being taxed.

        Arguments:
            None.

        Returns:
            float: Nominal gain, negative when under water.

        Warning:
            Unrealized; nothing has been sold at this point.
        """
        return (
            self.portfolio_value_float - self.invested_amount_float
        )


def _locate_month_index_int(
    plan: TimelinePlan,
    event: TimelineEvent,
    month_count_int: int,
) -> int:
    """Find the simulated month an event belongs to.

    Brief:
        Events before the plan start clamp to the first month and
        events past the horizon to the last, so every milestone
        has a real month to report against.

    Arguments:
        plan (TimelinePlan): Plan supplying the origin.
        event (TimelineEvent): Event being located.
        month_count_int (int): Months actually simulated.

    Returns:
        int: Month index within the simulated range.

    Warning:
        Returns zero when nothing was simulated at all.
    """
    if month_count_int <= 0:
        return 0
    month_gap_int = (
        event.event_date.year - plan.start_date.year
    ) * MONTHS_IN_YEAR_INT + (
        event.event_date.month - plan.start_date.month
    )
    return min(max(0, month_gap_int), month_count_int - 1)


def build_milestone_list(
    plan: TimelinePlan,
    result,
    inflation_percent_float: float = 0.0,
    inflation_schedule_tuple: tuple = (),
) -> list[JourneyMilestone]:
    """Report the portfolio at every event on the timeline.

    Brief:
        Walks the plan in calendar order and reads the simulated
        snapshot for each event's month, so the story and the
        numbers can never drift apart.

    Arguments:
        plan (TimelinePlan): Plan that was run.
        result: Completed simulation result.
        inflation_percent_float (float): Opening annual rate.
        inflation_schedule_tuple (tuple): Dated rate changes.

    Returns:
        List[JourneyMilestone]: One entry per event, in order.

    Warning:
        Returns an empty list when nothing was simulated, rather
        than reporting milestones against months that do not
        exist.
    """
    snapshot_list = list(result.monthly_snapshots_list)
    if not snapshot_list:
        return []
    return [
        _build_milestone(
            plan,
            event,
            snapshot_list,
            inflation_percent_float,
            inflation_schedule_tuple,
        )
        for event in plan.ordered_event_list
    ]


def _build_milestone(
    plan: TimelinePlan,
    event: TimelineEvent,
    snapshot_list: list,
    inflation_percent_float: float,
    inflation_schedule_tuple: tuple = (),
) -> JourneyMilestone:
    """Read one event's month out of the simulated series.

    Brief:
        The real value is deflated at the event's own date, which
        is the same convention the rest of the package uses.

    Arguments:
        plan (TimelinePlan): Plan that was run.
        event (TimelineEvent): Event being reported.
        snapshot_list (list): Simulated monthly snapshots.
        inflation_percent_float (float): Opening annual rate.
        inflation_schedule_tuple (tuple): Dated rate changes.

    Returns:
        JourneyMilestone: What the portfolio was worth then.

    Warning:
        Assumes the snapshot list is non-empty.
    """
    month_index_int = _locate_month_index_int(
        plan, event, len(snapshot_list)
    )
    snapshot = snapshot_list[month_index_int]
    deflation_factor_float = (
        calculate_varying_deflation_factor_float(
            inflation_schedule_tuple,
            month_index_int,
            inflation_percent_float,
        )
    )
    return JourneyMilestone(
        event=event,
        month_index_int=month_index_int,
        month_date=snapshot.month_date,
        portfolio_value_float=snapshot.portfolio_value_float,
        invested_amount_float=snapshot.invested_amount_float,
        tax_paid_float=snapshot.tax_paid_float,
        real_value_float=(
            snapshot.portfolio_value_float / deflation_factor_float
        ),
    )


def summarise_milestone_str(milestone: JourneyMilestone) -> str:
    """Say in one line what changed at this point of the plan.

    Brief:
        The event's own explanation states the intent; this adds
        what the portfolio was worth when it was acted on, which
        is the part a table of settings can never show.

    Arguments:
        milestone (JourneyMilestone): Milestone being described.

    Returns:
        str: One sentence naming the event and the corpus.

    Warning:
        Formats plainly; the caller decides the currency style.
    """
    return (
        f"{milestone.month_date:%b %Y} - "
        f"{milestone.event.event_type_str}, with "
        f"{milestone.portfolio_value_float:,.0f} invested and "
        f"grown from {milestone.invested_amount_float:,.0f} paid "
        "in."
    )
