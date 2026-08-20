"""Detecting which theme the viewer is actually looking at.

Streamlit lets a page declare a light and a dark theme, but it
applies only the *config* colours automatically. Anything drawn
inside a Plotly figure is coloured by this package, so the figures
have to be told which surface they are landing on.

This lives in the UI layer on purpose: `charts.py` and `palette.py`
stay free of any Streamlit import, so they remain testable and
reusable outside the dashboard.
"""

from __future__ import annotations

import streamlit as st

DARK_THEME_NAME_STR: str = "dark"


def is_dark_mode_bool() -> bool:
    """Report whether the page is currently rendering dark.

    Brief:
        Reads the browser-reported theme. The attribute is absent
        in some contexts, notably the headless test runner and
        older Streamlit builds, so every failure path resolves to
        light rather than raising.

    Arguments:
        None.

    Returns:
        bool: True when the viewer is in dark mode.

    Warning:
        Falling back to light is the safe default: the light
        palette is validated against a light surface, and being
        wrong about the theme costs contrast, not correctness.
    """
    try:
        theme_object = st.context.theme
    except Exception:  # noqa: BLE001
        return False
    theme_type_str = getattr(theme_object, "type", None)
    return str(theme_type_str).lower() == DARK_THEME_NAME_STR


def apply_page_figure_theme(figure):
    """Put a data figure on the same surface as the page.

    Brief:
        `plotly_white` is a white card. On the vellum canvas that is
        very nearly right and on the dark canvas it is a white box
        floating on a dark page, which is the same class of mistake
        as the rail drawing pale ink on a pale page - a figure that
        decided its own surface without asking what it was landing
        on.

        This states the surface instead. Data figures follow the
        page, because the fund colours in `palette.py` are validated
        against the page canvas and nothing else. The timeline and
        the Gantt deliberately do NOT go through here: they carry
        their own instrument panel, and no data series is ever drawn
        on it.

    Arguments:
        figure: A Plotly figure, modified in place.

    Returns:
        The same figure, so this can wrap a build call.

    Warning:
        Being wrong about the theme costs a figure drawn on the
        other canvas, which is ugly and still readable, because the
        template and the surface move together. It can never
        produce ink the colour of its own paper.
    """
    from investment_journey_simulator.design_tokens import (
        FONT_STACK_STR,
        resolve_chrome,
    )

    chrome = resolve_chrome(is_dark_mode_bool())
    figure.update_layout(
        template=(
            "plotly_dark" if chrome.is_dark_bool else "plotly_white"
        ),
        paper_bgcolor=chrome.app_canvas_str,
        plot_bgcolor=chrome.app_canvas_str,
        font=dict(color=chrome.ink_str, family=FONT_STACK_STR),
    )
    return figure
