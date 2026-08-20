"""Saying which tax rules are modelled, and which are assumed.

The one claim this program must never make by accident is that it
computes another country's capital gains tax. It computes India's,
in full - FIFO lots, the section 112A exemption per taxpayer per
year, surcharge with marginal relief, cess, grandfathering, loss
carry-forward. Everywhere else, choosing a country fills in that
country's headline rates as *opening values the reader can edit*.

`regimes.py` already draws that line with `is_fully_modelled_bool`.
This module is how the interface says it out loud, at the point the
choice is made rather than in a footnote nobody reads.

It is also what lets the product be described as global honestly:
the simulator is, the tax engine is India-deep and elsewhere
approximate, and both halves of that sentence are visible on screen.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.regimes import TaxRegime, describe_regime_str

MODELLED_HEADING_STR: str = "These tax rules are modelled in full"
APPROXIMATE_HEADING_STR: str = (
    "These tax rules are opening values, not a tax engine"
)
APPROXIMATE_BODY_STR: str = (
    "Choosing this country fills in its published headline rates "
    "so you have somewhere sensible to start. It does **not** "
    "teach this program that country's tax code: no local "
    "allowances, bands, reliefs or loss rules are applied, and "
    "every rate here is one you can and should edit.\n\n"
    "Treat the tax figures as *your assumptions, applied "
    "consistently* - which is still useful - rather than as a "
    "calculation of what you would owe."
)
MODELLED_BODY_STR: str = (
    "FIFO lots, the annual exemption applied per taxpayer rather "
    "than per fund, surcharge with marginal relief, cess on tax "
    "plus surcharge, grandfathering to 31 January 2018, and loss "
    "carry-forward are all applied. Every statutory parameter is "
    "sourced and dated in `docs/SOURCES.md`."
)


def render_regime_notice(regime: TaxRegime) -> None:
    """State how deeply this regime is actually modelled.

    Brief:
        Rendered wherever a tax figure is shown or a regime is
        chosen. Deliberately not an expander for the approximate
        case: a reader must not be able to miss it.

    Arguments:
        regime (TaxRegime): Regime currently in force.

    Returns:
        None: The notice is rendered.

    Warning:
        The fully-modelled case is quieter on purpose. Repeating a
        reassurance as loudly as a caveat trains readers to skip
        both.
    """
    if regime.is_fully_modelled_bool:
        with st.expander(MODELLED_HEADING_STR, expanded=False):
            st.markdown(describe_regime_str(regime))
            st.markdown(MODELLED_BODY_STR)
        return
    st.warning(
        f"**{APPROXIMATE_HEADING_STR}**\n\n"
        f"{describe_regime_str(regime)}\n\n"
        f"{APPROXIMATE_BODY_STR}"
    )


def render_sidebar_regime_line(scenario: PlanScenario) -> None:
    """Name the regime in the sidebar, on every page.

    Brief:
        A one-line reminder of which rules are in force, so a
        reader four screens deep never assumes the wrong ones.

    Arguments:
        scenario (PlanScenario): Scenario being displayed.

    Returns:
        None: The line is written into the sidebar.

    Warning:
        Marks the approximate case explicitly rather than leaving
        the absence of a mark to carry the meaning.
    """
    regime = scenario.presentation.regime
    if regime.is_fully_modelled_bool:
        st.sidebar.caption(f"Tax: {regime.name_str} - modelled")
        return
    st.sidebar.caption(
        f"Tax: {regime.name_str} - approximate, editable"
    )
