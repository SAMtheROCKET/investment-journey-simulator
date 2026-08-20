"""Capital gains regimes, and how deeply each one is modelled.

The dangerous failure here is not a wrong rate - it is a reader
believing this program models their country's tax code when it only
holds its headline rates. These tests hold that line explicitly.
"""

from __future__ import annotations

import pytest

from investment_journey_simulator.constants import (
    DEFAULT_CESS_PERCENT_FLOAT,
    EQUITY_EXEMPTION_AMOUNT_FLOAT,
    EQUITY_LONG_TERM_PERCENT_FLOAT,
    EQUITY_SHORT_TERM_PERCENT_FLOAT,
)
from investment_journey_simulator.currency import resolve_currency
from investment_journey_simulator.regimes import (
    DEFAULT_REGIME_CODE_STR,
    REGIME_TUPLE,
    describe_regime_str,
    list_regime_code_list,
    resolve_regime,
)


def test_india_is_the_default_regime() -> None:
    """Every statutory test in this suite is written for India.

    REFERENCE: G4-SYNTHETIC. The default must be the one regime
    the engine actually models.
    """
    assert DEFAULT_REGIME_CODE_STR == "IN"
    assert resolve_regime().code_str == "IN"
    assert resolve_regime("").code_str == "IN"
    assert resolve_regime("ZZ").code_str == "IN"


def test_indias_rates_match_the_constants_the_engine_uses(
) -> None:
    """The regime table must not drift from the tax constants.

    REFERENCE: G2-STATUTORY. Two sources of truth for the same
    rate is one too many, so they are asserted equal.
    """
    india = resolve_regime("IN")
    assert india.short_term_percent_float == (
        EQUITY_SHORT_TERM_PERCENT_FLOAT
    )
    assert india.long_term_percent_float == (
        EQUITY_LONG_TERM_PERCENT_FLOAT
    )
    assert india.annual_exemption_float == (
        EQUITY_EXEMPTION_AMOUNT_FLOAT
    )
    assert india.cess_percent_float == DEFAULT_CESS_PERCENT_FLOAT
    assert india.long_term_threshold_months_int == 12


def test_exactly_one_regime_claims_to_be_fully_modelled() -> None:
    """This is the claim that must never quietly broaden.

    REFERENCE: G4-SYNTHETIC. Adding a country is easy; adding its
    tax machinery is not, and the two must not be confused.
    """
    fully_modelled_list = [
        regime
        for regime in REGIME_TUPLE
        if regime.is_fully_modelled_bool
    ]
    assert len(fully_modelled_list) == 1
    assert fully_modelled_list[0].code_str == "IN"


def test_only_india_carries_a_cess() -> None:
    """Cess is an Indian mechanism, not a general one.

    REFERENCE: G2-STATUTORY. Charging it elsewhere would invent a
    levy that does not exist.
    """
    for regime in REGIME_TUPLE:
        if regime.code_str == "IN":
            continue
        assert regime.cess_percent_float == 0.0


@pytest.mark.parametrize(
    ("code_str", "expected_rate_float"),
    [
        ("JP", 20.315),
        ("GB", 24.0),
        ("SG", 0.0),
        ("AE", 0.0),
    ],
)
def test_headline_rates_are_the_published_ones(
    code_str: str,
    expected_rate_float: float,
) -> None:
    """A rate typed from memory is a rate that will be wrong.

    REFERENCE: G2-STATUTORY. Japan is 15.315% national including
    the reconstruction surtax plus 5% local. The UK higher rate is
    24%. Singapore and the UAE levy no capital gains tax on
    individuals. Checked against published commentary 6 Aug 2026
    and recorded in docs/SOURCES.md.
    """
    assert resolve_regime(
        code_str
    ).long_term_percent_float == pytest.approx(
        expected_rate_float
    )


def test_a_zero_tax_regime_really_charges_nothing() -> None:
    """Singapore and the UAE must not carry a hidden rate.

    REFERENCE: G2-STATUTORY. Guard on both ends of the holding
    period at once.
    """
    for code_str in ("SG", "AE"):
        regime = resolve_regime(code_str)
        assert regime.short_term_percent_float == 0.0
        assert regime.long_term_percent_float == 0.0
        assert regime.annual_exemption_float == 0.0


def test_japan_taxes_at_one_rate_however_long_you_held() -> None:
    """A holding-period split would be noise in Japan.

    REFERENCE: G2-STATUTORY. Listed shares are taxed at a flat
    20.315% regardless of holding period.
    """
    japan = resolve_regime("JP")
    assert japan.is_flat_bool is True
    assert "flat" in describe_regime_str(japan)


def test_india_is_not_flat_because_the_holding_period_matters(
) -> None:
    """The twelve-month split is the heart of Indian equity tax.

    REFERENCE: G2-STATUTORY.
    """
    assert resolve_regime("IN").is_flat_bool is False


def test_the_uk_exemption_is_carried() -> None:
    """An allowance left out would overstate the tax.

    REFERENCE: G2-STATUTORY. £3,000 annual exempt amount, 2026/27.
    """
    assert resolve_regime("GB").annual_exemption_float == 3_000.0


def test_every_regime_states_its_own_limits() -> None:
    """A regime that does not say what it omits is misleading.

    REFERENCE: G4-SYNTHETIC. The depth note is the honesty rule
    this whole module rests on.
    """
    for regime in REGIME_TUPLE:
        assert regime.depth_str
        assert regime.source_str
        assert len(regime.depth_str) > 40


def test_a_partly_modelled_regime_says_so_in_its_label() -> None:
    """The choice has to be informed before it is made.

    REFERENCE: G4-SYNTHETIC.
    """
    assert "fully modelled" in resolve_regime("IN").label_str
    for code_str in ("JP", "GB", "US", "SG", "AE"):
        assert "opening rates only" in resolve_regime(
            code_str
        ).label_str


def test_every_regime_names_a_currency_that_exists() -> None:
    """A regime pointing at an unknown currency would show rupees.

    REFERENCE: G4-SYNTHETIC. Cross-checks the two registries.
    """
    for regime in REGIME_TUPLE:
        currency = resolve_currency(regime.currency_code_str)
        assert currency.code_str == regime.currency_code_str


def test_the_menu_lists_every_regime_once() -> None:
    """A regime not in the menu cannot be chosen.

    REFERENCE: G4-SYNTHETIC.
    """
    code_list = list_regime_code_list()
    assert len(code_list) == len(set(code_list))
    assert code_list[0] == "IN"
    assert len(code_list) == len(REGIME_TUPLE)


def test_the_description_names_both_rates_when_they_differ(
) -> None:
    """A reader must see what they are choosing.

    REFERENCE: G4-SYNTHETIC.
    """
    described_str = describe_regime_str(resolve_regime("IN"))
    assert "20%" in described_str
    assert "12.5%" in described_str
    assert "12 months" in described_str
