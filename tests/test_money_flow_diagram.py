"""Money-flow diagram tests.

The predecessor of these diagrams shipped with five of its six icons
rendered as empty boxes, because it used `¤ ▣ ◇ ▥` as icons and no
common sans font carries them. Nobody noticed until the PNG was
opened. That is the class of bug these tests exist to make
impossible: a diagram that parses, that draws its marks rather than
typing them, and that keeps each of the three views to the job it
was separated out to do.
"""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest

from investment_journey_simulator.diagrams.money_flow import (
    DIAGRAM_BUILDER_DICT,
    FOREIGN_CURRENCY_STR,
    HIGH_LEVEL_STAGE_TUPLE,
    RUPEE_STR,
    WORKED_STAGE_TUPLE,
    build_detailed_svg_str,
    build_high_level_svg_str,
    build_worked_example_svg_str,
)
from investment_journey_simulator.diagrams.svg_kit import (
    ICON_BUILDER_DICT,
    icon_mark_str,
)

# Blocks whose glyphs are missing from most UI sans fonts. A
# character from any of these is how the previous diagram ended up
# full of tofu boxes.
UNSAFE_RANGE_TUPLE: tuple = (
    (0x2190, 0x21FF),  # arrows
    (0x25A0, 0x25FF),  # geometric shapes
    (0x2600, 0x26FF),  # miscellaneous symbols
    (0x2700, 0x27BF),  # dingbats
    (0x2B00, 0x2BFF),  # miscellaneous symbols and arrows
)
# The generic currency sign, which the old diagram used to mean
# "some currency" and which renders as a box almost everywhere.
UNSAFE_CHARACTER_TUPLE: tuple = ("¤",)

BUILDER_TUPLE: tuple = tuple(DIAGRAM_BUILDER_DICT.items())
THEME_TUPLE: tuple = ((False, "light"), (True, "dark"))

CASE_TUPLE: tuple = tuple(
    (name_str, builder, is_dark_bool)
    for name_str, builder in BUILDER_TUPLE
    for is_dark_bool, _label in THEME_TUPLE
)
CASE_ID_TUPLE: tuple = tuple(
    f"{name_str}-{label_str}"
    for name_str, _builder in BUILDER_TUPLE
    for _is_dark, label_str in THEME_TUPLE
)


def is_unsafe_bool(character_str: str) -> bool:
    """Whether one character is likely to render as a box."""
    if character_str in UNSAFE_CHARACTER_TUPLE:
        return True
    point_int = ord(character_str)
    return any(
        low_int <= point_int <= high_int
        for low_int, high_int in UNSAFE_RANGE_TUPLE
    )


@pytest.mark.parametrize(
    ("name_str", "builder", "is_dark_bool"),
    CASE_TUPLE,
    ids=CASE_ID_TUPLE,
)
def test_every_diagram_is_well_formed(
    name_str, builder, is_dark_bool
):
    """It parses as XML, in both themes."""
    svg_str = builder(is_dark_bool)
    minidom.parseString(svg_str)
    assert svg_str.startswith("<svg")
    assert svg_str.endswith("</svg>")


@pytest.mark.parametrize(
    ("name_str", "builder", "is_dark_bool"),
    CASE_TUPLE,
    ids=CASE_ID_TUPLE,
)
def test_no_diagram_types_an_icon_it_should_have_drawn(
    name_str, builder, is_dark_bool
):
    """No glyph from a block a UI font is likely to be missing.

    Currency symbols are deliberately allowed: the rupee, yen,
    dollar and euro signs are carried by every mainstream UI font,
    and they are the one place a symbol says more than a word.
    """
    svg_str = builder(is_dark_bool)
    found_list = sorted(
        {
            character_str
            for character_str in svg_str
            if is_unsafe_bool(character_str)
        }
    )
    assert found_list == [], (
        f"{name_str} contains {found_list}, which most sans fonts "
        "render as empty boxes. Draw the mark instead."
    )


def test_every_icon_is_stroked_geometry():
    """Icons are paths and primitives, never text."""
    for name_str in ICON_BUILDER_DICT:
        mark_str = icon_mark_str(name_str, 0, 0, "#000000")
        assert "<text" not in mark_str, (
            f"icon {name_str!r} draws a text element"
        )
        assert any(
            tag_str in mark_str
            for tag_str in ("<path", "<line", "<circle", "<ellipse")
        )


def test_an_unknown_icon_raises_rather_than_drawing_nothing():
    """A missing icon must fail loudly, not leave a hole."""
    with pytest.raises(KeyError):
        icon_mark_str("no-such-icon", 0, 0, "#000000")


def test_the_generic_diagrams_name_no_country_of_origin():
    """The high-level and detail views must travel.

    They describe an NRI's route into Indian assets, so India is
    named. Where the reader happens to live is not, or the diagram
    stops being true for anyone outside one country.
    """
    for svg_str in (
        build_high_level_svg_str(),
        build_detailed_svg_str(),
    ):
        lowered_str = svg_str.lower()
        for banned_str in ("japan", "jpy", "yen"):
            assert banned_str not in lowered_str, (
                f"the generic diagram names {banned_str!r}"
            )


def test_the_worked_example_is_concrete_where_it_should_be():
    """It names a country and a currency, because that is its job."""
    svg_str = build_worked_example_svg_str()
    assert "Japan" in svg_str
    assert RUPEE_STR in svg_str


def test_the_generic_flow_crosses_exactly_one_border():
    """One conversion, and it is drawn where the border is.

    The territory band is the whole conceptual argument of the
    redesign, so the stage list has to keep agreeing with it:
    everything before the crossing is in a foreign currency, and
    everything after it is in rupees.
    """
    currency_list = [
        stage.currency_str for stage in HIGH_LEVEL_STAGE_TUPLE
    ]
    crossing_int = currency_list.index("converted here")
    assert all(
        currency_str == FOREIGN_CURRENCY_STR
        for currency_str in currency_list[:crossing_int]
    )
    assert all(
        currency_str == RUPEE_STR
        for currency_str in currency_list[crossing_int + 1 :]
    )
    assert currency_list.count("converted here") == 1


def test_the_worked_example_ends_in_rupees():
    """Its last stage before the routes is a rupee account."""
    assert WORKED_STAGE_TUPLE[-1].currency_str == RUPEE_STR


@pytest.mark.parametrize(
    ("name_str", "builder", "is_dark_bool"),
    CASE_TUPLE,
    ids=CASE_ID_TUPLE,
)
def test_no_diagram_draws_a_drop_shadow(
    name_str, builder, is_dark_bool
):
    """Depth comes from a hairline and a change of surface.

    A soft shadow under every card is the most reliable single tell
    of generated design, and this system does not use one.
    """
    svg_str = builder(is_dark_bool)
    assert "feDropShadow" not in svg_str
    assert "filter=" not in svg_str


def test_the_two_themes_differ():
    """Dark mode is a separate drawing, not the same one."""
    assert build_high_level_svg_str(False) != (
        build_high_level_svg_str(True)
    )
