"""One value, two ways to set it - slider or keyboard.

A slider is the nicer thing to look at and the faster thing to
explore with: you can feel the shape of a range by dragging it. A
number box is the only thing that can express *exactly* 62.5%, or
₹33,333, without fighting a step size.

Neither is right for everyone, so neither is imposed. The reader
picks a style once and every control on the page follows it, and the
value survives switching between them because the number lives in
session state under its own key rather than inside a widget.

The rule this module exists to enforce: **a slider must never be the
only way to set something.** Being able to see a value is not the
same as being able to say it.
"""

from __future__ import annotations

import streamlit as st

INPUT_MODE_STATE_KEY_STR: str = "input_style_mode"
SLIDER_SUFFIX_STR: str = "__slider"
BOX_SUFFIX_STR: str = "__box"

INPUT_MODE_SLIDER_STR: str = "Sliders"
INPUT_MODE_TYPED_STR: str = "Type it"
INPUT_MODE_BOTH_STR: str = "Both"
INPUT_MODE_TUPLE: tuple = (
    INPUT_MODE_BOTH_STR,
    INPUT_MODE_SLIDER_STR,
    INPUT_MODE_TYPED_STR,
)
# Both, by default. A slider alone cannot land on 33,333 and a box
# alone makes a reader guess what a sensible figure even is; showing
# the pair means typing an exact number never depends on having
# found a setting first.
DEFAULT_INPUT_MODE_STR: str = INPUT_MODE_BOTH_STR

INPUT_MODE_HELP_STR: str = (
    "Both shows a slider and a box together. Sliders explore a "
    "range quickly; typing is the only way to land on an exact "
    "figure like 62.5% or 33,333. Switching keeps your value."
)


def read_input_mode_str() -> str:
    """Read which input style the reader prefers.

    Brief:
        Stored once and obeyed by every control, so the page does
        not mix styles from one row to the next.

    Arguments:
        None.

    Returns:
        str: The active input style.

    Warning:
        Seeds the default on first use.
    """
    if INPUT_MODE_STATE_KEY_STR not in st.session_state:
        st.session_state[INPUT_MODE_STATE_KEY_STR] = (
            DEFAULT_INPUT_MODE_STR
        )
    return str(st.session_state[INPUT_MODE_STATE_KEY_STR])


def render_input_mode_control() -> str:
    """Let the reader choose sliders or typing, once.

    Brief:
        A radio rather than a segmented control, because the test
        harness can drive a radio and every input on this page is
        covered by a test.

    Arguments:
        None.

    Returns:
        str: The chosen input style.

    Warning:
        Renders a widget as a side effect.
    """
    return str(
        st.radio(
            "Input style",
            list(INPUT_MODE_TUPLE),
            index=INPUT_MODE_TUPLE.index(read_input_mode_str()),
            key=INPUT_MODE_STATE_KEY_STR,
            horizontal=True,
            help=INPUT_MODE_HELP_STR,
        )
    )


def _clamp_float(
    value_float: float,
    minimum_float: float,
    maximum_float: float,
) -> float:
    """Keep a stored value inside a control's range.

    Brief:
        A value typed in one mode can fall outside the slider's
        range in the other, and Streamlit raises rather than
        clamping, so it is clamped here first.

    Arguments:
        value_float (float): Value being placed.
        minimum_float (float): Lowest the control allows.
        maximum_float (float): Highest the control allows.

    Returns:
        float: Value inside the range.

    Warning:
        Silently narrows an out-of-range value rather than
        refusing it, which is what keeps a mode switch safe.
    """
    return max(
        float(minimum_float),
        min(float(maximum_float), float(value_float)),
    )


def render_tunable_float(
    label_str: str,
    state_key_str: str,
    range_tuple: tuple,
    default_float: float,
    help_str: str = "",
) -> float:
    """Render one value as a slider or a box, reader's choice.

    The number lives in session state under `state_key_str` and
    every style writes back to it, so switching style keeps the
    figure. The step applies to the slider and to the box's arrows;
    a typed figure inside the range is always accepted, which is
    the whole reason the choice exists.
    """
    stored_float = _seed_stored_float(
        state_key_str, range_tuple, default_float
    )
    mode_str = read_input_mode_str()
    if mode_str == INPUT_MODE_SLIDER_STR:
        return _render_slider_float(
            label_str,
            state_key_str,
            range_tuple,
            stored_float,
            help_str,
        )
    if mode_str == INPUT_MODE_TYPED_STR:
        return _render_box_float(
            label_str,
            state_key_str,
            range_tuple,
            stored_float,
            help_str,
        )
    return _render_both_float(
        label_str, state_key_str, range_tuple, stored_float, help_str
    )


def _render_both_float(
    label_str: str,
    state_key_str: str,
    range_tuple: tuple,
    stored_float: float,
    help_str: str,
) -> float:
    """Draw the slider and the box together, in step.

    The box is drawn second and wins, so a reader who drags and
    then types ends on the typed figure. Dragging after typing
    reruns the script and re-seeds the box from the shared key, so
    the two never disagree on screen.
    """
    slider_float = _render_slider_float(
        label_str, state_key_str, range_tuple, stored_float, help_str
    )
    return _render_box_float(
        "Or type it exactly",
        state_key_str,
        range_tuple,
        slider_float,
        help_str,
    )


def _widget_key_str(state_key_str: str, suffix_str: str) -> str:
    """The key one style's widget stores its own value under."""
    return f"{state_key_str}{suffix_str}"


def _seed_stored_float(
    state_key_str: str,
    range_tuple: tuple,
    default_float: float,
) -> float:
    """Agree one value, and put it into every control that shows it.

    Streamlit ignores a widget's `value=` once that widget's key
    exists - the key wins - so a typed figure left the slider where
    it was, and a dragged slider left the box stale. Reconciling
    first fixes both: whichever control disagrees with the shared
    value is the one just touched, so its figure becomes the truth
    and is written into the other control's key too.

    Arguments:
        state_key_str (str): Key the value is stored under.
        range_tuple (tuple): Minimum, maximum and step.
        default_float (float): Value on first render.

    Returns:
        float: The agreed value, clamped into the range.

    Warning:
        Must run before the widgets. Streamlit refuses to let a
        widget's key be written once the widget exists, so calling
        this afterwards raises rather than syncing.
    """
    minimum_float, maximum_float, _ = range_tuple
    if state_key_str not in st.session_state:
        st.session_state[state_key_str] = default_float
    stored_float = _clamp_float(
        float(st.session_state[state_key_str]),
        minimum_float,
        maximum_float,
    )
    agreed_float = _resolve_agreed_float(
        state_key_str, stored_float
    )
    agreed_float = _clamp_float(
        agreed_float, minimum_float, maximum_float
    )
    st.session_state[state_key_str] = agreed_float
    for suffix_str in (SLIDER_SUFFIX_STR, BOX_SUFFIX_STR):
        st.session_state[
            _widget_key_str(state_key_str, suffix_str)
        ] = agreed_float
    return agreed_float


def _resolve_agreed_float(
    state_key_str: str,
    stored_float: float,
) -> float:
    """Decide which control the reader just changed.

    Brief:
        The box is asked first, so that a reader who drags and then
        types ends on the typed figure. That ordering is the same
        promise the two-control layout makes on screen.

    Arguments:
        state_key_str (str): Key the value is stored under.
        stored_float (float): Value the two last agreed on.

    Returns:
        float: The figure now in force.
    """
    for suffix_str in (BOX_SUFFIX_STR, SLIDER_SUFFIX_STR):
        widget_key_str = _widget_key_str(state_key_str, suffix_str)
        if widget_key_str not in st.session_state:
            continue
        widget_float = float(st.session_state[widget_key_str])
        if widget_float != stored_float:
            return widget_float
    return stored_float


def _render_slider_float(
    label_str: str,
    state_key_str: str,
    range_tuple: tuple,
    stored_float: float,
    help_str: str,
) -> float:
    """Draw the slider form of a tunable value.

    Brief:
        Uses its own widget key so switching style never collides
        with the box's widget of the same name.

    Arguments:
        label_str (str): Field label.
        state_key_str (str): Key the value is stored under.
        range_tuple (tuple): Minimum, maximum and step.
        stored_float (float): Current value.
        help_str (str): Tooltip text.

    Returns:
        float: The value now set.

    Warning:
        Writes back to the shared key so the box agrees.
    """
    minimum_float, maximum_float, step_float = range_tuple
    del stored_float
    chosen_float = float(
        st.slider(
            label_str,
            min_value=float(minimum_float),
            max_value=float(maximum_float),
            step=float(step_float),
            key=_widget_key_str(state_key_str, SLIDER_SUFFIX_STR),
            help=help_str,
        )
    )
    st.session_state[state_key_str] = chosen_float
    return chosen_float


def _render_box_float(
    label_str: str,
    state_key_str: str,
    range_tuple: tuple,
    stored_float: float,
    help_str: str,
) -> float:
    """Draw the keyboard form of a tunable value.

    Brief:
        The only form that can express a figure the step would
        otherwise skip over.

    Arguments:
        label_str (str): Field label.
        state_key_str (str): Key the value is stored under.
        range_tuple (tuple): Minimum, maximum and step.
        stored_float (float): Current value.
        help_str (str): Tooltip text.

    Returns:
        float: The value now set.

    Warning:
        Writes back to the shared key so the slider agrees.
    """
    minimum_float, maximum_float, step_float = range_tuple
    del stored_float
    chosen_float = float(
        st.number_input(
            label_str,
            min_value=float(minimum_float),
            max_value=float(maximum_float),
            step=float(step_float),
            key=_widget_key_str(state_key_str, BOX_SUFFIX_STR),
            help=help_str,
        )
    )
    st.session_state[state_key_str] = chosen_float
    return chosen_float


def set_tunable_float(
    state_key_str: str,
    value_float: float,
) -> None:
    """Fill a tunable value in from somewhere else.

    Brief:
        Used by the quick-pick buttons. Writing to the shared key
        rather than to a widget means the value shows up whichever
        style is active.

    Arguments:
        state_key_str (str): Key the value is stored under.
        value_float (float): Value to place.

    Returns:
        None: Session state is updated.

    Warning:
        Clears both widget keys so the freshly set value wins over
        whatever the widget was last showing.
    """
    st.session_state[state_key_str] = float(value_float)
    for suffix_str in (SLIDER_SUFFIX_STR, BOX_SUFFIX_STR):
        st.session_state.pop(
            _widget_key_str(state_key_str, suffix_str), None
        )
