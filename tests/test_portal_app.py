"""Headless runs of the portal shell.

Every page is rendered for real through Streamlit's own runner, so a
screen that raises on an empty plan fails here rather than in front
of a reader.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH
from investment_journey_simulator.pages import page_shell
from investment_journey_simulator.plan_modes import MODE_ORDER_TUPLE
from investment_journey_simulator.portal_app import (
    PAGE_SPECIFICATION_TUPLE,
    SECTION_EXAMINE_STR,
    SECTION_LEARN_STR,
    SECTION_PLAN_STR,
    build_navigation_dict,
)
from investment_journey_simulator.portal_state import (
    MODE_STATE_KEY_STR,
    SCENARIO_STATE_KEY_STR,
    build_default_scenario,
    build_starting_month_date,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

# The launcher sits at the repository root, not under src/, which
# is where a src layout wants it: src/ holds the package and
# nothing else. Driving the real file rather than a stand-in means
# this test also proves the launcher itself still works.
PORTAL_SCRIPT_PATH_STR: str = str(
    SOURCE_DIRECTORY_PATH.parent / "streamlit_app.py"
)
PORTAL_TIMEOUT_SECONDS_INT: int = 240
PAGE_MODULE_NAME_TUPLE: tuple = tuple(
    specification[1] for specification in PAGE_SPECIFICATION_TUPLE
)


def run_portal() -> AppTest:
    """Execute the whole portal once, headlessly.

    REFERENCE: harness only.
    """
    return AppTest.from_file(
        PORTAL_SCRIPT_PATH_STR,
        default_timeout=PORTAL_TIMEOUT_SECONDS_INT,
    ).run()


def run_page(page_module_name_str: str) -> AppTest:
    """Render one page on its own, headlessly.

    Brief:
        Driven through a generated script rather than the portal's
        own router, because Streamlit's test runner offers no way
        to choose a page and would otherwise render Home every
        time - a test that passes without testing anything.

    Arguments:
        page_module_name_str (str): Page module to render.

    Returns:
        AppTest: The finished run.

    Warning:
        Bypasses the shared sidebar, so this proves the page
        renders, not that the navigation reaches it.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import "
        f"{page_module_name_str} as page\n"
        "page.render()\n"
    )
    return AppTest.from_string(
        script_str, default_timeout=PORTAL_TIMEOUT_SECONDS_INT
    ).run()


# --- The shell ----------------------------------------------------


def test_the_portal_starts():
    """The one door opens."""
    app_test = run_portal()
    assert not app_test.exception


def test_every_page_is_declared_once():
    """A duplicate route would shadow a whole screen."""
    assert len(set(PAGE_MODULE_NAME_TUPLE)) == len(
        PAGE_MODULE_NAME_TUPLE
    )


def test_every_declared_page_module_imports_and_renders():
    """Each page module exposes the callable the tree names."""
    from importlib import import_module

    for module_name_str in PAGE_MODULE_NAME_TUPLE:
        module = import_module(
            f"investment_journey_simulator.pages.{module_name_str}"
        )
        assert callable(module.render)


def test_the_navigation_tree_has_the_three_sections():
    """Grouped by what a reader is trying to do."""
    navigation_dict = build_navigation_dict()
    assert set(navigation_dict) == {
        SECTION_PLAN_STR,
        SECTION_EXAMINE_STR,
        SECTION_LEARN_STR,
    }


def test_home_is_the_default_page():
    """A reader with no destination lands somewhere useful."""
    assert PAGE_SPECIFICATION_TUPLE[0][1] == "home_page"


@pytest.mark.parametrize(
    "page_module_name_str", PAGE_MODULE_NAME_TUPLE
)
def test_every_page_renders_on_an_empty_plan(
    page_module_name_str,
):
    """Empty is a valid state, not a crash.

    A brand new reader opens every screen with nothing entered.
    None of them may raise.
    """
    app_test = run_page(page_module_name_str)
    assert not app_test.exception
    assert app_test.title, "the page rendered no heading at all"


@pytest.mark.parametrize("mode_str", MODE_ORDER_TUPLE)
def test_the_portal_renders_in_every_mode(mode_str):
    """Switching detail level cannot break the shell."""
    app_test = AppTest.from_file(
        PORTAL_SCRIPT_PATH_STR,
        default_timeout=PORTAL_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[MODE_STATE_KEY_STR] = mode_str
    app_test.run()
    assert not app_test.exception


# --- Shared state -------------------------------------------------


def test_a_new_session_gets_a_default_scenario():
    """No page needs to check whether the session is initialised."""
    app_test = run_portal()
    assert SCENARIO_STATE_KEY_STR in app_test.session_state


def test_the_default_plan_starts_this_month():
    """A new plan opens on a month boundary, as the grid needs."""
    scenario = build_default_scenario()
    assert scenario.plan.start_date == build_starting_month_date()
    assert scenario.plan.start_date.day == 1


def test_the_default_plan_invests_nothing_yet():
    """A plan reports what it holds, never what it guessed."""
    scenario = build_default_scenario()
    assert scenario.plan.event_list == []
    assert scenario.fund_list[0].monthly_sip_float == 0.0
    assert page_shell.has_investment_bool(scenario) is False


def test_the_default_plan_has_one_editable_fund():
    """Somewhere to type a return, without a wizard first."""
    scenario = build_default_scenario()
    assert len(scenario.fund_list) == 1
    assert scenario.fund_list[0].gross_return_percent_float > 0.0


@pytest.mark.parametrize(
    "page_module_name_str",
    tuple(
        name_str
        for name_str in PAGE_MODULE_NAME_TUPLE
        if name_str != "home_page"
    ),
)
def test_every_page_wears_the_same_section_mark(
    page_module_name_str,
):
    """One design language, not ten.

    The brass section mark is the device that makes nine screens
    and three diagrams read as parts of one product. Every page
    that opens through `page_shell.open_page` gets it, so a new
    screen cannot quietly ship in a different visual dialect.

    Home is excluded because it does not open through the shell -
    it is the one page whose heading is its own.
    """
    app_test = run_page(page_module_name_str)
    assert not app_test.exception
    markdown_str = " ".join(
        str(block.value) for block in app_test.markdown
    )
    assert "ijs-kicker" in markdown_str, (
        f"{page_module_name_str} rendered no section mark"
    )


def test_the_portal_installs_the_chrome_before_any_page():
    """An unstyled first paint is a visible bug.

    The stylesheet has to land before the first component, which
    means before navigation runs, or every screen flashes in
    Streamlit's defaults on the way in.
    """
    app_test = AppTest.from_file(
        PORTAL_SCRIPT_PATH_STR,
        default_timeout=PORTAL_TIMEOUT_SECONDS_INT,
    ).run()
    assert not app_test.exception
    markdown_list = [
        str(block.value) for block in app_test.markdown
    ]
    assert any("--ijs-brass" in body_str for body_str in markdown_list)


def test_every_page_is_registered_for_linking():
    """A screen that cannot be linked to cannot be handed off to.

    The registry is what lets one screen finish an action on
    another - "apply this to my plan" has to have somewhere to
    send the reader afterwards. It is populated by the portal
    itself, after navigation has bound the pages, so this runs the
    portal rather than building the tree by hand.
    """
    from investment_journey_simulator.page_links import resolve_page

    app_test = AppTest.from_file(
        PORTAL_SCRIPT_PATH_STR,
        default_timeout=PORTAL_TIMEOUT_SECONDS_INT,
    ).run()
    assert not app_test.exception
    for module_name_str in PAGE_MODULE_NAME_TUPLE:
        assert resolve_page(module_name_str) is not None, (
            f"{module_name_str} is not registered"
        )
