"""The plan rail: a bare timeline you place events on.

The classic dashboard asks for a plan as a form. `timeline_view`
draws the answer as a curve. This module is the third thing: an
*input surface*. One horizontal rail on a plain panel, nothing else
competing for attention, and you place the events of a life on it.

Two rules shape everything here. First, the reader must be able to
learn what an option does **before** committing to it, so every
event type carries its explanation as a hover tooltip. Second, the
rail is the input - clicking it places the armed event at that
month, rather than making the reader fill in a date field.

Placement snaps to a month because the engine's grid is monthly.
Nothing here computes any finance; it only produces `TimelineEvent`
values that `timeline.compile_settings` already knows how to turn
into engine settings.
"""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from investment_journey_simulator.design_tokens import (
    FONT_STACK_STR,
    PANEL_ACCENT_STR,
    PANEL_INK_STR,
    PANEL_LINE_STR,
    PANEL_MUTED_STR,
    PANEL_SPAN_STR,
    PANEL_SURFACE_STR,
)
from investment_journey_simulator.formatting import format_money_amount_str
from investment_journey_simulator.time_utils import (
    build_month_start_dates_list,
)
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_EXPLANATION_DICT,
    EVENT_LUMPSUM_STR,
    EVENT_NEEDS_AMOUNT_TUPLE,
    EVENT_NEEDS_PERCENT_TUPLE,
    EVENT_RETIRE_STR,
    EVENT_START_SIP_STR,
    EVENT_TYPE_TUPLE,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
)
from investment_journey_simulator.ui.timeline_view import (
    DEFAULT_MARKER_COLOUR_STR,
    DEFAULT_MARKER_SYMBOL_STR,
    EVENT_MARKER_COLOUR_DICT,
    EVENT_MARKER_SYMBOL_DICT,
)

# The rail draws on its own instrument panel rather than on the
# page. See `design_tokens.PANEL_SURFACE_STR` for why, and for the
# measured contrast of every pair below against it.
RAIL_PANEL_COLOUR_STR: str = PANEL_SURFACE_STR
RAIL_INK_COLOUR_STR: str = PANEL_INK_STR
RAIL_MUTED_COLOUR_STR: str = PANEL_MUTED_STR
RAIL_LINE_COLOUR_STR: str = PANEL_LINE_STR
RAIL_ACCENT_COLOUR_STR: str = PANEL_ACCENT_STR
RAIL_SPAN_COLOUR_STR: str = PANEL_SPAN_STR
TRANSPARENT_STR: str = "rgba(0,0,0,0)"

RAIL_HEIGHT_INT: int = 300
RAIL_BASELINE_FLOAT: float = 0.0
RAIL_SPAN_LEVEL_FLOAT: float = -0.75
RAIL_STACK_STEP_FLOAT: float = 0.55
RAIL_Y_MINIMUM_FLOAT: float = -3.2
RAIL_Y_MAXIMUM_FLOAT: float = 3.0
RAIL_DOT_SIZE_INT: int = 16
RAIL_HIT_SIZE_INT: int = 22
RAIL_HIT_OPACITY_FLOAT: float = 0.001
RAIL_PENDING_SIZE_INT: int = 22
RAIL_PENDING_LEADER_FLOAT: float = -1.2

# The cash-flow band sits below everything else on the rail:
# spans occupy -0.75 and the pending leader reaches -1.2, so the
# band stays clear of both.
#
# Its baseline is in the *middle* of the reserved space, not at the
# bottom, because arrows point both ways - up for money in, down
# for money out. A baseline at the floor clipped every withdrawal,
# which `test_every_arrow_fits_inside_the_axis` now prevents.
MONEY_BASE_FLOAT: float = -2.4
MONEY_MAXIMUM_HEIGHT_FLOAT: float = 0.75
MONEY_MINIMUM_HEIGHT_FLOAT: float = 0.12
MONEY_IN_COLOUR_STR: str = "#2DD4BF"
MONEY_OUT_COLOUR_STR: str = "#F87171"
MONEY_ARROW_WIDTH_INT: int = 3
MONEY_ARROW_HEAD_SIZE_INT: int = 9
MONTHS_IN_YEAR_INT: int = 12

# Events that move money, split by whether the amount repeats
# every month or lands once. The split decides how an arrow is
# sized, not what the engine does with the figure.
EVENT_RECURRING_MONEY_TUPLE: tuple = (
    EVENT_START_SIP_STR,
    EVENT_CHANGE_SIP_STR,
    EVENT_WITHDRAW_STR,
    EVENT_RETIRE_STR,
)
EVENT_ONE_OFF_MONEY_TUPLE: tuple = (EVENT_LUMPSUM_STR,)
EVENT_MONEY_OUT_TUPLE: tuple = (
    EVENT_WITHDRAW_STR,
    EVENT_RETIRE_STR,
)
PALETTE_COLUMN_COUNT_INT: int = 3

ARMED_STATE_KEY_STR: str = "rail_armed_event_type"
PENDING_STATE_KEY_STR: str = "rail_pending_month_index"
QUICK_PLACE_STATE_KEY_STR: str = "rail_quick_place_enabled"

QUICK_PLACE_LABEL_STR: str = "Quick place"
QUICK_PLACE_HELP_STR: str = (
    "Keep one kind of event armed so you can drop several onto "
    "the timeline without choosing each time. Useful once you "
    "know the event types; unnecessary before then."
)
IDLE_HINT_STR: str = (
    "Click any month on the timeline to add something there."
)
RAIL_FIGURE_KEY_STR: str = "rail_figure"

# Hovering any month offers to add something there. Plotly cannot
# render a real button inside a hover label, so the plus lives in
# the label itself - the affordance a reader actually sees, and the
# click that follows is handled by the chart's selection event.
ADD_HERE_HOVER_STR: str = (
    "<b>＋  Add an event here</b><br>"
    "%{x|%b %Y}<br>"
    "<span style='color:#8FA3B8'>click to choose what happens"
    "</span><extra></extra>"
)

# Hovering a placed dot offers to take it away again. The minus is
# the counterpart of the plus on empty months: one gesture adds,
# the same gesture on something that exists removes it.
REMOVE_HINT_STR: str = (
    "<br><span style='color:#F87171'>−  click to remove</span>"
)
COUNT_HINT_STR: str = (
    "<br><span style='color:#8FA3B8'>{count} events this month"
    "</span>"
)

# Derived from the page's own text colour rather than fixed, for
# the same reason as everything else in this project: a panel with
# a hardcoded dark surface is a panel that inverts the moment the
# theme it was drawn for is not the theme running.
# The panel's surface is stated once, in `design_tokens`, and this
# template fills it in. The colours are not written here, so this
# stylesheet cannot drift from the figure that sits inside it.
RAIL_STYLE_TEMPLATE_STR: str = """
<style>
  .rail-panel {{
      background: {panel};
      border: 1px solid {line};
      border-radius: 3px;
      padding: .9rem 1.1rem .4rem 1.1rem;
  }}
  .rail-panel .rail-hint {{
      color: {muted};
      font-size: .8rem; font-weight: 300;
      margin: .1rem 0 .6rem 0;
  }}
  .rail-panel .rail-armed {{
      color: {accent};
      font-size: .82rem; font-weight: 500;
      letter-spacing: .04em;
  }}
</style>
"""


def build_rail_style_str() -> str:
    """Fill the panel template in from the tokens."""
    return RAIL_STYLE_TEMPLATE_STR.format(
        panel=PANEL_SURFACE_STR,
        line=PANEL_LINE_STR,
        muted=PANEL_MUTED_STR,
        accent=PANEL_ACCENT_STR,
    )


def render_rail_style() -> None:
    """Inject the rail panel's styling once.

    The panel around the rail, matching the surface the figure
    inside it draws on, so the two read as one instrument.

    Returns:
        None: A style block is written to the page.
    """
    st.markdown(build_rail_style_str(), unsafe_allow_html=True)


def read_armed_event_type_str() -> str:
    """Read which event type is currently ready to place.

    Brief:
        Streamlit reruns the whole script on every interaction, so
        the armed choice has to live in session state.

    Arguments:
        None.

    Returns:
        str: Armed event type, empty when nothing is armed.

    Warning:
        Seeds an empty selection on first use.
    """
    if ARMED_STATE_KEY_STR not in st.session_state:
        st.session_state[ARMED_STATE_KEY_STR] = ""
    return str(st.session_state[ARMED_STATE_KEY_STR])


def read_quick_place_bool() -> bool:
    """Whether the reader has asked for the arming palette.

    Brief:
        Off by default, and deliberately so. The timeline is the
        interface: you click a month and say what happens there.
        A row of thirteen chips above it turns that one gesture
        into a lesson in event taxonomy before a reader has placed
        anything at all.

        Arming stays available because it earns its place on the
        second visit - dropping four pauses in a row is tedious
        when every one asks you again what it is.

    Arguments:
        None.

    Returns:
        bool: True when the palette should be shown.

    Warning:
        Turning it off disarms whatever was armed, so the rail
        cannot be left in a state whose control is hidden.
    """
    if QUICK_PLACE_STATE_KEY_STR not in st.session_state:
        st.session_state[QUICK_PLACE_STATE_KEY_STR] = False
    return bool(st.session_state[QUICK_PLACE_STATE_KEY_STR])


def render_quick_place_toggle() -> bool:
    """Offer the arming palette without leading with it."""
    is_enabled_bool = st.toggle(
        QUICK_PLACE_LABEL_STR,
        value=read_quick_place_bool(),
        help=QUICK_PLACE_HELP_STR,
        key=QUICK_PLACE_STATE_KEY_STR,
    )
    if not is_enabled_bool:
        st.session_state[ARMED_STATE_KEY_STR] = ""
    return bool(is_enabled_bool)


def read_pending_month_index_int() -> int | None:
    """Read the month the reader clicked but has not filled in yet.

    Brief:
        Clicking the rail says *when* something happens; choosing
        from the dropdown says *what*. Between those two moments
        the month has to be remembered somewhere.

    Arguments:
        None.

    Returns:
        Optional[int]: Month awaiting an event, or None.

    Warning:
        None means no click is pending, not month zero.
    """
    value = st.session_state.get(PENDING_STATE_KEY_STR)
    return None if value is None else int(value)


def set_pending_month_index(month_index_int: int) -> None:
    """Remember which month the reader just clicked.

    Brief:
        Stored rather than acted on immediately, because the event
        type is chosen in the step that follows.

    Arguments:
        month_index_int (int): Month clicked on the rail.

    Returns:
        None: Session state is updated.

    Warning:
        Mutates session state; the caller must rerun.
    """
    st.session_state[PENDING_STATE_KEY_STR] = int(month_index_int)


def clear_pending_month_index() -> None:
    """Forget a pending click.

    Brief:
        Called once the event is placed, or when the reader
        cancels, so a stale month cannot attach itself to the next
        thing they choose.

    Arguments:
        None.

    Returns:
        None: Session state is updated.

    Warning:
        Safe to call when nothing is pending.
    """
    st.session_state[PENDING_STATE_KEY_STR] = None


def render_event_palette() -> str:
    """Show the event types as chips that explain themselves.

    Brief:
        Each chip carries its explanation as a hover tooltip, so
        the reader learns what an option does before choosing it.
        Clicking a chip arms that event type for placement.

    Arguments:
        None.

    Returns:
        str: The event type now armed, empty when none is.

    Warning:
        Mutates session state and reruns when a chip is clicked.
    """
    armed_type_str = read_armed_event_type_str()
    column_list = st.columns(PALETTE_COLUMN_COUNT_INT)
    for event_index_int, event_type_str in enumerate(
        EVENT_TYPE_TUPLE
    ):
        column = column_list[
            event_index_int % PALETTE_COLUMN_COUNT_INT
        ]
        is_armed_bool = event_type_str == armed_type_str
        if column.button(
            ("● " if is_armed_bool else "○ ") + event_type_str,
            key=f"arm_{event_index_int}",
            help=EVENT_EXPLANATION_DICT.get(event_type_str, ""),
            width="stretch",
        ):
            st.session_state[ARMED_STATE_KEY_STR] = (
                "" if is_armed_bool else event_type_str
            )
            st.rerun()
    return armed_type_str


def render_armed_hint(armed_type_str: str) -> None:
    """Tell the reader what clicking the rail will now do.

    Brief:
        An armed rail behaves differently from an idle one, and
        that difference has to be visible rather than remembered.

    Arguments:
        armed_type_str (str): Currently armed event type.

    Returns:
        None: A hint line is written to the page.

    Warning:
        Renders as HTML.
    """
    if not armed_type_str:
        st.markdown(
            f'<div class="rail-hint">{IDLE_HINT_STR}</div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'<div class="rail-armed">Click the rail to place: '
        f"{armed_type_str}</div>",
        unsafe_allow_html=True,
    )


def build_month_date_list(plan: TimelinePlan) -> list[date]:
    """Build the month grid the rail is drawn on.

    Brief:
        The same grid the engine simulates, so a click can only
        ever land on a month the simulation actually has.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        List[date]: One date per month of the horizon.

    Warning:
        A zero horizon produces an empty rail.
    """
    return build_month_start_dates_list(
        plan.start_date, plan.horizon_years_int * 12
    )


def _build_stack_level_dict(
    plan: TimelinePlan,
) -> dict[int, list[tuple]]:
    """Group the plan's events by the month they happen in.

    Brief:
        Several things may happen in one month of a life, so the
        rail stacks them upward rather than drawing them on top of
        one another. Each entry carries the event's position in the
        ordered list, so a click on a dot can be traced back to the
        event it belongs to.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        Dict[int, List[tuple]]: Position and event, keyed by month.

    Warning:
        Months are measured from the plan start and never negative.
    """
    grouped_dict: dict[int, list[tuple]] = {}
    for position_int, event in enumerate(plan.ordered_event_list):
        month_index_int = max(
            0,
            (event.event_date.year - plan.start_date.year) * 12
            + (event.event_date.month - plan.start_date.month),
        )
        grouped_dict.setdefault(month_index_int, []).append(
            (position_int, event)
        )
    return grouped_dict


def build_dot_order_list(plan: TimelinePlan) -> list[int]:
    """Positions of the events in the order their dots are drawn.

    Brief:
        A click reports which trace it hit, and the dots are traces
        added in this order. Exposing the order here - beside the
        code that draws them - keeps the mapping in one place
        instead of leaving the page to guess it.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        List[int]: Positions into the ordered event list.

    Warning:
        Must stay in step with `_add_event_dots`.
    """
    return [
        position_int
        for entry_list in _build_stack_level_dict(plan).values()
        for position_int, _ in entry_list
    ]


def _build_dot_hover_str(
    event: TimelineEvent,
    month_count_int: int = 1,
) -> str:
    """Compose the hover card for one placed event.

    Brief:
        Names the event, dates it, states its amount, explains
        what it does, says how many events share the month, and
        offers to remove it - so the rail teaches, records and
        edits from the same gesture.

    Arguments:
        event (TimelineEvent): Event being described.
        month_count_int (int): Events sharing this month.

    Returns:
        str: HTML hover text for Plotly.

    Warning:
        Plotly needs explicit breaks; newlines do nothing.
    """
    detail_str = ""
    if event.amount_float:
        detail_str = (
            f"<br>{format_money_amount_str(event.amount_float)}"
        )
    elif event.percent_float:
        detail_str = f"<br>{event.percent_float:.1f}% a year"
    count_str = (
        COUNT_HINT_STR.format(count=month_count_int)
        if month_count_int > 1
        else ""
    )
    return (
        f"<b>{event.event_type_str}</b><br>"
        f"{event.event_date:%b %Y}{detail_str}<br>"
        f"<span style='color:#8FA3B8'>"
        f"{EVENT_EXPLANATION_DICT.get(event.event_type_str, '')}"
        f"</span>{count_str}{REMOVE_HINT_STR}<extra></extra>"
    )


def _add_hit_layer(
    figure: go.Figure,
    month_date_list: list[date],
) -> None:
    """Add the invisible layer that makes the rail clickable.

    Brief:
        Plotly reports selections of *points*, not of empty space,
        so one near-invisible point per month gives the rail a
        target to snap a click to.

    Arguments:
        figure (go.Figure): Figure being populated.
        month_date_list (List[date]): Month grid.

    Returns:
        None: One trace is added in place.

    Warning:
        Must be trace zero, since the click reader identifies it
        by position rather than by name.
    """
    figure.add_trace(
        go.Scatter(
            x=month_date_list,
            y=[RAIL_BASELINE_FLOAT] * len(month_date_list),
            mode="markers",
            name="rail",
            showlegend=False,
            marker=dict(
                size=RAIL_HIT_SIZE_INT,
                color=RAIL_ACCENT_COLOUR_STR,
                opacity=RAIL_HIT_OPACITY_FLOAT,
            ),
            hovertemplate=ADD_HERE_HOVER_STR,
        )
    )


def _add_rail_line(
    figure: go.Figure,
    month_date_list: list[date],
) -> None:
    """Draw the rail itself.

    Brief:
        One quiet horizontal line. It carries no data, so it is
        drawn thin and unlabelled.

    Arguments:
        figure (go.Figure): Figure being populated.
        month_date_list (List[date]): Month grid.

    Returns:
        None: One trace is added in place.

    Warning:
        Skipped entirely when the horizon is empty.
    """
    if not month_date_list:
        return
    figure.add_trace(
        go.Scatter(
            x=[month_date_list[0], month_date_list[-1]],
            y=[RAIL_BASELINE_FLOAT, RAIL_BASELINE_FLOAT],
            mode="lines",
            showlegend=False,
            hoverinfo="skip",
            line=dict(width=2, color=RAIL_LINE_COLOUR_STR),
        )
    )


def _add_span_bars(
    figure: go.Figure,
    span_list: list[tuple],
) -> None:
    """Draw events that last, rather than events that happen.

    Brief:
        A pause is not a moment, it is a window. Drawing it as a
        bar beneath the rail says so without needing a legend.

    Arguments:
        figure (go.Figure): Figure being populated.
        span_list (List[tuple]): Start, end and label per span.

    Returns:
        None: One trace per span is added in place.

    Warning:
        A span whose end precedes its start is skipped.
    """
    for start_date, end_date, label_str in span_list:
        if end_date < start_date:
            continue
        figure.add_trace(
            go.Scatter(
                x=[start_date, end_date],
                y=[RAIL_SPAN_LEVEL_FLOAT, RAIL_SPAN_LEVEL_FLOAT],
                mode="lines",
                showlegend=False,
                line=dict(width=9, color=RAIL_SPAN_COLOUR_STR),
                hovertemplate=(
                    f"<b>{label_str}</b><br>"
                    f"{start_date:%b %Y} to {end_date:%b %Y}"
                    "<extra></extra>"
                ),
            )
        )


def _add_event_dots(
    figure: go.Figure,
    plan: TimelinePlan,
    month_date_list: list[date],
) -> None:
    """Place one dot per event, stacking those that share a month.

    Brief:
        Shape and colour both encode the event type, so the rail
        stays readable without relying on hue alone.

    Arguments:
        figure (go.Figure): Figure being populated.
        plan (TimelinePlan): Plan supplying the events.
        month_date_list (List[date]): Month grid.

    Returns:
        None: One trace per event is added in place.

    Warning:
        Events past the horizon are clamped to the last month.
    """
    if not month_date_list:
        return
    last_index_int = len(month_date_list) - 1
    for month_index_int, entry_list in _build_stack_level_dict(
        plan
    ).items():
        clamped_index_int = min(month_index_int, last_index_int)
        for stack_index_int, (_, event) in enumerate(entry_list):
            figure.add_trace(
                _build_dot_trace(
                    event,
                    month_date_list[clamped_index_int],
                    stack_index_int * RAIL_STACK_STEP_FLOAT,
                    len(entry_list),
                )
            )


def _build_dot_trace(
    event: TimelineEvent,
    marker_date: date,
    stack_offset_float: float,
    month_count_int: int = 1,
) -> go.Scatter:
    """Build the marker for one placed event.

    Brief:
        A short stem ties a stacked dot back to the rail, so the
        reader can still see which month it belongs to.

    Arguments:
        event (TimelineEvent): Event being drawn.
        marker_date (date): Month the dot sits above.
        stack_offset_float (float): Height above the rail.
        month_count_int (int): Events sharing this month.

    Returns:
        go.Scatter: Stem and marker as one trace.

    Warning:
        Kept out of the legend; the hover card carries the label.
    """
    return go.Scatter(
        x=[marker_date, marker_date],
        y=[RAIL_BASELINE_FLOAT, stack_offset_float],
        mode="lines+markers",
        showlegend=False,
        line=dict(width=1, color=RAIL_LINE_COLOUR_STR),
        marker=dict(
            size=[0, RAIL_DOT_SIZE_INT],
            symbol=EVENT_MARKER_SYMBOL_DICT.get(
                event.event_type_str, DEFAULT_MARKER_SYMBOL_STR
            ),
            color=EVENT_MARKER_COLOUR_DICT.get(
                event.event_type_str, DEFAULT_MARKER_COLOUR_STR
            ),
            line=dict(width=2, color="#101C2B"),
        ),
        hovertemplate=_build_dot_hover_str(
            event, month_count_int
        ),
    )


def build_rail_figure(
    plan: TimelinePlan,
    span_list: list[tuple] | None = None,
    pending_month_index_int: int | None = None,
) -> go.Figure:
    """Draw the bare rail with the plan's events on it.

    Brief:
        No corpus, no axis of rupees, nothing but time and the
        decisions placed along it. The money belongs on the result
        page; this one is for describing the plan.

    Arguments:
        plan (TimelinePlan): Plan being drawn.
        span_list (Optional[List[tuple]]): Spanning events.
        pending_month_index_int (Optional[int]): Month the reader
            has clicked but not yet answered for.

    Returns:
        go.Figure: Clickable rail.

    Warning:
        The hit layer must stay as trace zero for click reading.
    """
    month_date_list = build_month_date_list(plan)
    figure = go.Figure()
    _add_hit_layer(figure, month_date_list)
    _add_rail_line(figure, month_date_list)
    _add_span_bars(figure, span_list or [])
    _add_event_dots(figure, plan, month_date_list)
    _add_money_arrows(figure, plan, month_date_list)
    _add_pending_marker(
        figure, month_date_list, pending_month_index_int
    )
    return _apply_rail_layout(figure)


def build_yearly_amount_float(event: TimelineEvent) -> float:
    """How much this event moves in a year, for sizing only.

    Brief:
        A lump sum and an instalment are not comparable as typed.
        ₹5,00,000 once looks twenty times ₹25,000 a month, while
        the instalment is worth far more over any real horizon.

        Sizing both by *money per year* - the instalment
        annualised, the lump sum as itself - compares like with
        like. It is still an approximation, which is why the exact
        figure is in the hover and only the height is derived.

    Arguments:
        event (TimelineEvent): Event being sized.

    Returns:
        float: Annualised magnitude, zero when it moves no money.

    Warning:
        Sizing only. Nothing here reaches the engine, which reads
        the typed amount and never this.
    """
    if event.event_type_str in EVENT_RECURRING_MONEY_TUPLE:
        return abs(event.amount_float) * MONTHS_IN_YEAR_INT
    if event.event_type_str in EVENT_ONE_OFF_MONEY_TUPLE:
        return abs(event.amount_float)
    return 0.0


def _is_money_out_bool(event: TimelineEvent) -> bool:
    """Whether this event takes money out rather than putting in."""
    return event.event_type_str in EVENT_MONEY_OUT_TUPLE


def _add_money_arrows(
    figure: go.Figure,
    plan: TimelinePlan,
    month_date_list: list[date],
) -> None:
    """Draw the cash flows as arrows beneath the rail.

    Brief:
        The rail says *when* things happen. This band says *how
        much*, so a reader sees the shape of their contributions
        without reading a single number - up for money in, down
        for money out, height for size.

    Arguments:
        figure (go.Figure): Rail being drawn.
        plan (TimelinePlan): Plan being drawn.
        month_date_list (List[date]): The month grid.

    Returns:
        None: One trace per flow is added in place.

    Warning:
        Heights are relative to the largest flow in *this* plan,
        so two plans' bands cannot be compared by eye. The
        comparison that matters is between flows within one plan.
    """
    flow_list = [
        (event, build_yearly_amount_float(event))
        for event in plan.ordered_event_list
    ]
    flow_list = [
        (event, amount_float)
        for event, amount_float in flow_list
        if amount_float > 0.0
    ]
    if not flow_list:
        return
    largest_float = max(
        amount_float for _event, amount_float in flow_list
    )
    for event, amount_float in flow_list:
        _add_one_arrow(
            figure,
            event,
            amount_float,
            largest_float,
            month_date_list,
        )


def _add_one_arrow(
    figure: go.Figure,
    event: TimelineEvent,
    amount_float: float,
    largest_float: float,
    month_date_list: list[date],
) -> None:
    """Draw one cash flow as an arrow in the band."""
    month_index_int = _resolve_event_month_int(
        event, plan_start_date=month_date_list[0]
    )
    if not 0 <= month_index_int < len(month_date_list):
        return
    share_float = amount_float / largest_float
    height_float = MONEY_MINIMUM_HEIGHT_FLOAT + share_float * (
        MONEY_MAXIMUM_HEIGHT_FLOAT - MONEY_MINIMUM_HEIGHT_FLOAT
    )
    is_out_bool = _is_money_out_bool(event)
    tip_float = MONEY_BASE_FLOAT + (
        -height_float if is_out_bool else height_float
    )
    colour_str = (
        MONEY_OUT_COLOUR_STR
        if is_out_bool
        else MONEY_IN_COLOUR_STR
    )
    _add_arrow_traces(
        figure,
        month_date_list[month_index_int],
        tip_float,
        colour_str,
        is_out_bool,
        _build_arrow_hover_str(event),
    )


def _add_arrow_traces(
    figure: go.Figure,
    flow_date: date,
    tip_float: float,
    colour_str: str,
    is_out_bool: bool,
    hover_str: str,
) -> None:
    """Draw one arrow as a shaft and a separate head.

    Brief:
        Two traces rather than one `lines+markers` trace, because
        an event dot is identified elsewhere by exactly that mode
        and an arrow drawn the same way is counted as a dot. Both
        parts carry the same hover, so the arrow reads as one
        object however it is pointed at.

    Arguments:
        figure (go.Figure): Rail being drawn.
        flow_date (date): Month the flow lands in.
        tip_float (float): Where the head sits.
        colour_str (str): Colour of both parts.
        is_out_bool (bool): True when money leaves.
        hover_str (str): Shared hover label.

    Returns:
        None: Two traces are added in place.
    """
    figure.add_trace(
        go.Scatter(
            x=[flow_date, flow_date],
            y=[MONEY_BASE_FLOAT, tip_float],
            mode="lines",
            showlegend=False,
            hovertemplate=hover_str,
            line=dict(
                width=MONEY_ARROW_WIDTH_INT, color=colour_str
            ),
        )
    )
    figure.add_trace(
        _build_arrow_head_trace(
            flow_date,
            tip_float,
            colour_str,
            is_out_bool,
            hover_str,
        )
    )


def _build_arrow_head_trace(
    flow_date: date,
    tip_float: float,
    colour_str: str,
    is_out_bool: bool,
    hover_str: str,
) -> go.Scatter:
    """The triangle at the end of one cash-flow arrow."""
    return go.Scatter(
        x=[flow_date],
        y=[tip_float],
        mode="markers",
        showlegend=False,
        hovertemplate=hover_str,
        marker=dict(
            size=MONEY_ARROW_HEAD_SIZE_INT,
            symbol=(
                "triangle-down" if is_out_bool else "triangle-up"
            ),
            color=colour_str,
        ),
    )


def _resolve_event_month_int(
    event: TimelineEvent,
    plan_start_date: date,
) -> int:
    """Month index of an event on the rail's grid."""
    return (event.event_date.year - plan_start_date.year) * (
        MONTHS_IN_YEAR_INT
    ) + (event.event_date.month - plan_start_date.month)


def _build_arrow_hover_str(event: TimelineEvent) -> str:
    """Name the flow and its exact amount, as typed."""
    direction_str = (
        "out" if _is_money_out_bool(event) else "in"
    )
    amount_str = format_money_amount_str(event.amount_float)
    period_str = (
        " a month"
        if event.event_type_str in EVENT_RECURRING_MONEY_TUPLE
        else ""
    )
    return (
        f"<b>{event.event_type_str}</b><br>"
        f"{amount_str}{period_str} - money {direction_str}"
        "<extra></extra>"
    )


def _add_pending_marker(
    figure: go.Figure,
    month_date_list: list[date],
    pending_month_index_int: int | None,
) -> None:
    """Mark the month the reader just clicked, and point at it.

    Brief:
        A click asks a question, and the question is answered in a
        panel underneath. Without a mark on the rail the reader
        has to remember which month they hit, and the panel reads
        as unrelated to the thing they were looking at.

        A ring on the rail and a short leader dropping from it do
        what the dotted line does on paper: they say *this month,
        and the answer is down there*.

    Arguments:
        figure (go.Figure): Rail being drawn.
        month_date_list (List[date]): The month grid.
        pending_month_index_int (Optional[int]): Month clicked.

    Returns:
        None: Traces are added in place.

    Warning:
        Added last so it sits above the dots. It must never be
        trace zero, which the click reader depends on being the
        hit layer.
    """
    if pending_month_index_int is None:
        return
    if not 0 <= pending_month_index_int < len(month_date_list):
        return
    pending_date = month_date_list[pending_month_index_int]
    figure.add_trace(_build_leader_trace(pending_date))
    figure.add_trace(_build_pending_ring_trace(pending_date))


def _build_leader_trace(pending_date: date) -> go.Scatter:
    """The dotted line dropping from the rail to the answer."""
    return go.Scatter(
        x=[pending_date, pending_date],
        y=[RAIL_BASELINE_FLOAT, RAIL_PENDING_LEADER_FLOAT],
        mode="lines",
        showlegend=False,
        hoverinfo="skip",
        line=dict(
            width=1.5,
            color=RAIL_ACCENT_COLOUR_STR,
            dash="dot",
        ),
    )


def _build_pending_ring_trace(pending_date: date) -> go.Scatter:
    """The open ring marking the month awaiting an answer.

    Brief:
        Hollow rather than filled, so it cannot be mistaken for a
        placed event. Nothing has been added yet.

    Arguments:
        pending_date (date): Month the reader clicked.

    Returns:
        go.Scatter: The ring trace.

    Warning:
        Shares the accent colour with the leader, so the two read
        as one mark rather than two.
    """
    return go.Scatter(
        x=[pending_date],
        y=[RAIL_BASELINE_FLOAT],
        mode="markers",
        showlegend=False,
        hovertemplate=(
            f"{pending_date:%B %Y}<br>"
            "choose what happens here<extra></extra>"
        ),
        marker=dict(
            size=RAIL_PENDING_SIZE_INT,
            color=TRANSPARENT_STR,
            line=dict(width=2.5, color=RAIL_ACCENT_COLOUR_STR),
        ),
    )


def _build_rail_hover_label_dict() -> dict:
    """The tooltip, on the same panel the rail is drawn on."""
    return dict(
        bgcolor=RAIL_PANEL_COLOUR_STR,
        bordercolor=RAIL_ACCENT_COLOUR_STR,
        font=dict(
            color=RAIL_INK_COLOUR_STR,
            size=12,
            family=FONT_STACK_STR,
        ),
    )


def _apply_rail_layout(figure: go.Figure) -> go.Figure:
    """Strip the chart down to a rail.

    Brief:
        The vertical axis carries no meaning here, so it is hidden
        entirely and the height is fixed rather than scaled.

    Arguments:
        figure (go.Figure): Figure being styled.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        A fixed y-range keeps stacked dots inside the panel.
    """
    figure.update_layout(
        height=RAIL_HEIGHT_INT,
        # The year labels sit under the axis and need room to do
        # it. At b=10 they were clipped away entirely, which left
        # the rail floating with no scale on it at all.
        margin=dict(t=14, l=18, r=18, b=34),
        paper_bgcolor=RAIL_PANEL_COLOUR_STR,
        plot_bgcolor=RAIL_PANEL_COLOUR_STR,
        font=dict(
            color=RAIL_INK_COLOUR_STR,
            size=12,
            family=FONT_STACK_STR,
        ),
        hovermode="closest",
        clickmode="event+select",
        dragmode=False,
        hoverlabel=_build_rail_hover_label_dict(),
        xaxis=dict(
            showgrid=False,
            linecolor=RAIL_LINE_COLOUR_STR,
            tickcolor=RAIL_LINE_COLOUR_STR,
            tickfont=dict(color=RAIL_MUTED_COLOUR_STR, size=11),
            dtick="M24",
            tickformat="%Y",
        ),
        yaxis=dict(
            visible=False,
            fixedrange=True,
            range=[RAIL_Y_MINIMUM_FLOAT, RAIL_Y_MAXIMUM_FLOAT],
        ),
    )
    return figure


def read_clicked_month_index_int(
    selection_result,
    month_count_int: int,
) -> int | None:
    """Turn a click on the rail into a month index.

    Brief:
        Only clicks on the hit layer count, so clicking an event
        dot inspects it rather than placing a second event on top
        of it.

    Arguments:
        selection_result: Value returned by the chart.
        month_count_int (int): Months on the rail.

    Returns:
        Optional[int]: Month clicked, or None when nothing was.

    Warning:
        Returns None rather than guessing when the payload does
        not carry a usable point index.
    """
    point_list = _extract_point_list(selection_result)
    for point_dict in point_list:
        if point_dict.get("curve_number") != 0:
            continue
        index_int = point_dict.get("point_index")
        if index_int is None:
            continue
        if 0 <= int(index_int) < int(month_count_int):
            return int(index_int)
    return None


def resolve_clicked_event_index_int(
    selection_result,
    plan: TimelinePlan,
    span_count_int: int,
) -> int | None:
    """Turn a click on a placed dot back into its event.

    Brief:
        The rail draws the hit layer, then the rail line, then one
        trace per span, then one per dot. A click reports the trace
        it hit, so the event is that trace's offset into the dot
        order.

    Arguments:
        selection_result: Value returned by the chart.
        plan (TimelinePlan): Plan that was drawn.
        span_count_int (int): Spanning bars drawn beneath the rail.

    Returns:
        Optional[int]: Position of the clicked event, or None.

    Warning:
        Returns None for a click on anything that is not a dot,
        which is what keeps adding and removing distinct.
    """
    first_dot_curve_int = 2 + max(0, int(span_count_int))
    order_list = build_dot_order_list(plan)
    for point_dict in _extract_point_list(selection_result):
        curve_number_int = point_dict.get("curve_number")
        if curve_number_int is None:
            continue
        dot_index_int = int(curve_number_int) - first_dot_curve_int
        if 0 <= dot_index_int < len(order_list):
            return order_list[dot_index_int]
    return None


def _extract_point_list(selection_result) -> list:
    """Dig the selected points out of the chart's return value.

    Brief:
        The payload is a mapping in normal use but may be absent
        or shaped differently, so every access is defensive.

    Arguments:
        selection_result: Value returned by the chart.

    Returns:
        list: Selected point mappings, empty when there are none.

    Warning:
        Never raises; an unrecognised payload yields no points.
    """
    if not isinstance(selection_result, dict):
        return []
    selection_dict = selection_result.get("selection")
    if not isinstance(selection_dict, dict):
        return []
    point_list = selection_dict.get("points")
    return point_list if isinstance(point_list, list) else []


def needs_amount_bool(event_type_str: str) -> bool:
    """Say whether an event type carries a rupee amount.

    Brief:
        Used to decide which single input to show once an event
        has been placed, so the form never shows fields that the
        chosen event would ignore.

    Arguments:
        event_type_str (str): Event type being placed.

    Returns:
        bool: True when the event needs an amount.

    Warning:
        A type needing neither input shows no field at all.
    """
    return event_type_str in EVENT_NEEDS_AMOUNT_TUPLE


def needs_percent_bool(event_type_str: str) -> bool:
    """Say whether an event type carries a percentage.

    Brief:
        Only the step-up rule is expressed as a rate, but keeping
        the question here means the page never has to know that.

    Arguments:
        event_type_str (str): Event type being placed.

    Returns:
        bool: True when the event needs a percentage.

    Warning:
        Mutually exclusive with needing an amount.
    """
    return event_type_str in EVENT_NEEDS_PERCENT_TUPLE
