"""A second, event-driven interface onto the same engine.

The classic dashboard is untouched by this file. Both run the same
`PortfolioSimulator`, so the two can never disagree about what a
plan is worth - they differ only in how the plan is described.

Here, a plan is a timeline of events. You add "start investing",
"step up", "pause", "retire" to a horizontal axis and the page
answers with the corpus, the tax, and what is actually left.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Literal

import streamlit as st

from investment_journey_simulator.constants import (
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXPENSE_MODEL_ACCRUED_STR,
    MONTHS_IN_YEAR_INT,
    PRESET_DEBT_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.currency import (
    DEFAULT_CURRENCY_CODE_STR,
    Currency,
    describe_money_str,
    format_money_str,
    list_currency_code_list,
    resolve_currency,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.event_order import (
    describe_prospective_str,
    find_order_finding_list,
)
from investment_journey_simulator.formatting import (
    describe_annual_rate_str,
    describe_months_str,
    format_compact_money_str,
)
from investment_journey_simulator.gantt import build_active_lane_list
from investment_journey_simulator.journey import build_milestone_list
from investment_journey_simulator.models import FundConfiguration, TaxSettings
from investment_journey_simulator.money_weighted import (
    calculate_post_tax_xirr_percent_float,
    calculate_pre_tax_xirr_percent_float,
)
from investment_journey_simulator.regimes import (
    DEFAULT_REGIME_CODE_STR,
    TaxRegime,
    describe_regime_str,
    list_regime_code_list,
    resolve_regime,
)
from investment_journey_simulator.timeline import (
    EVENT_ANNOTATION_TUPLE,
    EVENT_CHANGE_SIP_STR,
    EVENT_EXPLANATION_DICT,
    EVENT_GROUP_TUPLE,
    EVENT_INCOME_STR,
    EVENT_INFLATION_STR,
    EVENT_LUMPSUM_STR,
    EVENT_NEEDS_AMOUNT_TUPLE,
    EVENT_NEEDS_PERCENT_TUPLE,
    EVENT_RETIRE_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_TYPE_TUPLE,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
    apply_plan_to_fund,
    collect_inflation_schedule_tuple,
    compile_settings,
)
from investment_journey_simulator.ui.gantt_view import (
    EMPTY_GANTT_MESSAGE_STR,
    build_gantt_figure,
)
from investment_journey_simulator.ui.rail_view import (
    RAIL_FIGURE_KEY_STR,
    build_rail_figure,
    clear_pending_month_index,
    needs_percent_bool,
    read_clicked_month_index_int,
    read_pending_month_index_int,
    render_armed_hint,
    render_event_palette,
    render_quick_place_toggle,
    render_rail_style,
    resolve_clicked_event_index_int,
    set_pending_month_index,
)
from investment_journey_simulator.ui.timeline_view import (
    build_timeline_figure,
    render_hero,
    render_outcome_cards,
    render_page_style,
    render_return_cards,
)
from investment_journey_simulator.ui.value_input import (
    render_input_mode_control,
    render_tunable_float,
    set_tunable_float,
)

PAGE_LAYOUT_STR: Literal["centered", "wide"] = "wide"
PAGE_TITLE_STR: str = "Plan Timeline"
HERO_TITLE_STR: str = "Your plan, as a timeline"
HERO_SUBTITLE_STR: str = (
    "Add what happens and when. The curve is your money; the "
    "markers are your decisions. Hover any marker to see what it "
    "does."
)
EVENT_STATE_KEY_STR: str = "timeline_event_list"
DEFAULT_START_DATE: date = date(2026, 1, 1)
DEFAULT_HORIZON_YEARS_INT: int = 20
DEFAULT_MONTHLY_AMOUNT_FLOAT: float = 25000.0
DEFAULT_RETURN_PERCENT_FLOAT: float = 12.0
DEFAULT_EXPENSE_PERCENT_FLOAT: float = 0.5
STATUTORY_EXEMPTION_FLOAT: float = 125000.0
LONG_TERM_RATE_FLOAT: float = 12.5
SHORT_TERM_RATE_FLOAT: float = 20.0
CESS_PERCENT_FLOAT: float = 4.0
EMPTY_PLAN_MESSAGE_STR: str = (
    "Add a **Start investing** event to begin. Everything else is "
    "optional."
)
DEFAULT_STEPUP_PERCENT_FLOAT: float = 10.0
DEFAULT_LUMPSUM_FLOAT: float = 200000.0
DEFAULT_WITHDRAWAL_FLOAT: float = 50000.0
DEFAULT_INCOME_FLOAT: float = 1500000.0
DEFAULT_EVENT_AMOUNT_DICT: dict[str, float] = {
    EVENT_START_SIP_STR: DEFAULT_MONTHLY_AMOUNT_FLOAT,
    EVENT_CHANGE_SIP_STR: DEFAULT_MONTHLY_AMOUNT_FLOAT,
    EVENT_LUMPSUM_STR: DEFAULT_LUMPSUM_FLOAT,
    EVENT_WITHDRAW_STR: DEFAULT_WITHDRAWAL_FLOAT,
    EVENT_RETIRE_STR: DEFAULT_WITHDRAWAL_FLOAT,
    EVENT_INCOME_STR: DEFAULT_INCOME_FLOAT,
}
VIEW_PLAN_STR: str = "Plan"
VIEW_RESULT_STR: str = "Result"
VIEW_STATE_KEY_STR: str = "timeline_view_mode"
GANTT_FIGURE_KEY_STR: str = "gantt_figure"
REFERENCE_AMOUNT_FLOAT: float = 100000.0

# Every amount field says what unit it is in, because a rupee
# figure means nothing until you know whether it repeats.
AMOUNT_UNIT_DICT: dict[str, str] = {
    EVENT_START_SIP_STR: "How much every month ({symbol} a month)",
    EVENT_CHANGE_SIP_STR: "New monthly amount ({symbol} a month)",
    EVENT_LUMPSUM_STR: "How much, once ({symbol}, one time)",
    EVENT_WITHDRAW_STR: "How much to draw ({symbol} a month)",
    EVENT_RETIRE_STR: (
        "Monthly income to draw ({symbol} a month)"
    ),
    EVENT_INCOME_STR: "Total annual income ({symbol} a year)",
}
DEFAULT_AMOUNT_UNIT_STR: str = "Amount ({symbol})"
PERCENT_UNIT_DICT: dict[str, str] = {
    EVENT_STEPUP_STR: "Increase the instalment by (% a year)",
    EVENT_INFLATION_STR: "Prices rise by (% a year)",
}
AMOUNT_HELP_DICT: dict[str, str] = {
    EVENT_START_SIP_STR: (
        "Deducted every month from this month on, until you "
        "change or pause it."
    ),
    EVENT_CHANGE_SIP_STR: (
        "Replaces the amount running before it. Any step-up then "
        "grows from this new figure."
    ),
    EVENT_LUMPSUM_STR: (
        "A single investment. It compounds from this month only, "
        "not from the start of the plan."
    ),
    EVENT_WITHDRAW_STR: (
        "Taken out every month. The report names the exact month "
        "the money would run out."
    ),
    EVENT_RETIRE_STR: (
        "Contributions stop and this income starts, both in the "
        "same month."
    ),
    EVENT_INCOME_STR: (
        "Your total income for the year, already net of "
        "deductions. It funds nothing here - it decides the "
        "surcharge on your capital gains."
    ),
}
# Quick picks. Every one of these is a shortcut, never a limit -
# the box beside them accepts any figure you type, and the presets
# only exist so a common amount takes one click instead of nine
# keystrokes.
AMOUNT_PRESET_DICT: dict[str, tuple] = {
    EVENT_START_SIP_STR: (
        5_000.0, 10_000.0, 25_000.0, 50_000.0, 100_000.0
    ),
    EVENT_CHANGE_SIP_STR: (
        5_000.0, 10_000.0, 25_000.0, 50_000.0, 100_000.0
    ),
    EVENT_LUMPSUM_STR: (
        50_000.0, 100_000.0, 500_000.0, 1_000_000.0, 5_000_000.0
    ),
    EVENT_WITHDRAW_STR: (
        20_000.0, 50_000.0, 100_000.0, 200_000.0
    ),
    EVENT_RETIRE_STR: (
        20_000.0, 50_000.0, 100_000.0, 200_000.0
    ),
    EVENT_INCOME_STR: (
        500_000.0, 1_200_000.0, 2_500_000.0, 5_000_000.0,
        10_000_000.0,
    ),
}
PERCENT_PRESET_DICT: dict[str, tuple] = {
    EVENT_STEPUP_STR: (5.0, 10.0, 15.0, 20.0),
    EVENT_INFLATION_STR: (4.0, 5.0, 6.0, 7.0, 9.0),
}
EQUITY_PRESET_TUPLE: tuple = (0.0, 40.0, 60.0, 80.0, 100.0)
AMOUNT_STATE_KEY_STR: str = "chooser_amount"
PERCENT_STATE_KEY_STR: str = "chooser_percent"
NOTE_STATE_KEY_STR: str = "chooser_note"
MAXIMUM_RATE_PERCENT_FLOAT: float = 100.0
EQUITY_STATE_KEY_STR: str = "portfolio_equity_percent"

# A slider needs an upper end. These are generous ceilings chosen so
# the slider is usable, never a statement about what is reasonable -
# and the same ceiling applies when typing, so the two styles can
# always express exactly the same set of values.
AMOUNT_CEILING_DICT: dict[str, float] = {
    EVENT_START_SIP_STR: 500_000.0,
    EVENT_CHANGE_SIP_STR: 500_000.0,
    EVENT_LUMPSUM_STR: 50_000_000.0,
    EVENT_WITHDRAW_STR: 2_000_000.0,
    EVENT_RETIRE_STR: 2_000_000.0,
    EVENT_INCOME_STR: 100_000_000.0,
}
DEFAULT_AMOUNT_CEILING_FLOAT: float = 10_000_000.0
HORIZON_STATE_KEY_STR: str = "plan_horizon_years"
HELP_PICK_THE_EVENT_STR: str = (
    "Pick the event. The line underneath explains what it does "
    "before you add it."
)
HELP_PLAN_BUILDS_THE_TIMELINE_STR: str = (
    "Plan builds the timeline. Result runs it and shows the "
    "figures."
)
START_MONTH_STATE_KEY_STR: str = "plan_start_month"
RETURN_STATE_KEY_STR: str = "plan_return_percent"
EXPENSE_STATE_KEY_STR: str = "plan_expense_percent"
CURRENCY_STATE_KEY_STR: str = "plan_currency_code"
INFLATION_STATE_KEY_STR: str = "plan_inflation_percent"
REGIME_STATE_KEY_STR: str = "plan_tax_regime_code"

PERCENT_HELP_DICT: dict[str, str] = {
    EVENT_STEPUP_STR: (
        "Applied once a year to the instalment in force, "
        "compounding."
    ),
    EVENT_INFLATION_STR: (
        "Changes no rupee of the balance. It only restates what "
        "that balance is worth in today's money."
    ),
}
INFLATION_PERCENT_FLOAT: float = 6.0
EQUITY_FUND_NAME_STR: str = "Equity plan"
DEBT_FUND_NAME_STR: str = "Debt plan"
DEFAULT_EQUITY_PERCENT_FLOAT: float = 100.0
DEFAULT_DEBT_RETURN_PERCENT_FLOAT: float = 7.0
DEFAULT_DEBT_EXPENSE_PERCENT_FLOAT: float = 0.25
SLAB_RATE_PERCENT_FLOAT: float = 30.0


def build_default_event_list() -> list[TimelineEvent]:
    """Seed the page with a plan worth looking at.

    Brief:
        An empty timeline teaches nothing, so the page opens on a
        plain monthly plan that the reader can then edit.

    Arguments:
        None.

    Returns:
        List[TimelineEvent]: One opening event.

    Warning:
        Only used the first time the page loads in a session.
    """
    return [
        TimelineEvent(
            EVENT_START_SIP_STR,
            DEFAULT_START_DATE,
            amount_float=DEFAULT_MONTHLY_AMOUNT_FLOAT,
        )
    ]


def read_event_list() -> list[TimelineEvent]:
    """Read the timeline out of session state.

    Brief:
        Streamlit reruns the whole script on every interaction, so
        the plan has to live in session state to survive.

    Arguments:
        None.

    Returns:
        List[TimelineEvent]: The current timeline.

    Warning:
        Seeds the default plan on first use.
    """
    if EVENT_STATE_KEY_STR not in st.session_state:
        st.session_state[EVENT_STATE_KEY_STR] = (
            build_default_event_list()
        )
    return list(st.session_state[EVENT_STATE_KEY_STR])


def _render_event_inputs_tuple(
    event_type_str: str,
    column,
) -> tuple[float, float]:
    """Show only the input the chosen event actually needs.

    Brief:
        A step-up wants a percentage, everything else that carries
        money wants an amount, and a pause wants neither. Showing
        all three every time would make the form noise.

    Arguments:
        event_type_str (str): Chosen event type.
        column: Streamlit column to render into.

    Returns:
        Tuple[float, float]: Amount and percentage, zero when the
            event does not use one.

    Warning:
        Renders widgets as a side effect.
    """
    if event_type_str in EVENT_NEEDS_AMOUNT_TUPLE:
        return (
            float(
                column.number_input(
                    describe_amount_unit_str(event_type_str),
                    min_value=0.0,
                    value=DEFAULT_EVENT_AMOUNT_DICT.get(
                        event_type_str, DEFAULT_MONTHLY_AMOUNT_FLOAT
                    ),
                    step=1000.0,
                    help=AMOUNT_HELP_DICT.get(event_type_str, ""),
                )
            ),
            0.0,
        )
    if event_type_str in EVENT_NEEDS_PERCENT_TUPLE:
        return 0.0, _render_composer_percent_float(
            event_type_str, column
        )
    return 0.0, 0.0


def _render_composer_percent_float(
    event_type_str: str,
    column,
) -> float:
    """Ask for a rate in the older add-an-event form.

    Brief:
        Split out so both branches of the form stay short enough
        to read at a glance.

    Arguments:
        event_type_str (str): Chosen event type.
        column: Streamlit column to render into.

    Returns:
        float: Rate the reader entered.

    Warning:
        Renders a widget as a side effect.
    """
    return float(
        column.number_input(
            describe_percent_unit_str(event_type_str),
            min_value=0.0,
            max_value=MAXIMUM_RATE_PERCENT_FLOAT,
            value=DEFAULT_STEPUP_PERCENT_FLOAT,
            step=0.5,
            help=PERCENT_HELP_DICT.get(event_type_str, ""),
        )
    )


def place_event_on_rail(
    event_type_str: str,
    month_index_int: int,
    plan_start_date: date,
) -> None:
    """Add the armed event at the month the reader clicked.

    Brief:
        The amount is left at zero and edited afterwards, so a
        click places something immediately rather than opening a
        form before anything is visible on the rail.

    Arguments:
        event_type_str (str): Event type being placed.
        month_index_int (int): Month clicked on the rail.
        plan_start_date (date): Origin of the month grid.

    Returns:
        None: Session state gains one event.

    Warning:
        Mutates session state; the caller must rerun.
    """
    event_date = resolve_event_date(
        plan_start_date, month_index_int
    )
    st.session_state[EVENT_STATE_KEY_STR] = [
        *read_event_list(),
        TimelineEvent(
            event_type_str,
            event_date,
            DEFAULT_EVENT_AMOUNT_DICT.get(event_type_str, 0.0),
            DEFAULT_STEPUP_PERCENT_FLOAT
            if needs_percent_bool(event_type_str)
            else 0.0,
        ),
    ]


def build_span_list(plan: TimelinePlan) -> list[tuple]:
    """Describe the events that last rather than happen.

    Brief:
        A pause is a window, not a moment. Reading the windows
        back out of the compiled settings means the rail shows
        exactly what the engine was told, not a second guess.

    Arguments:
        plan (TimelinePlan): Plan being drawn.

    Returns:
        List[tuple]: Start, end and label for each span.

    Warning:
        Derived from the compiler, so an unmatched pause shows as
        running to the horizon - which is what it does.
    """
    return [
        (
            pause_range.start_date,
            pause_range.end_date,
            "Contributions paused",
        )
        for pause_range in compile_settings(
            plan
        ).pauses.pause_ranges_list
    ]


def describe_amount_unit_str(event_type_str: str) -> str:
    """Label an amount field with the unit it is measured in.

    Brief:
        A rupee figure means nothing without knowing whether it is
        per month, once, or per year. Saying so in the label is
        cheaper than a caption the reader has to look for.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        str: Field label carrying the unit.

    Warning:
        An unrecognised event falls back to a plain rupee label.
    """
    return AMOUNT_UNIT_DICT.get(
        event_type_str, DEFAULT_AMOUNT_UNIT_STR
    ).format(symbol=read_currency().symbol_str)


def describe_percent_unit_str(event_type_str: str) -> str:
    """Label a percentage field with what it is a percentage of.

    Brief:
        A step-up percentage grows an instalment; an inflation
        percentage erodes purchasing power. Same unit, opposite
        meanings, so the label has to distinguish them.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        str: Field label carrying the unit.

    Warning:
        An unrecognised event falls back to a plain rate label.
    """
    return PERCENT_UNIT_DICT.get(event_type_str, "Rate (% a year)")


def describe_percent_effect_str(
    event_type_str: str,
    percent_float: float,
) -> str:
    """Turn a typed rate into a sentence about what it will do.

    Brief:
        A step-up is applied to money, so it is echoed against a
        realistic instalment. Inflation is not, so it is echoed as
        what it does to the value of a fixed sum.

    Arguments:
        event_type_str (str): Event being configured.
        percent_float (float): Rate the reader typed.

    Returns:
        str: One line describing the rate's effect.

    Warning:
        The illustration uses a reference amount, not the reader's
        own - it is there to give the rate a scale, not a forecast.
    """
    if event_type_str == EVENT_INFLATION_STR:
        currency = read_currency()
        eroded_float = REFERENCE_AMOUNT_FLOAT / (
            (1.0 + percent_float / 100.0) ** 10
        )
        return (
            f"{percent_float:.2f}% a year - in ten years "
            f"{format_money_str(REFERENCE_AMOUNT_FLOAT, currency)}"
            f" buys what "
            f"{format_money_str(eroded_float, currency)} buys today"
        )
    return describe_annual_rate_str(
        percent_float, DEFAULT_MONTHLY_AMOUNT_FLOAT
    )


def resolve_event_date(
    plan_start_date: date,
    month_index_int: int,
) -> date:
    """Turn a month index on the rail into a calendar month.

    Brief:
        The rail speaks in month offsets and the plan speaks in
        dates; this is the one place that converts between them.

    Arguments:
        plan_start_date (date): Origin of the month grid.
        month_index_int (int): Month clicked on the rail.

    Returns:
        date: First day of that month.

    Warning:
        Assumes a non-negative offset.
    """
    zero_based_int = (
        plan_start_date.month - 1 + int(month_index_int)
    )
    return date(
        plan_start_date.year + zero_based_int // 12,
        zero_based_int % 12 + 1,
        1,
    )


def build_group_name_list() -> list[str]:
    """Name each family of events, for the category control.

    The categories used to be inserted into the event dropdown as
    entries the reader could select, and choosing one produced a
    scolding caption telling them it was only a heading. A menu
    that offers a choice and then refuses it is a broken menu, so
    the categories are now a control of their own.

    Returns:
        List[str]: Category names, in menu order.
    """
    return [
        group_name_str for group_name_str, _events in
        EVENT_GROUP_TUPLE
    ]


def resolve_group_event_tuple(group_name_str: str) -> tuple:
    """The events belonging to one category.

    Arguments:
        group_name_str (str): Category chosen by the reader.

    Returns:
        Tuple: Event names in that category, or every event when
            the name is not recognised.
    """
    for candidate_str, event_tuple in EVENT_GROUP_TUPLE:
        if candidate_str == group_name_str:
            return event_tuple
    return EVENT_TYPE_TUPLE


def render_event_chooser(
    plan: TimelinePlan,
    month_index_int: int,
) -> None:
    """Ask what happens at the month the reader clicked.

    Brief:
        The click already said *when*. This says *what*, offering
        every operation the tool models, grouped by what it does,
        with the chosen one explaining itself before it is added.

    Arguments:
        plan (TimelinePlan): Plan being edited.
        month_index_int (int): Month awaiting an event.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Mutates session state and reruns on add or cancel.
    """
    event_date = resolve_event_date(plan.start_date, month_index_int)
    with st.container(border=True):
        st.markdown(
            f"**＋ Something happens in "
            f"{event_date:%B %Y}** - what is it?"
        )
        group_name_str = str(
            st.radio(
                "Kind of event",
                build_group_name_list(),
                horizontal=True,
                key="chooser_event_group",
                help=(
                    "Narrows the list below. Nothing here changes "
                    "your plan until you add an event."
                ),
            )
        )
        event_type_str = str(
            st.selectbox(
                "What happens?",
                list(resolve_group_event_tuple(group_name_str)),
                key="chooser_event_type",
                help=HELP_PICK_THE_EVENT_STR,
            )
        )
        _render_chooser_body(event_type_str, event_date)


def _render_chooser_body(
    event_type_str: str,
    event_date: date,
) -> None:
    """Explain the chosen event and offer to add it.

    Brief:
        Every entry in the menu is now a real event, so this only
        has to explain the chosen one and offer to place it.

    Arguments:
        event_type_str (str): Selected dropdown entry.
        event_date (date): Month it would happen in.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Mutates session state through the buttons it renders.
    """
    st.caption(EVENT_EXPLANATION_DICT.get(event_type_str, ""))
    if event_type_str in EVENT_ANNOTATION_TUPLE:
        st.caption(
            ":grey[This one changes no number. It is a marker on "
            "your story, not on your money.]"
        )
    chosen_event = _build_chosen_event(event_type_str, event_date)
    # Warned before the button, never instead of it. A reader may
    # be building the plan out of order, and refusing the event
    # would be a worse failure than letting them place it knowing.
    warning_str = describe_prospective_str(
        chosen_event, read_event_list()
    )
    if warning_str:
        st.warning(warning_str)
    _render_chooser_buttons(chosen_event, event_date)


def _build_chosen_event(
    event_type_str: str,
    event_date: date,
) -> TimelineEvent:
    """Collect the one input the chosen event needs.

    Brief:
        A step-up wants a rate, anything carrying money wants an
        amount, and a pause wants neither - so only the relevant
        field is ever shown.

    Arguments:
        event_type_str (str): Event being added.
        event_date (date): Month it happens in.

    Returns:
        TimelineEvent: Event ready to add to the plan.

    Warning:
        Renders widgets as a side effect.
    """
    amount_float = 0.0
    percent_float = 0.0
    if event_type_str in EVENT_NEEDS_AMOUNT_TUPLE:
        amount_float = _render_amount_input_float(event_type_str)
    elif event_type_str in EVENT_NEEDS_PERCENT_TUPLE:
        percent_float = _render_percent_input_float(event_type_str)
    return TimelineEvent(
        event_type_str,
        _render_event_date_input(event_date),
        amount_float,
        percent_float,
        _render_note_input_str(event_type_str),
    )


def _render_event_date_input(event_date: date) -> date:
    """Let the month be corrected without clicking again.

    Brief:
        The click on the rail chose a month, but a click can miss.
        Offering the date as a field means the reader can type an
        exact month rather than hunting for the right pixel.

    Arguments:
        event_date (date): Month the click landed on.

    Returns:
        date: Month the event will actually use.

    Warning:
        Renders a widget as a side effect.
    """
    chosen_date = st.date_input(
        "When (change it if the click missed)",
        value=event_date,
        key="chooser_date",
        help=(
            "Anything in this month counts as this month; the "
            "engine simulates on a monthly grid."
        ),
    )
    return chosen_date if isinstance(chosen_date, date) else event_date


def _render_note_input_str(event_type_str: str) -> str:
    """Collect the words that make a marker worth having.

    Brief:
        A note with no text is a dot with nothing to say, so the
        one event type that changes no number gets the one field
        that carries meaning instead.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        str: Note text, empty for every other event type.

    Warning:
        Renders a widget as a side effect for notes only.
    """
    if event_type_str not in EVENT_ANNOTATION_TUPLE:
        return ""
    return str(
        st.text_input(
            "What happened?",
            key=NOTE_STATE_KEY_STR,
            placeholder="bought a house",
            help=(
                "Shown on the rail and in the journey report. It "
                "changes no number."
            ),
        )
    )


def resolve_amount_preset_tuple(event_type_str: str) -> tuple:
    """Quick picks offered beside an amount box.

    Brief:
        Presets are a shortcut, never a constraint. Anything not
        listed is still typeable, so this returning nothing simply
        means the reader types the figure.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        tuple: Suggested amounts, empty when there are none.

    Warning:
        Never treat a preset as a permitted value; the box beside
        it accepts any number.
    """
    return AMOUNT_PRESET_DICT.get(event_type_str, ())


def resolve_amount_ceiling_float(event_type_str: str) -> float:
    """Upper end of the range an amount can be set to.

    Brief:
        A slider has to stop somewhere. The ceiling is deliberately
        generous, and it applies to the typed box too - so the two
        styles can express exactly the same set of values and
        switching between them never loses a figure.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        float: Highest amount this field accepts.

    Warning:
        A ceiling is a control limit, not a judgement about what
        amount is sensible.
    """
    return AMOUNT_CEILING_DICT.get(
        event_type_str, DEFAULT_AMOUNT_CEILING_FLOAT
    )


def resolve_percent_preset_tuple(event_type_str: str) -> tuple:
    """Quick picks offered beside a rate box.

    Brief:
        Same contract as the amount presets: a shortcut only.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        tuple: Suggested rates, empty when there are none.

    Warning:
        Any rate inside the field's own range is still typeable.
    """
    return PERCENT_PRESET_DICT.get(event_type_str, ())


def _apply_preset_choice(
    state_key_str: str,
    preset_tuple: tuple,
    format_function,
) -> None:
    """Offer quick picks and push the chosen one into the box.

    Brief:
        A preset is a one-shot action, not a sticky selection: it
        fills the box in and then gets out of the way, leaving the
        figure free to be edited. Buttons say that; a chip that
        stays lit would imply the value is now locked to it.

    Arguments:
        state_key_str (str): Key of the number box being seeded.
        preset_tuple (tuple): Values to offer.
        format_function: Turns a value into its chip label.

    Returns:
        None: Session state may be updated.

    Warning:
        Does nothing when no presets are offered.
    """
    if not preset_tuple:
        return
    st.caption("Quick picks - or type your own below")
    column_list = st.columns(len(preset_tuple))
    for preset_index_int, preset_float in enumerate(preset_tuple):
        if column_list[preset_index_int].button(
            format_function(preset_float),
            key=f"{state_key_str}_preset_{preset_index_int}",
            width="stretch",
        ):
            set_tunable_float(state_key_str, preset_float)
            st.rerun()


def _render_amount_input_float(event_type_str: str) -> float:
    """Ask for a rupee amount, in its unit, and echo it back.

    Brief:
        The label carries the unit, the tooltip explains what the
        amount does, and the caption restates the figure in lakh
        or crore so an extra zero is obvious immediately.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        float: Amount the reader entered.

    Warning:
        Renders widgets as a side effect.
    """
    _apply_preset_choice(
        AMOUNT_STATE_KEY_STR,
        resolve_amount_preset_tuple(event_type_str),
        format_compact_money_str,
    )
    amount_float = render_tunable_float(
        describe_amount_unit_str(event_type_str),
        AMOUNT_STATE_KEY_STR,
        (0.0, resolve_amount_ceiling_float(event_type_str), 1000.0),
        DEFAULT_EVENT_AMOUNT_DICT.get(
            event_type_str, DEFAULT_MONTHLY_AMOUNT_FLOAT
        ),
        help_str=AMOUNT_HELP_DICT.get(event_type_str, ""),
    )
    st.caption(describe_money_str(amount_float, read_currency()))
    return amount_float


def _render_percent_input_float(event_type_str: str) -> float:
    """Ask for an annual rate and say what it will do.

    Brief:
        A rate is abstract until it is applied to something, so the
        caption spells out its effect on a reference amount.

    Arguments:
        event_type_str (str): Event being configured.

    Returns:
        float: Rate the reader entered.

    Warning:
        Renders widgets as a side effect.
    """
    _apply_preset_choice(
        PERCENT_STATE_KEY_STR,
        resolve_percent_preset_tuple(event_type_str),
        lambda value_float: f"{value_float:g}%",
    )
    percent_float = render_tunable_float(
        describe_percent_unit_str(event_type_str),
        PERCENT_STATE_KEY_STR,
        (0.0, MAXIMUM_RATE_PERCENT_FLOAT, 0.25),
        DEFAULT_STEPUP_PERCENT_FLOAT,
        help_str=PERCENT_HELP_DICT.get(event_type_str, ""),
    )
    st.caption(
        describe_percent_effect_str(event_type_str, percent_float)
    )
    return percent_float


def _render_chooser_buttons(
    event: TimelineEvent | None,
    event_date: date,
) -> None:
    """Confirm or abandon the event being placed.

    Brief:
        Cancelling has to be as easy as adding, or a stray click on
        the rail becomes something the reader has to undo later.

    Arguments:
        event (Optional[TimelineEvent]): Event to add, if valid.
        event_date (date): Month it happens in.

    Returns:
        None: Buttons are written to the page.

    Warning:
        Mutates session state and reruns.
    """
    column_list = st.columns(2)
    if event is not None and column_list[0].button(
        f"Add to {event_date:%b %Y}",
        width="stretch",
        type="primary",
    ):
        st.session_state[EVENT_STATE_KEY_STR] = [
            *read_event_list(),
            event,
        ]
        clear_pending_month_index()
        st.rerun()
    if column_list[1].button("Cancel", width="stretch"):
        clear_pending_month_index()
        st.rerun()


def render_rail_panel(plan: TimelinePlan) -> None:
    """Render the bare rail and handle a click on it.

    Brief:
        Two ways in, because people work differently. Hover any
        month and the rail offers to add something there; click and
        a dropdown asks what. Or arm a chip from the palette first
        and click the rail to place it straight away.

    Arguments:
        plan (TimelinePlan): Plan being edited.

    Returns:
        None: The panel is written to the page.

    Warning:
        Reruns the page when an event is placed or a month is
        clicked.
    """
    armed_type_str = (
        render_event_palette()
        if render_quick_place_toggle()
        else ""
    )
    render_armed_hint(armed_type_str)
    span_list = build_span_list(plan)
    selection_result = st.plotly_chart(
        build_rail_figure(
            plan, span_list, read_pending_month_index_int()
        ),
        width="stretch",
        key=RAIL_FIGURE_KEY_STR,
        on_select="rerun",
        selection_mode="points",
    )
    if _handle_dot_click(selection_result, plan, len(span_list)):
        return
    _handle_rail_click(selection_result, plan, armed_type_str)
    pending_month_index_int = read_pending_month_index_int()
    if pending_month_index_int is not None:
        render_event_chooser(plan, pending_month_index_int)
    render_gantt_panel(plan)


def _handle_dot_click(
    selection_result,
    plan: TimelinePlan,
    span_count_int: int,
) -> bool:
    """Take an event away when its dot is clicked.

    Brief:
        The minus on a dot's hover card is the counterpart of the
        plus on an empty month: the same gesture adds where there
        is nothing and removes where there is something.

    Arguments:
        selection_result: Value returned by the chart.
        plan (TimelinePlan): Plan that was drawn.
        span_count_int (int): Spanning bars drawn on the rail.

    Returns:
        bool: True when an event was removed and the page rerun.

    Warning:
        Mutates session state and reruns.
    """
    event_index_int = resolve_clicked_event_index_int(
        selection_result, plan, span_count_int
    )
    if event_index_int is None:
        return False
    doomed_event = plan.ordered_event_list[event_index_int]
    st.session_state[EVENT_STATE_KEY_STR] = [
        event
        for event in read_event_list()
        if event is not doomed_event
    ]
    clear_pending_month_index()
    st.rerun()
    return True


def _handle_rail_click(
    selection_result,
    plan: TimelinePlan,
    armed_type_str: str,
) -> None:
    """Place or begin placing an event on a clicked month.

    Brief:
        With a chip armed the event lands straight away; without
        one the month is remembered and the chooser asks what
        happens there.

    Arguments:
        selection_result: Value returned by the chart.
        plan (TimelinePlan): Plan being edited.
        armed_type_str (str): Armed event type, if any.

    Returns:
        None: Session state may be updated.

    Warning:
        Mutates session state and may rerun.
    """
    month_index_int = read_clicked_month_index_int(
        selection_result, plan.horizon_years_int * 12
    )
    if month_index_int is None:
        return
    if armed_type_str:
        place_event_on_rail(
            armed_type_str, month_index_int, plan.start_date
        )
        st.rerun()
    set_pending_month_index(month_index_int)


def render_gantt_panel(plan: TimelinePlan) -> None:
    """Draw the plan as phases, live, beneath the rail.

    Brief:
        Streamlit reruns the whole script on every interaction, so
        this redraws itself as the plan is typed rather than
        waiting for a button. It reads the compiled settings, which
        is what lets it show a pause the reader has not yet closed.

    Arguments:
        plan (TimelinePlan): Plan being edited.

    Returns:
        None: The panel is written to the page.

    Warning:
        Compiles the plan on every rerun.
    """
    st.markdown("#### What is running, and when")
    if not build_active_lane_list(plan):
        st.info(EMPTY_GANTT_MESSAGE_STR)
        return
    st.plotly_chart(
        build_gantt_figure(plan),
        width="stretch",
        key=GANTT_FIGURE_KEY_STR,
    )
    st.caption(
        "Solid means money is moving. Hatched means that activity "
        "is paused - drawn rather than hidden, because a gap you "
        "cannot see is a gap you cannot reason about. Faint bars "
        "are context: your salary and inflation shape the answer "
        "without being actions you take. Hover any bar for how "
        "long it lasts."
    )


def render_event_composer(plan_start_date: date) -> None:
    """Render the control that adds an event to the timeline.

    Brief:
        The explanation of the selected event type is shown before
        the reader commits to it, which is the whole point of the
        hover-to-learn idea carried into the editor.

    Arguments:
        plan_start_date (date): Default date for a new event.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Mutates session state when the add button is pressed.
    """
    with st.expander("Add an event", expanded=True):
        event_type_str = str(
            st.selectbox(
                "What happens?",
                list(EVENT_TYPE_TUPLE),
                key="composer_event_type",
                help=HELP_PICK_THE_EVENT_STR,
            )
        )
        st.caption(EVENT_EXPLANATION_DICT.get(event_type_str, ""))
        column_list = st.columns(3)
        event_date = column_list[0].date_input(
            "When?",
            value=plan_start_date,
            help="The month this happens in.",
        )
        amount_float, percent_float = _render_event_inputs_tuple(
            event_type_str, column_list[1]
        )
        note_str = _render_composer_note_str(event_type_str)
        if column_list[2].button("Add to timeline", width="stretch"):
            st.session_state[EVENT_STATE_KEY_STR] = [
                *read_event_list(),
                TimelineEvent(
                    event_type_str,
                    event_date,
                    amount_float,
                    percent_float,
                    note_str,
                ),
            ]
            st.rerun()


def _render_composer_note_str(event_type_str: str) -> str:
    """Collect a marker's text in the older add-an-event form.

    Brief:
        Only the annotation events carry words, so every other
        event type skips the field entirely.

    Arguments:
        event_type_str (str): Chosen event type.

    Returns:
        str: Note text, empty for events that change a number.

    Warning:
        Renders a widget as a side effect for notes only.
    """
    if event_type_str not in EVENT_ANNOTATION_TUPLE:
        return ""
    return str(
        st.text_input(
            "What happened?",
            help=(
                "A few words, for your own reference later."
            ),
            key="composer_note",
            placeholder="bought a house",
        )
    )


def describe_event_value_str(event: TimelineEvent) -> str:
    """The one figure an event carries, whatever kind it is."""
    if event.amount_float:
        return format_money_str(
            event.amount_float, read_currency()
        )
    if event.percent_float:
        return f"{event.percent_float:g}%"
    return "no amount"


def write_event_at(
    event_index_int: int,
    event: TimelineEvent | None,
) -> None:
    """Replace or delete one event, keeping the rest as they are.

    Brief:
        The single write path for editing the rail. Passing None
        deletes; passing an event replaces in place, which is what
        keeps a correction from becoming a delete and a retype.

    Arguments:
        event_index_int (int): Position in the current list.
        event (Optional[TimelineEvent]): Replacement, or None.

    Returns:
        None: Session state is updated.
    """
    current_list = read_event_list()
    updated_list = [
        existing
        for other_index_int, existing in enumerate(current_list)
        if other_index_int != event_index_int
    ]
    if event is not None:
        updated_list.insert(event_index_int, event)
    st.session_state[EVENT_STATE_KEY_STR] = updated_list


def _render_event_editor(
    event_index_int: int,
    event: TimelineEvent,
) -> None:
    """Edit one event's date, figure and note, in place.

    Correcting an amount used to mean removing the event and
    adding it again from scratch, which loses the date and the note
    and invites a reader to mistype the thing they were only trying
    to nudge.
    """
    key_str = f"edit_{event_index_int}"
    first, second = st.columns(2)
    event_date = first.date_input(
        "When",
        value=event.event_date,
        key=f"{key_str}_date",
        help="The month this happens in.",
    )
    amount_float, percent_float = _render_editor_figure_tuple(
        event, second, key_str
    )
    note_str = _render_editor_note_str(event, key_str)
    save_column, delete_column = st.columns(2)
    if save_column.button(
        "Save changes", key=f"{key_str}_save", width="stretch"
    ):
        write_event_at(
            event_index_int,
            TimelineEvent(
                event.event_type_str,
                event_date,
                amount_float,
                percent_float,
                note_str,
            ),
        )
        st.rerun()
    if delete_column.button(
        "Remove this event",
        key=f"remove_{event_index_int}",
        width="stretch",
    ):
        write_event_at(event_index_int, None)
        st.rerun()


def _render_editor_note_str(
    event: TimelineEvent,
    key_str: str,
) -> str:
    """Ask for the words, on the events that carry any."""
    if event.event_type_str not in EVENT_ANNOTATION_TUPLE:
        return event.note_str
    return str(
        st.text_input(
            "Note",
            help=(
                "A few words, for your own reference later."
            ),
            value=event.note_str,
            key=f"{key_str}_note",
        )
    )


def _render_editor_figure_tuple(
    event: TimelineEvent,
    column,
    key_str: str,
) -> tuple:
    """Ask for whichever figure this kind of event carries."""
    if event.event_type_str in EVENT_NEEDS_AMOUNT_TUPLE:
        return (
            float(
                column.number_input(
                    "Amount",
                    min_value=0.0,
                    value=float(event.amount_float),
                    step=1000.0,
                    key=f"{key_str}_amount",
                    help="Type the figure directly.",
                )
            ),
            event.percent_float,
        )
    if event.event_type_str in EVENT_NEEDS_PERCENT_TUPLE:
        return (
            event.amount_float,
            float(
                column.number_input(
                    "Percent",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(event.percent_float),
                    step=0.5,
                    key=f"{key_str}_percent",
                    help="A yearly rate, in percent.",
                )
            ),
        )
    column.caption("This event carries no figure.")
    return (event.amount_float, event.percent_float)


def render_order_warnings(
    event_list: list[TimelineEvent],
) -> None:
    """Flag every event on the rail that cannot take effect.

    Checked over the whole plan rather than as each event is
    placed, so adding the missing start later clears the warning
    without the reader having to re-order anything by hand.
    """
    finding_list = find_order_finding_list(event_list)
    if not finding_list:
        return
    st.warning(
        f"**{len(finding_list)} event"
        f"{'' if len(finding_list) == 1 else 's'} on this "
        "timeline will not do anything as placed.**"
    )
    for finding in finding_list:
        st.caption(finding.sentence_str)


def render_event_list(event_list: list[TimelineEvent]) -> None:
    """List the events, each one editable in place.

    Brief:
        A timeline you cannot edit is a picture, not an input, and
        one you can only delete from is barely better: a reader
        correcting a figure should not have to destroy the event
        that carried it.

    Arguments:
        event_list (List[TimelineEvent]): Current timeline.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Mutates session state when save or remove is pressed.
    """
    if not event_list:
        st.info(EMPTY_PLAN_MESSAGE_STR)
        return
    render_order_warnings(event_list)
    st.markdown(f"**Events on the timeline ({len(event_list)})**")
    st.caption("Open any one to change its date or its figure.")
    for event_index_int, event in enumerate(event_list):
        with st.expander(
            f"{event.event_date:%b %Y} · {event.event_type_str}"
            f" · {describe_event_value_str(event)}"
        ):
            _render_event_editor(event_index_int, event)


def build_base_fund() -> FundConfiguration:
    """Build the single equity fund the timeline invests in.

    Brief:
        One fund keeps the timeline about *events* rather than
        about asset allocation, which the classic dashboard
        already handles well.

    Arguments:
        None.

    Returns:
        FundConfiguration: Equity fund at statutory tax rates.

    Warning:
        Amounts are overwritten by the compiled timeline.
    """
    return FundConfiguration(
        name_str=EQUITY_FUND_NAME_STR,
        preset_str=PRESET_EQUITY_STR,
        monthly_sip_float=0.0,
        stepup_percent_float=0.0,
        gross_return_percent_float=DEFAULT_RETURN_PERCENT_FLOAT,
        expense_percent_float=DEFAULT_EXPENSE_PERCENT_FLOAT,
        start_date=DEFAULT_START_DATE,
        target_allocation_percent_float=100.0,
        short_term_tax_percent_float=(
            read_regime().short_term_percent_float
        ),
        long_term_tax_percent_float=(
            read_regime().long_term_percent_float
        ),
        long_term_threshold_months_int=(
            read_regime().long_term_threshold_months_int
        ),
        exemption_amount_float=(
            read_regime().annual_exemption_float
        ),
        exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
        is_always_short_term_bool=False,
        expense_model_str=EXPENSE_MODEL_ACCRUED_STR,
    )


def build_debt_fund(
    equity_percent_float: float,
) -> FundConfiguration:
    """Build the debt side of the portfolio.

    Brief:
        A rebalance needs two things to move between, so the
        timeline carries a debt fund alongside the equity one. It
        is taxed as a specified mutual fund: always short term at
        the slab rate, per section 50AA.

    Arguments:
        equity_percent_float (float): Equity's target share.

    Returns:
        FundConfiguration: Debt fund taking the remaining share.

    Warning:
        Amounts are overwritten by the compiled timeline.
    """
    return FundConfiguration(
        name_str=DEBT_FUND_NAME_STR,
        preset_str=PRESET_DEBT_STR,
        monthly_sip_float=0.0,
        stepup_percent_float=0.0,
        gross_return_percent_float=DEFAULT_DEBT_RETURN_PERCENT_FLOAT,
        expense_percent_float=DEFAULT_DEBT_EXPENSE_PERCENT_FLOAT,
        start_date=DEFAULT_START_DATE,
        target_allocation_percent_float=(
            100.0 - float(equity_percent_float)
        ),
        short_term_tax_percent_float=SLAB_RATE_PERCENT_FLOAT,
        long_term_tax_percent_float=SLAB_RATE_PERCENT_FLOAT,
        long_term_threshold_months_int=12,
        exemption_amount_float=0.0,
        exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
        is_always_short_term_bool=True,
        expense_model_str=EXPENSE_MODEL_ACCRUED_STR,
    )


def build_fund_list(
    equity_percent_float: float,
    return_percent_float: float,
    expense_percent_float: float,
) -> list[FundConfiguration]:
    """Build the portfolio the timeline invests through.

    Brief:
        One equity fund and one debt fund, split by the target the
        reader chose. A hundred percent equity still produces both,
        with the debt side simply targeting nothing, so the same
        code path runs whatever the split.

    Arguments:
        equity_percent_float (float): Equity's target share.
        return_percent_float (float): Equity return assumption.
        expense_percent_float (float): Equity fee assumption.

    Returns:
        List[FundConfiguration]: Equity and debt, in that order.

    Warning:
        Instalments are split by these same target weights.
    """
    return [
        replace(
            build_base_fund(),
            gross_return_percent_float=return_percent_float,
            expense_percent_float=expense_percent_float,
            target_allocation_percent_float=float(
                equity_percent_float
            ),
        ),
        build_debt_fund(equity_percent_float),
    ]


def render_assumption_controls() -> tuple[int, float, float]:
    """Collect the few assumptions the timeline still needs.

    Brief:
        Horizon, return and fee are not events, so they stay as
        plain controls rather than being forced onto the axis.

    Arguments:
        None.

    Returns:
        Tuple[int, float, float]: Horizon, return and expense.

    Warning:
        The return is an assumption, not a forecast.
    """
    column_list = st.columns(3)
    horizon_years_int = _render_horizon_input_int(column_list[0])
    return_percent_float = _render_return_input_float(
        column_list[1]
    )
    expense_percent_float = _render_expense_input_float(
        column_list[2]
    )
    return (
        horizon_years_int,
        return_percent_float,
        expense_percent_float,
    )


def build_outcome_dict(result, settings) -> dict:
    """Reduce a completed run to the figures the cards show.

    Brief:
        One place where the page's headline numbers are decided,
        so the cards and any future export cannot drift apart.

    Arguments:
        result: Completed simulation result.
        settings: Settings the run used.

    Returns:
        dict: Figures keyed for the card renderers.

    Warning:
        The spendable figure is only net of exit tax when the
        final liquidation setting was enabled.
    """
    return {
        "invested": result.ending_invested_float,
        "corpus": result.ending_value_float,
        "exit_cost": result.total_exit_cost_float,
        "spendable": result.post_tax_ending_value_float,
        "gain": (
            result.ending_value_float
            - result.ending_invested_float
        ),
        "xirr_pre": calculate_pre_tax_xirr_percent_float(
            result, settings.sip_at_month_start_bool
        ),
        "xirr_post": calculate_post_tax_xirr_percent_float(
            result, settings.sip_at_month_start_bool
        ),
    }


def run_plan(plan: TimelinePlan, fund_list: list):
    """Compile a timeline and run it through the engine.

    Brief:
        One place where a plan becomes an answer, so the rail, the
        result chart and the report can never be looking at
        different runs.

    Arguments:
        plan (TimelinePlan): Plan being valued.
        fund_list (list): Funds carrying the assumptions.

    Returns:
        tuple: Completed result and the settings that produced it.

    Warning:
        Runs the whole horizon; not free on every rerun.
    """
    regime = read_regime()
    settings = compile_settings(
        plan,
        TaxSettings(
            apply_final_liquidation_tax_bool=True,
            cess_percent_float=regime.cess_percent_float,
            exemption_level_str=EXEMPTION_LEVEL_PORTFOLIO_STR,
            portfolio_exemption_amount_float=(
                regime.annual_exemption_float
            ),
        ),
    )
    result = PortfolioSimulator(
        [apply_plan_to_fund(fund, plan) for fund in fund_list],
        settings,
    ).run()
    return result, settings


def render_journey_report(plan: TimelinePlan, result) -> None:
    """Narrate the plan event by event, with the money attached.

    Brief:
        A corpus at the end says how much but never how. This
        walks the same simulated months the chart draws and states
        what the portfolio was worth as each decision was taken.

    Arguments:
        plan (TimelinePlan): Plan that was run.
        result: Completed simulation result.

    Returns:
        None: A table is written to the page.

    Warning:
        Real values assume a fixed inflation rate.
    """
    milestone_list = build_milestone_list(
        plan,
        result,
        read_inflation_percent_float(),
        collect_inflation_schedule_tuple(plan),
    )
    if not milestone_list:
        st.info(EMPTY_PLAN_MESSAGE_STR)
        return
    st.markdown("#### Your journey, decision by decision")
    st.dataframe(
        [
            build_milestone_row_dict(milestone)
            for milestone in milestone_list
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "This is the value the month the event happened. The "
        f"last column restates it in {DEFAULT_START_DATE.year} "
        f"purchasing power at "
        f"{read_inflation_percent_float():.2f}% "
        "inflation unless the rail says otherwise. Tax so far is "
        "what the plan had already paid by that month, not the tax "
        "on a full exit."
    )


def build_milestone_row_dict(milestone) -> dict:
    """Turn one milestone into a row of the journey table.

    Brief:
        Keeps the column names and their order in one place, so
        the table and its caption cannot drift apart.

    Arguments:
        milestone (JourneyMilestone): Milestone being rendered.

    Returns:
        dict: One row keyed by column heading.

    Warning:
        Values stay numeric so the table can format them.
    """
    currency = read_currency()
    return {
        "When": f"{milestone.month_date:%b %Y}",
        "What happened": milestone.event.event_type_str,
        f"Value ({currency.code_str})": (
            milestone.portfolio_value_float
        ),
        "Paid in": milestone.invested_amount_float,
        "Gain": milestone.gain_float,
        "Tax so far": milestone.tax_paid_float,
        f"In {DEFAULT_START_DATE.year} money": (
            milestone.real_value_float
        ),
    }


def render_result_view(plan: TimelinePlan, result, settings) -> None:
    """Draw the outcome: cards, the corpus curve and the story.

    Brief:
        The curve answers "how much", the report answers "how it
        got there", and the cards carry the figure that actually
        matters - what is left after tax.

    Arguments:
        plan (TimelinePlan): Plan that was run.
        result: Completed simulation result.
        settings: Settings the run used.

    Returns:
        None: The result page is written.

    Warning:
        Assumes the plan and the result describe the same run.
    """
    outcome_dict = build_outcome_dict(result, settings)
    render_outcome_cards(outcome_dict)
    st.write("")
    st.plotly_chart(
        build_timeline_figure(
            plan,
            [
                snapshot.month_date
                for snapshot in result.monthly_snapshots_list
            ],
            [
                snapshot.portfolio_value_float
                for snapshot in result.monthly_snapshots_list
            ],
            [
                snapshot.invested_amount_float
                for snapshot in result.monthly_snapshots_list
            ],
        ),
        width="stretch",
        key="timeline_figure",
    )
    render_return_cards(outcome_dict)
    st.write("")
    render_journey_report(plan, result)


def render_start_month_control(default_date: date) -> date:
    """Ask which month the timeline opens in.

    The rail used to begin in the current month and offer only a
    length, which made it impossible to model a plan already
    running - somebody three years into a SIP had nowhere to put
    the three years - or one starting next April. Any month is
    allowed, past or future.

    Arguments:
        default_date (date): Month to open on the first visit.

    Returns:
        date: Chosen opening month, anchored to the first.

    Warning:
        Moving the start does not drag the events with it. A plan
        that begins a year earlier is not the same plan shifted; a
        reader who wanted the events moved can edit their dates.
    """
    chosen_date = st.date_input(
        "Timeline starts",
        value=st.session_state.get(
            START_MONTH_STATE_KEY_STR, default_date
        ),
        key=START_MONTH_STATE_KEY_STR,
        help=(
            "Any month, past or future. Pick a past month to "
            "model a plan already running."
        ),
    )
    if isinstance(chosen_date, tuple):
        chosen_date = chosen_date[0] if chosen_date else default_date
    return date(chosen_date.year, chosen_date.month, 1)


def _render_horizon_input_int(column) -> int:
    """Ask how long the plan runs, and echo it in months.

    Brief:
        Plans are typed in years and simulated in months, so both
        are shown rather than leaving the reader to convert.

    Arguments:
        column: Streamlit column to render into.

    Returns:
        int: Horizon in whole years.

    Warning:
        Renders widgets as a side effect.
    """
    with column:
        horizon_years_int = int(
            render_tunable_float(
                "How long the plan runs (years)",
                HORIZON_STATE_KEY_STR,
                (1.0, 60.0, 1.0),
                float(DEFAULT_HORIZON_YEARS_INT),
                help_str=(
                    "Simulated month by month, so a 20-year plan "
                    "is 240 steps."
                ),
            )
        )
    column.caption(
        describe_months_str(horizon_years_int * MONTHS_IN_YEAR_INT)
    )
    return horizon_years_int


def _render_return_input_float(column) -> float:
    """Ask for the assumed return and show what it compounds to.

    Brief:
        Naming the monthly rate is the honest way to state this
        number, because dividing by twelve is the mistake other
        calculators make.

    Arguments:
        column: Streamlit column to render into.

    Returns:
        float: Assumed annual return percent.

    Warning:
        An assumption, never a forecast.
    """
    with column:
        return_percent_float = render_tunable_float(
            "Assumed return (% a year, before fees)",
            RETURN_STATE_KEY_STR,
            (-20.0, 40.0, 0.25),
            DEFAULT_RETURN_PERCENT_FLOAT,
            help_str=(
                "Your assumption, not a forecast. Compounded "
                "monthly at the effective rate, not divided by 12."
            ),
        )
    column.caption(describe_annual_rate_str(return_percent_float))
    return return_percent_float


def _render_expense_input_float(column) -> float:
    """Ask for the fund fee and price it per lakh held.

    Brief:
        A TER of half a percent sounds like nothing until it is
        stated in rupees against an amount you recognise.

    Arguments:
        column: Streamlit column to render into.

    Returns:
        float: Annual expense ratio percent.

    Warning:
        Accrued on value, not subtracted from the return.
    """
    with column:
        expense_percent_float = render_tunable_float(
            "Fund fee, TER (% a year)",
            EXPENSE_STATE_KEY_STR,
            (0.0, 3.0, 0.05),
            DEFAULT_EXPENSE_PERCENT_FLOAT,
            help_str=(
                "Charged by the fund house and accrued daily on "
                "the value, not subtracted from the return."
            ),
        )
    currency = read_currency()
    fee_float = (
        REFERENCE_AMOUNT_FLOAT * expense_percent_float / 100.0
    )
    column.caption(
        f"{expense_percent_float:.2f}% a year on the value - about "
        f"{format_money_str(fee_float, currency)} a year for every "
        f"{format_money_str(REFERENCE_AMOUNT_FLOAT, currency)} held"
    )
    return expense_percent_float


def read_inflation_percent_float() -> float:
    """Read the inflation the report restates figures at.

    Brief:
        Held in session state so the control and the report cannot
        disagree about which rate was used.

    Arguments:
        None.

    Returns:
        float: Annual inflation percent.

    Warning:
        Falls back to the chosen currency's opening assumption
        before the control has been rendered.
    """
    return float(
        st.session_state.get(
            INFLATION_STATE_KEY_STR,
            read_currency().default_inflation_percent_float,
        )
    )


def read_regime() -> TaxRegime:
    """Read which country's capital gains treatment applies.

    Brief:
        Held in session state so the funds, the tax settings and
        the notice on the page cannot disagree about which regime
        was chosen.

    Arguments:
        None.

    Returns:
        TaxRegime: The chosen regime.

    Warning:
        Only India is modelled beyond its headline rates. Every
        other regime supplies opening values the reader edits.
    """
    return resolve_regime(
        str(
            st.session_state.get(
                REGIME_STATE_KEY_STR, DEFAULT_REGIME_CODE_STR
            )
        )
    )


def render_regime_control() -> TaxRegime:
    """Let the reader pick whose capital gains rules apply.

    Brief:
        States the depth of each regime beneath the menu, because
        choosing a country here fills in rates - it does not teach
        this program that country's tax code.

    Arguments:
        None.

    Returns:
        TaxRegime: The chosen regime.

    Warning:
        Renders widgets as a side effect.
    """
    code_list = list_regime_code_list()
    st.selectbox(
        "Tax regime",
        code_list,
        index=code_list.index(read_regime().code_str),
        key=REGIME_STATE_KEY_STR,
        format_func=lambda code_str: resolve_regime(
            code_str
        ).label_str,
        help=(
            "India is modelled in full. Every other regime fills "
            "in opening rates you can then edit - it does not add "
            "that country's own machinery."
        ),
    )
    regime = read_regime()
    st.caption(describe_regime_str(regime))
    if not regime.is_fully_modelled_bool:
        st.caption(
            ":orange[Surcharge, cess, marginal relief and "
            "grandfathering are Indian mechanisms and are switched "
            "off for this regime.]"
        )
    return regime


def read_currency() -> Currency:
    """Read the currency every figure on the page is shown in.

    Brief:
        Held in session state so one choice reaches the labels,
        the captions, the journey report and the cards at once.

    Arguments:
        None.

    Returns:
        Currency: The chosen currency.

    Warning:
        Changes only how figures are *displayed*. It converts
        nothing, and it does not change the tax rules, which are
        Indian throughout.
    """
    return resolve_currency(
        str(
            st.session_state.get(
                CURRENCY_STATE_KEY_STR, DEFAULT_CURRENCY_CODE_STR
            )
        )
    )


def render_currency_control() -> Currency:
    """Let the reader pick the currency figures are shown in.

    Brief:
        Grouping and magnitude names follow the choice, so a
        dollar figure is named in millions and a rupee figure in
        lakh - naming either in the other's units would be worse
        than not naming it at all.

    Arguments:
        None.

    Returns:
        Currency: The chosen currency.

    Warning:
        Renders a widget as a side effect, and states plainly that
        no conversion or change of tax rules is implied.
    """
    code_list = list_currency_code_list()
    st.selectbox(
        "Currency",
        code_list,
        index=code_list.index(read_currency().code_str),
        key=CURRENCY_STATE_KEY_STR,
        format_func=lambda code_str: resolve_currency(
            code_str
        ).label_str,
        help=(
            "Changes the symbol, the digit grouping and the words "
            "used for large numbers. It converts nothing, and the "
            "tax rules stay Indian - see docs/SOURCES.md."
        ),
    )
    return read_currency()


def render_inflation_control(currency: Currency) -> float:
    """Collect the inflation the report restates figures at.

    Brief:
        Opens at a figure of the right order for the chosen
        currency's economy, and is overwritable like everything
        else. A rate placed on the rail overrides it from its own
        month onward.

    Arguments:
        currency (Currency): Currency supplying the opening rate.

    Returns:
        float: Annual inflation percent.

    Warning:
        Changes no rupee of the corpus - only what the corpus is
        said to be worth in today's money.
    """
    return render_tunable_float(
        "Inflation (% a year)",
        INFLATION_STATE_KEY_STR,
        (0.0, 30.0, 0.25),
        currency.default_inflation_percent_float,
        help_str=(
            "Used to restate the value in today's money. It "
            "changes no rupee of the plan itself. An inflation "
            "event on the rail overrides this from its month on."
        ),
    )


def render_allocation_control() -> float:
    """Collect the equity share of the portfolio.

    Brief:
        The split is not an event - it is the shape of the
        portfolio the events act on - so it stays a plain control.
        It also decides what a rebalance event realigns towards.

    Arguments:
        None.

    Returns:
        float: Equity's target percentage of the portfolio.

    Warning:
        At a hundred percent there is nothing to rebalance, and a
        rebalance event placed on the rail will do nothing.
    """
    _apply_preset_choice(
        EQUITY_STATE_KEY_STR,
        EQUITY_PRESET_TUPLE,
        lambda value_float: f"{value_float:g}% equity",
    )
    equity_percent_float = render_tunable_float(
        "Equity share of the portfolio (% of the total)",
        EQUITY_STATE_KEY_STR,
        (0.0, 100.0, 0.5),
        DEFAULT_EQUITY_PERCENT_FLOAT,
        help_str=(
            "Drag it or type it, whichever you prefer - the style "
            "control at the top switches every input on the page. "
            "The rest goes to a debt fund, taxed at your slab rate "
            "under section 50AA. A rebalance event sells whatever "
            "has drifted above its share."
        ),
    )
    st.caption(describe_split_str(equity_percent_float))
    return equity_percent_float


def describe_split_str(equity_percent_float: float) -> str:
    """Say what the chosen split means for rebalancing.

    Brief:
        At nought or a hundred percent there is only one asset, so
        a rebalance event has nothing to move - worth saying, since
        the event would otherwise appear to do nothing silently.

    Arguments:
        equity_percent_float (float): Equity's target share.

    Returns:
        str: One line describing the split.

    Warning:
        Display only; the engine reads the number, not this text.
    """
    split_str = (
        f"{equity_percent_float:g}% equity and "
        f"{100.0 - equity_percent_float:g}% debt"
    )
    if equity_percent_float in (0.0, 100.0):
        return (
            f"{split_str} - with a single asset there is nothing "
            "for a rebalance event to move"
        )
    return split_str


def render_view_toggle() -> str:
    """Let the reader switch between planning and the answer.

    Brief:
        Separating the two keeps the rail uncluttered while the
        plan is being described, and keeps the answer undisturbed
        once it has been generated.

    Arguments:
        None.

    Returns:
        str: The view the reader chose.

    Warning:
        Defaults to the planning view on a fresh session. Rendered
        as a radio rather than a segmented control because the
        latter cannot be driven by Streamlit's own test harness,
        and every input on this page is covered by a test.
    """
    return str(
        st.radio(
            "View",
            [VIEW_PLAN_STR, VIEW_RESULT_STR],
            index=0,
            key=VIEW_STATE_KEY_STR,
            help=HELP_PLAN_BUILDS_THE_TIMELINE_STR,
            horizontal=True,
            label_visibility="collapsed",
        )
        or VIEW_PLAN_STR
    )


def main() -> None:
    """Render the timeline page end to end.

    Brief:
        Reads the timeline, compiles it into engine settings, runs
        the same simulator the classic dashboard uses, and draws
        either the rail being planned on or the answer.

    Arguments:
        None.

    Returns:
        None: The page is rendered.

    Warning:
        Streamlit re-executes this on every interaction.
    """
    st.set_page_config(
        page_title=PAGE_TITLE_STR, layout=PAGE_LAYOUT_STR
    )
    render_page_style()
    render_rail_style()
    render_hero(HERO_TITLE_STR, HERO_SUBTITLE_STR)
    with st.sidebar:
        st.markdown("### Settings")
        render_input_mode_control()
        currency = render_currency_control()
        render_regime_control()
        (
            horizon_years_int,
            return_percent_float,
            expense_percent_float,
        ) = render_assumption_controls()
        equity_percent_float = render_allocation_control()
        render_inflation_control(currency)
    plan = TimelinePlan(
        DEFAULT_START_DATE, horizon_years_int, read_event_list()
    )
    if render_view_toggle() == VIEW_PLAN_STR:
        render_rail_panel(plan)
        render_event_composer(DEFAULT_START_DATE)
        render_event_list(plan.event_list)
        return
    result, settings = run_plan(
        plan,
        build_fund_list(
            equity_percent_float,
            return_percent_float,
            expense_percent_float,
        ),
    )
    render_result_view(plan, result, settings)
