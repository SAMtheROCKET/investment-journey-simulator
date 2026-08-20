"""Furniture every page shares.

Kept in one place so that nine screens cannot drift into nine
slightly different ideas of what a heading, an empty state or a
disclosure looks like.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.page_links import resolve_page
from investment_journey_simulator.plan_modes import resolve_projection
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import (
    read_mode_str,
    read_scenario,
)
from investment_journey_simulator.ui.chrome import (
    render_flash,
    render_kicker,
    render_top_bar,
)
from investment_journey_simulator.ui.mode_banner import (
    render_hidden_settings_banner,
)


def open_page(
    title_str: str,
    lead_str: str,
) -> PlanScenario:
    """Render the top of a page and hand back the scenario.

    Brief:
        Every page starts the same way: a heading, one sentence
        saying what the page is for, and the banner that keeps the
        current mode honest about what it is not showing.

    Arguments:
        title_str (str): Heading of the page.
        lead_str (str): One sentence on what the page answers.

    Returns:
        PlanScenario: The session's scenario, ready to work on.

    Warning:
        Returns the shared object. Pages must write a modified copy
        back through `write_scenario` rather than mutating it.
    """
    scenario = read_scenario()
    mode_str = read_mode_str()
    render_top_bar(title_str, _top_bar_meta_tuple(scenario, mode_str))
    render_kicker(title_str)
    st.title(title_str)
    st.caption(lead_str)
    _render_mode_flash(mode_str)
    render_hidden_settings_banner(scenario, mode_str)
    return scenario


def _render_mode_flash(mode_str: str) -> None:
    """Show what the last detail-level switch revealed.

    Brief:
        Beside the controls that changed rather than beside the
        switch that changed them, and only once - it is taken from
        session state, so it does not reappear on every rerun.

    Arguments:
        mode_str (str): The level now in force.

    Returns:
        None: The flash is rendered, or nothing is.
    """
    from investment_journey_simulator.portal_app import (
        take_mode_flash_str,
    )

    sentence_str = take_mode_flash_str()
    if not sentence_str:
        return
    render_flash(
        sentence_str,
        next_step_str=resolve_projection(mode_str).promise_str,
    )


def _top_bar_meta_tuple(
    scenario: PlanScenario,
    mode_str: str,
) -> tuple:
    """The pills the utility bar shows on the right.

    Brief:
        Plan state first, then the detail level, which is the one
        piece of context that changes what a screen is willing to
        show and is therefore the one most worth keeping visible.

    Arguments:
        scenario (PlanScenario): The plan currently loaded.
        mode_str (str): The reader's chosen detail level.

    Returns:
        Tuple: `(text, is_active)` pairs.
    """
    compiled = compile_scenario(scenario)
    return (
        (scenario.name_str, False),
        (compiled.currency.code_str, False),
        (f"{scenario.plan.horizon_years_int} years", False),
        (resolve_projection(mode_str).label_str, True),
    )


def render_page_link(
    module_name_str: str,
    label_str: str,
    icon_str: str = "",
) -> None:
    """Offer a real way to the screen this one just named.

    Brief:
        Prose telling a reader to "go to Quick Projection" leaves
        them to find it. This puts the door where the sentence is.

    Arguments:
        module_name_str (str): Target page's module name.
        label_str (str): What the link says.
        icon_str (str): Optional leading icon.

    Returns:
        None: The link is rendered, or a caption when the portal
            is not running.

    Warning:
        Falls back to plain text whenever the link cannot be made.
        A page object is only linkable once `st.navigation` has
        bound it, so a page rendered on its own - which is how the
        suite renders every one of them - has no rail to link into.
        That must cost a link, never the screen it was on.
    """
    page = resolve_page(module_name_str)
    if page is None:
        st.caption(f"→ {label_str}")
        return
    try:
        st.page_link(page, label=label_str, icon=icon_str or None)
    except Exception:  # noqa: BLE001
        st.caption(f"→ {label_str}")


def switch_to_page(module_name_str: str) -> None:
    """Send the reader to another screen, now.

    Brief:
        Used after an action has changed the plan, so the reader
        lands where the change is visible rather than being told
        it happened.

    Arguments:
        module_name_str (str): Target page's module name.

    Returns:
        None: Navigation happens, or nothing does.

    Warning:
        Silently does nothing when no navigation is registered.
        Every caller applies its change *before* calling this, so
        a failure to move costs a step and never an edit. That
        ordering is the contract and it is not optional.
    """
    page = resolve_page(module_name_str)
    if page is None:
        return
    try:
        st.switch_page(page)
    except Exception:  # noqa: BLE001
        return


def render_empty_state(
    heading_str: str,
    body_str: str,
    hint_str: str = "",
) -> None:
    """Say what to do next when there is nothing to show yet.

    Brief:
        A blank chart tells a reader nothing. An empty state that
        names the next action tells them everything.

    Arguments:
        heading_str (str): What is missing.
        body_str (str): Why the page needs it.
        hint_str (str): Where to go to supply it.

    Returns:
        None: The empty state is rendered.

    Warning:
        Deliberately not an error. Nothing has gone wrong when a
        plan is new.
    """
    st.info(f"**{heading_str}**\n\n{body_str}")
    if hint_str:
        st.caption(hint_str)


def has_investment_bool(scenario: PlanScenario) -> bool:
    """Whether this plan puts any money in at all.

    Brief:
        The one precondition most pages share. A plan with no
        contribution and no opening lump sum has nothing to show.

    Arguments:
        scenario (PlanScenario): Scenario being inspected.

    Returns:
        bool: True when some money enters the plan.

    Warning:
        Reads both sources, because either the events or the funds
        may own the amounts.
    """
    if scenario.timeline_owns_amounts_bool:
        return bool(scenario.plan.event_list)
    return any(
        fund.monthly_sip_float or fund.initial_investment_float
        for fund in scenario.fund_list
    )
