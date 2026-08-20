"""Slider or keyboard - the reader's choice, never the tool's.

A slider reads better and explores a range faster. A number box is
the only thing that can say *exactly* 62.5% or 33,333. These tests
hold both open: the style is a preference, the value survives
switching between them, and nothing is reachable by only one route.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_launch_script_str
from investment_journey_simulator.timeline import (
    EVENT_INCOME_STR,
    EVENT_LUMPSUM_STR,
    EVENT_NOTE_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
)
from investment_journey_simulator.timeline_app import (
    AMOUNT_PRESET_DICT,
    AMOUNT_STATE_KEY_STR,
    EQUITY_STATE_KEY_STR,
    NOTE_STATE_KEY_STR,
    PERCENT_STATE_KEY_STR,
    VIEW_PLAN_STR,
    VIEW_RESULT_STR,
    VIEW_STATE_KEY_STR,
)
from investment_journey_simulator.ui.rail_view import PENDING_STATE_KEY_STR
from investment_journey_simulator.ui.value_input import (
    INPUT_MODE_BOTH_STR,
    INPUT_MODE_SLIDER_STR,
    INPUT_MODE_STATE_KEY_STR,
    INPUT_MODE_TYPED_STR,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

TIMELINE_SCRIPT_STR: str = build_launch_script_str("timeline_app")
APP_TIMEOUT_SECONDS_INT: int = 240


def open_chooser_app(
    event_type_str: str = "",
    input_mode_str: str = INPUT_MODE_TYPED_STR,
) -> AppTest:
    """Run the plan view with the event chooser already open.

    REFERENCE: harness only.
    """
    app_test = AppTest.from_string(
        TIMELINE_SCRIPT_STR,
        default_timeout=APP_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[VIEW_STATE_KEY_STR] = VIEW_PLAN_STR
    app_test.session_state[PENDING_STATE_KEY_STR] = 24
    app_test.session_state[INPUT_MODE_STATE_KEY_STR] = input_mode_str
    if event_type_str:
        # The chooser narrows by category first, so the event is
        # only offered once its own category is selected.
        app_test.session_state["chooser_event_group"] = (
            resolve_group_name_str(event_type_str)
        )
        app_test.session_state["chooser_event_type"] = event_type_str
    return app_test.run()


def resolve_group_name_str(event_type_str: str) -> str:
    """The category one event belongs to.

    REFERENCE: harness only.
    """
    from investment_journey_simulator.timeline import (
        EVENT_GROUP_TUPLE,
    )

    for group_name_str, event_tuple in EVENT_GROUP_TUPLE:
        if event_type_str in event_tuple:
            return group_name_str
    raise AssertionError(f"{event_type_str!r} is in no category")


def widget_by_key(widget_list, key_str: str):
    """Find the one widget carrying a key.

    REFERENCE: harness only.
    """
    return [
        widget for widget in widget_list if widget.key == key_str
    ][0]


def test_sliders_are_offered_because_they_read_better() -> None:
    """A slider is the nicer control, so it must be available.

    REFERENCE: G4-SYNTHETIC. Banning sliders to guarantee typing
    was the wrong trade; both styles are offered instead.
    """
    app_test = open_chooser_app(
        EVENT_START_SIP_STR, INPUT_MODE_SLIDER_STR
    )
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]
    assert any(
        widget.key == f"{AMOUNT_STATE_KEY_STR}__slider"
        for widget in app_test.slider
    )


def test_typing_replaces_every_slider_when_chosen() -> None:
    """Choosing to type must convert the whole page, not part.

    REFERENCE: G4-SYNTHETIC. A page that mixed styles would leave
    some value reachable only by dragging.
    """
    app_test = open_chooser_app(
        EVENT_START_SIP_STR, INPUT_MODE_TYPED_STR
    )
    assert not app_test.slider
    assert any(
        widget.key == f"{AMOUNT_STATE_KEY_STR}__box"
        for widget in app_test.number_input
    )


def test_the_input_style_is_offered_as_a_choice() -> None:
    """The reader decides, and the control has to be findable.

    REFERENCE: G4-SYNTHETIC.
    """
    style_control = widget_by_key(
        open_chooser_app().radio, INPUT_MODE_STATE_KEY_STR
    )
    assert list(style_control.options) == [
        INPUT_MODE_BOTH_STR,
        INPUT_MODE_SLIDER_STR,
        INPUT_MODE_TYPED_STR,
    ]


def test_a_value_survives_switching_between_styles() -> None:
    """Switching style must not quietly reset what you set.

    REFERENCE: G4-SYNTHETIC. The number lives in session state
    under its own key, not inside either widget, which is what
    makes the two styles two views of one value.
    """
    app_test = open_chooser_app(
        EVENT_START_SIP_STR, INPUT_MODE_TYPED_STR
    )
    widget_by_key(
        app_test.number_input, f"{AMOUNT_STATE_KEY_STR}__box"
    ).set_value(33_333.0).run()
    assert app_test.session_state[AMOUNT_STATE_KEY_STR] == (
        pytest.approx(33_333.0)
    )
    widget_by_key(
        app_test.radio, INPUT_MODE_STATE_KEY_STR
    ).set_value(INPUT_MODE_SLIDER_STR).run()
    assert app_test.session_state[AMOUNT_STATE_KEY_STR] == (
        pytest.approx(33_333.0)
    )


def test_an_awkward_amount_survives_being_typed() -> None:
    """Real amounts are not round, so a step must not round them.

    REFERENCE: G4-SYNTHETIC. 33,333 is not a multiple of the step,
    and typed mode is what makes it expressible at all.
    """
    app_test = open_chooser_app(EVENT_START_SIP_STR)
    widget_by_key(
        app_test.number_input, f"{AMOUNT_STATE_KEY_STR}__box"
    ).set_value(33_333.0).run()
    assert app_test.session_state[AMOUNT_STATE_KEY_STR] == (
        pytest.approx(33_333.0)
    )


def test_a_fractional_rate_survives_being_typed() -> None:
    """Rates are not whole numbers either.

    REFERENCE: G4-SYNTHETIC. 7.25% must not snap to 7 or 7.5.
    """
    app_test = open_chooser_app(EVENT_STEPUP_STR)
    widget_by_key(
        app_test.number_input, f"{PERCENT_STATE_KEY_STR}__box"
    ).set_value(7.25).run()
    assert app_test.session_state[PERCENT_STATE_KEY_STR] == (
        pytest.approx(7.25)
    )


def test_the_portfolio_split_can_be_typed_not_only_dragged(
) -> None:
    """A 5% step would make 62.5% equity impossible to express.

    REFERENCE: G4-SYNTHETIC. The slider is welcome; being the only
    control was the problem.
    """
    app_test = AppTest.from_string(
        TIMELINE_SCRIPT_STR,
        default_timeout=APP_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[VIEW_STATE_KEY_STR] = VIEW_RESULT_STR
    app_test.session_state[INPUT_MODE_STATE_KEY_STR] = (
        INPUT_MODE_TYPED_STR
    )
    app_test.run()
    widget_by_key(
        app_test.number_input, f"{EQUITY_STATE_KEY_STR}__box"
    ).set_value(62.5).run()
    assert app_test.session_state[EQUITY_STATE_KEY_STR] == (
        pytest.approx(62.5)
    )


def test_a_note_can_carry_the_words_that_matter() -> None:
    """A marker with no text is a dot with nothing to say.

    REFERENCE: G4-SYNTHETIC. The note event existed before this
    test with no way at all to type its text.
    """
    app_test = open_chooser_app(EVENT_NOTE_STR)
    note_input = [
        element
        for element in app_test.text_input
        if element.key == NOTE_STATE_KEY_STR
    ]
    assert len(note_input) == 1
    note_input[0].set_value("bought a house").run()
    assert app_test.session_state[NOTE_STATE_KEY_STR] == (
        "bought a house"
    )


def test_the_date_can_be_corrected_after_a_missed_click() -> None:
    """A click can land a month out, and retyping beats reclicking.

    REFERENCE: G4-SYNTHETIC. The chooser opens on the clicked
    month but must not be stuck with it.
    """
    assert [
        element
        for element in open_chooser_app().date_input
        if element.key == "chooser_date"
    ]


@pytest.mark.parametrize(
    "event_type_str",
    [EVENT_START_SIP_STR, EVENT_LUMPSUM_STR, EVENT_INCOME_STR],
)
def test_quick_picks_sit_beside_the_control_not_instead_of_it(
    event_type_str: str,
) -> None:
    """Presets are a shortcut; they must never be the only way in.

    REFERENCE: G4-SYNTHETIC. Both have to be present at once, or
    the chips would be a constraint dressed as a help.
    """
    app_test = open_chooser_app(event_type_str)
    preset_button_list = [
        button
        for button in app_test.button
        if button.key
        and button.key.startswith(f"{AMOUNT_STATE_KEY_STR}_preset")
    ]
    assert len(preset_button_list) >= 3
    assert any(
        widget.key == f"{AMOUNT_STATE_KEY_STR}__box"
        for widget in app_test.number_input
    )


def test_a_quick_pick_fills_the_control_without_locking_it(
) -> None:
    """A preset must set the figure, then get out of the way.

    REFERENCE: G4-SYNTHETIC. Clicking a chip fills the control;
    the control must then still accept a different number.
    """
    app_test = open_chooser_app(EVENT_START_SIP_STR)
    preset_button_list = [
        button
        for button in app_test.button
        if button.key
        and button.key.startswith(f"{AMOUNT_STATE_KEY_STR}_preset")
    ]
    preset_button_list[0].click().run()
    assert (
        app_test.session_state[AMOUNT_STATE_KEY_STR]
        in AMOUNT_PRESET_DICT[EVENT_START_SIP_STR]
    )
    widget_by_key(
        app_test.number_input, f"{AMOUNT_STATE_KEY_STR}__box"
    ).set_value(41_500.0).run()
    assert app_test.session_state[AMOUNT_STATE_KEY_STR] == (
        pytest.approx(41_500.0)
    )


# ------------------------------------------------------------------
# The slider and the box are one value wearing two faces. Streamlit
# ignores a widget's `value=` once its key exists, so until the two
# were reconciled before rendering, typing a figure left the slider
# where it was and dragging the slider left the box stale.
# ------------------------------------------------------------------
TUNABLE_SCRIPT_STR: str = (
    "import sys\n"
    f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
    "import streamlit as st\n"
    "from investment_journey_simulator.ui.value_input import (\n"
    "    render_tunable_float,\n"
    "    set_tunable_float,\n"
    "    INPUT_MODE_STATE_KEY_STR,\n"
    "    INPUT_MODE_BOTH_STR,\n"
    ")\n"
    "st.session_state.setdefault(\n"
    "    INPUT_MODE_STATE_KEY_STR, INPUT_MODE_BOTH_STR\n"
    ")\n"
    "if st.button('preset', key='preset_btn'):\n"
    "    set_tunable_float('demo_value', 75000.0)\n"
    "    st.rerun()\n"
    "render_tunable_float(\n"
    "    'Amount', 'demo_value', (0.0, 100000.0, 1000.0), 10000.0\n"
    ")\n"
)


def open_tunable_app() -> AppTest:
    """One value shown as both a slider and a box.

    REFERENCE: harness only.
    """
    return AppTest.from_string(
        TUNABLE_SCRIPT_STR, default_timeout=APP_TIMEOUT_SECONDS_INT
    ).run()


def assert_agreed(app_test, expected_float: float) -> None:
    """Both controls and the shared value show one figure.

    REFERENCE: harness only.
    """
    assert app_test.slider[0].value == pytest.approx(expected_float)
    assert app_test.number_input[0].value == pytest.approx(
        expected_float
    )
    assert app_test.session_state["demo_value"] == pytest.approx(
        expected_float
    )


def test_typing_a_figure_moves_the_slider() -> None:
    """The reported bug, in one assertion."""
    app_test = open_tunable_app()
    app_test.number_input[0].set_value(33333.0).run()
    assert_agreed(app_test, 33333.0)


def test_dragging_the_slider_updates_the_box() -> None:
    """And the same failure in the other direction."""
    app_test = open_tunable_app()
    app_test.slider[0].set_value(50000.0).run()
    assert_agreed(app_test, 50000.0)


def test_a_preset_moves_both_controls() -> None:
    """Clicking a quick pick has to move the slider too."""
    app_test = open_tunable_app()
    app_test.button[0].click().run()
    assert_agreed(app_test, 75000.0)


def test_the_two_controls_stay_agreed_across_a_sequence() -> None:
    """Type, drag, type, preset, drag - never disagreeing.

    A single interaction working proves little; the failure was a
    stale widget key, which only shows up once one control has
    been used and then the other.
    """
    app_test = open_tunable_app()
    app_test.number_input[0].set_value(33333.0).run()
    assert_agreed(app_test, 33333.0)
    app_test.slider[0].set_value(50000.0).run()
    assert_agreed(app_test, 50000.0)
    app_test.number_input[0].set_value(7777.0).run()
    assert_agreed(app_test, 7777.0)
    app_test.button[0].click().run()
    assert_agreed(app_test, 75000.0)
    app_test.slider[0].set_value(20000.0).run()
    assert_agreed(app_test, 20000.0)
