"""First run: what a reader sees before they have entered anything.

Empty is the state every reader starts in and the one least likely
to be checked by hand. The rule these tests enforce is that no
screen may render a blank chart or an unexplained void: if a page
cannot do its job yet, it must say what to do instead, and name
where to do it.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH
from investment_journey_simulator.portal_app import PAGE_SPECIFICATION_TUPLE
from investment_journey_simulator.portal_state import build_default_scenario

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 900

# Pages that answer a question about a plan, and therefore have
# nothing to show until one exists. Each must route the reader
# somewhere rather than rendering an empty frame.
PLAN_DEPENDENT_PAGE_TUPLE: tuple = (
    "quick_page",
    "compare_page",
    "goal_page",
    "risk_page",
    "reports_page",
)

# Screens a reader can use before building anything: Home explains
# the program, Guides teach, the Rebalancing Lab runs its own
# controlled experiment, and Guided and Advanced *are* where a plan
# gets built.
PLAN_INDEPENDENT_PAGE_TUPLE: tuple = (
    "home_page",
    "guides_page",
    "rebalancing_page",
    "guided_page",
    "advanced_page",
)

# The screens an empty state is allowed to send someone to.
DESTINATION_TUPLE: tuple = (
    "Quick Projection",
    "Guided Journey",
    "Advanced Simulator",
)


def run_page(page_module_name_str: str) -> AppTest:
    """Render one page against a brand new plan.

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
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    ).run()


def read_all_text_str(app_test: AppTest) -> str:
    """Everything the page wrote, joined.

    REFERENCE: harness only.
    """
    part_list = []
    for collection in (
        app_test.markdown,
        app_test.caption,
        app_test.info,
        app_test.warning,
        app_test.success,
        app_test.title,
        app_test.header,
        app_test.subheader,
    ):
        part_list.extend(
            element.value for element in collection
        )
    return " ".join(part_list)


def test_the_page_lists_cover_every_declared_page():
    """A new page must be classified, not silently unchecked."""
    declared_set = {
        specification[1]
        for specification in PAGE_SPECIFICATION_TUPLE
    }
    covered_set = set(PLAN_DEPENDENT_PAGE_TUPLE) | set(
        PLAN_INDEPENDENT_PAGE_TUPLE
    )
    assert declared_set == covered_set


def test_a_new_plan_really_is_empty():
    """The premise of every test below."""
    scenario = build_default_scenario()
    assert scenario.plan.event_list == []
    assert scenario.fund_list[0].monthly_sip_float == 0.0


@pytest.mark.parametrize(
    "page_module_name_str",
    PLAN_DEPENDENT_PAGE_TUPLE + PLAN_INDEPENDENT_PAGE_TUPLE,
)
def test_every_page_renders_something_on_a_new_plan(
    page_module_name_str,
):
    """No blank screens, and no exceptions."""
    app_test = run_page(page_module_name_str)
    assert not app_test.exception
    assert app_test.title, "no heading rendered"
    assert read_all_text_str(app_test).strip(), "no text rendered"


@pytest.mark.parametrize(
    "page_module_name_str", PLAN_DEPENDENT_PAGE_TUPLE
)
def test_a_plan_dependent_page_says_what_to_do_next(
    page_module_name_str,
):
    """An empty state that names no next step is a dead end."""
    text_str = read_all_text_str(run_page(page_module_name_str))
    assert any(
        destination_str in text_str
        for destination_str in DESTINATION_TUPLE
    ), f"{page_module_name_str} routes the reader nowhere"


@pytest.mark.parametrize(
    "page_module_name_str", PLAN_DEPENDENT_PAGE_TUPLE
)
def test_a_plan_dependent_page_shows_no_figures_yet(
    page_module_name_str,
):
    """A confident zero is worse than an honest prompt."""
    app_test = run_page(page_module_name_str)
    assert app_test.metric == []


def test_home_explains_the_program_without_any_input():
    """A reader arriving cold must learn what this is."""
    text_str = read_all_text_str(run_page("home_page"))
    assert "not" in text_str and "forecast" in text_str
    for destination_str in DESTINATION_TUPLE:
        assert destination_str in text_str


def test_home_leads_with_questions_not_tool_names():
    """Nobody arrives wanting a "simulator".

    They arrive wanting to know whether they will have enough. A
    reader has to be able to recognise their own situation before
    learning any of this program's vocabulary, so the route cards
    lead with the question and name the screen underneath.
    """
    from investment_journey_simulator.pages.home_page import ROUTE_TUPLE

    text_str = read_all_text_str(run_page("home_page"))
    assert "Start with a question" in text_str
    for _icon, question_str, screen_str, _body, _module in (
        ROUTE_TUPLE
    ):
        assert question_str in text_str
        assert screen_str in text_str


def test_every_home_route_names_a_real_screen():
    """A route pointing nowhere is worse than no route.

    The navigation tree is the authority on what exists; Home only
    describes it.
    """
    from investment_journey_simulator.pages.home_page import (
        ROUTE_TUPLE,
    )
    from investment_journey_simulator.portal_app import (
        PAGE_SPECIFICATION_TUPLE,
    )

    title_set = {
        specification[2]
        for specification in PAGE_SPECIFICATION_TUPLE
    }
    for _icon, _question, screen_str, _body, _module in (
        ROUTE_TUPLE
    ):
        assert screen_str in title_set, (
            f"Home offers {screen_str!r}, which is not a page"
        )


def test_home_states_what_is_modelled_and_what_is_not():
    """The honest framing, on the first screen a reader sees."""
    text_str = read_all_text_str(run_page("home_page"))
    assert "models exactly" in text_str
    assert "approximates" in text_str
    assert "does not attempt" in text_str
