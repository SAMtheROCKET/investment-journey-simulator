"""Starter tax treatments, and the honesty flag on each.

The point of this module is not the rates. It is that a reader can
tell which rates were verified against the Act and which are a
sensible guess - the same line `regimes.py` draws between the one
country modelled in full and the rest.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from investment_journey_simulator.asset_presets import (
    ALL_PRESET_NAME_TUPLE,
    ASSET_PRESET_TUPLE,
    PRESET_DEPOSIT_STR,
    PRESET_GOLD_STR,
    PRESET_PROPERTY_STR,
    PRESET_STOCK_STR,
    USE_SLAB_RATE_FLOAT,
    describe_preset_str,
    resolve_preset,
)
from investment_journey_simulator.constants import (
    COLUMN_LONG_TERM_MONTHS_STR,
    COLUMN_LONG_TERM_TAX_STR,
    COLUMN_OVERRIDE_PRESET_STR,
    COLUMN_PRESET_STR,
    COLUMN_SHORT_TERM_TAX_STR,
    PRESET_CUSTOM_STR,
    PRESET_DEBT_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.fund_builder import (
    apply_tax_preset_to_row,
    build_fund_row_dict,
)

SLAB_RATE_PERCENT_FLOAT: float = 30.0
PLAN_START_DATE: date = date(2026, 1, 1)


def build_row(preset_str: str) -> pd.Series:
    """One editor row carrying the named tax treatment."""
    row_dict = build_fund_row_dict(
        fund_name_str="Test asset",
        monthly_sip_float=1000.0,
        gross_return_percent_float=10.0,
        expense_percent_float=0.5,
        start_date=PLAN_START_DATE,
        target_allocation_percent_float=100.0,
    )
    row_dict[COLUMN_PRESET_STR] = preset_str
    return pd.Series(row_dict)


def apply(preset_str: str) -> pd.Series:
    """Apply one treatment to a row and hand back the result."""
    return apply_tax_preset_to_row(
        build_row(preset_str), SLAB_RATE_PERCENT_FLOAT
    )


# --- The honesty flag ---------------------------------------------


def test_only_the_treatments_sources_covers_claim_to_be_sourced():
    """docs/SOURCES.md verifies funds and shares, nothing else.

    Gold, property and deposits were added as opening values. If
    someone later sources them properly they may flip this flag -
    but flipping it without adding the sourcing would be the one
    change here that actually misleads a reader.
    """
    sourced_set = {
        preset.name_str
        for preset in ASSET_PRESET_TUPLE
        if preset.is_sourced_bool
    }
    assert sourced_set == {
        PRESET_EQUITY_STR,
        PRESET_DEBT_STR,
        PRESET_STOCK_STR,
    }


@pytest.mark.parametrize(
    "preset_str",
    [PRESET_GOLD_STR, PRESET_PROPERTY_STR, PRESET_DEPOSIT_STR],
)
def test_an_unsourced_treatment_says_so_in_its_label(preset_str):
    """The menu itself has to carry the caveat."""
    preset = resolve_preset(preset_str)
    assert preset is not None
    assert "opening values" in preset.label_str


@pytest.mark.parametrize(
    "preset_str", [PRESET_EQUITY_STR, PRESET_STOCK_STR]
)
def test_a_sourced_treatment_does_not(preset_str):
    """Reassurance repeated as loudly as a caveat kills both."""
    preset = resolve_preset(preset_str)
    assert preset is not None
    assert "opening values" not in preset.label_str


def test_every_treatment_explains_itself():
    """A dropdown of bare names teaches nobody anything."""
    for preset in ASSET_PRESET_TUPLE:
        description_str = describe_preset_str(preset)
        assert description_str
        assert preset.note_str in description_str


# --- What the treatments actually do ------------------------------


def test_gold_and_property_use_the_longer_holding_period():
    """Non-financial assets do not share the fund threshold."""
    for preset_str in (PRESET_GOLD_STR, PRESET_PROPERTY_STR):
        row = apply(preset_str)
        assert row[COLUMN_LONG_TERM_MONTHS_STR] == 24
        assert row[COLUMN_LONG_TERM_TAX_STR] == 12.5


def test_slab_taxed_treatments_pick_up_the_readers_own_rate():
    """The sentinel must resolve, not reach the engine as -1."""
    for preset_str in (
        PRESET_DEBT_STR,
        PRESET_GOLD_STR,
        PRESET_DEPOSIT_STR,
    ):
        row = apply(preset_str)
        assert (
            row[COLUMN_SHORT_TERM_TAX_STR]
            == SLAB_RATE_PERCENT_FLOAT
        )


def test_the_sentinel_never_reaches_a_row():
    """A negative tax rate would silently pay the reader."""
    for preset in ASSET_PRESET_TUPLE:
        row = apply(preset.name_str)
        assert (
            row[COLUMN_SHORT_TERM_TAX_STR] != USE_SLAB_RATE_FLOAT
        )
        assert row[COLUMN_SHORT_TERM_TAX_STR] >= 0.0


def test_listed_shares_match_the_fund_treatment():
    """They fall under the same sections, so they must agree."""
    share_row = apply(PRESET_STOCK_STR)
    fund_row = apply(PRESET_EQUITY_STR)
    for column_str in (
        COLUMN_SHORT_TERM_TAX_STR,
        COLUMN_LONG_TERM_TAX_STR,
        COLUMN_LONG_TERM_MONTHS_STR,
    ):
        assert share_row[column_str] == fund_row[column_str]


def test_a_deposit_is_always_short_term():
    """Interest does not become long-term by waiting."""
    preset = resolve_preset(PRESET_DEPOSIT_STR)
    assert preset is not None
    assert preset.is_always_short_term_bool is True


# --- Custom and the unknown ---------------------------------------


def test_custom_leaves_every_typed_rate_alone():
    """Custom is the absence of a preset, not another one."""
    row = build_row(PRESET_CUSTOM_STR)
    row[COLUMN_SHORT_TERM_TAX_STR] = 7.5
    applied = apply_tax_preset_to_row(
        row, SLAB_RATE_PERCENT_FLOAT
    )
    assert applied[COLUMN_SHORT_TERM_TAX_STR] == 7.5


def test_an_unknown_treatment_is_treated_as_custom():
    """A file saved with a dropped preset still opens intact."""
    row = build_row("Something this build has never heard of")
    row[COLUMN_SHORT_TERM_TAX_STR] = 7.5
    applied = apply_tax_preset_to_row(
        row, SLAB_RATE_PERCENT_FLOAT
    )
    assert applied[COLUMN_SHORT_TERM_TAX_STR] == 7.5


def test_the_override_flag_still_wins():
    """An expert who typed a rate keeps it."""
    row = build_row(PRESET_DEBT_STR)
    row[COLUMN_OVERRIDE_PRESET_STR] = True
    row[COLUMN_SHORT_TERM_TAX_STR] = 1.25
    applied = apply_tax_preset_to_row(
        row, SLAB_RATE_PERCENT_FLOAT
    )
    assert applied[COLUMN_SHORT_TERM_TAX_STR] == 1.25


# --- The menu -----------------------------------------------------


def test_the_menu_offers_every_treatment_and_custom():
    """Nothing defined here may be unreachable from the editor."""
    assert set(ALL_PRESET_NAME_TUPLE) == {
        preset.name_str for preset in ASSET_PRESET_TUPLE
    } | {PRESET_CUSTOM_STR}


def test_the_original_two_treatments_keep_their_exact_names():
    """Renaming one would orphan every file that used it.

    The preset name is stored *as a value* inside a saved plan.
    The column-alias map in the migration renames columns, not
    values, so these strings are load-bearing.
    """
    assert PRESET_EQUITY_STR == "Equity-Oriented (Default)"
    assert PRESET_DEBT_STR == "Debt (post Apr 1, 2023) - slab"
    assert PRESET_CUSTOM_STR == "Custom"
