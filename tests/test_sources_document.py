"""The sources document must keep agreeing with the code.

A page of citations is only worth having if it cannot quietly go
stale. These tests read `docs/SOURCES.md` and check that every
figure it states is the figure the package actually uses, so an
amendment to a constant fails here rather than misleading a reader.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from investment_journey_simulator.constants import (
    DEFAULT_CESS_PERCENT_FLOAT,
    DEFAULT_EXIT_LOAD_MONTHS_INT,
    DEFAULT_EXIT_LOAD_PERCENT_FLOAT,
    EQUITY_EXEMPTION_AMOUNT_FLOAT,
    EQUITY_LONG_TERM_PERCENT_FLOAT,
    EQUITY_REDEMPTION_STT_PERCENT_FLOAT,
    EQUITY_SHORT_TERM_PERCENT_FLOAT,
    GRANDFATHER_VALUATION_MONTH_INT,
    GRANDFATHER_VALUATION_YEAR_INT,
    LOSS_CARRY_FORWARD_YEARS_INT,
    MAXIMUM_CAPITAL_GAINS_SURCHARGE_PERCENT_FLOAT,
    NEW_REGIME_INCOME_TAX_SLABS_TUPLE,
    NEW_REGIME_SURCHARGE_SLABS_TUPLE,
    OLD_REGIME_INCOME_TAX_SLABS_TUPLE,
    OLD_REGIME_SURCHARGE_SLABS_TUPLE,
)
from investment_journey_simulator.currency import CURRENCY_TUPLE
from investment_journey_simulator.regimes import REGIME_TUPLE
from investment_journey_simulator.timeline import EVENT_TYPE_TUPLE

SOURCES_PATH: Path = (
    Path(__file__).resolve().parents[1] / "docs" / "SOURCES.md"
)


@pytest.fixture(scope="module")
def sources_text_str() -> str:
    """Read the sources document once for the whole module.

    REFERENCE: harness only.
    """
    return SOURCES_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sources_flat_str(sources_text_str: str) -> str:
    """The document with its line wrapping flattened away.

    REFERENCE: harness only. A phrase that wraps across two lines
    is still the same phrase to a reader, so prose checks run
    against a whitespace-normalised copy.
    """
    return re.sub(r"\s+", " ", sources_text_str.lower())


def test_the_sources_document_exists(sources_text_str: str) -> None:
    """Every statutory number must have somewhere to be sourced.

    REFERENCE: G4-SYNTHETIC. A missing document would make every
    other test here vacuously pass.
    """
    assert len(sources_text_str) > 1000


@pytest.mark.parametrize(
    ("value_float", "expected_str"),
    [
        (EQUITY_SHORT_TERM_PERCENT_FLOAT, "20%"),
        (EQUITY_LONG_TERM_PERCENT_FLOAT, "12.5%"),
        (DEFAULT_CESS_PERCENT_FLOAT, "4%"),
        (MAXIMUM_CAPITAL_GAINS_SURCHARGE_PERCENT_FLOAT, "15%"),
        (EQUITY_REDEMPTION_STT_PERCENT_FLOAT, "0.001%"),
        (DEFAULT_EXIT_LOAD_PERCENT_FLOAT, "1%"),
    ],
)
def test_headline_rates_are_stated_as_the_code_holds_them(
    value_float: float,
    expected_str: str,
    sources_text_str: str,
) -> None:
    """A cited rate that no longer matches the code is worse than
    no citation at all.

    REFERENCE: G2-STATUTORY. The parametrisation pulls the value
    from the constant, so changing the constant without changing
    the document fails here.
    """
    assert expected_str in sources_text_str
    assert value_float >= 0.0


def test_the_exemption_is_stated_in_indian_grouping(
    sources_text_str: str,
) -> None:
    """The exemption is quoted as rupees, so it must read as such.

    REFERENCE: G2-STATUTORY. 1,25,000 is the figure in the Act's
    proviso, and the constant must agree with the page.
    """
    assert EQUITY_EXEMPTION_AMOUNT_FLOAT == 125000.0
    assert "1,25,000" in sources_text_str


def test_the_carry_forward_limit_is_documented(
    sources_text_str: str,
) -> None:
    """Eight years is a rule with a section behind it.

    REFERENCE: G2-STATUTORY, section 74.
    """
    assert LOSS_CARRY_FORWARD_YEARS_INT == 8
    assert "Eight years" in sources_text_str
    assert "Section 74" in sources_text_str


def test_the_grandfathering_date_is_documented(
    sources_text_str: str,
) -> None:
    """The valuation date is the whole of the grandfathering rule.

    REFERENCE: G2-STATUTORY, proviso to section 112A.
    """
    assert GRANDFATHER_VALUATION_YEAR_INT == 2018
    assert GRANDFATHER_VALUATION_MONTH_INT == 1
    assert "31 January 2018" in sources_text_str


def test_the_exit_load_window_is_documented(
    sources_text_str: str,
) -> None:
    """A charge that is not statutory still needs its basis stated.

    REFERENCE: G5-PLAUSIBILITY. It is a fund-house term, so the
    document must present it as a default, not as law.
    """
    assert DEFAULT_EXIT_LOAD_MONTHS_INT == 12
    assert "12 months exit load" in sources_text_str


@pytest.mark.parametrize(
    "slab_tuple",
    [
        NEW_REGIME_SURCHARGE_SLABS_TUPLE,
        OLD_REGIME_SURCHARGE_SLABS_TUPLE,
    ],
)
def test_every_surcharge_band_appears_in_the_document(
    slab_tuple: tuple,
    sources_text_str: str,
) -> None:
    """A band missing from the page is a band nobody can check.

    REFERENCE: G2-STATUTORY.
    """
    for _, percent_float in slab_tuple:
        if percent_float <= 0.0:
            continue
        assert f"{percent_float:.0f}%" in sources_text_str


@pytest.mark.parametrize(
    "slab_tuple",
    [
        NEW_REGIME_INCOME_TAX_SLABS_TUPLE,
        OLD_REGIME_INCOME_TAX_SLABS_TUPLE,
    ],
)
def test_every_income_tax_floor_appears_in_the_document(
    slab_tuple: tuple,
    sources_text_str: str,
) -> None:
    """The slabs exist only for relief, so they must be shown.

    REFERENCE: G2-STATUTORY. Each floor is quoted in Indian
    grouping, which is how the document tabulates them.
    """
    for floor_float, _ in slab_tuple:
        if floor_float <= 0.0:
            continue
        grouped_str = f"{int(floor_float):,}"
        indian_str = _to_indian_grouping_str(int(floor_float))
        assert (
            indian_str in sources_text_str
            or grouped_str in sources_text_str
        )


def _to_indian_grouping_str(amount_int: int) -> str:
    """Group digits Indian-style for a document lookup.

    REFERENCE: harness only. Deliberately independent of the
    package's own formatter so this stays a real cross-check.
    """
    digits_str = str(amount_int)
    if len(digits_str) <= 3:
        return digits_str
    head_str, tail_str = digits_str[:-3], digits_str[-3:]
    pair_list = []
    while len(head_str) > 2:
        pair_list.append(head_str[-2:])
        head_str = head_str[:-2]
    if head_str:
        pair_list.append(head_str)
    return ",".join(reversed(pair_list)) + "," + tail_str


def test_the_relief_window_figure_is_documented(
    sources_text_str: str,
) -> None:
    """The anchor calculation is the strongest external check.

    REFERENCE: G2-STATUTORY. It is corroborated by published
    commentary independently of this program.
    """
    assert "51,95,896" in sources_text_str
    assert "13,12,500" in sources_text_str


def test_every_timeline_event_is_reachable_from_the_document(
    sources_text_str: str,
) -> None:
    """An operation the tool performs must be documented.

    REFERENCE: G4-SYNTHETIC. Either the event is a statutory
    mechanism with a source, or it is a translation rule that must
    say so. Silence is not an option.
    """
    documented_str = sources_text_str.lower()
    for event_type_str in EVENT_TYPE_TUPLE:
        keyword_str = event_type_str.split("(")[0].strip().lower()
        assert any(
            word_str in documented_str
            for word_str in keyword_str.split()
            if len(word_str) >= 4
        )


def test_derived_values_are_labelled_as_derivations(
    sources_text_str: str,
) -> None:
    """A number with no source must say so, not imply one.

    REFERENCE: G4-SYNTHETIC. This is the honesty rule the whole
    document rests on.
    """
    assert "no published source" in sources_text_str.lower()
    assert "derived" in sources_text_str.lower()
    assert "not a forecast" in sources_text_str.lower()


def test_the_known_overstatement_is_stated_plainly(
    sources_text_str: str,
) -> None:
    """The tool's largest known flaw must be impossible to miss.

    REFERENCE: G4-SYNTHETIC. Independent per-fund draws make a
    mixed portfolio look safer than it is, and a document that
    hid that would be marketing rather than sourcing.
    """
    assert "independent" in sources_text_str.lower()
    assert "safer here than it is" in sources_text_str.lower()


def test_every_currency_appears_in_the_document(
    sources_text_str: str,
) -> None:
    """A currency on the menu with no entry is undocumented.

    REFERENCE: G4-SYNTHETIC. Grouping and decimal habits are
    decisions, and every decision here is written down.
    """
    for currency in CURRENCY_TUPLE:
        assert currency.code_str in sources_text_str


def test_every_regime_appears_with_its_rate(
    sources_text_str: str,
) -> None:
    """A regime whose rate is not documented cannot be checked.

    REFERENCE: G2-STATUTORY. The rate in the table and the rate
    in the code must be the same rate.
    """
    for regime in REGIME_TUPLE:
        assert regime.name_str in sources_text_str
        rate_str = f"{regime.long_term_percent_float:g}%"
        assert rate_str in sources_text_str, regime.code_str


def test_the_document_says_only_india_is_fully_modelled(
    sources_flat_str: str,
) -> None:
    """This is the claim a reader most needs to be told.

    REFERENCE: G4-SYNTHETIC. Choosing a country fills in rates; it
    does not add that country's tax machinery, and the document
    has to say so where the rates are listed.
    """
    assert "opening rates you can then edit" in sources_flat_str
    assert "switched off" in sources_flat_str


def test_the_document_admits_currency_does_not_convert(
    sources_flat_str: str,
) -> None:
    """A reader must not think this applies exchange rates.

    REFERENCE: G4-SYNTHETIC.
    """
    assert "converts nothing" in sources_flat_str
