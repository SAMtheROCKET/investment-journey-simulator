"""Ground-truth references and independent reimplementations.

Provenance tags used across the whole test suite:

    G1-ANALYTIC     Closed-form mathematics or a standard financial
                    function (identical to spreadsheet FV/PV). The
                    expected value is computed live from the formula,
                    so the test cannot drift from the definition.
    G2-STATUTORY    Indian Income-tax Act parameters, applicable
                    to transfers on or after 23 July 2024 under the
                    Finance (No. 2) Act 2024. Every value below was
                    checked against published sources on
                    2026-08-04; see tests/README.md for the list.
                    Re-verify after each Budget.
    G3-CROSSCHECK   Values produced by an independent earlier
                    implementation, `notebooks/testing.ipynb`, written
                    before this package existed. Agreement between
                    two independent implementations is the check.
    G4-SYNTHETIC    Hand-derived scenario whose arithmetic is shown
                    in the test docstring.
    G5-PLAUSIBILITY Real-world magnitudes used only as realistic
                    inputs, never asserted as truth.

The reimplementations below are copied from `notebooks/testing.ipynb`
deliberately. They must stay naive and independent of the package.
"""

from __future__ import annotations

# ------------------------------------------------------------------
# G2-STATUTORY: equity-oriented mutual funds, transfers on or after
# 23 July 2024 (Finance (No. 2) Act 2024).
# ------------------------------------------------------------------
STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT: float = 20.0
STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT: float = 12.5
STATUTORY_EQUITY_THRESHOLD_MONTHS_INT: int = 12
STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT: float = 125000.0
STATUTORY_FINANCIAL_YEAR_START_MONTH_INT: int = 4
STATUTORY_DEBT_IS_ALWAYS_SHORT_TERM_BOOL: bool = True
STATUTORY_CESS_PERCENT_FLOAT: float = 4.0
STATUTORY_MAXIMUM_GAINS_SURCHARGE_PERCENT_FLOAT: float = 15.0
STATUTORY_EQUITY_REDEMPTION_STT_PERCENT_FLOAT: float = 0.001
STATUTORY_SOURCE_CHECK_DATE_STR: str = "2026-08-04"

# ------------------------------------------------------------------
# G2-STATUTORY: marginal relief on the surcharge.
#
# Old regime tax at fifty lakh, computed by hand from the slabs:
#     5% x  2,50,000  =    12,500
#    20% x  5,00,000  =  1,00,000
#    30% x 40,00,000  = 12,00,000
#                       ---------
#                       13,12,500
#
# Relief runs out when the extra tax equals the extra income:
#    0.10 x 13,12,500 / 0.67 = 1,95,895.52
# so the window closes at 50,00,000 + 1,95,896 = 51,95,896. That
# figure appears in published commentary and is the reason this
# boundary, rather than a new-regime one, is the anchor test.
# ------------------------------------------------------------------
STATUTORY_OLD_REGIME_TAX_AT_FIFTY_LAKH_FLOAT: float = 1_312_500.0
STATUTORY_RELIEF_WINDOW_CLOSE_RUPEES_FLOAT: float = 5_195_896.0

# ------------------------------------------------------------------
# G5-PLAUSIBILITY: realistic Indian market magnitudes used as inputs.
# ------------------------------------------------------------------
PLAUSIBLE_EQUITY_RETURN_PERCENT_FLOAT: float = 12.0
PLAUSIBLE_DEBT_RETURN_PERCENT_FLOAT: float = 7.0
PLAUSIBLE_INFLATION_PERCENT_FLOAT: float = 6.0
PLAUSIBLE_EQUITY_EXPENSE_PERCENT_FLOAT: float = 0.5
PLAUSIBLE_INDEX_FUND_EXPENSE_PERCENT_FLOAT: float = 0.2
PLAUSIBLE_SLAB_RATE_PERCENT_FLOAT: float = 30.0

# ------------------------------------------------------------------
# G3-CROSSCHECK: expected dictionaries copied verbatim from
# notebooks/testing.ipynb. Keys are horizons in years.
# ------------------------------------------------------------------
NOTEBOOK_SIP_EXPECTED_DICT: dict[int, dict[str, float]] = {
    1: {"invested": 1200.0, "future_value": 1276.6498},
    2: {"invested": 2400.0, "future_value": 2706.4976},
    3: {"invested": 3600.0, "future_value": 4307.9271},
    5: {"invested": 6000.0, "future_value": 8110.3613},
    10: {"invested": 12000.0, "future_value": 22403.589},
    11: {"invested": 13200.0, "future_value": 26368.6694},
    15: {"invested": 18000.0, "future_value": 47593.1399},
    25: {"invested": 30000.0, "future_value": 170220.6573},
}

NOTEBOOK_STEPUP_EXPECTED_DICT: dict[int, dict[str, float]] = {
    1: {"invested": 1200.0, "future_value": 1276.6498},
    2: {"invested": 2520.0, "future_value": 2834.1625},
    3: {"invested": 3972.0, "future_value": 4719.0083},
    5: {"invested": 7326.12, "future_value": 9691.7943},
    10: {"invested": 19124.9095, "future_value": 32688.9848},
    11: {"invested": 22237.4005, "future_value": 39922.9638},
    15: {"invested": 38126.978, "future_value": 82747.179},
    25: {"invested": 118016.4713, "future_value": 393550.1796},
}

NOTEBOOK_LUMPSUM_EXPECTED_DICT: dict[int, float] = {
    1: 112.0,
    2: 125.44,
    3: 140.4928,
    5: 176.2342,
    10: 310.5848,
    11: 347.855,
    15: 547.3566,
    25: 1700.0064,
}

NOTEBOOK_THREE_FUND_FIFTEEN_YEAR_DICT: dict[float, float] = {
    10.0: 1204863.65,
    12.0: 1427794.20,
    14.0: 1695621.41,
}

NOTEBOOK_SIP_GAP_EXPECTED_DICT: dict[int, float] = {
    2: 101804.5699,
    4: 109224.1983,
    6: 115356.1226,
}


def reference_sip_future_value_float(
    monthly_amount_float: float,
    annual_return_percent_float: float,
    years_int: int,
    is_annuity_due_bool: bool = False,
) -> float:
    """Reimplementation of the notebook's SIP future value.

    Brief:
        G1-ANALYTIC and G3-CROSSCHECK. Standard annuity formula,
        identical to a spreadsheet FV() with the same sign
        convention, kept independent of the package on purpose.

    Arguments:
        monthly_amount_float (float): Instalment per month.
        annual_return_percent_float (float): Annual return percent.
        years_int (int): Horizon in whole years.
        is_annuity_due_bool (bool): True for start-of-month.

    Returns:
        float: Future value of the instalment stream.

    Warning:
        Deliberately naive; never optimise or refactor this to use
        package code, or the cross-check becomes circular.
    """
    annual_rate_float = annual_return_percent_float / 100.0
    total_months_int = 12 * years_int
    monthly_rate_float = (1 + annual_rate_float) ** (1 / 12) - 1
    future_value_float = (
        monthly_amount_float
        * ((1 + monthly_rate_float) ** total_months_int - 1)
        / monthly_rate_float
    )
    if is_annuity_due_bool:
        future_value_float *= 1 + monthly_rate_float
    return future_value_float


def reference_stepup_future_value_float(
    monthly_amount_float: float,
    annual_return_percent_float: float,
    years_int: int,
    stepup_percent_float: float = 10.0,
    is_annuity_due_bool: bool = False,
) -> float:
    """Reimplementation of the notebook's step-up SIP.

    Brief:
        G3-CROSSCHECK. Escalates the instalment on every twelfth
        month and compounds month by month.

    Arguments:
        monthly_amount_float (float): Starting instalment.
        annual_return_percent_float (float): Annual return percent.
        years_int (int): Horizon in whole years.
        stepup_percent_float (float): Yearly escalation percent.
        is_annuity_due_bool (bool): True for start-of-month.

    Returns:
        float: Future value of the escalating stream.

    Warning:
        Deliberately naive; keep it independent of the package.
    """
    monthly_rate_float = (
        1 + annual_return_percent_float / 100.0
    ) ** (1 / 12) - 1
    future_value_float = 0.0
    current_instalment_float = monthly_amount_float
    for month_index_int in range(years_int * 12):
        if month_index_int > 0 and month_index_int % 12 == 0:
            current_instalment_float *= (
                1 + stepup_percent_float / 100.0
            )
        if is_annuity_due_bool:
            future_value_float = (
                future_value_float + current_instalment_float
            ) * (1 + monthly_rate_float)
        else:
            future_value_float = (
                future_value_float * (1 + monthly_rate_float)
                + current_instalment_float
            )
    return future_value_float


def reference_lumpsum_future_value_float(
    principal_float: float,
    annual_return_percent_float: float,
    years_int: int,
) -> float:
    """Reimplementation of the notebook's lumpsum growth.

    Brief:
        G1-ANALYTIC and G3-CROSSCHECK. Plain annual compounding.

    Arguments:
        principal_float (float): Amount invested once.
        annual_return_percent_float (float): Annual return percent.
        years_int (int): Horizon in whole years.

    Returns:
        float: Future value of the lump sum.

    Warning:
        Compounds annually, so it matches monthly compounding only
        because the effective monthly rate is derived from it.
    """
    return principal_float * (
        1 + annual_return_percent_float / 100.0
    ) ** years_int


def reference_swp_remaining_corpus_float(
    principal_float: float,
    annual_return_percent_float: float,
    years_int: int,
    monthly_withdrawal_float: float,
    is_annuity_due_bool: bool = False,
) -> float:
    """Reimplementation of the notebook's withdrawal plan.

    Brief:
        G3-CROSSCHECK. Ordinary timing grows the corpus first and
        then withdraws, which is the convention the engine uses.

    Arguments:
        principal_float (float): Opening corpus.
        annual_return_percent_float (float): Annual return percent.
        years_int (int): Horizon in whole years.
        monthly_withdrawal_float (float): Amount taken monthly.
        is_annuity_due_bool (bool): True withdraws before growth.

    Returns:
        float: Corpus remaining at the end of the horizon.

    Warning:
        Stops at zero once the corpus is exhausted.
    """
    monthly_rate_float = (
        1 + annual_return_percent_float / 100.0
    ) ** (1 / 12) - 1
    corpus_float = float(principal_float)
    for _month_index_int in range(years_int * 12):
        if is_annuity_due_bool:
            corpus_float -= monthly_withdrawal_float
            if corpus_float <= 0:
                return 0.0
            corpus_float *= 1 + monthly_rate_float
        else:
            corpus_float *= 1 + monthly_rate_float
            corpus_float -= monthly_withdrawal_float
            if corpus_float <= 0:
                return 0.0
    return corpus_float


def reference_sip_with_gap_future_value_float(
    monthly_amount_float: float,
    annual_return_percent_float: float,
    years_int: int,
    gap_years_int: int,
    gap_start_year_int: int,
    is_annuity_due_bool: bool = False,
) -> float:
    """Reimplementation of the notebook's paused SIP.

    Brief:
        G3-CROSSCHECK. Skips whole years of instalments.

    Arguments:
        monthly_amount_float (float): Instalment.
        annual_return_percent_float (float): Annual return.
        years_int (int): Horizon in years.
        gap_years_int (int): Number of paused years.
        gap_start_year_int (int): First paused year.
        is_annuity_due_bool (bool): Start-of-month flag.

    Returns:
        float: Future value after the pause.

    Warning:
        Deliberately naive.
    """
    monthly_rate_float = (
        1 + annual_return_percent_float / 100.0
    ) ** (1 / 12) - 1
    gap_start_month_int = (gap_start_year_int - 1) * 12
    gap_end_month_int = gap_start_month_int + gap_years_int * 12
    future_value_float = 0.0
    for month_index_int in range(years_int * 12):
        is_paused_bool = (
            gap_start_month_int <= month_index_int
            < gap_end_month_int
        )
        if is_paused_bool:
            future_value_float *= 1 + monthly_rate_float
        elif is_annuity_due_bool:
            future_value_float = (
                future_value_float + monthly_amount_float
            ) * (1 + monthly_rate_float)
        else:
            future_value_float = (
                future_value_float * (1 + monthly_rate_float)
                + monthly_amount_float
            )
    return future_value_float


def reference_old_regime_income_tax_float(
    total_income_float: float,
) -> float:
    """Naive old-regime income tax, written out slab by slab.

    Brief:
        G2-STATUTORY and G4-SYNTHETIC. Spelled out longhand rather
        than looped so the slab boundaries are readable, and kept
        independent of the package on purpose.

    Arguments:
        total_income_float (float): Total income for the year.

    Returns:
        float: Income tax before surcharge and cess.

    Warning:
        Deliberately naive; never refactor this to call package
        code, or the cross-check becomes circular.
    """
    tax_float = 0.0
    if total_income_float > 250_000.0:
        tax_float += 0.05 * (
            min(total_income_float, 500_000.0) - 250_000.0
        )
    if total_income_float > 500_000.0:
        tax_float += 0.20 * (
            min(total_income_float, 1_000_000.0) - 500_000.0
        )
    if total_income_float > 1_000_000.0:
        tax_float += 0.30 * (total_income_float - 1_000_000.0)
    return tax_float


def reference_surcharge_payable_float(
    total_income_float: float,
    band_percent_float: float,
    threshold_float: float,
    previous_band_percent_float: float = 0.0,
) -> float:
    """Naive surcharge after marginal relief, in rupees.

    Brief:
        G2-STATUTORY. States the rule directly: the tax plus
        surcharge at this income may not exceed what would be owed
        at the threshold plus every rupee earned above it.

    Arguments:
        total_income_float (float): Total income for the year.
        band_percent_float (float): Surcharge band rate percent.
        threshold_float (float): Income floor of that band.
        previous_band_percent_float (float): Rate below the floor.

    Returns:
        float: Surcharge actually payable, never below zero.

    Warning:
        Old regime only, since it uses the old-regime tax function.
        Relief is computed before cess, as the Act prescribes.
    """
    tax_float = reference_old_regime_income_tax_float(
        total_income_float
    )
    surcharge_float = tax_float * band_percent_float / 100.0
    tax_at_threshold_float = reference_old_regime_income_tax_float(
        threshold_float
    )
    capped_liability_float = (
        tax_at_threshold_float
        * (1.0 + previous_band_percent_float / 100.0)
        + (total_income_float - threshold_float)
    )
    relief_float = max(
        0.0,
        tax_float + surcharge_float - capped_liability_float,
    )
    return max(0.0, surcharge_float - relief_float)
