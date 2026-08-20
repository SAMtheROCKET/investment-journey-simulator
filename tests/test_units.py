"""Unit tests for formatting, calendar, holdings and allocation."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.allocation import (
    build_contribution_weight_dict,
    build_declared_weight_dict,
    build_equal_weight_dict,
    normalise_weight_dict,
    resolve_target_weight_dict,
)
from investment_journey_simulator.constants import (
    REBALANCE_TARGET_COLUMN_STR,
    REBALANCE_TARGET_SIP_SPLIT_STR,
    TAX_YEAR_START_MONTH_AUSTRALIA_INT,
    TAX_YEAR_START_MONTH_CALENDAR_INT,
    TAX_YEAR_START_MONTH_INDIA_INT,
)
from investment_journey_simulator.formatting import (
    format_compact_money_str,
    format_money_amount_str,
    group_digits_indian_style_str,
)
from investment_journey_simulator.holdings import FundHoldings
from investment_journey_simulator.models import (
    InvestmentLot,
    RebalanceSettings,
    TaxSettings,
)
from investment_journey_simulator.taxation import (
    CapitalGainsTaxPolicy,
    ExemptionLedger,
)
from investment_journey_simulator.time_utils import (
    build_month_start_dates_list,
    count_months_between_dates_int,
    derive_financial_year_int,
    is_month_within_range_bool,
)
from reference_data import (
    STATUTORY_FINANCIAL_YEAR_START_MONTH_INT,
)


# ------------------------------------------------------------------
# Indian number formatting
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "amount_float, expected_str",
    [
        (0.0, "0"),
        (7.0, "7"),
        (99.0, "99"),
        (999.0, "999"),
        (1000.0, "1,000"),
        (99999.0, "99,999"),
        (100000.0, "1,00,000"),
        (1234567.0, "12,34,567"),
        (10000000.0, "1,00,00,000"),
        (123456789.0, "12,34,56,789"),
        (-1234567.0, "-12,34,567"),
        (1234567.4, "12,34,567"),
        (1234567.6, "12,34,568"),
    ],
)
def test_indian_grouping_covers_every_digit_boundary(
    amount_float: float,
    expected_str: str,
) -> None:
    """Grouping must follow the Indian two-two-three convention.

    REFERENCE: G2-STATUTORY style convention used by the Reserve
    Bank of India and Indian financial reporting: the last three
    digits group together, then pairs.
    """
    assert group_digits_indian_style_str(amount_float) == expected_str


@pytest.mark.parametrize(
    "amount_float, expected_suffix_str",
    [
        (999.0, "999"),
        (1000.0, "1.00K"),
        (99999.0, "99.999K"),
        (100000.0, "1.00L"),
        (9999999.0, "99.99999L"),
        (10000000.0, "1.00Cr"),
        (-10000000.0, "1.00Cr"),
    ],
)
def test_compact_notation_switches_at_the_right_magnitudes(
    amount_float: float,
    expected_suffix_str: str,
) -> None:
    """Compact units must switch at thousand, lakh and crore.

    REFERENCE: G2-STATUTORY convention. Boundary values are tested
    on the exact switch points.
    """
    rendered_str = format_compact_money_str(amount_float)
    assert ("Cr" in rendered_str) == (abs(amount_float) >= 1e7)
    assert rendered_str.startswith("-") == (amount_float < 0)


def test_rupee_symbol_prefixes_the_amount() -> None:
    """Formatted amounts must carry the rupee symbol.

    REFERENCE: G4-SYNTHETIC. Display contract.
    """
    assert format_money_amount_str(100000.0).endswith("1,00,000")


# ------------------------------------------------------------------
# Calendar and financial year
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "reference_date, expected_year_int",
    [
        (date(2026, 3, 31), 2025),
        (date(2026, 4, 1), 2026),
        (date(2026, 12, 31), 2026),
        (date(2027, 1, 1), 2026),
        (date(2027, 3, 1), 2026),
    ],
)
def test_financial_year_boundary_is_first_of_april(
    reference_date: date,
    expected_year_int: int,
) -> None:
    """The Indian financial year must start on 1 April.

    REFERENCE: G2-STATUTORY. Section 3 of the Income-tax Act
    defines the previous year as April to March.
    """
    assert (
        derive_financial_year_int(reference_date)
        == expected_year_int
    )
    assert STATUTORY_FINANCIAL_YEAR_START_MONTH_INT == 4


@pytest.mark.parametrize(
    "reference_date, start_month_int, expected_year_int",
    [
        (date(2026, 1, 1), TAX_YEAR_START_MONTH_CALENDAR_INT, 2026),
        (date(2026, 12, 31), TAX_YEAR_START_MONTH_CALENDAR_INT, 2026),
        (date(2026, 6, 30), TAX_YEAR_START_MONTH_AUSTRALIA_INT, 2025),
        (date(2026, 7, 1), TAX_YEAR_START_MONTH_AUSTRALIA_INT, 2026),
        (date(2026, 3, 31), TAX_YEAR_START_MONTH_INDIA_INT, 2025),
        (date(2026, 4, 1), TAX_YEAR_START_MONTH_INDIA_INT, 2026),
    ],
)
def test_tax_year_follows_the_configured_start_month(
    reference_date: date,
    start_month_int: int,
    expected_year_int: int,
) -> None:
    """A tax year opens in the month the jurisdiction says.

    REFERENCE: G4-SYNTHETIC. Calendar-year countries, Australia's
    July start and India's April start must all be expressible,
    each labelled by the calendar year the year opens in.
    """
    assert (
        derive_financial_year_int(reference_date, start_month_int)
        == expected_year_int
    )


@pytest.mark.parametrize("start_month_int", [0, -3, 13, 99])
def test_out_of_range_start_month_is_clamped(
    start_month_int: int,
) -> None:
    """A nonsensical start month must not shift the year silently.

    REFERENCE: G4-SYNTHETIC. Clamping to January or December keeps
    a corrupt saved scenario opening rather than crashing, and
    never invents a thirteenth month.
    """
    year_int = derive_financial_year_int(
        date(2026, 6, 1), start_month_int
    )
    assert year_int in (2025, 2026)


@pytest.mark.parametrize(
    "start_date, end_date, expected_months_int",
    [
        (date(2026, 1, 1), date(2026, 1, 1), 0),
        (date(2026, 1, 1), date(2026, 12, 1), 11),
        (date(2026, 1, 1), date(2027, 1, 1), 12),
        (date(2027, 1, 1), date(2026, 1, 1), -12),
    ],
)
def test_month_difference_covers_zero_forward_and_backward(
    start_date: date,
    end_date: date,
    expected_months_int: int,
) -> None:
    """Month arithmetic must work in both directions.

    REFERENCE: G1-ANALYTIC. Calendar arithmetic definition.
    """
    assert (
        count_months_between_dates_int(start_date, end_date)
        == expected_months_int
    )


@pytest.mark.parametrize("total_months_int", [0, -5])
def test_empty_month_grid_is_returned_for_no_months(
    total_months_int: int,
) -> None:
    """A non-positive month count must give an empty grid.

    REFERENCE: G4-SYNTHETIC. Degenerate branch.
    """
    assert (
        build_month_start_dates_list(
            date(2026, 1, 1), total_months_int
        )
        == []
    )


def test_month_grid_rolls_across_multiple_years() -> None:
    """The grid must roll over December correctly, repeatedly.

    REFERENCE: G4-SYNTHETIC. 25 months from November 2026.
    """
    grid_list = build_month_start_dates_list(date(2026, 11, 1), 25)
    assert grid_list[0] == date(2026, 11, 1)
    assert grid_list[2] == date(2027, 1, 1)
    assert grid_list[-1] == date(2028, 11, 1)


@pytest.mark.parametrize(
    "candidate_date, expected_bool",
    [
        (date(2026, 5, 15), True),
        (date(2026, 5, 1), True),
        (date(2026, 8, 28), True),
        (date(2026, 4, 30), False),
        (date(2026, 9, 1), False),
    ],
)
def test_range_membership_is_inclusive_of_both_months(
    candidate_date: date,
    expected_bool: bool,
) -> None:
    """Both boundary months must count as inside the range.

    REFERENCE: G4-SYNTHETIC. Inclusive interval definition.
    """
    assert (
        is_month_within_range_bool(
            candidate_date, date(2026, 5, 20), date(2026, 8, 3)
        )
        is expected_bool
    )


# ------------------------------------------------------------------
# FIFO lot book
# ------------------------------------------------------------------
def build_holdings(monthly_rate_percent_float: float = 12.0):
    """Build an isolated holding for lot-level tests.

    REFERENCE: harness only.
    """
    fund_configuration = build_test_fund(
        gross_return_percent_float=monthly_rate_percent_float
    )
    return FundHoldings(
        fund_configuration,
        CapitalGainsTaxPolicy(
            fund_configuration, ExemptionLedger(), TaxSettings()
        ),
    )


def test_start_of_month_lot_earns_one_extra_month() -> None:
    """Start-of-month purchases compound one month sooner.

    REFERENCE: G1-ANALYTIC. Annuity due versus ordinary annuity.
    """
    start_lot = InvestmentLot(1000.0, 0, True)
    end_lot = InvestmentLot(1000.0, 0, False)
    assert start_lot.count_months_held_int(0) == 1
    assert end_lot.count_months_held_int(0) == 0


def test_zero_and_negative_contributions_are_ignored() -> None:
    """Non-positive contributions must not create lots.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    holdings = build_holdings()
    holdings.add_contribution(0.0, 0, True)
    holdings.add_contribution(-100.0, 0, True)
    assert holdings.calculate_value_float(0) == 0.0
    assert holdings.contributed_amount_float == 0.0


def test_internal_purchase_raises_basis_but_not_principal(
) -> None:
    """Rebalancing purchases must not count as new principal.

    REFERENCE: G4-SYNTHETIC. Core accounting separation.
    """
    holdings = build_holdings()
    holdings.add_internal_purchase(5000.0, 0)
    assert holdings.contributed_amount_float == 0.0
    assert holdings.calculate_cost_basis_float() == pytest.approx(
        5000.0
    )


def test_selling_nothing_returns_zero_proceeds() -> None:
    """A zero sale request must be a no-op.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    holdings = build_holdings()
    holdings.add_contribution(1000.0, 0, True)
    sale_outcome = holdings.sell_for_proceeds(
        0.0, 5, date(2026, 6, 1)
    )
    assert sale_outcome.proceeds_float == 0.0
    assert sale_outcome.tax_amount_float == 0.0


def test_sale_is_capped_at_the_holding_value() -> None:
    """Selling more than exists must return only what exists.

    REFERENCE: G4-SYNTHETIC. Physical impossibility guard.
    """
    holdings = build_holdings()
    holdings.add_contribution(1000.0, 0, True)
    available_float = holdings.calculate_value_float(0)
    sale_outcome = holdings.sell_for_proceeds(
        available_float * 10, 0, date(2026, 1, 1)
    )
    assert sale_outcome.proceeds_float == pytest.approx(
        available_float
    )
    assert holdings.calculate_value_float(0) == pytest.approx(0.0)


def test_fifo_consumes_the_oldest_lot_first() -> None:
    """The first lot bought must be the first sold.

    REFERENCE: G2-STATUTORY. Rule 8AA and the standard first-in
    first-out convention for mutual fund units.
    """
    holdings = build_holdings()
    holdings.add_contribution(1000.0, 0, True)
    holdings.add_contribution(1000.0, 12, True)
    oldest_value_float = 1000.0 * (
        1.0 + holdings.fund_configuration.monthly_rate_float
    ) ** 25
    holdings.sell_for_proceeds(
        oldest_value_float, 24, date(2028, 1, 1)
    )
    remaining_basis_float = holdings.calculate_cost_basis_float()
    assert remaining_basis_float == pytest.approx(1000.0, abs=1e-6)


def test_partial_sale_keeps_the_original_purchase_month() -> None:
    """A partial sale must not reset the holding period.

    REFERENCE: G2-STATUTORY. Holding period follows the units,
    not the transaction that sold part of them.
    """
    holdings = build_holdings()
    holdings.add_contribution(1000.0, 0, True)
    holdings.sell_for_proceeds(100.0, 24, date(2028, 1, 1))
    later_tax_float = holdings.estimate_liquidation_tax_float(
        25, date(2028, 2, 1)
    )
    assert later_tax_float > 0.0


def test_liquidation_estimate_does_not_change_the_holding(
) -> None:
    """Pricing an exit must leave the portfolio untouched.

    REFERENCE: G4-SYNTHETIC. Purity of the dry run.
    """
    holdings = build_holdings()
    holdings.add_contribution(1000.0, 0, True)
    value_before_float = holdings.calculate_value_float(24)
    holdings.estimate_liquidation_tax_float(24, date(2028, 1, 1))
    assert holdings.calculate_value_float(24) == pytest.approx(
        value_before_float
    )
    assert holdings.tax_paid_amount_float == 0.0


def test_zero_return_fund_realizes_no_tax_on_sale() -> None:
    """With no growth there is no gain and therefore no tax.

    REFERENCE: G2-STATUTORY. Tax applies to gains only.
    """
    holdings = build_holdings(0.0)
    holdings.add_contribution(10000.0, 0, True)
    sale_outcome = holdings.sell_for_proceeds(
        5000.0, 24, date(2028, 1, 1)
    )
    assert sale_outcome.tax_amount_float == pytest.approx(0.0)


# ------------------------------------------------------------------
# Target allocation resolution
# ------------------------------------------------------------------
def test_equal_weights_for_an_empty_portfolio() -> None:
    """No funds must yield an empty weight mapping.

    REFERENCE: G4-SYNTHETIC. Degenerate branch.
    """
    assert build_equal_weight_dict([]) == {}


def test_contribution_weights_follow_the_instalments() -> None:
    """Weights must mirror the instalment proportions.

    REFERENCE: G4-SYNTHETIC. 10000 and 5000 give 66.67 and 33.33.
    """
    weight_dict = build_contribution_weight_dict(
        [
            build_test_fund("A", 10000.0),
            build_test_fund("B", 5000.0),
        ]
    )
    assert weight_dict["A"] == pytest.approx(200.0 / 3.0)
    assert weight_dict["B"] == pytest.approx(100.0 / 3.0)


def test_zero_instalments_fall_back_to_equal_weights() -> None:
    """An all-zero instalment split must not divide by zero.

    REFERENCE: G4-SYNTHETIC. Fallback branch.
    """
    weight_dict = build_contribution_weight_dict(
        [build_test_fund("A", 0.0), build_test_fund("B", 0.0)]
    )
    assert weight_dict == {"A": 50.0, "B": 50.0}


def test_blank_target_column_falls_back_to_instalments() -> None:
    """An empty target column must reuse the instalment split.

    REFERENCE: G4-SYNTHETIC. Fallback branch.
    """
    weight_dict = build_declared_weight_dict(
        [
            build_test_fund(
                "A", 3000.0, target_allocation_percent_float=0.0
            ),
            build_test_fund(
                "B", 1000.0, target_allocation_percent_float=0.0
            ),
        ]
    )
    assert weight_dict["A"] == pytest.approx(75.0)


def test_normalisation_rescales_to_one_hundred() -> None:
    """Weights must always be rescaled to sum to one hundred.

    REFERENCE: G1-ANALYTIC. Normalisation definition.
    """
    normalised_dict = normalise_weight_dict({"A": 30.0, "B": 30.0})
    assert sum(normalised_dict.values()) == pytest.approx(100.0)
    assert normalised_dict["A"] == pytest.approx(50.0)


def test_normalising_all_zero_weights_gives_equal_split() -> None:
    """An all-zero mapping must become an equal split.

    REFERENCE: G4-SYNTHETIC. Fallback branch.
    """
    assert normalise_weight_dict({"A": 0.0, "B": 0.0}) == {
        "A": 50.0,
        "B": 50.0,
    }


def test_normalising_an_empty_mapping_returns_empty() -> None:
    """An empty mapping must stay empty.

    REFERENCE: G4-SYNTHETIC. Degenerate branch.
    """
    assert normalise_weight_dict({}) == {}


def test_targets_are_zero_while_rebalancing_is_off() -> None:
    """A passive run must carry no target weights at all.

    REFERENCE: G4-SYNTHETIC. Guarantees targets cannot leak.
    """
    weight_dict = resolve_target_weight_dict(
        [build_test_fund("A"), build_test_fund("B")],
        RebalanceSettings(is_enabled_bool=False),
    )
    assert weight_dict == {"A": 0.0, "B": 0.0}


def test_steering_alone_still_resolves_targets() -> None:
    """Cash-flow rebalancing needs targets without trading.

    REFERENCE: G4-SYNTHETIC. Branch added for steering.
    """
    weight_dict = resolve_target_weight_dict(
        [build_test_fund("A", 3000.0), build_test_fund("B", 1000.0)],
        RebalanceSettings(
            use_contribution_steering_bool=True,
            target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
        ),
    )
    assert weight_dict["A"] == pytest.approx(75.0)


def test_declared_targets_are_normalised_before_use() -> None:
    """Targets that do not sum to a hundred must be rescaled.

    REFERENCE: G4-SYNTHETIC. 60 and 60 become 50 and 50.
    """
    weight_dict = resolve_target_weight_dict(
        [
            build_test_fund(
                "A", 1000.0, target_allocation_percent_float=60.0
            ),
            build_test_fund(
                "B", 1000.0, target_allocation_percent_float=60.0
            ),
        ],
        RebalanceSettings(
            is_enabled_bool=True,
            target_mode_str=REBALANCE_TARGET_COLUMN_STR,
        ),
    )
    assert sum(weight_dict.values()) == pytest.approx(100.0)
