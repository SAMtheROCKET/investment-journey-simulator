"""The tax machinery, against a second reading of the rules.

Tax was the one part of this engine with no independent check at
all. `reference_simulator` cannot help: it has no lot book, and
that is exactly what makes it good evidence about value. But tax
depends entirely on which units were sold, when they were bought,
and which financial year the sale fell in - so checking it needs a
lot book, and a second one had to be written.

`reference_tax.py` is that second book, written from the rules
rather than from `taxation.py`. These tests run both over the same
random plans and require them to agree on the tax, the charges, the
corpus, the principal and the payout.

WHAT THE DISAGREEMENT WAS

The first run disagreed on 97 of 400 plans - on tax alone, with
every other figure matching, which is what said the flows were
right and only the classification was wrong. The cause was the
holding-period boundary. Section 2(42A) calls an asset short term
when it was held for *not more than* the threshold, so twelve whole
months is short term and the thirteenth month is what earns the
lower rate. The comparison is strict, and the engine had it right;
the second reading had it wrong. Every one of the 97 was a parcel
sold at exactly the boundary, taxed at 12.5 per cent instead of 20.

That is worth recording because it is the case a hand-written test
suite tends to miss: not a wrong formula, but a wrong inequality on
one line, visible only when a sale lands on the exact month.

WHAT IS AND IS NOT COVERED

Covered: first-in first-out consumption, partial sales that keep
their original purchase month, short against long term, the annual
exemption per fund and per taxpayer, the April financial-year
boundary, exemption scope, specified debt funds that are always
short term, loss set-off and its pools, carry-forward expiry,
surcharge and cess, exit loads and the transaction tax, and all of
that while contributions, withdrawals and rebalances are running.

Not covered here, and held by their own tests instead:
grandfathering, which cannot arise in a plan starting in 2026, and
the automatic surcharge bands, where the rate is derived from total
income rather than stated.
"""

from __future__ import annotations

import pytest

from investment_journey_simulator.engine import PortfolioSimulator
from reference_tax import run_reference_tax
from scenario_factory import (
    build_taxed_scenario_tuple,
    describe_scenario_str,
)

PAISA_TOLERANCE_FLOAT: float = 0.01
RELATIVE_TOLERANCE_FLOAT: float = 1e-9
TAX_SCENARIO_COUNT_INT: int = 400


def is_close_bool(got_float: float, want_float: float) -> bool:
    """Equal to the paisa, or to nine significant figures."""
    return abs(got_float - want_float) <= max(
        PAISA_TOLERANCE_FLOAT,
        RELATIVE_TOLERANCE_FLOAT
        * max(abs(got_float), abs(want_float)),
    )


def compare_one_scenario(seed_int: int) -> None:
    """Run both books over one plan and require agreement."""
    fund_list, settings = build_taxed_scenario_tuple(seed_int)
    engine_result = PortfolioSimulator(fund_list, settings).run()
    reference_run = run_reference_tax(fund_list, settings)
    for label_str, got_float, want_float in (
        (
            "tax",
            engine_result.ending_tax_paid_float,
            reference_run.tax_float,
        ),
        (
            "charges",
            engine_result.charges_paid_float,
            reference_run.charges_float,
        ),
        (
            "ending value",
            engine_result.ending_value_float,
            reference_run.ending_value_float,
        ),
        (
            "invested",
            engine_result.ending_invested_float,
            reference_run.invested_float,
        ),
        (
            "withdrawn",
            engine_result.ending_withdrawn_float,
            reference_run.withdrawn_float,
        ),
    ):
        assert is_close_bool(got_float, want_float), (
            f"seed {seed_int}: {label_str} "
            f"engine={got_float:,.4f} "
            f"reference={want_float:,.4f} "
            f"difference={got_float - want_float:,.4f}"
            + chr(10)
            + describe_scenario_str(fund_list, settings)
            + chr(10)
            + f"exemption level "
            f"{settings.tax.exemption_level_str}, set-off "
            f"{settings.tax.allow_loss_set_off_bool}, surcharge "
            f"{settings.tax.surcharge_percent_float}, cess "
            f"{settings.tax.cess_percent_float}"
        )


@pytest.mark.parametrize(
    "batch_start_int", range(TAX_SCENARIO_COUNT_INT // 20)
)
def test_the_tax_agrees_with_a_second_reading_of_the_rules(
    batch_start_int,
):
    """Twenty taxed plans per batch, five figures each.

    REFERENCE: G3-CROSSCHECK. Two lot books, written separately,
    walking the same sales.
    """
    for offset_int in range(20):
        compare_one_scenario(batch_start_int * 20 + offset_int)


@pytest.mark.parametrize("seed_int", range(5000, 5040))
def test_the_tax_agrees_on_a_second_block_of_seeds(seed_int):
    """A different block, so the fixed seeds are not the whole test.

    REFERENCE: G3-CROSSCHECK.
    """
    compare_one_scenario(seed_int)


def test_a_sale_at_exactly_the_threshold_is_short_term():
    """The inequality that the cross-check disagreed on.

    REFERENCE: G2-STATUTORY. Section 2(42A) defines a short-term
    capital asset as one held for *not more than* the threshold.
    Twelve whole months is therefore short term, and only the
    thirteenth month earns the long term rate. Pinned here because
    it is one character in one comparison, and because getting it
    wrong moves the rate from 20 per cent to 12.5.
    """
    from datetime import date

    from conftest import build_test_fund
    from investment_journey_simulator.models import TaxSettings
    from investment_journey_simulator.taxation import (
        CapitalGainsTaxPolicy,
        ExemptionLedger,
        LossLedger,
    )

    fund_configuration = build_test_fund(
        long_term_threshold_months_int=12,
        short_term_tax_percent_float=20.0,
        long_term_tax_percent_float=12.5,
        exemption_amount_float=0.0,
    )
    policy = CapitalGainsTaxPolicy(
        fund_configuration,
        ExemptionLedger(),
        TaxSettings(),
        LossLedger(),
    )
    assert not policy.is_long_term_holding_bool(12)
    assert policy.is_long_term_holding_bool(13)
    sale_date = date(2027, 6, 1)
    assert policy.calculate_tax_breakdown(
        100000.0, 12, sale_date
    ).tax_amount_float == pytest.approx(20000.0)
    assert policy.calculate_tax_breakdown(
        100000.0, 13, sale_date
    ).tax_amount_float == pytest.approx(12500.0)
