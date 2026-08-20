"""Tests for exit charges, loss set-off, figures and scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import pandas as pd
import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.charts import (
    build_allocation_figure,
    build_dashboard_figure,
    build_drawdown_figure,
    build_fund_history_figure,
    build_gain_loss_bar_trace,
)
from investment_journey_simulator.constants import (
    EQUITY_REDEMPTION_STT_PERCENT_FLOAT,
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TARGET_SIP_SPLIT_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.ledgers import build_fund_history_dataframe
from investment_journey_simulator.models import (
    RebalanceSettings,
    SimulationSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.scenarios import (
    build_scenario_dict,
    build_scenario_json_bytes,
    encode_json_value,
    parse_scenario_dict,
)
from investment_journey_simulator.tables import (
    build_fund_summary_dataframe,
    build_monthly_series_dataframe,
)
from investment_journey_simulator.taxation import (
    CapitalGainsTaxPolicy,
    ExemptionLedger,
    LossLedger,
    calculate_exit_charges_float,
)
from reference_data import (
    STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
    STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT,
)

SALE_DATE: date = date(2030, 6, 1)
WITHDRAWING_SETTINGS = build_test_settings(
    horizon_years_int=8,
    withdrawal=WithdrawalSettings(
        is_enabled_bool=True,
        start_month_index_int=36,
        mode_str=WITHDRAWAL_MODE_FIXED_STR,
        fixed_amount_float=5000.0,
    ),
)


def build_policy(
    tax_settings: TaxSettings = None,
    loss_ledger: LossLedger = None,
) -> CapitalGainsTaxPolicy:
    """Build a tax policy for isolated levy tests.

    REFERENCE: harness only.
    """
    return CapitalGainsTaxPolicy(
        build_test_fund(),
        ExemptionLedger(),
        tax_settings or TaxSettings(),
        loss_ledger or LossLedger(),
    )


# ------------------------------------------------------------------
# Surcharge and cess
# ------------------------------------------------------------------
def test_cess_is_charged_on_the_tax_amount() -> None:
    """A four percent cess must raise the tax by four percent.

    REFERENCE: G2-STATUTORY. Health and education cess of 4% is
    levied on income tax. 1,00,000 at 12.5% is 12,500; with cess
    it is 13,000.
    """
    breakdown = build_policy(
        TaxSettings(cess_percent_float=4.0)
    ).calculate_tax_breakdown(100000.0, 24, SALE_DATE)
    assert breakdown.tax_amount_float == pytest.approx(13000.0)


def test_surcharge_is_charged_before_cess() -> None:
    """Cess must apply to tax plus surcharge, in that order.

    REFERENCE: G2-STATUTORY. 12,500 tax, 10% surcharge gives
    13,750, then 4% cess gives 14,300.
    """
    breakdown = build_policy(
        TaxSettings(
            surcharge_percent_float=10.0, cess_percent_float=4.0
        )
    ).calculate_tax_breakdown(100000.0, 24, SALE_DATE)
    assert breakdown.tax_amount_float == pytest.approx(14300.0)


def test_zero_levies_leave_the_base_tax_unchanged() -> None:
    """With no surcharge or cess the base rate must apply.

    REFERENCE: G4-SYNTHETIC. Identity case.
    """
    breakdown = build_policy().calculate_tax_breakdown(
        100000.0, 24, SALE_DATE
    )
    assert breakdown.tax_amount_float == pytest.approx(
        100000.0 * STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT / 100.0
    )


# ------------------------------------------------------------------
# Capital loss set-off
# ------------------------------------------------------------------
def test_a_loss_is_booked_and_taxed_at_zero() -> None:
    """Selling below cost must produce no tax and book a loss.

    REFERENCE: G2-STATUTORY. Tax applies to gains only.
    """
    breakdown = build_policy().calculate_tax_breakdown(
        -50000.0, 24, SALE_DATE
    )
    assert breakdown.tax_amount_float == 0.0
    assert breakdown.realized_loss_float == pytest.approx(50000.0)


def test_short_term_loss_offsets_a_later_gain() -> None:
    """A booked short term loss must shelter a later gain.

    REFERENCE: G2-STATUTORY, section 74. A 40,000 short term loss
    against a 1,00,000 long term gain leaves 60,000 taxable.
    """
    policy = build_policy()
    policy.calculate_tax_breakdown(-40000.0, 6, SALE_DATE)
    breakdown = policy.calculate_tax_breakdown(
        100000.0, 24, SALE_DATE
    )
    assert breakdown.offset_loss_float == pytest.approx(40000.0)
    assert breakdown.tax_amount_float == pytest.approx(
        60000.0 * 0.125
    )


def test_long_term_loss_cannot_offset_a_short_term_gain() -> None:
    """Long term losses shelter long term gains only.

    REFERENCE: G2-STATUTORY, section 74(1)(b). A 40,000 long term
    loss must not reduce a short term gain.
    """
    policy = build_policy()
    policy.calculate_tax_breakdown(-40000.0, 24, SALE_DATE)
    breakdown = policy.calculate_tax_breakdown(
        100000.0, 6, SALE_DATE
    )
    assert breakdown.offset_loss_float == 0.0
    assert breakdown.tax_amount_float == pytest.approx(20000.0)


def test_set_off_happens_before_the_exemption() -> None:
    """Losses must be applied before the yearly exemption.

    REFERENCE: G2-STATUTORY. A 1,00,000 loss and a 2,00,000 gain
    leave 1,00,000, which the 1,25,000 exemption fully shelters.
    """
    policy = CapitalGainsTaxPolicy(
        build_test_fund(),
        ExemptionLedger(),
        TaxSettings(
            exemption_level_str=EXEMPTION_LEVEL_PORTFOLIO_STR,
            portfolio_exemption_amount_float=(
                STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
            ),
        ),
        LossLedger(),
    )
    policy.calculate_tax_breakdown(-100000.0, 24, SALE_DATE)
    breakdown = policy.calculate_tax_breakdown(
        200000.0, 24, SALE_DATE
    )
    assert breakdown.tax_amount_float == 0.0


def test_disabling_set_off_ignores_booked_losses() -> None:
    """The planning switch must make losses inert.

    REFERENCE: G4-SYNTHETIC. Feature switch branch.
    """
    policy = build_policy(
        TaxSettings(allow_loss_set_off_bool=False)
    )
    policy.calculate_tax_breakdown(-40000.0, 6, SALE_DATE)
    breakdown = policy.calculate_tax_breakdown(
        100000.0, 24, SALE_DATE
    )
    assert breakdown.offset_loss_float == 0.0
    assert breakdown.tax_amount_float == pytest.approx(12500.0)


def test_loss_pool_is_consumed_only_once() -> None:
    """A loss must not shelter two different gains twice.

    REFERENCE: G4-SYNTHETIC. Ledger arithmetic.
    """
    loss_ledger = LossLedger()
    loss_ledger.record_loss(50000.0, False, 2026)
    first_tuple = loss_ledger.offset_gain_float(30000.0, False, 2026)
    second_tuple = loss_ledger.offset_gain_float(
        30000.0, False, 2026
    )
    assert first_tuple == (0.0, 30000.0)
    assert second_tuple[1] == pytest.approx(20000.0)
    assert loss_ledger.available_loss_float == 0.0


def test_recording_a_non_positive_loss_is_ignored() -> None:
    """Zero and negative loss magnitudes must be rejected.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    loss_ledger = LossLedger()
    loss_ledger.record_loss(0.0, False, 2026)
    loss_ledger.record_loss(-100.0, True, 2026)
    assert loss_ledger.available_loss_float == 0.0


def test_losses_expire_after_eight_assessment_years() -> None:
    """A capital loss lapses once its carry-forward window ends.

    REFERENCE: G2-STATUTORY. A loss computed in a financial year
    may be set off in that year and in the eight that follow it.
    A loss booked in FY 2026 is therefore usable up to FY 2034 and
    dead in FY 2035.
    """
    loss_ledger = LossLedger()
    loss_ledger.record_loss(50000.0, False, 2026)
    remaining_float, used_float = loss_ledger.offset_gain_float(
        50000.0, False, 2034
    )
    assert used_float == pytest.approx(50000.0)
    assert remaining_float == pytest.approx(0.0)

    expired_ledger = LossLedger()
    expired_ledger.record_loss(50000.0, False, 2026)
    remaining_float, used_float = expired_ledger.offset_gain_float(
        50000.0, False, 2035
    )
    assert used_float == pytest.approx(0.0)
    assert remaining_float == pytest.approx(50000.0)
    assert expired_ledger.available_loss_float == 0.0


def test_expired_losses_are_swept_out_of_the_pool() -> None:
    """Lapsed losses leave the pool instead of lingering.

    REFERENCE: G2-STATUTORY. The sweep reports what it wrote off
    so the dashboard can distinguish unused shelter from expired
    shelter.
    """
    loss_ledger = LossLedger()
    loss_ledger.record_loss(10000.0, False, 2020)
    loss_ledger.record_loss(4000.0, True, 2030)
    expired_float = loss_ledger.expire_stale_losses(2030)
    assert expired_float == pytest.approx(10000.0)
    assert loss_ledger.available_loss_float == pytest.approx(4000.0)


def test_oldest_losses_are_spent_before_newer_ones() -> None:
    """Set-off consumes the loss closest to expiry first.

    REFERENCE: G4-SYNTHETIC. Spending the oldest pool first wastes
    the least shelter, because that pool is the one about to lapse.
    """
    loss_ledger = LossLedger()
    loss_ledger.record_loss(10000.0, False, 2026)
    loss_ledger.record_loss(10000.0, False, 2030)
    loss_ledger.offset_gain_float(10000.0, False, 2031)
    remaining_float, used_float = loss_ledger.offset_gain_float(
        10000.0, False, 2038
    )
    assert used_float == pytest.approx(10000.0)
    assert remaining_float == pytest.approx(0.0)
    assert loss_ledger.available_loss_float == pytest.approx(0.0)


# ------------------------------------------------------------------
# Exit load and securities transaction tax
# ------------------------------------------------------------------
def test_exit_load_applies_only_inside_its_window() -> None:
    """Exit load must stop once the window has passed.

    REFERENCE: G4-SYNTHETIC, and real-world: most equity funds
    charge 1% if redeemed within twelve months.
    """
    fund_configuration = build_test_fund(
        exit_load_percent_float=1.0,
        exit_load_within_months_int=12,
    )
    inside_float = calculate_exit_charges_float(
        fund_configuration, 100000.0, 6
    )
    outside_float = calculate_exit_charges_float(
        fund_configuration, 100000.0, 12
    )
    assert inside_float == pytest.approx(1000.0)
    assert outside_float == 0.0


def test_transaction_tax_applies_to_every_redemption() -> None:
    """STT must be charged regardless of holding period.

    REFERENCE: G2-STATUTORY. Securities transaction tax on equity
    mutual fund redemption is 0.001% of the redemption value.
    """
    fund_configuration = build_test_fund(
        transaction_tax_percent_float=(
            EQUITY_REDEMPTION_STT_PERCENT_FLOAT
        )
    )
    charges_float = calculate_exit_charges_float(
        fund_configuration, 1000000.0, 120
    )
    assert charges_float == pytest.approx(10.0)


def test_no_charges_configured_means_no_deduction() -> None:
    """A fund without charges must redeem at full value.

    REFERENCE: G4-SYNTHETIC. Default case.
    """
    assert calculate_exit_charges_float(
        build_test_fund(), 100000.0, 1
    ) == 0.0


def test_zero_sale_value_incurs_no_charge() -> None:
    """Selling nothing must cost nothing.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert calculate_exit_charges_float(
        build_test_fund(exit_load_percent_float=1.0), 0.0, 1
    ) == 0.0


def test_exit_load_reduces_what_the_investor_receives() -> None:
    """A withdrawal charge is deducted from the payout.

    REFERENCE: G4-SYNTHETIC, and real-world: exit load is netted
    out of the redemption amount. The portfolio still loses the
    units it sold, so the corpus is unchanged; the investor simply
    receives less than the gross redemption.

    What this test used to assert - that the charge equals one per
    cent of what was withdrawn - was true whether or not the charge
    was ever deducted from anything. It passed while the money
    quietly stayed in the portfolio. It now compares two runs, so
    the charge has to actually go somewhere.
    """
    result_by_load_dict = {}
    for exit_load_percent_float in (0.0, 1.0):
        result_by_load_dict[exit_load_percent_float] = (
            PortfolioSimulator(
                [
                    build_test_fund(
                        monthly_sip_float=50000.0,
                        exit_load_percent_float=(
                            exit_load_percent_float
                        ),
                        exit_load_within_months_int=600,
                    )
                ],
                WITHDRAWING_SETTINGS,
            ).run()
        )
    free_result = result_by_load_dict[0.0]
    charged_result = result_by_load_dict[1.0]
    charges_float = charged_result.charges_paid_float
    assert charges_float > 0.0
    # The same units were sold either way, so the corpus matches.
    assert charged_result.ending_value_float == pytest.approx(
        free_result.ending_value_float
    )
    # The whole of the difference in the payout is the charge.
    assert (
        free_result.ending_withdrawn_float
        - charged_result.ending_withdrawn_float
    ) == pytest.approx(charges_float)


def test_exit_load_reduces_the_corpus_when_rebalancing() -> None:
    """A charge paid while rebalancing is money out of the fund.

    REFERENCE: G4-SYNTHETIC. Unlike a withdrawal, a rebalance
    reinvests the proceeds, so the charge shrinks the corpus.
    """
    value_by_load_dict = {}
    for exit_load_percent_float in (0.0, 1.0):
        simulation_result = PortfolioSimulator(
            [
                build_test_fund(
                    "Fund-A",
                    5000.0,
                    14.0,
                    exit_load_percent_float=(
                        exit_load_percent_float
                    ),
                    exit_load_within_months_int=600,
                ),
                build_test_fund(
                    "Fund-B",
                    5000.0,
                    8.0,
                    exit_load_percent_float=(
                        exit_load_percent_float
                    ),
                    exit_load_within_months_int=600,
                ),
            ],
            build_test_settings(
                horizon_years_int=10,
                rebalance=RebalanceSettings(
                    is_enabled_bool=True,
                    interval_months_int=12,
                    method_str=REBALANCE_METHOD_FULL_STR,
                    target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                ),
            ),
        ).run()
        value_by_load_dict[exit_load_percent_float] = (
            simulation_result.ending_value_float
        )
    assert value_by_load_dict[1.0] < value_by_load_dict[0.0]


def test_charges_are_reported_separately_from_tax() -> None:
    """Charges must be visible, not folded into the tax figure.

    REFERENCE: G4-SYNTHETIC. Reporting contract.
    """
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=50000.0,
                exit_load_percent_float=1.0,
                exit_load_within_months_int=600,
            )
        ],
        WITHDRAWING_SETTINGS,
    ).run()
    assert simulation_result.charges_paid_float > 0.0
    assert simulation_result.fund_outcomes_list[
        0
    ].charges_paid_float > 0.0


def test_exit_cost_includes_charges_as_well_as_tax() -> None:
    """The cost of leaving must count both levies.

    REFERENCE: G4-SYNTHETIC. Spendable corpus definition.
    """
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=50000.0,
                exit_load_percent_float=1.0,
                exit_load_within_months_int=600,
            )
        ],
        build_test_settings(
            horizon_years_int=10,
            tax=TaxSettings(
                apply_final_liquidation_tax_bool=True
            ),
        ),
    ).run()
    assert (
        simulation_result.final_liquidation_charges_float > 0.0
    )
    assert simulation_result.total_exit_cost_float > (
        simulation_result.final_liquidation_tax_float
    )
    assert (
        simulation_result.post_tax_ending_value_float
        < simulation_result.ending_value_float
    )


# ------------------------------------------------------------------
# Figures
# ------------------------------------------------------------------
@pytest.fixture(scope="module")
def rebalanced_result():
    """A run with trades, pauses and withdrawals for the charts.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(
        [
            build_test_fund("Fund-A", 5000.0, 14.0),
            build_test_fund("Fund-B", 5000.0, 8.0),
        ],
        build_test_settings(
            horizon_years_int=10,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=12,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
            ),
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                start_month_index_int=60,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=4000.0,
            ),
        ),
    ).run()


def test_gain_loss_bar_colours_losses_differently() -> None:
    """A loss bar must not look like a gain bar.

    REFERENCE: G4-SYNTHETIC. The whole point of replacing the pie.
    """
    bar_trace = build_gain_loss_bar_trace(
        ["A", "B"], [1000.0, -500.0]
    )
    assert list(bar_trace.y) == [1000.0, -500.0]
    assert bar_trace.marker.color[0] != bar_trace.marker.color[1]


def test_dashboard_marks_rebalances_and_pauses(
    rebalanced_result,
) -> None:
    """Trades and paused months must be drawn on the chart.

    REFERENCE: G4-SYNTHETIC. Ten yearly trades give ten markers.
    """
    figure = build_dashboard_figure(
        build_monthly_series_dataframe(rebalanced_result),
        build_fund_summary_dataframe(rebalanced_result),
        "Test",
        [
            event.month_date
            for event in rebalanced_result.rebalance_events_list
        ],
        [pd.Timestamp(date(2028, 5, 1))],
    )
    shape_type_list = [
        shape.type for shape in figure.layout.shapes
    ]
    assert shape_type_list.count("line") == 10
    assert shape_type_list.count("rect") == 1


def test_drawdown_figure_is_never_positive(
    rebalanced_result,
) -> None:
    """Drawdown measures distance below a peak, so it is negative.

    REFERENCE: G1-ANALYTIC. Definition of drawdown.
    """
    figure = build_drawdown_figure(
        build_monthly_series_dataframe(rebalanced_result)
    )
    assert max(figure.data[0].y) <= 1e-9


def test_fund_history_figure_has_one_line_per_fund(
    rebalanced_result,
) -> None:
    """Every fund must get its own history line.

    REFERENCE: G4-SYNTHETIC. Structural contract.
    """
    figure = build_fund_history_figure(
        build_fund_history_dataframe(rebalanced_result)
    )
    assert len(figure.data) == 2


def test_allocation_figure_draws_target_lines(
    rebalanced_result,
) -> None:
    """Targets must appear as reference lines.

    REFERENCE: G4-SYNTHETIC. Target-versus-actual contract.
    """
    figure = build_allocation_figure(
        build_fund_history_dataframe(rebalanced_result),
        {"Fund-A": 50.0, "Fund-B": 50.0},
    )
    assert len(figure.data) == 2
    assert len(figure.layout.shapes) == 2


def test_zero_targets_draw_no_reference_lines(
    rebalanced_result,
) -> None:
    """A passive run has no targets, so it must draw none.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    figure = build_allocation_figure(
        build_fund_history_dataframe(rebalanced_result),
        {"Fund-A": 0.0, "Fund-B": 0.0},
    )
    assert len(figure.layout.shapes) == 0


# ------------------------------------------------------------------
# Scenario save and load
# ------------------------------------------------------------------
@dataclass(frozen=True)
class FakeSelections:
    """Minimal stand-in for the sidebar selections."""

    settings: SimulationSettings
    inflation_percent_float: float
    slab_rate_percent_float: float
    expense_model_str: str


def test_dates_are_encoded_as_iso_strings() -> None:
    """A date must survive the trip through JSON.

    REFERENCE: G4-SYNTHETIC. Serialisation contract.
    """
    assert encode_json_value(date(2026, 4, 1)) == "2026-04-01"
    assert encode_json_value(pd.Timestamp("2026-04-01")) == (
        "2026-04-01"
    )


def test_nested_settings_are_encoded_recursively() -> None:
    """Nested dataclasses must become nested dictionaries.

    REFERENCE: G4-SYNTHETIC. Serialisation contract.
    """
    encoded_dict = encode_json_value(build_test_settings())
    assert encoded_dict["rebalance"]["is_enabled_bool"] is False
    assert encoded_dict["portfolio_start_date"] == "2026-01-01"


def test_unknown_objects_fall_back_to_text() -> None:
    """An unserialisable object must not break the save.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    assert encode_json_value(object()) .startswith("<object")
    assert encode_json_value(None) is None


def test_a_saved_scenario_round_trips() -> None:
    """Saving and loading must return the same inputs.

    REFERENCE: G4-SYNTHETIC. Round-trip property.
    """
    selections = FakeSelections(
        settings=build_test_settings(horizon_years_int=17),
        inflation_percent_float=6.0,
        slab_rate_percent_float=30.0,
        expense_model_str="CONTINUOUS_ACCRUAL",
    )
    fund_dataframe = pd.DataFrame(
        [{"MF Name": "Fund-A", "SIP / month": 5000}]
    )
    scenario_bytes = build_scenario_json_bytes(
        build_scenario_dict(selections, fund_dataframe)
    )
    restored_dict = parse_scenario_dict(scenario_bytes)
    assert restored_dict["settings"]["horizon_years_int"] == 17
    assert restored_dict["inflation_percent"] == 6.0
    assert restored_dict["funds"][0]["MF Name"] == "Fund-A"


def test_a_foreign_json_file_is_rejected() -> None:
    """A file without the version marker must be refused.

    REFERENCE: G4-SYNTHETIC. Validation branch.
    """
    with pytest.raises(ValueError):
        parse_scenario_dict(json.dumps({"hello": 1}).encode())


def test_broken_json_raises_a_decode_error() -> None:
    """Malformed JSON must raise, not silently return nothing.

    REFERENCE: G4-SYNTHETIC. Validation branch.
    """
    with pytest.raises(json.JSONDecodeError):
        parse_scenario_dict(b"{not json")


def test_capital_gains_surcharge_is_capped_at_fifteen() -> None:
    """Surcharge on equity gains must not exceed fifteen percent.

    REFERENCE: G2-STATUTORY, verified 2026-08-04. Surcharge on
    gains taxed under sections 111A and 112A is capped at 15%,
    even where the taxpayer's other income attracts 25% or 37%.
    12,500 tax x 1.15 x 1.04 = 14,950, not the 17,968.75 that an
    uncapped 37% would give.
    """
    breakdown = build_policy(
        TaxSettings(
            surcharge_percent_float=37.0, cess_percent_float=4.0
        )
    ).calculate_tax_breakdown(100000.0, 24, SALE_DATE)
    assert breakdown.tax_amount_float == pytest.approx(14950.0)


def test_slab_taxed_debt_gains_keep_the_full_surcharge() -> None:
    """Specified funds are slab income, so the cap does not apply.

    REFERENCE: G2-STATUTORY, section 50AA. Gains on specified
    mutual funds are taxed as ordinary income at slab rates, so
    the 111A/112A surcharge cap is not available to them.
    """
    debt_policy = CapitalGainsTaxPolicy(
        build_test_fund(
            is_always_short_term_bool=True,
            short_term_tax_percent_float=30.0,
        ),
        ExemptionLedger(),
        TaxSettings(
            surcharge_percent_float=37.0, cess_percent_float=4.0
        ),
        LossLedger(),
    )
    breakdown = debt_policy.calculate_tax_breakdown(
        100000.0, 60, SALE_DATE
    )
    assert breakdown.tax_amount_float == pytest.approx(
        30000.0 * 1.37 * 1.04
    )
