"""The theme file, checked rather than trusted.

Streamlit sends each theme variant to the browser with its own
`base`, and `base` is only a registerable option inside `[theme]`.
`runtime/app_session.py` says what happens to a variant that does
not state one:

    "If unset, base and font will default to the protobuf enum zero
     values, which are BaseTheme.LIGHT ..."

So `[theme.dark]` arrives claiming to be a light theme, and every
colour it leaves unstated takes a light-theme default. `grayText`
defaults to `#31333f` at 60% - a dark grey - and gets painted on a
dark background. That is text nobody can read until they hover over
it, which is what shipped.

There is no way to set the base per variant, so the only defence is
to leave nothing derived. These tests hold that: every option with a
theme-dependent default must be stated outright, and every pair the
file declares must measure up on the surface it lands on.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from investment_journey_simulator.design_tokens import (
    TEXT_CONTRAST_GATE_FLOAT,
    contrast_ratio_float,
)

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = PROJECT_ROOT_PATH / ".streamlit" / "config.toml"

NON_TEXT_GATE_FLOAT: float = 3.0

# Handled elsewhere and deliberately not stated per variant:
# `base` cannot be, and the chart sets live in `palette.py` because
# they are assigned per trace in code.
DERIVATION_EXEMPT_TUPLE: tuple = (
    "base",
    "chartCategoricalColors",
    "chartSequentialColors",
)

SEMANTIC_FAMILY_TUPLE: tuple = (
    "gray",
    "blue",
    "green",
    "orange",
    "red",
    "violet",
    "yellow",
)


def read_config_dict() -> dict:
    """The theme file, parsed."""
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def read_theme_dict() -> dict:
    """The shared `[theme]` table."""
    return read_config_dict()["theme"]


def read_dark_dict() -> dict:
    """The `[theme.dark]` table."""
    return read_theme_dict()["dark"]


def collect_theme_dependent_name_list() -> list[str]:
    """Every option whose default depends on which theme is active.

    Read from Streamlit itself rather than hardcoded, so a new
    option in a future release is caught the first time the suite
    runs against it.
    """
    from streamlit import config

    name_list: list[str] = []
    for name_str, option in config._config_options_template.items():
        if not name_str.startswith("theme."):
            continue
        if name_str.count(".") != 1:
            continue
        description_str = " ".join(
            (option.description or "").split()
        )
        if (
            "light theme" in description_str
            or "dark theme" in description_str
        ):
            name_list.append(name_str.split(".", 1)[1])
    return sorted(name_list)


def test_the_theme_file_parses():
    """A malformed theme is a blank app."""
    assert "theme" in read_config_dict()


def test_the_dark_variant_leaves_nothing_to_derive():
    """The regression that shipped, in one assertion.

    Anything unstated here inherits a light-theme default and gets
    painted on a dark background.
    """
    dark_dict = read_dark_dict()
    missing_list = [
        name_str
        for name_str in collect_theme_dependent_name_list()
        if name_str not in DERIVATION_EXEMPT_TUPLE
        and name_str not in dark_dict
    ]
    assert missing_list == [], (
        "these have theme-dependent defaults and are not stated in "
        f"[theme.dark], so they will derive as light: {missing_list}"
    )


def test_every_declared_option_is_one_streamlit_accepts():
    """A typo in this file is silently ignored otherwise."""
    from streamlit import config

    valid_set = {
        name_str.split(".", 2)[2]
        for name_str in config._config_options_template
        if name_str.startswith("theme.dark.")
    }
    unknown_list = sorted(set(read_dark_dict()) - valid_set)
    assert unknown_list == [], (
        f"[theme.dark] declares options Streamlit does not know: "
        f"{unknown_list}"
    )


@pytest.mark.parametrize("family_str", SEMANTIC_FAMILY_TUPLE)
def test_each_family_reads_on_its_own_background(family_str):
    """Alerts, badges and code, in the dark variant.

    Each family states a text colour and the background it sits on,
    so the pair has to be checked together rather than each against
    the page.
    """
    dark_dict = read_dark_dict()
    ratio_float = contrast_ratio_float(
        dark_dict[f"{family_str}TextColor"],
        dark_dict[f"{family_str}BackgroundColor"],
    )
    assert ratio_float >= TEXT_CONTRAST_GATE_FLOAT, (
        f"{family_str} text measures {ratio_float:.2f} on its own "
        "background"
    )


@pytest.mark.parametrize("family_str", SEMANTIC_FAMILY_TUPLE)
def test_each_family_colour_shows_against_the_page(family_str):
    """The icon and rule colour, held to the non-text gate."""
    dark_dict = read_dark_dict()
    ratio_float = contrast_ratio_float(
        dark_dict[f"{family_str}Color"],
        dark_dict["backgroundColor"],
    )
    assert ratio_float >= NON_TEXT_GATE_FLOAT, (
        f"{family_str} measures {ratio_float:.2f} on the page"
    )


def test_secondary_text_reads_on_both_dark_surfaces():
    """The exact colour that was invisible.

    Inactive tab labels, captions and helper lines all take the
    grey text colour, on the page and on the secondary surface
    alike.
    """
    dark_dict = read_dark_dict()
    for key_str in (
        "backgroundColor",
        "secondaryBackgroundColor",
    ):
        ratio_float = contrast_ratio_float(
            dark_dict["grayTextColor"], dark_dict[key_str]
        )
        assert ratio_float >= TEXT_CONTRAST_GATE_FLOAT, (
            f"grey text measures {ratio_float:.2f} on {key_str}"
        )


def test_the_main_text_reads_in_both_variants():
    """The pair that decides whether anything is readable at all."""
    theme_dict = read_theme_dict()
    dark_dict = read_dark_dict()
    for label_str, ink_str, page_str in (
        (
            "light",
            theme_dict["textColor"],
            theme_dict["backgroundColor"],
        ),
        (
            "dark",
            dark_dict["textColor"],
            dark_dict["backgroundColor"],
        ),
    ):
        ratio_float = contrast_ratio_float(ink_str, page_str)
        assert ratio_float >= TEXT_CONTRAST_GATE_FLOAT, (
            f"{label_str} text measures {ratio_float:.2f}"
        )


def test_the_console_reads_in_both_variants():
    """The rail keeps one colour scheme whatever the page does."""
    sidebar_dict = read_theme_dict()["sidebar"]
    for key_str in ("textColor", "primaryColor", "linkColor"):
        ratio_float = contrast_ratio_float(
            sidebar_dict[key_str], sidebar_dict["backgroundColor"]
        )
        assert ratio_float >= TEXT_CONTRAST_GATE_FLOAT, (
            f"console {key_str} measures {ratio_float:.2f}"
        )
