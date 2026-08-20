"""The banner that keeps a mode honest about what it is hiding.

Every screen that shows fewer controls than the scenario carries
renders this. It is deliberately unmissable and deliberately not an
error: the hidden settings are working normally, they simply are not
on this screen.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.plan_modes import (
    build_hidden_summary_str,
    describe_hidden_setting_list,
)
from investment_journey_simulator.plan_scenario import PlanScenario

DETAIL_HEADING_STR: str = "What is still running"
EXPERT_HINT_STR: str = (
    "Open **Advanced Simulator** to see and change these."
)


def render_hidden_settings_banner(
    scenario: PlanScenario,
    mode_str: str,
) -> str:
    """Announce any active setting this screen does not show.

    Brief:
        Renders nothing at all when nothing is hidden, so a screen
        can call this unconditionally.

    Arguments:
        scenario (PlanScenario): Scenario being displayed.
        mode_str (str): Mode this screen is running in.

    Returns:
        str: The summary shown, empty when nothing was hidden.

    Warning:
        Uses an informational tone, never a warning one. A reader
        who configured these deliberately has done nothing wrong.
    """
    summary_str = build_hidden_summary_str(scenario, mode_str)
    if not summary_str:
        return ""
    with st.expander(summary_str, expanded=False):
        st.caption(
            "These are part of your plan and are included in every "
            "figure on this page. They are hidden here only to keep "
            "this screen short."
        )
        _render_hidden_detail(scenario, mode_str)
        st.caption(EXPERT_HINT_STR)
    return summary_str


def _render_hidden_detail(
    scenario: PlanScenario,
    mode_str: str,
) -> None:
    """List each hidden setting under the group it belongs to."""
    grouped_dict: dict[str, list[str]] = {}
    for hidden in describe_hidden_setting_list(scenario, mode_str):
        grouped_dict.setdefault(hidden.group_str, []).append(
            hidden.sentence_str
        )
    for group_str, sentence_list in grouped_dict.items():
        st.markdown(f"**{group_str}**")
        for sentence_str in sentence_list:
            st.markdown(f"- {sentence_str}")
