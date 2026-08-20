"""Putting the money-flow diagrams on a Streamlit page.

Thin on purpose. Everything about how the diagrams *look* lives in
`diagrams/money_flow.py`, which imports no Streamlit and can be
rendered to a file by `tools/render_diagrams.py`. This module knows
only two things Streamlit-specific: which theme the reader is on, and
how to get an SVG into a page without it being sanitised away.
"""

from __future__ import annotations

import base64

import streamlit as st

from investment_journey_simulator.diagrams.money_flow import (
    build_detailed_svg_str,
    build_high_level_svg_str,
    build_worked_example_svg_str,
)
from investment_journey_simulator.ui.theme import is_dark_mode_bool

HIGH_LEVEL_CAPTION_STR: str = (
    "The shape of the process. Nothing here is specific to a "
    "country you might be living in, or to any provider."
)
DETAILED_CAPTION_STR: str = (
    "The same six steps, opened up at the only two points where "
    "the choice you make changes what you end up holding."
)
WORKED_CAPTION_STR: str = (
    "One person's actual path, step by step. An illustration of a "
    "route that works - not a recommendation."
)


def _svg_image_str(svg_str: str) -> str:
    """Wrap an SVG document as an inline image element.

    Brief:
        Base64 into a data URI rather than dropping the markup
        straight into the page. Streamlit's markdown sanitiser has
        historically stripped raw `<svg>`, and an `<img>` also gives
        the reader the ordinary right-click-and-save behaviour that
        inline markup does not.

    Arguments:
        svg_str (str): A complete SVG document.

    Returns:
        str: An `<img>` element carrying the whole diagram.

    Warning:
        UTF-8 before base64, because the currency symbols in these
        diagrams are outside Latin-1 and a default encode would
        raise on them.
    """
    encoded_str = base64.b64encode(
        svg_str.encode("utf-8")
    ).decode("ascii")
    return (
        "<img alt='Money flow diagram' "
        "style='width:100%;height:auto;display:block' "
        f"src='data:image/svg+xml;base64,{encoded_str}'/>"
    )


def render_diagram(
    svg_str: str,
    caption_str: str,
    download_name_str: str,
) -> None:
    """Draw one diagram, its caption and its download.

    Brief:
        The download is not a nicety. These diagrams answer a
        question people ask their family and their bank, and an SVG
        they can send on is more use than one they can only look at
        inside this app.

    Arguments:
        svg_str (str): The diagram.
        caption_str (str): One sentence on what it is for.
        download_name_str (str): Suggested file name.

    Returns:
        None: The diagram is rendered.
    """
    st.markdown(_svg_image_str(svg_str), unsafe_allow_html=True)
    st.caption(caption_str)
    st.download_button(
        "Download this diagram (SVG)",
        data=svg_str.encode("utf-8"),
        file_name=download_name_str,
        mime="image/svg+xml",
        key=f"download_{download_name_str}",
    )


def render_money_flow_section() -> None:
    """Draw all three views, in the order a reader needs them.

    Brief:
        High level first and always visible; the other two behind
        disclosure. That order is the whole argument of the
        redesign - a reader who has not yet grasped the shape is
        not helped by being shown the exceptions to it, and a
        reader who opens with somebody else's provider list learns
        the provider rather than the process.

    Arguments:
        None.

    Returns:
        None: The section is rendered.

    Warning:
        The worked example must stay collapsed by default. Left
        open it becomes the thing people copy, which is exactly
        what the labelling on it asks them not to do.
    """
    is_dark_bool = is_dark_mode_bool()
    st.subheader("How the money actually moves")
    render_diagram(
        build_high_level_svg_str(is_dark_bool),
        HIGH_LEVEL_CAPTION_STR,
        "money_flow_high_level.svg",
    )
    with st.expander("Open up the two decisions that matter"):
        render_diagram(
            build_detailed_svg_str(is_dark_bool),
            DETAILED_CAPTION_STR,
            "money_flow_detailed.svg",
        )
    with st.expander("See a worked example - Japan to India"):
        st.info(
            "**This is one person's setup, not a recommendation.** "
            "Steps are described by what they do rather than by "
            "who provides them, so the route transfers to whatever "
            "bank and platform you end up using."
        )
        render_diagram(
            build_worked_example_svg_str(is_dark_bool),
            WORKED_CAPTION_STR,
            "money_flow_worked_example.svg",
        )
