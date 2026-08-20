"""Guides: getting started, and the paperwork nobody warns you about.

The content is markdown rather than Python for one deliberate
reason: the same words go into the repository README, the LinkedIn
post and the Reddit post. Written once, rendered everywhere, and
never drifting between copies.

It ships *inside the package* and is read through
`importlib.resources`. It used to be read from `docs/guides/` by
walking up three parents from this file, which is the repository
when run from a clone and nothing at all when run from an installed
wheel - so this page rendered three empty tabs and an apology to
anyone who had pip-installed the tool.
"""

from __future__ import annotations

from importlib import resources

import streamlit as st

from investment_journey_simulator.pages.page_shell import open_page
from investment_journey_simulator.ui.money_flow_view import (
    render_money_flow_section,
)

TITLE_STR: str = "Guides"

# The diagram tab leads, because the question underneath every one
# of these guides is the same one and it is spatial: where is my
# money right now, and what does it have to pass through next. A
# reader who can see that answers half the checklist themselves.
MONEY_FLOW_TAB_STR: str = "How the money moves"
LEAD_STR: str = (
    "The simulator answers what your money could become. These "
    "answer what you actually have to do first."
)

GUIDE_PACKAGE_STR: str = "investment_journey_simulator.guides"

GUIDE_SPECIFICATION_TUPLE: tuple = (
    (
        "Starting investments",
        "starting_investments.md",
        "Wherever you live. The order that saves months.",
    ),
    (
        "India resident checklist",
        "india_resident.md",
        "PAN, KYC, mandates, and the mismatches that block them.",
    ),
    (
        "NRI investment checklist",
        "nri_investment.md",
        "NRE and NRO, embassy attestation, and updating your "
        "status everywhere before it blocks a redemption.",
    ),
)

MISSING_GUIDE_MESSAGE_STR: str = (
    "This guide is not bundled with this build, which is a "
    "packaging fault rather than anything you did. The text is in "
    "`src/investment_journey_simulator/guides/` in the repository."
)


def read_guide_str(file_name_str: str) -> str:
    """Read one guide off disk.

    Brief:
        Returns a plain message rather than raising when a guide is
        missing, so a packaging mistake costs one tab rather than
        the whole page.

    Arguments:
        file_name_str (str): Guide file to read.

    Returns:
        str: The guide's markdown, or an explanation.

    Warning:
        Read on every rerun. The files are small and reading them
        fresh means an edit shows up without restarting.
    """
    try:
        return (
            resources.files(GUIDE_PACKAGE_STR)
            .joinpath(file_name_str)
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return MISSING_GUIDE_MESSAGE_STR


def render_disclaimer() -> None:
    """State what these are and are not, once, at the top."""
    st.info(
        "**These are maps of a process, not advice.** Rules, "
        "thresholds and institutional requirements change, "
        "sometimes annually. Confirm anything you are about to "
        "act on with the institution involved or a qualified "
        "professional."
    )


def render() -> None:
    """Render the Guides page."""
    open_page(TITLE_STR, LEAD_STR)
    render_disclaimer()
    label_list = [MONEY_FLOW_TAB_STR]
    label_list.extend(
        title_str
        for title_str, _file, _summary in GUIDE_SPECIFICATION_TUPLE
    )
    tab_list = st.tabs(label_list)
    with tab_list[0]:
        render_money_flow_section()
    for tab, specification in zip(
        tab_list[1:], GUIDE_SPECIFICATION_TUPLE, strict=True
    ):
        _title_str, file_name_str, summary_str = specification
        with tab:
            st.caption(summary_str)
            st.markdown(read_guide_str(file_name_str))
