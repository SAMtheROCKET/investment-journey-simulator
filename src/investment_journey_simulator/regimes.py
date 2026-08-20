"""Capital gains regimes, and how deeply each one is modelled.

This program was built around Indian tax law and models it in full:
FIFO lots under Rule 8AA, the section 112A exemption per taxpayer
per year, surcharge slabs with marginal relief, cess charged on tax
plus surcharge, grandfathering to 31 January 2018, section 50AA for
debt funds, and loss carry-forward under section 74.

None of that machinery is portable. A regime here is therefore an
honest, narrow thing: **a set of opening values for the tax fields
the reader can already edit**, plus a plain statement of what it
does and does not cover. Choosing "United Kingdom" fills in 24% and
a £3,000 allowance; it does not teach this program the UK tax code.

`is_fully_modelled_bool` is the line between the two. Exactly one
regime sets it, and the interface says so out loud rather than
letting a reader assume otherwise.

Every rate below was checked against published commentary on
6 August 2026 and is recorded in `docs/SOURCES.md`. Re-verify after
each country's budget.
"""

from __future__ import annotations

from dataclasses import dataclass

REGIME_INDIA_STR: str = "IN"
DEFAULT_REGIME_CODE_STR: str = REGIME_INDIA_STR


@dataclass(frozen=True)
class TaxRegime:
    """One country's capital gains treatment, as opening values."""

    code_str: str
    name_str: str
    currency_code_str: str
    short_term_percent_float: float
    long_term_percent_float: float
    long_term_threshold_months_int: int
    annual_exemption_float: float
    cess_percent_float: float = 0.0
    is_fully_modelled_bool: bool = False
    depth_str: str = ""
    source_str: str = ""

    @property
    def label_str(self) -> str:
        """How this regime is offered in a menu.

        Brief:
            Marks the one regime that is modelled in full, so the
            choice is informed before it is made.

        Arguments:
            None.

        Returns:
            str: For example "India - fully modelled".

        Warning:
            Display only; the code is the identifier.
        """
        suffix_str = (
            "fully modelled"
            if self.is_fully_modelled_bool
            else "opening rates only"
        )
        return f"{self.name_str} - {suffix_str}"

    @property
    def is_flat_bool(self) -> bool:
        """Whether holding period changes the rate at all.

        Brief:
            Japan taxes listed shares at one rate however long they
            were held, so a holding-period split would be noise.

        Arguments:
            None.

        Returns:
            bool: True when both rates are the same.

        Warning:
            A flat regime still records a threshold, which is
            simply never load-bearing.
        """
        return (
            self.short_term_percent_float
            == self.long_term_percent_float
        )


REGIME_TUPLE: tuple = (
    TaxRegime(
        code_str="IN",
        name_str="India",
        currency_code_str="INR",
        short_term_percent_float=20.0,
        long_term_percent_float=12.5,
        long_term_threshold_months_int=12,
        annual_exemption_float=125_000.0,
        cess_percent_float=4.0,
        is_fully_modelled_bool=True,
        depth_str=(
            "Modelled in full: FIFO lots, the per-taxpayer annual "
            "exemption, surcharge slabs with marginal relief, cess "
            "on tax plus surcharge, grandfathering to 31 Jan 2018, "
            "s.50AA debt treatment and eight-year loss carry-"
            "forward."
        ),
        source_str=(
            "ss.111A and 112A as amended by the Finance (No. 2) "
            "Act 2024, for transfers on or after 23 July 2024."
        ),
    ),
    TaxRegime(
        code_str="JP",
        name_str="Japan",
        currency_code_str="JPY",
        short_term_percent_float=20.315,
        long_term_percent_float=20.315,
        long_term_threshold_months_int=0,
        annual_exemption_float=0.0,
        depth_str=(
            "Flat rate on listed shares whatever the holding "
            "period, so the long-term split never bites. NISA "
            "accounts, loss carry-forward and the separate "
            "treatment of unlisted shares are not modelled."
        ),
        source_str=(
            "20.315% = 15.315% national including the "
            "reconstruction surtax, plus 5% local inhabitant tax."
        ),
    ),
    TaxRegime(
        code_str="GB",
        name_str="United Kingdom",
        currency_code_str="GBP",
        short_term_percent_float=24.0,
        long_term_percent_float=24.0,
        long_term_threshold_months_int=0,
        annual_exemption_float=3_000.0,
        depth_str=(
            "The higher rate is used, which is the conservative "
            "reading. The 18% basic-rate band, ISA shelters and "
            "Business Asset Disposal Relief are not modelled - "
            "override the rate if you are a basic-rate payer."
        ),
        source_str=(
            "18% within the basic-rate band and 24% above it, "
            "with a £3,000 annual exempt amount, 2026/27."
        ),
    ),
    TaxRegime(
        code_str="US",
        name_str="United States",
        currency_code_str="USD",
        short_term_percent_float=24.0,
        long_term_percent_float=15.0,
        long_term_threshold_months_int=12,
        annual_exemption_float=0.0,
        depth_str=(
            "Long-term uses the middle 15% bracket and short-term "
            "a mid ordinary rate. The 0% and 20% brackets, the "
            "3.8% net investment income tax and every state tax "
            "are not modelled - override both rates for your own "
            "bracket."
        ),
        source_str=(
            "Long-term capital gains bracketed at 0%, 15% and "
            "20% by income; short-term taxed as ordinary income."
        ),
    ),
    TaxRegime(
        code_str="SG",
        name_str="Singapore",
        currency_code_str="SGD",
        short_term_percent_float=0.0,
        long_term_percent_float=0.0,
        long_term_threshold_months_int=0,
        annual_exemption_float=0.0,
        depth_str=(
            "Singapore levies no capital gains tax on investment "
            "disposals. Gains from trading as a business can be "
            "taxed as income, which is not modelled."
        ),
        source_str="No general capital gains tax regime.",
    ),
    TaxRegime(
        code_str="AE",
        name_str="United Arab Emirates",
        currency_code_str="AED",
        short_term_percent_float=0.0,
        long_term_percent_float=0.0,
        long_term_threshold_months_int=0,
        annual_exemption_float=0.0,
        depth_str=(
            "No personal income or capital gains tax on "
            "individuals. The corporate tax introduced in 2023 "
            "does not reach personal investment gains."
        ),
        source_str="No personal capital gains tax.",
    ),
)

REGIME_BY_CODE_DICT: dict[str, TaxRegime] = {
    regime.code_str: regime for regime in REGIME_TUPLE
}


def resolve_regime(code_str: str = "") -> TaxRegime:
    """Find a regime by its two-letter country code.

    Brief:
        Falls back to India, the only regime this program models
        in full and the one every statutory test is written for.

    Arguments:
        code_str (str): Two-letter country code.

    Returns:
        TaxRegime: The regime, or India when unknown.

    Warning:
        An unknown code is not an error; it means "use the
        default", so a stale saved scenario still opens.
    """
    return REGIME_BY_CODE_DICT.get(
        str(code_str).upper(),
        REGIME_BY_CODE_DICT[DEFAULT_REGIME_CODE_STR],
    )


def list_regime_code_list() -> list[str]:
    """Every regime code on offer, in menu order.

    Brief:
        India first, because it is the default and the only one
        modelled beyond its headline rates.

    Arguments:
        None.

    Returns:
        List[str]: Country codes in display order.

    Warning:
        Order is presentational; the code is the identifier.
    """
    return [regime.code_str for regime in REGIME_TUPLE]


def describe_regime_str(regime: TaxRegime) -> str:
    """Say what a regime charges and how far it is modelled.

    Brief:
        The depth matters as much as the rate. A reader choosing
        anything other than India is choosing opening values, not
        a second tax engine, and must be told so plainly.

    Arguments:
        regime (TaxRegime): Regime being described.

    Returns:
        str: One paragraph naming rates, exemption and depth.

    Warning:
        Display only.
    """
    if regime.is_flat_bool:
        rate_str = (
            f"{regime.short_term_percent_float:g}% flat, whatever "
            "the holding period"
        )
    else:
        rate_str = (
            f"{regime.short_term_percent_float:g}% short-term and "
            f"{regime.long_term_percent_float:g}% long-term above "
            f"{regime.long_term_threshold_months_int} months"
        )
    return f"**{rate_str}.** {regime.depth_str}"
