"""The plan drawn as phases, regenerated on every keystroke.

Streamlit re-executes the whole script on every interaction, so this
chart is live by construction: change an amount, add an event, drag
the horizon, and the bars redraw from the freshly compiled settings.

The visual grammar is deliberately narrow. A **solid** bar means
money is moving. A **hatched, muted** bar means the same activity is
paused - drawn rather than omitted, because a gap you cannot see is
a gap you cannot reason about. A **quiet outlined** bar is context:
salary and inflation, which shape the answer without being actions
the reader takes.
"""

from __future__ import annotations

import plotly.graph_objects as go

from investment_journey_simulator.design_tokens import (
    FONT_STACK_STR,
    PANEL_GRID_STR,
    PANEL_SURFACE_STR,
)
from investment_journey_simulator.gantt import (
    KIND_CONTEXT_STR,
    KIND_PAUSED_STR,
    GanttBar,
    GanttMarker,
    build_active_lane_list,
    build_bar_list,
    build_marker_list,
)
from investment_journey_simulator.timeline import TimelinePlan
from investment_journey_simulator.ui.rail_view import (
    RAIL_INK_COLOUR_STR,
    RAIL_LINE_COLOUR_STR,
    RAIL_MUTED_COLOUR_STR,
)
from investment_journey_simulator.ui.timeline_view import (
    DEFAULT_MARKER_COLOUR_STR,
    DEFAULT_MARKER_SYMBOL_STR,
    EVENT_MARKER_COLOUR_DICT,
    EVENT_MARKER_SYMBOL_DICT,
)

ACTIVE_COLOUR_STR: str = "#2DD4BF"
PAUSED_COLOUR_STR: str = "#64748B"
CONTEXT_COLOUR_STR: str = "#7C8FA6"

MILLISECONDS_PER_DAY_INT: int = 86_400_000
BAR_THICKNESS_INT: int = 18
MARKER_SIZE_INT: int = 13
LANE_HEIGHT_INT: int = 46
BASE_HEIGHT_INT: int = 110
MINIMUM_HEIGHT_INT: int = 180
EMPTY_GANTT_MESSAGE_STR: str = (
    "Nothing is running yet. Add a **Start investing** event and "
    "the phases of your plan will appear here."
)

KIND_STYLE_DICT: dict[str, tuple] = {
    KIND_PAUSED_STR: (PAUSED_COLOUR_STR, "/", 0.55),
    KIND_CONTEXT_STR: (CONTEXT_COLOUR_STR, "", 0.40),
}
DEFAULT_STYLE_TUPLE: tuple = (ACTIVE_COLOUR_STR, "", 0.85)


def _resolve_style_tuple(kind_str: str) -> tuple:
    """Pick colour, hatch and opacity for one kind of bar.

    Brief:
        Three kinds only - running, paused, context - so the chart
        can be read without a legend once the rule is known.

    Arguments:
        kind_str (str): Bar kind.

    Returns:
        tuple: Colour, hatch pattern and opacity.

    Warning:
        An unknown kind is drawn as a running bar.
    """
    return KIND_STYLE_DICT.get(kind_str, DEFAULT_STYLE_TUPLE)


def _build_bar_hover_str(bar: GanttBar) -> str:
    """Compose the hover card for one phase bar.

    Brief:
        States what is in force, over which months, and for how
        long - the last being the part a reader cannot work out by
        looking at a bar.

    Arguments:
        bar (GanttBar): Bar being described.

    Returns:
        str: HTML hover text for Plotly.

    Warning:
        Plotly needs explicit breaks; newlines do nothing.
    """
    year_count_float = bar.months_int / 12.0
    return (
        f"<b>{bar.lane_str}</b><br>"
        f"{bar.label_str}<br>"
        f"{bar.start_date:%b %Y} to {bar.end_date:%b %Y}<br>"
        f"<span style='color:#8FA3B8'>{bar.months_int} months"
        f" ({year_count_float:.1f} years)</span>"
        "<extra></extra>"
    )


def _duration_milliseconds_int(bar: GanttBar) -> int:
    """Length of a bar in milliseconds, for a date axis.

    Brief:
        Plotly measures a horizontal bar on a date axis as a
        duration in milliseconds. Handing it a timedelta looks
        natural and fails at serialisation, so the conversion is
        done here once rather than inline.

    Arguments:
        bar (GanttBar): Bar being measured.

    Returns:
        int: Length in milliseconds, never negative.

    Warning:
        Measured in whole days, which is exact for a month grid
        anchored to the first of each month.
    """
    return max(
        0, (bar.end_date - bar.start_date).days
    ) * MILLISECONDS_PER_DAY_INT


def _add_bar_trace(
    figure: go.Figure,
    bar: GanttBar,
    lane_list: list[str],
) -> None:
    """Draw one phase as a horizontal bar on its lane.

    Brief:
        Uses a bar with a base rather than a shape, so Plotly gives
        it hover behaviour for free.

    Arguments:
        figure (go.Figure): Figure being populated.
        bar (GanttBar): Bar being drawn.
        lane_list (List[str]): Lanes in display order.

    Returns:
        None: One trace is added in place.

    Warning:
        Bars whose lane is not displayed are skipped.
    """
    if bar.lane_str not in lane_list:
        return
    colour_str, hatch_str, opacity_float = _resolve_style_tuple(
        bar.kind_str
    )
    figure.add_trace(
        go.Bar(
            x=[_duration_milliseconds_int(bar)],
            y=[bar.lane_str],
            base=[bar.start_date],
            orientation="h",
            width=BAR_THICKNESS_INT / 24.0,
            marker=dict(
                color=colour_str,
                opacity=opacity_float,
                pattern=dict(shape=hatch_str, size=4),
                line=dict(width=0),
            ),
            showlegend=False,
            hovertemplate=_build_bar_hover_str(bar),
        )
    )


def _add_marker_trace(
    figure: go.Figure,
    marker: GanttMarker,
) -> None:
    """Draw one point-in-time event on the events lane.

    Brief:
        Shape and colour follow the same mapping the rail uses, so
        a lump sum looks like a lump sum on both charts.

    Arguments:
        figure (go.Figure): Figure being populated.
        marker (GanttMarker): Marker being drawn.

    Returns:
        None: One trace is added in place.

    Warning:
        Kept out of the legend; the hover card carries the label.
    """
    detail_str = (
        f"<br>{marker.detail_str}" if marker.detail_str else ""
    )
    figure.add_trace(
        go.Scatter(
            x=[marker.marker_date],
            y=[marker.lane_str],
            mode="markers",
            showlegend=False,
            marker=dict(
                size=MARKER_SIZE_INT,
                symbol=EVENT_MARKER_SYMBOL_DICT.get(
                    marker.event_type_str, DEFAULT_MARKER_SYMBOL_STR
                ),
                color=EVENT_MARKER_COLOUR_DICT.get(
                    marker.event_type_str, DEFAULT_MARKER_COLOUR_STR
                ),
                line=dict(width=2, color="#101C2B"),
            ),
            hovertemplate=(
                f"<b>{marker.label_str}</b><br>"
                f"{marker.marker_date:%b %Y}{detail_str}"
                "<extra></extra>"
            ),
        )
    )


def build_gantt_figure(plan: TimelinePlan) -> go.Figure:
    """Draw the plan as phases, one lane per kind of activity.

    Brief:
        Regenerated from the compiled settings every time the page
        reruns, which is what makes it live while the plan is being
        typed rather than something to press a button for.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        go.Figure: Gantt chart, empty when the plan does nothing.

    Warning:
        Lanes carrying nothing are omitted, so the chart's height
        changes as the plan grows.
    """
    lane_list = build_active_lane_list(plan)
    figure = go.Figure()
    for bar in build_bar_list(plan):
        _add_bar_trace(figure, bar, lane_list)
    for marker in build_marker_list(plan):
        _add_marker_trace(figure, marker)
    return _apply_gantt_layout(figure, lane_list, plan)


def _apply_gantt_layout(
    figure: go.Figure,
    lane_list: list[str],
    plan: TimelinePlan,
) -> go.Figure:
    """Style the Gantt and lock its axes to the plan.

    Brief:
        The time axis is pinned to the whole horizon so bars keep
        their meaning as events are added, rather than rescaling
        under the reader every time.

    Arguments:
        figure (go.Figure): Figure being styled.
        lane_list (List[str]): Lanes in display order.
        plan (TimelinePlan): Plan supplying the axis range.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        Lanes are reversed so the first reads at the top.
    """
    figure.update_layout(
        height=max(
            MINIMUM_HEIGHT_INT,
            BASE_HEIGHT_INT + LANE_HEIGHT_INT * len(lane_list),
        ),
        margin=dict(t=10, l=10, r=10, b=10),
        paper_bgcolor=PANEL_SURFACE_STR,
        plot_bgcolor=PANEL_SURFACE_STR,
        font=dict(
            color=RAIL_INK_COLOUR_STR,
            size=12,
            family=FONT_STACK_STR,
        ),
        barmode="overlay",
        bargap=0.35,
        hovermode="closest",
        hoverlabel=_build_hover_label_dict(),
        xaxis=_build_gantt_time_axis_dict(plan),
        yaxis=dict(
            categoryorder="array",
            categoryarray=list(reversed(lane_list)),
            showgrid=False,
            tickfont=dict(color=RAIL_INK_COLOUR_STR, size=12),
        ),
    )
    return figure


def _build_hover_label_dict() -> dict:
    """The tooltip, on the same panel surface as the chart."""
    return dict(
        bgcolor=PANEL_SURFACE_STR,
        bordercolor=ACTIVE_COLOUR_STR,
        font=dict(
            color=RAIL_INK_COLOUR_STR,
            size=12,
            family=FONT_STACK_STR,
        ),
    )


def _build_gantt_time_axis_dict(plan: TimelinePlan) -> dict:
    """Pin the time axis to the plan's whole horizon.

    Brief:
        Fixing the range means a bar keeps its position as events
        are added, instead of the chart rescaling under the reader
        every time the plan changes.

    Arguments:
        plan (TimelinePlan): Plan supplying the range.

    Returns:
        dict: Plotly x-axis configuration.

    Warning:
        Ticks every two years; a very short horizon shows few.
    """
    return dict(
        type="date",
        range=[plan.start_date, plan.end_date],
        showgrid=True,
        gridcolor=PANEL_GRID_STR,
        linecolor=RAIL_LINE_COLOUR_STR,
        tickfont=dict(color=RAIL_MUTED_COLOUR_STR, size=11),
        dtick="M24",
        tickformat="%Y",
    )
