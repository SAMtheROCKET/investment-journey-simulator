"""Letting one screen hand a reader to another.

Every screen in this portal used to end by naming the next one in
prose - "set a monthly amount on Quick Projection, then come back".
That is a dead end dressed as guidance: the reader has to find the
screen in the rail themselves, and worse, an *action* on one screen
could not finish its job on another. "Apply this to my plan" had
nowhere to go.

Streamlit's `st.switch_page` and `st.page_link` both want the
`st.Page` object, which only exists inside `portal_app`'s navigation
build. Rather than have nine pages import the portal - which is the
cycle `portal_app` deliberately avoids by importing pages lazily -
the navigation build *registers* its pages here, and pages read them
back by module name.

The registry is empty under a bare `AppTest` that renders one page in
isolation, which is exactly when a link cannot work anyway. Every
reader here tolerates that rather than raising: a missing link
should cost a link, not the screen it was on.
"""

from __future__ import annotations

from typing import Any

# Module name -> the st.Page that renders it. Keys are the module
# names in `portal_app.PAGE_SPECIFICATION_TUPLE`, so a page refers
# to its neighbour by the same name the navigation tree uses.
_PAGE_REGISTRY_DICT: dict = {}

QUICK_PAGE_STR: str = "quick_page"
GUIDED_PAGE_STR: str = "guided_page"
ADVANCED_PAGE_STR: str = "advanced_page"
COMPARE_PAGE_STR: str = "compare_page"
GOAL_PAGE_STR: str = "goal_page"
RISK_PAGE_STR: str = "risk_page"
REBALANCING_PAGE_STR: str = "rebalancing_page"
REPORTS_PAGE_STR: str = "reports_page"
GUIDES_PAGE_STR: str = "guides_page"


def register_page(module_name_str: str, page: Any) -> None:
    """Record the page object that renders one module.

    Brief:
        Called once per page by the navigation build, before any
        page runs.

    Arguments:
        module_name_str (str): Module name, as in the nav tree.
        page (Any): The `st.Page` object.

    Returns:
        None: The page is registered.

    Warning:
        Registering the same name twice replaces the entry. That
        is what a rerun does, and it is harmless.
    """
    _PAGE_REGISTRY_DICT[module_name_str] = page


def resolve_page(module_name_str: str) -> Any:
    """Find the page object for one module, if there is one.

    Arguments:
        module_name_str (str): Module name to look up.

    Returns:
        Any: The `st.Page`, or None when nothing is registered.

    Warning:
        Returns None rather than raising. A page rendered outside
        the portal - which is how the test suite renders them -
        has no navigation, and that must not be an error.
    """
    return _PAGE_REGISTRY_DICT.get(module_name_str)


def clear_registry() -> None:
    """Forget every registered page.

    Brief:
        For tests that need to assert the graceful path when no
        navigation exists.
    """
    _PAGE_REGISTRY_DICT.clear()
