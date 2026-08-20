"""Capital gains tests against Indian statutory parameters."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    EXEMPTION_LEVEL_FUND_STR,
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXEMPTION_SCOPE_TOTAL_GAINS_STR,
    LOSS_CARRY_FORWARD_YEARS_INT,
    SURCHARGE_MODE_MANUAL_STR,
    SURCHARGE_MODE_SLAB_STR,
    SURCHARGE_REGIME_NEW_STR,
    SURCHARGE_REGIME_OLD_STR,
    TAX_YEAR_START_MONTH_AUSTRALIA_INT,
    TAX_YEAR_START_MONTH_CALENDAR_INT,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import TaxSettings
from investment_journey_simulator.taxation import (
    CapitalGainsTaxPolicy,
    ExemptionLedger,
    calculate_income_tax_float,
    resolve_relieved_surcharge_percent_float,
    resolve_surcharge_percent_float,
    resolve_surcharge_slab_percent_float,
    resolve_total_income_float,
)
from reference_data import (
    STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
    STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT,
    STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT,
    STATUTORY_OLD_REGIME_TAX_AT_FIFTY_LAKH_FLOAT,
    STATUTORY_RELIEF_WINDOW_CLOSE_RUPEES_FLOAT,
    reference_old_regime_income_tax_float,
    reference_surcharge_payable_float,
)

SALE_DATE: date = date(2030, 6, 1)
NEXT_YEAR_SALE_DATE: date = date(2031, 6, 1)
SAME_FINANCIAL_YEAR_DATE: date = date(2031, 3, 1)


def build_policy(
    exemption_amount_float: float = 0.0,
    exemption_scope_str: str = EXEMPTION_SCOPE_LONG_TERM_STR,
    is_always_short_term_bool: bool = False,
    tax_settings: TaxSettings = None,
    ledger: ExemptionLedger = None,
) -> CapitalGainsTaxPolicy:
    """Build a tax policy for one isolated fund.

    REFERENCE: harness only; carries statutory rates by default.
    """
    fund_configuration = build_test_fund(
        exemption_amount_float=exemption_amount_float,
        is_always_short_term_bool=is_always_short_term_bool,
    )
    fund_configuration.exemption_scope_str = exemption_scope_str
    return CapitalGainsTaxPolicy(
        fund_configuration,
        ledger or ExemptionLedger(),
        tax_settings or TaxSettings(),
    )


def test_short_term_rate_matches_section_111a() -> None:
    """Equity gains below the threshold are taxed at 20 percent.

    REFERENCE: G2-STATUTORY, section 111A as amended by the
    Finance (No. 2) Act 2024 for transfers from 23 July 2024.
    """
    breakdown = build_policy().calculate_tax_breakdown(
        100000.0, 6, SALE_DATE
    )
    assert breakdown.tax_amount_float == pytest.approx(
        100000.0 * STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT / 100.0
    )
    assert breakdown.short_term_gain_float == 100000.0
    assert breakdown.long_term_gain_float == 0.0


def test_long_term_rate_matches_section_112a() -> None:
    """Equity gains beyond the threshold are taxed at 12.5 percent.

    REFERENCE: G2-STATUTORY, section 112A as amended by the
    Finance (No. 2) Act 2024.
    """
    breakdown = build_policy().calculate_tax_breakdown(
        100000.0, 24, SALE_DATE
    )
    assert breakdown.tax_amount_float == pytest.approx(
        100000.0 * STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT / 100.0
    )
    assert breakdown.long_term_gain_float == 100000.0
    assert breakdown.short_term_gain_float == 0.0


@pytest.mark.parametrize(
    "months_held_int, is_long_term_bool",
    [(0, False), (11, False), (12, False), (13, True)],
)
def test_holding_threshold_boundary_is_exclusive(
    months_held_int: int,
    is_long_term_bool: bool,
) -> None:
    """Exactly twelve months is still short term.

    REFERENCE: G2-STATUTORY, section 2(42A) defines a short-term
    capital asset as one held for *not more than* twelve months.
    A holding of exactly twelve months therefore fails the test,
    and the thirteenth month is what earns the long term rate.
    Boundary asserted on both sides.
    """
    policy = build_policy()
    assert (
        policy.is_long_term_holding_bool(months_held_int)
        is is_long_term_bool
    )
    assert months_held_int >= 0


def test_a_lot_held_exactly_a_year_pays_the_short_term_rate(
) -> None:
    """The boundary has to change the tax, not just a flag.

    REFERENCE: G2-STATUTORY. Selling in the twelfth month is a
    section 111A transfer at 20%, not a section 112A one at 12.5%.
    Getting this backwards understates the tax by 7.5% of the gain
    on every lot sold exactly a year after it was bought.
    """
    policy = build_policy()
    assert policy.calculate_tax_breakdown(
        100000.0, 12, SALE_DATE
    ).tax_amount_float == pytest.approx(
        100000.0 * STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT / 100.0
    )
    assert policy.calculate_tax_breakdown(
        100000.0, 13, NEXT_YEAR_SALE_DATE
    ).tax_amount_float == pytest.approx(
        100000.0 * STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT / 100.0
    )


def test_debt_style_fund_is_never_long_term() -> None:
    """Debt funds bought after 1 April 2023 are always short term.

    REFERENCE: G2-STATUTORY, section 50AA specified mutual funds.
    """
    policy = build_policy(is_always_short_term_bool=True)
    assert policy.is_long_term_holding_bool(120) is False
    breakdown = policy.calculate_tax_breakdown(
        50000.0, 120, SALE_DATE
    )
    assert breakdown.short_term_gain_float == 50000.0


def test_exemption_shelters_the_first_lakh_and_a_quarter() -> None:
    """Only gains beyond 1,25,000 are taxable in a year.

    REFERENCE: G2-STATUTORY, proviso to section 112A.
    Gain 2,00,000 - 1,25,000 = 75,000 taxable at 12.5 percent.
    """
    breakdown = build_policy(
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
    ).calculate_tax_breakdown(200000.0, 24, SALE_DATE)
    assert breakdown.tax_amount_float == pytest.approx(75000.0 * 0.125)


def test_exemption_is_consumed_only_once_per_year() -> None:
    """A second sale in the same year gets no fresh exemption.

    REFERENCE: G2-STATUTORY. The exemption is annual, not per
    transaction. Two sales of 1,00,000 in one financial year
    leave 75,000 taxable in total.
    """
    policy = build_policy(STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT)
    first_breakdown = policy.calculate_tax_breakdown(
        100000.0, 24, SALE_DATE
    )
    second_breakdown = policy.calculate_tax_breakdown(
        100000.0, 24, SAME_FINANCIAL_YEAR_DATE
    )
    assert first_breakdown.tax_amount_float == 0.0
    assert second_breakdown.tax_amount_float == pytest.approx(
        75000.0 * 0.125
    )


def test_exemption_resets_in_the_next_financial_year() -> None:
    """A new financial year restores the full exemption.

    REFERENCE: G2-STATUTORY. Indian financial years run April to
    March, so June 2030 and June 2031 are different years.
    """
    policy = build_policy(STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT)
    policy.calculate_tax_breakdown(125000.0, 24, SALE_DATE)
    later_breakdown = policy.calculate_tax_breakdown(
        125000.0, 24, NEXT_YEAR_SALE_DATE
    )
    assert later_breakdown.tax_amount_float == 0.0


def test_long_term_scope_does_not_shelter_short_term_gains() -> None:
    """A long-term-only exemption must not cover short term gains.

    REFERENCE: G2-STATUTORY. Section 112A relief applies to long
    term gains only; section 111A carries no exemption.
    """
    breakdown = build_policy(
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
        EXEMPTION_SCOPE_LONG_TERM_STR,
    ).calculate_tax_breakdown(100000.0, 6, SALE_DATE)
    assert breakdown.tax_amount_float == pytest.approx(20000.0)


def test_total_gains_scope_shelters_short_term_gains() -> None:
    """A total-gains scope shelters short term gains as well.

    REFERENCE: G4-SYNTHETIC. Planning-mode branch that models a
    generic allowance rather than section 112A.
    """
    breakdown = build_policy(
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
        EXEMPTION_SCOPE_TOTAL_GAINS_STR,
    ).calculate_tax_breakdown(100000.0, 6, SALE_DATE)
    assert breakdown.tax_amount_float == 0.0


def test_zero_and_negative_gains_are_never_taxed() -> None:
    """Losses and zero gains must produce no tax at all.

    REFERENCE: G2-STATUTORY. Tax applies to gains only.
    """
    policy = build_policy()
    for gain_float in (0.0, -50000.0):
        breakdown = policy.calculate_tax_breakdown(
            gain_float, 24, SALE_DATE
        )
        assert breakdown.tax_amount_float == 0.0
        assert breakdown.short_term_gain_float == 0.0
        assert breakdown.long_term_gain_float == 0.0


def test_portfolio_exemption_is_shared_between_funds() -> None:
    """One taxpayer gets one exemption across all equity funds.

    REFERENCE: G2-STATUTORY. Section 112A relief is per taxpayer,
    not per scheme. Two funds each realising 1,00,000 share the
    single 1,25,000 allowance, leaving 75,000 taxable.
    """
    shared_ledger = ExemptionLedger()
    tax_settings = TaxSettings(
        exemption_level_str=EXEMPTION_LEVEL_PORTFOLIO_STR,
        portfolio_exemption_amount_float=(
            STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
        ),
    )
    first_policy = CapitalGainsTaxPolicy(
        build_test_fund("Fund-A"), shared_ledger, tax_settings
    )
    second_policy = CapitalGainsTaxPolicy(
        build_test_fund("Fund-B"), shared_ledger, tax_settings
    )
    total_tax_float = (
        first_policy.calculate_tax_breakdown(
            100000.0, 24, SALE_DATE
        ).tax_amount_float
        + second_policy.calculate_tax_breakdown(
            100000.0, 24, SALE_DATE
        ).tax_amount_float
    )
    assert total_tax_float == pytest.approx(75000.0 * 0.125)


def test_per_fund_exemption_multiplies_the_shelter() -> None:
    """Per-fund tracking understates tax, which is why it is not
    the default.

    REFERENCE: G4-SYNTHETIC contrast with the statutory case
    above. Two funds each get their own 1,25,000, so nothing is
    taxed even though the taxpayer realised 2,00,000.
    """
    shared_ledger = ExemptionLedger()
    tax_settings = TaxSettings(
        exemption_level_str=EXEMPTION_LEVEL_FUND_STR
    )
    total_tax_float = 0.0
    for name_str in ("Fund-A", "Fund-B"):
        fund_configuration = build_test_fund(
            name_str,
            exemption_amount_float=(
                STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
            ),
        )
        policy = CapitalGainsTaxPolicy(
            fund_configuration, shared_ledger, tax_settings
        )
        total_tax_float += policy.calculate_tax_breakdown(
            100000.0, 24, SALE_DATE
        ).tax_amount_float
    assert total_tax_float == 0.0


def test_dry_run_copy_does_not_consume_the_real_exemption() -> None:
    """Pricing a hypothetical exit must not spend the allowance.

    REFERENCE: G4-SYNTHETIC. The final-liquidation estimate must
    be side-effect free.
    """
    policy = build_policy(STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT)
    policy.build_dry_run_copy().calculate_tax_breakdown(
        125000.0, 24, SALE_DATE
    )
    real_breakdown = policy.calculate_tax_breakdown(
        125000.0, 24, SALE_DATE
    )
    assert real_breakdown.tax_amount_float == 0.0


def test_ledger_returns_full_gain_when_no_exemption_remains() -> None:
    """Once the allowance is spent the whole gain is taxable.

    REFERENCE: G4-SYNTHETIC. Ledger arithmetic at the boundary.
    """
    ledger = ExemptionLedger()
    ledger.consume_exemption_float("F", 2030, "S", 125000.0, 125000.0)
    remaining_float = ledger.consume_exemption_float(
        "F", 2030, "S", 50000.0, 125000.0
    )
    assert remaining_float == pytest.approx(50000.0)


def test_ledger_treats_a_negative_limit_as_zero() -> None:
    """A negative exemption cap must not create tax shelter.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    ledger = ExemptionLedger()
    assert ledger.consume_exemption_float(
        "F", 2030, "S", 1000.0, -500.0
    ) == pytest.approx(1000.0)


# ------------------------------------------------------------------
# Surcharge slabs
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("total_income_float", "expected_percent_float"),
    [
        (0.0, 0.0),
        (4_999_999.0, 0.0),
        (5_000_000.0, 0.0),
        (5_000_001.0, 10.0),
        (10_000_000.0, 10.0),
        (10_000_001.0, 15.0),
        (20_000_000.0, 15.0),
        (20_000_001.0, 25.0),
        (100_000_000.0, 25.0),
    ],
)
def test_new_regime_surcharge_slabs_match_the_statute(
    total_income_float: float,
    expected_percent_float: float,
) -> None:
    """The new regime slabs stop at twenty-five percent.

    REFERENCE: G2-STATUTORY. Surcharge on total income: nil up to
    fifty lakh, 10% above it, 15% above one crore and 25% above
    two crore. The new regime, the default since FY 2023-24,
    dropped the 37% band the old regime still carries.
    """
    assert resolve_surcharge_slab_percent_float(
        total_income_float, SURCHARGE_REGIME_NEW_STR
    ) == pytest.approx(expected_percent_float)


@pytest.mark.parametrize(
    ("total_income_float", "expected_percent_float"),
    [
        (20_000_001.0, 25.0),
        (50_000_000.0, 25.0),
        (50_000_001.0, 37.0),
    ],
)
def test_old_regime_keeps_the_thirty_seven_percent_band(
    total_income_float: float,
    expected_percent_float: float,
) -> None:
    """The old regime still charges 37% above five crore.

    REFERENCE: G2-STATUTORY. The two regimes differ only in the
    top band, so that is the only place worth asserting.
    """
    assert resolve_surcharge_slab_percent_float(
        total_income_float, SURCHARGE_REGIME_OLD_STR
    ) == pytest.approx(expected_percent_float)


def test_manual_mode_ignores_total_income() -> None:
    """Manual mode uses the typed rate and nothing else.

    REFERENCE: G4-SYNTHETIC. Preserves the behaviour every earlier
    scenario relied on, so an existing saved scenario is unchanged.
    """
    settings = TaxSettings(
        surcharge_mode_str=SURCHARGE_MODE_MANUAL_STR,
        surcharge_percent_float=7.0,
        total_income_float=100_000_000.0,
    )
    assert resolve_surcharge_percent_float(
        settings
    ) == pytest.approx(7.0)


def test_slab_mode_derives_the_rate_from_income() -> None:
    """Slab mode ignores the manually typed rate.

    REFERENCE: G4-SYNTHETIC. The two modes must not blend, or the
    reported surcharge would depend on a stale widget value.
    """
    settings = TaxSettings(
        surcharge_mode_str=SURCHARGE_MODE_SLAB_STR,
        surcharge_percent_float=7.0,
        total_income_float=15_000_000.0,
    )
    assert resolve_surcharge_percent_float(
        settings
    ) == pytest.approx(15.0)


def test_equity_gains_surcharge_is_capped_at_fifteen_percent(
    single_equity_fund_list: list,
) -> None:
    """A twenty-five percent slab cannot reach equity gains.

    REFERENCE: G2-STATUTORY. Surcharge on gains taxed under
    sections 111A and 112A is capped at 15% however high the
    taxpayer's other income is.
    """
    policy = CapitalGainsTaxPolicy(
        single_equity_fund_list[0],
        ExemptionLedger(),
        TaxSettings(
            surcharge_mode_str=SURCHARGE_MODE_SLAB_STR,
            total_income_float=30_000_000.0,
        ),
    )
    breakdown = policy.calculate_tax_breakdown(
        100000.0, 24, date(2030, 6, 1)
    )
    assert breakdown.tax_amount_float == pytest.approx(
        100000.0 * 0.125 * 1.15
    )


# ------------------------------------------------------------------
# Marginal relief on the surcharge
# ------------------------------------------------------------------
def total_liability_float(
    total_income_float: float,
    surcharge_regime_str: str,
) -> float:
    """Tax plus relieved surcharge, before cess.

    REFERENCE: harness only. Cess is excluded because marginal
    relief is computed before cess is added.
    """
    tax_float = calculate_income_tax_float(
        total_income_float, surcharge_regime_str
    )
    percent_float = resolve_relieved_surcharge_percent_float(
        total_income_float, surcharge_regime_str
    )
    return tax_float * (1.0 + percent_float / 100.0)


def test_old_regime_tax_at_fifty_lakh_matches_the_hand_figure(
) -> None:
    """The anchor for every relief calculation must be right.

    REFERENCE: G2-STATUTORY. 5% of 2.5 lakh plus 20% of 5 lakh
    plus 30% of 40 lakh is 13,12,500; the arithmetic is written
    out in reference_data.
    """
    assert calculate_income_tax_float(
        5_000_000.0, SURCHARGE_REGIME_OLD_STR
    ) == pytest.approx(STATUTORY_OLD_REGIME_TAX_AT_FIFTY_LAKH_FLOAT)


@pytest.mark.parametrize(
    "total_income_float",
    [0.0, 250_000.0, 400_000.0, 1_000_000.0, 5_000_000.0,
     5_100_000.0, 12_345_678.0, 60_000_000.0],
)
def test_income_tax_matches_an_independent_slab_walk(
    total_income_float: float,
) -> None:
    """The looped slab walk must equal a longhand one.

    REFERENCE: G3-CROSSCHECK. reference_data spells the old regime
    out slab by slab without loops, so a boundary error in either
    implementation shows up as a disagreement.
    """
    assert calculate_income_tax_float(
        total_income_float, SURCHARGE_REGIME_OLD_STR
    ) == pytest.approx(
        reference_old_regime_income_tax_float(total_income_float)
    )


@pytest.mark.parametrize(
    ("threshold_float", "surcharge_regime_str"),
    [
        (5_000_000.0, SURCHARGE_REGIME_NEW_STR),
        (10_000_000.0, SURCHARGE_REGIME_NEW_STR),
        (20_000_000.0, SURCHARGE_REGIME_NEW_STR),
        (5_000_000.0, SURCHARGE_REGIME_OLD_STR),
        (10_000_000.0, SURCHARGE_REGIME_OLD_STR),
        (20_000_000.0, SURCHARGE_REGIME_OLD_STR),
        (50_000_000.0, SURCHARGE_REGIME_OLD_STR),
    ],
)
def test_earning_one_more_rupee_never_costs_more_than_a_rupee(
    threshold_float: float,
    surcharge_regime_str: str,
) -> None:
    """This is the entire purpose of marginal relief.

    REFERENCE: G2-STATUTORY. Without relief, crossing fifty lakh
    by one rupee adds over a lakh of surcharge. The relieved
    liability may rise by at most the extra rupee itself.
    """
    liability_at_floor_float = total_liability_float(
        threshold_float, surcharge_regime_str
    )
    liability_above_float = total_liability_float(
        threshold_float + 1.0, surcharge_regime_str
    )
    increase_float = liability_above_float - liability_at_floor_float
    assert -1e-6 <= increase_float <= 1.0 + 1e-6


def test_the_relief_window_closes_at_the_published_income() -> None:
    """Relief must run out exactly where commentary says it does.

    REFERENCE: G2-STATUTORY. On the old regime the fifty lakh
    window closes at 51,95,896, the figure published in tax
    commentary and derived in reference_data.
    """
    assert resolve_relieved_surcharge_percent_float(
        STATUTORY_RELIEF_WINDOW_CLOSE_RUPEES_FLOAT,
        SURCHARGE_REGIME_OLD_STR,
    ) == pytest.approx(10.0)
    assert resolve_relieved_surcharge_percent_float(
        STATUTORY_RELIEF_WINDOW_CLOSE_RUPEES_FLOAT - 50_000.0,
        SURCHARGE_REGIME_OLD_STR,
    ) < 10.0


@pytest.mark.parametrize(
    "total_income_float",
    [5_000_001.0, 5_100_000.0, 5_195_896.0, 6_000_000.0],
)
def test_relieved_surcharge_matches_an_independent_statement(
    total_income_float: float,
) -> None:
    """The rate must reproduce the rule stated directly in rupees.

    REFERENCE: G3-CROSSCHECK. reference_data states the relief rule
    as a rupee amount; the package returns an effective percent of
    tax. Converting one into the other must agree.
    """
    tax_float = calculate_income_tax_float(
        total_income_float, SURCHARGE_REGIME_OLD_STR
    )
    package_surcharge_float = (
        tax_float
        * resolve_relieved_surcharge_percent_float(
            total_income_float, SURCHARGE_REGIME_OLD_STR
        )
        / 100.0
    )
    assert package_surcharge_float == pytest.approx(
        reference_surcharge_payable_float(
            total_income_float, 10.0, 5_000_000.0
        )
    )


@pytest.mark.parametrize(
    ("total_income_float", "expected_percent_float"),
    [
        (4_000_000.0, 0.0),
        (6_000_000.0, 10.0),
        (15_000_000.0, 15.0),
        (30_000_000.0, 25.0),
    ],
)
def test_incomes_clear_of_a_boundary_keep_the_full_band_rate(
    total_income_float: float,
    expected_percent_float: float,
) -> None:
    """Relief must not leak into incomes it does not apply to.

    REFERENCE: G2-STATUTORY. Relief is a boundary softening only.
    Well inside a band the full statutory rate is collected.
    """
    assert resolve_relieved_surcharge_percent_float(
        total_income_float, SURCHARGE_REGIME_NEW_STR
    ) == pytest.approx(expected_percent_float)


def test_marginal_relief_reaches_the_capital_gains_tax(
    single_equity_fund_list: list,
) -> None:
    """Relief must change the tax bill, not just a resolver.

    REFERENCE: G4-SYNTHETIC. At 50,10,000 the raw band is 10% but
    relief cuts it to well under that, so the tax on a gain must
    fall between the un-surcharged and fully surcharged figures.
    """
    settings = TaxSettings(
        surcharge_mode_str=SURCHARGE_MODE_SLAB_STR,
        total_income_float=5_010_000.0,
        cess_percent_float=0.0,
    )
    policy = CapitalGainsTaxPolicy(
        single_equity_fund_list[0], ExemptionLedger(), settings
    )
    breakdown = policy.calculate_tax_breakdown(
        100000.0, 24, SALE_DATE
    )
    base_tax_float = 100000.0 * 0.125
    assert base_tax_float < breakdown.tax_amount_float
    assert breakdown.tax_amount_float < base_tax_float * 1.10


# ------------------------------------------------------------------
# Grandfathering, proviso to section 112A
# ------------------------------------------------------------------
GRANDFATHER_START_DATE: date = date(2015, 1, 1)
GRANDFATHER_PRINCIPAL_FLOAT: float = 100000.0


def _run_grandfather_outcome(
    apply_grandfathering_bool: bool,
    start_date: date = GRANDFATHER_START_DATE,
    horizon_years_int: int = 11,
):
    """Run a single lump sum and return its fund outcome.

    REFERENCE: helper only; see the tests that call it.
    """
    fund_list = [
        build_test_fund(
            "Equity",
            0.0,
            12.0,
            0.0,
            start_date,
            initial_investment_float=GRANDFATHER_PRINCIPAL_FLOAT,
            exemption_amount_float=0.0,
            long_term_tax_percent_float=(
                STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT
            ),
        )
    ]
    settings = build_test_settings(
        horizon_years_int=horizon_years_int,
        portfolio_start_date=start_date,
        tax=TaxSettings(
            apply_final_liquidation_tax_bool=True,
            apply_grandfathering_bool=apply_grandfathering_bool,
        ),
    )
    return PortfolioSimulator(
        fund_list, settings
    ).run().fund_outcomes_list[0]


def test_grandfathering_uses_the_deemed_cost_of_acquisition() -> None:
    """Pre-2018 units are taxed against the 31 Jan 2018 value.

    REFERENCE: G2-STATUTORY and G4-SYNTHETIC. Under the proviso to
    section 112A the cost is deemed to be the higher of the actual
    cost and the lower of the 31 January 2018 fair market value
    and the sale value. A lump sum of Rs 1,00,000 invested on
    1 Jan 2015 at 12% is worth 1,00,000 x (1.12)^(37/12) =
    Rs 1,41,825.91 at the close of January 2018, and Rs 3,47,855
    after eleven years. The deemed cost is therefore Rs 1,41,825.91
    and the taxable gain Rs 2,06,029.09, taxed at 12.5%.
    """
    monthly_rate_float = (1.12) ** (1 / 12) - 1
    fair_value_float = GRANDFATHER_PRINCIPAL_FLOAT * (
        (1 + monthly_rate_float) ** 37
    )
    outcome = _run_grandfather_outcome(True)
    deemed_cost_float = max(
        GRANDFATHER_PRINCIPAL_FLOAT,
        min(fair_value_float, outcome.ending_value_float),
    )
    expected_tax_float = (
        outcome.ending_value_float - deemed_cost_float
    ) * (STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT / 100.0)
    assert outcome.final_liquidation_tax_float == pytest.approx(
        expected_tax_float
    )


def test_grandfathering_can_only_reduce_the_tax() -> None:
    """The deemed cost never falls below the actual cost.

    REFERENCE: G2-STATUTORY. The statutory formula takes the
    higher of actual cost and the capped fair value, so it can
    only raise the cost and therefore only shrink the gain.
    """
    with_relief = _run_grandfather_outcome(True)
    without_relief = _run_grandfather_outcome(False)
    assert (
        with_relief.final_liquidation_tax_float
        < without_relief.final_liquidation_tax_float
    )


def test_grandfathering_does_not_touch_post_cutoff_units() -> None:
    """Units bought after 1 Feb 2018 get no relief at all.

    REFERENCE: G2-STATUTORY. The proviso applies only to units
    acquired before 1 February 2018, so a modern plan must produce
    byte-identical tax whether the switch is on or off.
    """
    modern_start_date = date(2026, 1, 1)
    with_relief = _run_grandfather_outcome(
        True, modern_start_date, 10
    )
    without_relief = _run_grandfather_outcome(
        False, modern_start_date, 10
    )
    assert (
        with_relief.final_liquidation_tax_float
        == pytest.approx(
            without_relief.final_liquidation_tax_float
        )
    )


def test_grandfathering_never_applies_to_specified_funds() -> None:
    """Debt style funds sit outside section 112A entirely.

    REFERENCE: G2-STATUTORY. Specified funds under section 50AA
    are always short term and taxed at slab, so the section 112A
    proviso cannot reach them.
    """
    fund_list = [
        build_test_fund(
            "Debt",
            0.0,
            12.0,
            0.0,
            GRANDFATHER_START_DATE,
            initial_investment_float=GRANDFATHER_PRINCIPAL_FLOAT,
            exemption_amount_float=0.0,
            is_always_short_term_bool=True,
            short_term_tax_percent_float=30.0,
        )
    ]
    settings = build_test_settings(
        horizon_years_int=11,
        portfolio_start_date=GRANDFATHER_START_DATE,
        tax=TaxSettings(
            apply_final_liquidation_tax_bool=True,
            apply_grandfathering_bool=True,
        ),
    )
    outcome = PortfolioSimulator(
        fund_list, settings
    ).run().fund_outcomes_list[0]
    expected_tax_float = (
        outcome.ending_value_float - GRANDFATHER_PRINCIPAL_FLOAT
    ) * 0.30
    assert outcome.final_liquidation_tax_float == pytest.approx(
        expected_tax_float
    )


def _run_two_fund_exit_tax_float(
    exemption_level_str: str,
    portfolio_exemption_amount_float: float,
) -> float:
    """Exit tax of two identical equity funds under one setting.

    REFERENCE: harness only.
    """
    fund_list = [
        build_test_fund(
            name_str,
            10000.0,
            12.0,
            0.0,
            date(2026, 1, 1),
            exemption_amount_float=(
                STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
            ),
            long_term_tax_percent_float=(
                STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT
            ),
        )
        for name_str in ("Alpha", "Beta")
    ]
    return PortfolioSimulator(
        fund_list,
        build_test_settings(
            horizon_years_int=15,
            tax=TaxSettings(
                apply_final_liquidation_tax_bool=True,
                exemption_level_str=exemption_level_str,
                portfolio_exemption_amount_float=(
                    portfolio_exemption_amount_float
                ),
            ),
        ),
    ).run().final_liquidation_tax_float


def test_exit_estimate_shares_one_exemption_across_funds() -> None:
    """Two funds exiting together share one taxpayer allowance.

    REFERENCE: G2-STATUTORY. Section 112A relief belongs to the
    taxpayer, so a whole-portfolio exit may consume it once. This
    is a regression test: each fund's exit estimate previously ran
    against its own private copy of the ledger, so a two-fund plan
    claimed Rs 1,25,000 twice and understated the tax by exactly
    one allowance at the long term rate.
    """
    per_fund_float = _run_two_fund_exit_tax_float(
        EXEMPTION_LEVEL_FUND_STR, 0.0
    )
    per_taxpayer_float = _run_two_fund_exit_tax_float(
        EXEMPTION_LEVEL_PORTFOLIO_STR,
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
    )
    extra_tax_float = per_taxpayer_float - per_fund_float
    assert extra_tax_float == pytest.approx(
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
        * STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT
        / 100.0
    )


# ------------------------------------------------------------------
# Income that changes over a lifetime
# ------------------------------------------------------------------
def test_a_plan_with_no_dated_income_keeps_its_single_figure(
) -> None:
    """The existing single-income behaviour must be preserved.

    REFERENCE: G4-SYNTHETIC. Every saved scenario predates dated
    income and must value identically after the change.
    """
    settings = TaxSettings(total_income_float=6_000_000.0)
    assert resolve_total_income_float(
        settings, 2031
    ) == pytest.approx(6_000_000.0)


@pytest.mark.parametrize(
    ("financial_year_int", "expected_income_float"),
    [
        (2029, 4_000_000.0),
        (2030, 6_000_000.0),
        (2031, 6_000_000.0),
        (2032, 25_000_000.0),
        (2040, 25_000_000.0),
    ],
)
def test_the_income_in_force_is_the_latest_one_declared(
    financial_year_int: int,
    expected_income_float: float,
) -> None:
    """A raise must apply from its year, not before or never.

    REFERENCE: G4-SYNTHETIC. Income of 40 lakh until FY 2030, then
    60 lakh, then 2.5 crore from FY 2032. Years before the first
    entry fall back to the plan's opening income.
    """
    settings = TaxSettings(
        total_income_float=4_000_000.0,
        income_by_year_tuple=(
            (2030, 6_000_000.0),
            (2032, 25_000_000.0),
        ),
    )
    assert resolve_total_income_float(
        settings, financial_year_int
    ) == pytest.approx(expected_income_float)


def test_a_later_raise_never_inflates_an_earlier_surcharge(
) -> None:
    """Selling before the raise must be taxed at the old band.

    REFERENCE: G2-STATUTORY. Surcharge is judged on the income of
    the year of the transfer. In FY 2029 the income is 40 lakh, so
    no surcharge applies at all; by FY 2032 it is 2.5 crore, which
    reaches the 25% band and is then capped at 15% for equity.
    """
    settings = TaxSettings(
        surcharge_mode_str=SURCHARGE_MODE_SLAB_STR,
        total_income_float=4_000_000.0,
        income_by_year_tuple=((2032, 25_000_000.0),),
    )
    assert resolve_surcharge_percent_float(
        settings, 2029
    ) == pytest.approx(0.0)
    assert resolve_surcharge_percent_float(
        settings, 2032
    ) == pytest.approx(25.0)


def test_dated_income_reaches_the_capital_gains_tax_bill(
    single_equity_fund_list: list,
) -> None:
    """The year of the sale must decide the surcharge charged.

    REFERENCE: G4-SYNTHETIC. The same gain sold in two different
    financial years must be taxed differently when the taxpayer's
    income crossed a surcharge threshold in between. Sales are in
    June, so the financial years are 2030 and 2032.
    """
    settings = TaxSettings(
        surcharge_mode_str=SURCHARGE_MODE_SLAB_STR,
        total_income_float=4_000_000.0,
        income_by_year_tuple=((2032, 25_000_000.0),),
    )
    early_policy = CapitalGainsTaxPolicy(
        single_equity_fund_list[0], ExemptionLedger(), settings
    )
    late_policy = CapitalGainsTaxPolicy(
        single_equity_fund_list[0], ExemptionLedger(), settings
    )
    early_tax_float = early_policy.calculate_tax_breakdown(
        100000.0, 24, date(2030, 6, 1)
    ).tax_amount_float
    late_tax_float = late_policy.calculate_tax_breakdown(
        100000.0, 24, date(2032, 6, 1)
    ).tax_amount_float
    assert early_tax_float == pytest.approx(100000.0 * 0.125)
    assert late_tax_float == pytest.approx(
        100000.0 * 0.125 * 1.15
    )


def test_manual_surcharge_mode_ignores_dated_income() -> None:
    """A typed rate must stay typed however income moves.

    REFERENCE: G4-SYNTHETIC. Manual mode means the user has
    already done this arithmetic themselves.
    """
    settings = TaxSettings(
        surcharge_mode_str=SURCHARGE_MODE_MANUAL_STR,
        surcharge_percent_float=7.0,
        income_by_year_tuple=((2032, 250_000_000.0),),
    )
    assert resolve_surcharge_percent_float(
        settings, 2032
    ) == pytest.approx(7.0)


# ------------------------------------------------------------------
# Tax year boundaries outside India
#
# The annual exemption resets, and a carried-forward loss expires,
# on the tax year boundary. A jurisdiction that does not run April
# to March has to move both. Every test below is built so that the
# April default would give the opposite answer - otherwise it would
# pass whether or not the setting were honoured at all.
# ------------------------------------------------------------------
LONG_TERM_MONTHS_INT: int = 24
LONG_TERM_RATE_FLOAT: float = (
    STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT / 100.0
)


def build_exempting_policy(
    start_month_int: int,
) -> CapitalGainsTaxPolicy:
    """Build a policy whose exemption resets on a given month.

    REFERENCE: harness only; one fund carrying the full statutory
    exemption, with the tax year opening where asked.
    """
    return build_policy(
        exemption_amount_float=(
            STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
        ),
        tax_settings=TaxSettings(
            tax_year_start_month_int=start_month_int
        ),
    )


def sheltered_tax_float(
    policy: CapitalGainsTaxPolicy,
    sale_date: date,
) -> float:
    """Realize exactly one exemption's worth of long term gain.

    REFERENCE: harness only; returns the tax the sale attracted.
    """
    return policy.calculate_tax_breakdown(
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
        LONG_TERM_MONTHS_INT,
        sale_date,
    ).tax_amount_float


def test_calendar_tax_year_resets_exemption_in_january() -> None:
    """December and January must draw on different exemptions.

    REFERENCE: G4-SYNTHETIC. Under India's April year these two
    sales share financial year 2030 and the second would be taxed
    in full, so a passing result proves the setting is read.
    """
    policy = build_exempting_policy(
        TAX_YEAR_START_MONTH_CALENDAR_INT
    )
    assert sheltered_tax_float(
        policy, date(2030, 12, 1)
    ) == pytest.approx(0.0)
    assert sheltered_tax_float(
        policy, date(2031, 1, 1)
    ) == pytest.approx(0.0)


def test_calendar_tax_year_does_not_reset_in_april() -> None:
    """January and June must share one calendar exemption.

    REFERENCE: G4-SYNTHETIC. Under India's April year these fall
    in financial years 2029 and 2030 and both would be sheltered.
    """
    policy = build_exempting_policy(
        TAX_YEAR_START_MONTH_CALENDAR_INT
    )
    assert sheltered_tax_float(
        policy, date(2030, 1, 1)
    ) == pytest.approx(0.0)
    assert sheltered_tax_float(
        policy, date(2030, 6, 1)
    ) == pytest.approx(
        STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
        * LONG_TERM_RATE_FLOAT
    )


def test_australian_tax_year_resets_exemption_in_july() -> None:
    """June and July must draw on different exemptions.

    REFERENCE: G4-SYNTHETIC. Australia runs 1 July to 30 June.
    Under India's April year both sales sit in 2030 and the second
    would be taxed in full.
    """
    policy = build_exempting_policy(
        TAX_YEAR_START_MONTH_AUSTRALIA_INT
    )
    assert sheltered_tax_float(
        policy, date(2030, 6, 1)
    ) == pytest.approx(0.0)
    assert sheltered_tax_float(
        policy, date(2030, 7, 1)
    ) == pytest.approx(0.0)


def build_calendar_loss_policy() -> CapitalGainsTaxPolicy:
    """Build an exemption-free policy on a calendar tax year.

    REFERENCE: harness only; isolates loss set-off from shelter.
    """
    return build_policy(
        tax_settings=TaxSettings(
            tax_year_start_month_int=(
                TAX_YEAR_START_MONTH_CALENDAR_INT
            )
        ),
    )


def test_calendar_loss_survives_its_eighth_carry_year() -> None:
    """A January loss must still shelter a gain eight years on.

    REFERENCE: G2-STATUTORY, section 74 read on a calendar year.
    The loss is computed in 2030 and set off in 2038, the eighth
    year after. Under India's April year the loss would fall in
    2029, expire in 2037 and leave this gain fully taxed.
    """
    assert LOSS_CARRY_FORWARD_YEARS_INT == 8
    policy = build_calendar_loss_policy()
    policy.calculate_tax_breakdown(
        -100000.0, LONG_TERM_MONTHS_INT, date(2030, 1, 1)
    )
    breakdown = policy.calculate_tax_breakdown(
        100000.0, LONG_TERM_MONTHS_INT, date(2038, 12, 1)
    )
    assert breakdown.tax_amount_float == pytest.approx(0.0)
    assert breakdown.offset_loss_float == pytest.approx(100000.0)


def test_calendar_loss_expires_in_its_ninth_carry_year() -> None:
    """One month later the same loss must be gone.

    REFERENCE: G2-STATUTORY, section 74. A loss computed in 2030
    cannot be set off in 2039, so the gain is taxed in full and
    nothing is offset against it.
    """
    policy = build_calendar_loss_policy()
    policy.calculate_tax_breakdown(
        -100000.0, LONG_TERM_MONTHS_INT, date(2030, 1, 1)
    )
    breakdown = policy.calculate_tax_breakdown(
        100000.0, LONG_TERM_MONTHS_INT, date(2039, 1, 1)
    )
    assert breakdown.tax_amount_float == pytest.approx(
        100000.0 * LONG_TERM_RATE_FLOAT
    )
    assert breakdown.offset_loss_float == pytest.approx(0.0)
