"""Opening tax values for the asset classes a reader may name.

The engine has never cared what an asset is called. A row can be a
mutual fund, a stock, gold, land, a deposit or a business, and the
engine applies whatever return and tax treatment that row carries.

What a preset buys is not new machinery - it is *somewhere sensible
to start*, so a reader modelling land does not have to look up four
numbers before seeing a curve.

## The honesty this module has to carry

`docs/SOURCES.md` verifies the equity and debt treatments against
the Act, by section, with a date. **It does not cover gold,
property or deposits.** Presenting invented figures for those
alongside sourced ones, with nothing to tell them apart, would be
worse than offering no preset at all.

So each preset states whether it is sourced. `regimes.py` draws the
same line between the one tax regime modelled in full and the rest,
for the same reason: a limit is only honest if a reader can see it.
"""

from __future__ import annotations

from dataclasses import dataclass

from investment_journey_simulator.constants import (
    DEBT_EXEMPTION_AMOUNT_FLOAT,
    DEBT_EXEMPTION_SCOPE_STR,
    DEBT_LONG_TERM_MONTHS_INT,
    DEBT_LONG_TERM_PERCENT_FLOAT,
    EQUITY_EXEMPTION_AMOUNT_FLOAT,
    EQUITY_EXEMPTION_SCOPE_STR,
    EQUITY_LONG_TERM_MONTHS_INT,
    EQUITY_LONG_TERM_PERCENT_FLOAT,
    EQUITY_SHORT_TERM_PERCENT_FLOAT,
    EXEMPTION_SCOPE_TOTAL_GAINS_STR,
    PRESET_CUSTOM_STR,
    PRESET_DEBT_STR,
    PRESET_EQUITY_STR,
)

# Short-term rate sentinel meaning "charge at the reader's own
# income slab", which the fund builder substitutes at read time.
USE_SLAB_RATE_FLOAT: float = -1.0

PRESET_STOCK_STR: str = "Listed shares"
PRESET_GOLD_STR: str = "Gold or similar asset"
PRESET_PROPERTY_STR: str = "Property or land"
PRESET_DEPOSIT_STR: str = "Deposit or interest income"

NON_FINANCIAL_LONG_TERM_MONTHS_INT: int = 24
NON_FINANCIAL_LONG_TERM_PERCENT_FLOAT: float = 12.5

UNSOURCED_NOTICE_STR: str = (
    "Opening values only - not verified against the Act the way "
    "the fund treatments are. Check them against your own "
    "position before trusting a tax figure."
)


@dataclass(frozen=True)
class AssetPreset:
    """One asset class, as a set of opening tax values."""

    name_str: str
    short_term_percent_float: float
    long_term_percent_float: float
    long_term_months_int: int
    exemption_amount_float: float
    exemption_scope_str: str
    is_always_short_term_bool: bool = False
    is_sourced_bool: bool = False
    note_str: str = ""

    @property
    def label_str(self) -> str:
        """How this preset is offered in the menu."""
        if self.is_sourced_bool:
            return self.name_str
        return f"{self.name_str} (opening values)"


ASSET_PRESET_TUPLE: tuple = (
    AssetPreset(
        name_str=PRESET_EQUITY_STR,
        short_term_percent_float=EQUITY_SHORT_TERM_PERCENT_FLOAT,
        long_term_percent_float=EQUITY_LONG_TERM_PERCENT_FLOAT,
        long_term_months_int=EQUITY_LONG_TERM_MONTHS_INT,
        exemption_amount_float=EQUITY_EXEMPTION_AMOUNT_FLOAT,
        exemption_scope_str=EQUITY_EXEMPTION_SCOPE_STR,
        is_sourced_bool=True,
        note_str=(
            "Sections 111A and 112A, verified and dated in "
            "docs/SOURCES.md."
        ),
    ),
    AssetPreset(
        name_str=PRESET_DEBT_STR,
        short_term_percent_float=USE_SLAB_RATE_FLOAT,
        long_term_percent_float=DEBT_LONG_TERM_PERCENT_FLOAT,
        long_term_months_int=DEBT_LONG_TERM_MONTHS_INT,
        exemption_amount_float=DEBT_EXEMPTION_AMOUNT_FLOAT,
        exemption_scope_str=DEBT_EXEMPTION_SCOPE_STR,
        is_always_short_term_bool=True,
        is_sourced_bool=True,
        note_str=(
            "Section 50AA: taxed at your slab whatever the holding "
            "period. Verified in docs/SOURCES.md."
        ),
    ),
    AssetPreset(
        name_str=PRESET_STOCK_STR,
        short_term_percent_float=EQUITY_SHORT_TERM_PERCENT_FLOAT,
        long_term_percent_float=EQUITY_LONG_TERM_PERCENT_FLOAT,
        long_term_months_int=EQUITY_LONG_TERM_MONTHS_INT,
        exemption_amount_float=EQUITY_EXEMPTION_AMOUNT_FLOAT,
        exemption_scope_str=EQUITY_EXEMPTION_SCOPE_STR,
        is_sourced_bool=True,
        note_str=(
            "Listed shares fall under the same sections as an "
            "equity fund, so this carries the same verified rates."
        ),
    ),
    AssetPreset(
        name_str=PRESET_GOLD_STR,
        short_term_percent_float=USE_SLAB_RATE_FLOAT,
        long_term_percent_float=(
            NON_FINANCIAL_LONG_TERM_PERCENT_FLOAT
        ),
        long_term_months_int=NON_FINANCIAL_LONG_TERM_MONTHS_INT,
        exemption_amount_float=0.0,
        exemption_scope_str=EXEMPTION_SCOPE_TOTAL_GAINS_STR,
        note_str=UNSOURCED_NOTICE_STR,
    ),
    AssetPreset(
        name_str=PRESET_PROPERTY_STR,
        short_term_percent_float=USE_SLAB_RATE_FLOAT,
        long_term_percent_float=(
            NON_FINANCIAL_LONG_TERM_PERCENT_FLOAT
        ),
        long_term_months_int=NON_FINANCIAL_LONG_TERM_MONTHS_INT,
        exemption_amount_float=0.0,
        exemption_scope_str=EXEMPTION_SCOPE_TOTAL_GAINS_STR,
        note_str=UNSOURCED_NOTICE_STR,
    ),
    AssetPreset(
        name_str=PRESET_DEPOSIT_STR,
        short_term_percent_float=USE_SLAB_RATE_FLOAT,
        long_term_percent_float=0.0,
        long_term_months_int=DEBT_LONG_TERM_MONTHS_INT,
        exemption_amount_float=0.0,
        exemption_scope_str=EXEMPTION_SCOPE_TOTAL_GAINS_STR,
        is_always_short_term_bool=True,
        note_str=UNSOURCED_NOTICE_STR,
    ),
)

PRESET_BY_NAME_DICT: dict[str, AssetPreset] = {
    preset.name_str: preset for preset in ASSET_PRESET_TUPLE
}

# Custom is deliberately absent from the table above: it means
# "leave every tax column exactly as typed", which is the absence
# of a preset rather than another one.
ALL_PRESET_NAME_TUPLE: tuple = tuple(
    [preset.name_str for preset in ASSET_PRESET_TUPLE]
    + [PRESET_CUSTOM_STR]
)


def resolve_preset(name_str: str) -> AssetPreset | None:
    """Find the preset of that name, if there is one.

    Brief:
        Returns None for Custom and for anything unrecognised,
        which the caller reads as "leave the row's tax columns
        alone".

    Arguments:
        name_str (str): Preset name from the editor.

    Returns:
        Optional[AssetPreset]: The preset, or None.

    Warning:
        An unknown name is treated as Custom rather than raising,
        so a file saved with a preset this build has dropped still
        opens with its typed rates intact.
    """
    return PRESET_BY_NAME_DICT.get(name_str)


def describe_preset_str(preset: AssetPreset) -> str:
    """One line naming the rates and how far they are trusted."""
    if preset.is_always_short_term_bool:
        rate_str = "taxed at your slab, whatever the holding period"
    else:
        rate_str = (
            f"{preset.long_term_percent_float:g}% above "
            f"{preset.long_term_months_int} months"
        )
    return f"**{rate_str}.** {preset.note_str}"
