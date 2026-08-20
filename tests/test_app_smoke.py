"""Headless runs of the whole Streamlit app.

These tests execute the real script through Streamlit's own test
runner, so they catch failures that only appear once widgets are
actually rendered, such as duplicate element identifiers.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from conftest import build_launch_script_str
from investment_journey_simulator.timeline import (
    EVENT_GROUP_TUPLE,
    EVENT_TYPE_TUPLE,
)
from investment_journey_simulator.timeline_app import (
    VIEW_PLAN_STR,
    VIEW_RESULT_STR,
    VIEW_STATE_KEY_STR,
)
from investment_journey_simulator.ui.rail_view import PENDING_STATE_KEY_STR
from investment_journey_simulator.ui.result_view import (
    CHART_TAB_LABELS_TUPLE,
    LEDGER_TAB_LABELS_TUPLE,
    build_element_key_str,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

APP_SCRIPT_STR: str = build_launch_script_str("app")
APP_TIMEOUT_SECONDS_INT: int = 240
RUN_LABEL_TUPLE: tuple = ("Nominal", "Real")


def run_app() -> AppTest:
    """Execute the dashboard script once, headlessly.

    REFERENCE: harness only.
    """
    app_test = AppTest.from_string(
        APP_SCRIPT_STR, default_timeout=APP_TIMEOUT_SECONDS_INT
    )
    return app_test.run()


def test_every_element_key_is_unique() -> None:
    """Two runs must never generate the same widget key.

    REFERENCE: G4-SYNTHETIC. Weight and drawdown figures are ratios
    and empty ledgers are identical frames, so the nominal and real
    versions collide unless the run label is part of the key.
    """
    key_list = [
        build_element_key_str(run_label_str, element_name_str)
        for run_label_str in RUN_LABEL_TUPLE
        for element_name_str in (
            CHART_TAB_LABELS_TUPLE + LEDGER_TAB_LABELS_TUPLE
        )
    ]
    assert len(key_list) == len(set(key_list))


def test_element_keys_are_safe_identifiers() -> None:
    """Keys must contain no spaces or punctuation.

    REFERENCE: G4-SYNTHETIC. Keys travel into the DOM.
    """
    key_str = build_element_key_str("Real", "Weights vs target")
    assert key_str == "real_weights_vs_target"


def test_the_dashboard_renders_without_exceptions() -> None:
    """The whole app must run end to end with no error.

    REFERENCE: G4-SYNTHETIC. This is the check that catches
    duplicate element identifiers, which no headless unit test can
    see because they only arise when widgets register themselves.
    """
    app_test = run_app()
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]


def test_the_dashboard_shows_both_runs() -> None:
    """Nominal and inflation-adjusted sections must both render.

    REFERENCE: G4-SYNTHETIC. Page structure contract.
    """
    app_test = run_app()
    heading_text_str = " ".join(
        element.value for element in app_test.subheader
    )
    assert "Nominal" in heading_text_str
    assert "Inflation-adjusted" in heading_text_str


def test_the_dashboard_draws_every_chart() -> None:
    """Both runs must render all four of their figures.

    REFERENCE: G4-SYNTHETIC. Four charts per run, two runs.
    """
    app_test = run_app()
    assert len(app_test.get("plotly_chart")) == 2 * len(
        CHART_TAB_LABELS_TUPLE
    )


def test_the_dashboard_shows_the_headline_metrics() -> None:
    """The KPI tiles must be present on the first render.

    REFERENCE: G4-SYNTHETIC. Per run: four headline tiles, four
    exit-cost tiles and two money-weighted return tiles, rendered
    once for the nominal run and once for the real run.
    """
    app_test = run_app()
    assert len(app_test.get("metric")) == 2 * 10


def test_every_chart_registers_a_unique_identifier() -> None:
    """No two charts may share a Streamlit element id.

    REFERENCE: G4-SYNTHETIC. This is exactly the condition whose
    violation raised StreamlitDuplicateElementId: the weight and
    drawdown figures of the two runs are structurally identical,
    because weights are ratios and are unaffected by deflation.
    """
    app_test = run_app()
    identifier_list = [
        element.proto.id for element in app_test.get("plotly_chart")
    ]
    assert len(identifier_list) == 2 * len(CHART_TAB_LABELS_TUPLE)
    assert len(set(identifier_list)) == len(identifier_list)


@pytest.mark.parametrize("run_label_str", RUN_LABEL_TUPLE)
def test_chart_identifiers_carry_the_run_label(
    run_label_str: str,
) -> None:
    """Each run's charts must be keyed by that run.

    REFERENCE: G4-SYNTHETIC. Guards the fix for the duplicate
    identifier crash at the level the user actually hit it.
    """
    app_test = run_app()
    identifier_list = [
        element.proto.id for element in app_test.get("plotly_chart")
    ]
    for tab_label_str in CHART_TAB_LABELS_TUPLE:
        expected_key_str = build_element_key_str(
            run_label_str, tab_label_str
        )
        assert any(
            identifier_str.endswith(expected_key_str)
            for identifier_str in identifier_list
        )


def test_the_page_states_the_constant_return_assumption() -> None:
    """The headline corpus must carry its own health warning.

    REFERENCE: G4-SYNTHETIC. Every figure above the caveat comes
    from compounding one fixed rate every month, which no market
    has done. Shipping the number without the caveat is the
    overclaim this tool exists to avoid.
    """
    app_test = run_app()
    caption_list = [caption.value for caption in app_test.caption]
    assert any(
        "never once done" in caption_str
        for caption_str in caption_list
    )
    assert any(
        "Not a forecast" in caption_str
        for caption_str in caption_list
    )


def test_the_page_offers_the_risk_panel() -> None:
    """The risk panel and its framing must both be present.

    REFERENCE: G4-SYNTHETIC. The constant-return caveat points the
    reader at the Risk section, so that section has to exist or
    the caveat sends them nowhere.
    """
    app_test = run_app()
    assert any(
        "fan of outcomes" in caption.value
        for caption in app_test.caption
    )
    assert any(
        "Risk" in subheader.value
        for subheader in app_test.subheader
    )
    assert any(
        "Simulate a range of market paths" in toggle.label
        for toggle in app_test.toggle
    )


def test_the_risk_simulation_is_off_by_default() -> None:
    """A page load must not pay for hundreds of simulations.

    REFERENCE: G4-SYNTHETIC. Each path is a full run of the
    engine, so the panel is opt-in; leaving it on by default would
    make every interaction slow.
    """
    app_test = run_app()
    risk_toggle_list = [
        toggle
        for toggle in app_test.toggle
        if "Simulate a range of market paths" in toggle.label
    ]
    assert len(risk_toggle_list) == 1
    assert risk_toggle_list[0].value is False


TIMELINE_SCRIPT_STR: str = build_launch_script_str("timeline_app")


def run_timeline_app(view_str: str = VIEW_PLAN_STR) -> AppTest:
    """Execute the timeline script once, headlessly.

    REFERENCE: harness only. The view is seeded through session
    state because the toggle cannot be clicked before the first
    run has drawn it.
    """
    app_test = AppTest.from_string(
        TIMELINE_SCRIPT_STR,
        default_timeout=APP_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[VIEW_STATE_KEY_STR] = view_str
    return app_test.run()


def test_the_timeline_app_renders_without_exceptions() -> None:
    """The second front end must run end to end.

    REFERENCE: G4-SYNTHETIC. The timeline is a separate script on
    purpose, so it needs its own smoke test; a break here must not
    be discovered only by a user.
    """
    app_test = run_timeline_app()
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]


def test_the_timeline_offers_every_event_type() -> None:
    """Every modelled event must be selectable.

    REFERENCE: G4-SYNTHETIC. An event the compiler understands but
    the menu never offers is dead code.
    """
    app_test = run_timeline_app()
    composer_selectbox = [
        widget
        for widget in app_test.selectbox
        if widget.key == "composer_event_type"
    ]
    assert len(composer_selectbox) == 1
    assert list(composer_selectbox[0].options) == list(
        EVENT_TYPE_TUPLE
    )


def test_the_timeline_draws_its_figure_and_cards() -> None:
    """The result view must render the curve and its cards.

    REFERENCE: G4-SYNTHETIC. Seven cards: four outcome figures and
    three return figures.
    """
    app_test = run_timeline_app(VIEW_RESULT_STR)
    assert len(app_test.get("plotly_chart")) == 1
    card_list = [
        element.value
        for element in app_test.markdown
        if '<div class="tl-card">' in element.value
    ]
    assert len(card_list) == 7


def read_palette_button_list(app_test: AppTest) -> list:
    """The arming chips, if any are on screen.

    REFERENCE: harness only.
    """
    return [
        button
        for button in app_test.button
        if button.label.startswith(("○ ", "● "))
    ]


def test_the_plan_view_opens_on_a_rail_and_nothing_else() -> None:
    """The timeline is the interface, not a preamble to it.

    REFERENCE: G4-SYNTHETIC. Two charts - the rail and the live
    Gantt beneath it - and *no* palette. Thirteen chips above the
    rail turn one gesture into a lesson in event taxonomy before
    the reader has placed anything, which is exactly the
    complication the click-a-month design removes.
    """
    app_test = run_timeline_app(VIEW_PLAN_STR)
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]
    assert len(app_test.get("plotly_chart")) == 2
    assert read_palette_button_list(app_test) == []


def test_quick_place_brings_the_palette_back() -> None:
    """Arming still exists; it just no longer leads.

    REFERENCE: G4-SYNTHETIC. Dropping four pauses in a row is
    tedious when every one asks what it is, so the accelerator
    stays - one toggle away, with every chip still explaining
    itself on hover.
    """
    app_test = run_timeline_app(VIEW_PLAN_STR)
    app_test.toggle[0].set_value(True).run()
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]
    palette_button_list = read_palette_button_list(app_test)
    assert len(palette_button_list) == len(EVENT_TYPE_TUPLE)
    assert all(button.help for button in palette_button_list)


def test_the_result_view_reports_the_journey() -> None:
    """The generated answer must narrate, not only total.

    REFERENCE: G4-SYNTHETIC. One row per event placed on the rail,
    so the reader sees what the corpus was worth at each decision.
    """
    app_test = run_timeline_app(VIEW_RESULT_STR)
    assert any(
        "journey" in element.value.lower()
        for element in app_test.markdown
    )
    assert len(app_test.dataframe) == 1


def test_clicking_the_rail_opens_the_event_chooser() -> None:
    """Hover offers a plus; clicking must then ask what happens.

    REFERENCE: G4-SYNTHETIC. The month is chosen first and the
    event second, so a pending month has to produce the dropdown
    without anything being armed beforehand.
    """
    app_test = AppTest.from_string(
        TIMELINE_SCRIPT_STR,
        default_timeout=APP_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[VIEW_STATE_KEY_STR] = VIEW_PLAN_STR
    app_test.session_state[PENDING_STATE_KEY_STR] = 36
    app_test.run()
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]
    assert any(
        "Something happens in January 2029" in element.value
        for element in app_test.markdown
    )
    chooser_list = [
        element
        for element in app_test.selectbox
        if element.key == "chooser_event_type"
    ]
    assert len(chooser_list) == 1
    # The dropdown now shows one category at a time, so the
    # guarantee moves up a level: every event the compiler
    # understands has to be reachable through some category.
    from investment_journey_simulator.timeline_app import (
        build_group_name_list,
        resolve_group_event_tuple,
    )

    reachable_set = {
        event_type_str
        for group_name_str in build_group_name_list()
        for event_type_str in resolve_group_event_tuple(
            group_name_str
        )
    }
    assert set(EVENT_TYPE_TUPLE).issubset(reachable_set)
    assert set(chooser_list[0].options).issubset(reachable_set)


def test_the_chooser_offers_every_event_grouped() -> None:
    """The dropdown must expose the whole vocabulary, in groups.

    REFERENCE: G4-SYNTHETIC. An operation the compiler understands
    but the menu never offers is unreachable from the rail.
    """
    app_test = AppTest.from_string(
        TIMELINE_SCRIPT_STR,
        default_timeout=APP_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[VIEW_STATE_KEY_STR] = VIEW_PLAN_STR
    app_test.session_state[PENDING_STATE_KEY_STR] = 0
    app_test.run()
    option_list = list(
        [
            element
            for element in app_test.selectbox
            if element.key == "chooser_event_type"
        ][0].options
    )
    group_list = list(
        [
            element
            for element in app_test.radio
            if element.key == "chooser_event_group"
        ][0].options
    )
    # Categories are a control of their own. They were once rows in
    # this dropdown, which meant the menu offered a choice and then
    # refused it, so every option here has to be a real event.
    assert group_list == [
        group_name_str for group_name_str, _events in
        EVENT_GROUP_TUPLE
    ]
    assert set(option_list) <= set(EVENT_TYPE_TUPLE)
    assert option_list, "the first category offers no events"


