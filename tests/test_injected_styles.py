"""No module may decide what colour the page is.

Three separate bugs in this project came from the same habit: a
stylesheet that fixed a colour, and a surface that turned out not to
be the one it was written for.

    - the chrome picked its tokens from a guess about the theme
    - the console inherited the page's tokens onto a dark rail
    - the timeline page force-painted `.stApp` dark and lifted every
      label to a pale ink, while Streamlit kept drawing its buttons
      on the light theme's white

The last one is the clearest: the forced rule reached the button's
*label* but not its *background*, so the label went pale and the
button stayed white. Pale text on a white pill, on a page that had
been painted dark by the same stylesheet.

The rule that prevents all three is one line long: **a colour in an
injected stylesheet must be derived from `currentColor`, or be a
pigment mixed toward it.** Then a rule cannot be written for the
wrong surface, because it does not name a surface at all.

This scans every style block the application injects and holds that
rule. It reads the modules as text rather than importing them,
because several need a Streamlit runtime to import.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent
SOURCE_PATH: Path = (
    PROJECT_ROOT_PATH / "src" / "investment_journey_simulator"
)

# Properties that decide what a reader can or cannot see. A fixed
# value on any of these is a fixed polarity.
COLOUR_PROPERTY_TUPLE: tuple = (
    "color",
    "background",
    "background-color",
    "border-color",
    "border",
    "border-top",
    "border-left",
    "border-right",
    "border-bottom",
    "box-shadow",
    "fill",
    "stroke",
)

# The two pigments the design is allowed to name. Both are always
# mixed toward `currentColor` or toward transparent before use, so
# neither fixes a polarity. Plus the two colours on the brand mark,
# which sit on saturated pigment rather than on the page.
ALLOWED_COLOUR_TUPLE: tuple = (
    "#A9762F",
    "#28887E",
    "#6d4711",
    "#fff7ea",
)

HEX_PATTERN_STR: str = r"#[0-9A-Fa-f]{3,8}\b"
FUNCTIONAL_PATTERN_STR: str = r"\brgba?\s*\(|\bhsla?\s*\("


def collect_style_module_list() -> list[Path]:
    """Every module that injects a stylesheet."""
    return sorted(
        file_path
        for file_path in SOURCE_PATH.rglob("*.py")
        if "__pycache__" not in str(file_path)
        and "<style>" in file_path.read_text(encoding="utf-8")
    )


STYLE_MODULE_LIST: list[Path] = collect_style_module_list()


def extract_style_block_list(text_str: str) -> list[str]:
    """Every `<style>` block in one module."""
    return re.findall(
        r"<style>(.*?)</style>", text_str, flags=re.DOTALL
    )


def test_there_are_style_blocks_to_check():
    """A sweep over nothing would pass for the wrong reason."""
    assert len(STYLE_MODULE_LIST) >= 3


@pytest.mark.parametrize(
    "file_path",
    STYLE_MODULE_LIST,
    ids=lambda path: path.name,
)
def test_no_stylesheet_fixes_a_colour(file_path):
    """Derived, or one of the two named pigments. Nothing else."""
    found_list: list[str] = []
    for block_str in extract_style_block_list(
        file_path.read_text(encoding="utf-8")
    ):
        found_list.extend(
            hex_str
            for hex_str in re.findall(HEX_PATTERN_STR, block_str)
            if hex_str not in ALLOWED_COLOUR_TUPLE
        )
    assert found_list == [], (
        f"{file_path.name} fixes {sorted(set(found_list))} in a "
        "stylesheet. Derive it from currentColor, or mix a pigment "
        "toward currentColor, so it follows the surface it lands on."
    )


@pytest.mark.parametrize(
    "file_path",
    STYLE_MODULE_LIST,
    ids=lambda path: path.name,
)
def test_no_stylesheet_uses_a_fixed_rgba(file_path):
    """The same rule, in the other notation.

    `rgba(148,163,184,.18)` is exactly as fixed as a hex; it was
    how the rail panel's border was written.
    """
    for block_str in extract_style_block_list(
        file_path.read_text(encoding="utf-8")
    ):
        assert not re.search(FUNCTIONAL_PATTERN_STR, block_str), (
            f"{file_path.name} uses a fixed rgb/hsl colour in a "
            "stylesheet. Use color-mix with currentColor instead."
        )


@pytest.mark.parametrize(
    "file_path",
    STYLE_MODULE_LIST,
    ids=lambda path: path.name,
)
def test_no_stylesheet_paints_the_whole_app(file_path):
    """No screen may decide what colour the application is.

    One page painting `.stApp` was what put pale text on white
    buttons: the page went dark, the widgets did not, and the two
    halves of every control disagreed.
    """
    for block_str in extract_style_block_list(
        file_path.read_text(encoding="utf-8")
    ):
        for rule_str in block_str.split("}"):
            if ".stApp" not in rule_str.split("{")[0]:
                continue
            declaration_str = (
                rule_str.split("{")[1]
                if "{" in rule_str
                else ""
            )
            for property_str in ("background", "color"):
                assert f"{property_str}:" not in declaration_str, (
                    f"{file_path.name} sets {property_str} on "
                    ".stApp. The theme owns the page."
                )
