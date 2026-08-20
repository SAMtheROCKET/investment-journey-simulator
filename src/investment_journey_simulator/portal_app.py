"""The portal: one site over one scenario.

Three front ends used to be three programs. This is the one door
into all of them, plus the screens that only make sense once a plan
is shared - comparison, goals, risk and the guides.

The navigation tree below is the easy half. The half that matters is
that every page reads the same `PlanScenario` out of
`portal_state.py`, which is why moving from Quick to Compare never
asks a reader to type anything again.
"""

from __future__ import annotations

import sys

import streamlit as st

from investment_journey_simulator.page_links import register_page
from investment_journey_simulator.plan_modes import (
    MODE_ORDER_TUPLE,
    describe_mode_change_str,
    resolve_projection,
)
from investment_journey_simulator.plan_scenario import compile_scenario
from investment_journey_simulator.portal_state import (
    read_mode_str,
    read_scenario,
    reset_scenario,
    write_mode_str,
)
from investment_journey_simulator.ui.chrome import (
    install_chrome,
    render_brand_mark,
    render_plan_capsule,
)
from investment_journey_simulator.ui.regime_notice import (
    render_sidebar_regime_line,
)

PORTAL_TITLE_STR: str = "Investment Journey Simulator"
PORTAL_ICON_STR: str = "📈"
CONSOLE_TAGLINE_STR: str = "Decision studio"
MODE_FLASH_STATE_KEY_STR: str = "portal_mode_flash"

SECTION_PLAN_STR: str = "Plan"
SECTION_EXAMINE_STR: str = "Examine"
SECTION_LEARN_STR: str = "Learn"


def configure_page() -> None:
    """Set the page shell before anything else renders.

    Brief:
        Streamlit requires this to run before any other command,
        so it is the first thing `main` does.

    Arguments:
        None.

    Returns:
        None: The page is configured in place.

    Warning:
        Calling this twice in one run raises, which is why no page
        module may call it.
    """
    st.set_page_config(
        page_title=PORTAL_TITLE_STR,
        page_icon=PORTAL_ICON_STR,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_mode_picker() -> str:
    """Offer the three experience levels and remember the choice.

    Brief:
        Shown on every page, because the level a reader wants is a
        property of the reader and not of the screen they happen
        to be on.

    Arguments:
        None.

    Returns:
        str: The chosen mode.

    Warning:
        Changing the mode never changes the plan. Only what is
        shown changes, which is the promise the banner keeps.
    """
    current_str = read_mode_str()
    label_list = [
        resolve_projection(mode_str).label_str
        for mode_str in MODE_ORDER_TUPLE
    ]
    chosen_str = st.sidebar.radio(
        "Detail level",
        help=(
            "How much of the plan each screen puts on show. It never changes "
            "the plan itself."
        ),
        options=MODE_ORDER_TUPLE,
        index=MODE_ORDER_TUPLE.index(current_str)
        if current_str in MODE_ORDER_TUPLE
        else 1,
        format_func=lambda mode_str: label_list[
            MODE_ORDER_TUPLE.index(mode_str)
        ],
        key="portal_mode_picker",
    )
    if chosen_str != current_str:
        write_mode_str(chosen_str)
        # Recorded rather than shown here: the picker lives in the
        # rail, and a confirmation of what changed belongs beside
        # the controls that changed, not beside the switch.
        st.session_state[MODE_FLASH_STATE_KEY_STR] = (
            describe_mode_change_str(current_str, chosen_str)
        )
    st.sidebar.caption(
        resolve_projection(chosen_str).promise_str
    )
    return chosen_str


def take_mode_flash_str() -> str:
    """Read the pending mode announcement, and clear it.

    Brief:
        Taken rather than read, so the flash appears once on the
        screen after the switch and never again on every rerun
        that screen happens to do.

    Arguments:
        None.

    Returns:
        str: The sentence to show, or empty when there is none.
    """
    return str(
        st.session_state.pop(MODE_FLASH_STATE_KEY_STR, "")
    )


def render_scenario_summary() -> None:
    """Show what plan is loaded, on every page.

    Brief:
        A reader four screens deep must never have to wonder which
        plan they are looking at. The concept files make this a
        capsule in the console rather than a run of captions,
        because a capsule is one object the eye can find again.

    Arguments:
        None.

    Returns:
        None: The summary is rendered into the sidebar.

    Warning:
        Reads the scenario rather than a cached copy, so it always
        reflects the edit that was just made.
    """
    scenario = read_scenario()
    compiled = compile_scenario(scenario)
    event_count_int = len(scenario.plan.event_list)
    fund_count_int = len(scenario.fund_list)
    with st.sidebar:
        render_plan_capsule(
            scenario.name_str,
            "live",
            (
                f"{scenario.plan.horizon_years_int} years",
                compiled.currency.code_str,
                f"{fund_count_int} asset"
                f"{'' if fund_count_int == 1 else 's'}",
                f"{event_count_int} event"
                f"{'' if event_count_int == 1 else 's'}",
            ),
        )
        st.caption(f"From {scenario.plan.start_date:%B %Y}")
    render_sidebar_regime_line(scenario)


def render_sidebar_footer() -> None:
    """Offer the actions that belong to the whole session."""
    st.sidebar.divider()
    if st.sidebar.button(
        "Start a new plan", width="stretch"
    ):
        reset_scenario()
        st.rerun()
    st.sidebar.caption(
        "Every figure is a projection from the assumptions you "
        "enter, not a forecast of any market."
    )


# The navigation tree, as data: section, module name, title, icon.
# Grouped by what a reader is trying to do - build a plan, examine
# one, or learn how any of it works - rather than by which module
# happens to implement each screen.
PAGE_SPECIFICATION_TUPLE: tuple = (
    (SECTION_PLAN_STR, "home_page", "Home", "🏠"),
    (SECTION_PLAN_STR, "quick_page", "Quick Projection", "⚡"),
    (SECTION_PLAN_STR, "guided_page", "Guided Journey", "🧭"),
    (SECTION_PLAN_STR, "advanced_page", "Advanced Simulator", "🎛"),
    (
        SECTION_EXAMINE_STR,
        "compare_page",
        "Compare Journeys",
        "⚖",
    ),
    (SECTION_EXAMINE_STR, "goal_page", "Goal Planner", "🎯"),
    (
        SECTION_EXAMINE_STR,
        "risk_page",
        "Historical & Risk Lab",
        "📉",
    ),
    (
        SECTION_EXAMINE_STR,
        "rebalancing_page",
        "Rebalancing Lab",
        "🔁",
    ),
    (SECTION_EXAMINE_STR, "reports_page", "Reports & Audit", "📄"),
    (SECTION_LEARN_STR, "guides_page", "Guides", "📚"),
)


# Module name paired with the page object built for it, in tree
# order. Rebuilt on every run and read by `register_navigation`
# once `st.navigation` has bound the pages.
_PAGE_PAIR_LIST: list = []


def build_navigation_dict() -> dict:
    """Build the sections and pages the sidebar shows.

    Brief:
        Driven entirely by `PAGE_SPECIFICATION_TUPLE`, so adding a
        screen is one row rather than an edit in three places.

    Arguments:
        None.

    Returns:
        Dict: Section name mapped to its pages, in order.

    Warning:
        Imports the page modules here rather than at module scope,
        which keeps the import graph acyclic - pages import shared
        state, and this imports pages.
    """
    from importlib import import_module

    _PAGE_PAIR_LIST.clear()
    navigation_dict: dict = {}
    for index_int, specification in enumerate(
        PAGE_SPECIFICATION_TUPLE
    ):
        section_str, module_name_str, title_str, icon_str = (
            specification
        )
        module = import_module(
            f"investment_journey_simulator.pages.{module_name_str}"
        )
        page = st.Page(
            module.render,
            title=title_str,
            icon=icon_str,
            url_path=module_name_str,
            default=index_int == 0,
        )
        _PAGE_PAIR_LIST.append((module_name_str, page))
        navigation_dict.setdefault(section_str, []).append(page)
    return navigation_dict


def register_navigation() -> None:
    """Publish the pages so screens can link to one another.

    Brief:
        Runs *after* `st.navigation` has been handed the tree, not
        before. A page object is not linkable until navigation has
        bound it, so registering at construction time publishes
        pages that raise the moment anything links to them.

    Arguments:
        None.

    Returns:
        None: Every page is registered under its module name.

    Warning:
        Keys on the module name recorded at build time, never on
        `page.url_path`. Streamlit reports the *default* page's url
        path as an empty string, so keying on it silently filed
        Home under "" and left the one page every other screen
        wants to link back to unreachable.
    """
    for module_name_str, page in _PAGE_PAIR_LIST:
        register_page(module_name_str, page)


def main() -> None:
    """Run the portal.

    Brief:
        Configures the page, renders the shared sidebar, then hands
        control to whichever page the reader has chosen.

    Arguments:
        None.

    Returns:
        None: The chosen page renders itself.

    Warning:
        The sidebar is rendered before the page so that a page can
        rely on the mode and the scenario already being resolved.
        The chrome goes in before either, or the first paint of
        every screen is unstyled.
    """
    configure_page()
    install_chrome()
    with st.sidebar:
        render_brand_mark(PORTAL_TITLE_STR, CONSOLE_TAGLINE_STR)
    render_mode_picker()
    render_scenario_summary()
    render_sidebar_footer()
    navigation = st.navigation(build_navigation_dict())
    register_navigation()
    navigation.run()


def launch() -> None:
    """Start the portal from an installed copy.

    Brief:
        Backs the `investment-journey` console command, so a user
        who ran `pip install` has a way in that does not require
        knowing where the launcher file ended up.

    Arguments:
        None.

    Returns:
        None: Control passes to Streamlit, which does not return
            until the server stops.

    Warning:
        Rewrites `sys.argv`, because Streamlit's command line is
        the only supported way to start a server. Do not call this
        from inside a running Streamlit session - it would try to
        start a second one.
    """
    from pathlib import Path

    from streamlit.web import cli as streamlit_cli

    entry_file_path = (
        Path(__file__).resolve().parent / "_app_entry.py"
    )
    sys.argv = ["streamlit", "run", str(entry_file_path)]
    streamlit_cli.main()
