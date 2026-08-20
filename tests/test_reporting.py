"""Tests for ledgers, invariants, fund building and the lab."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    COLUMN_EXEMPTION_AMOUNT_STR,
    COLUMN_FUND_NAME_STR,
    COLUMN_LONG_TERM_TAX_STR,
    COLUMN_OVERRIDE_PRESET_STR,
    COLUMN_PRESET_STR,
    COLUMN_SHORT_TERM_TAX_STR,
    PRESET_DEBT_STR,
    PRESET_EQUITY_STR,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TARGET_SIP_SPLIT_STR,
    TAX_FUNDING_OUTSIDE_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.fund_builder import (
    apply_tax_presets_to_dataframe,
    build_default_fund_dataframe,
    build_fund_configurations_list,
    deduplicate_fund_names_list,
    read_date_value,
    read_float_value,
)
from investment_journey_simulator.ledgers import (
    build_annual_summary_dataframe,
    build_fund_history_dataframe,
    build_rebalance_ledger_dataframe,
    build_withdrawal_ledger_dataframe,
    format_weight_dict_str,
)
from investment_journey_simulator.models import (
    RebalanceSettings,
    SimulationResult,
    WithdrawalSettings,
)
from investment_journey_simulator.validation import (
    build_invariant_dataframe,
    check_no_rebalance_when_disabled,
    check_withdrawal_feasibility,
    run_all_invariants_list,
)
from reference_data import (
    PLAUSIBLE_SLAB_RATE_PERCENT_FLOAT,
    STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT,
    STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT,
)

REBALANCED_SETTINGS = build_test_settings(
    horizon_years_int=10,
    rebalance=RebalanceSettings(
        is_enabled_bool=True,
        interval_months_int=12,
        method_str=REBALANCE_METHOD_FULL_STR,
        target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
        tax_funding_str=TAX_FUNDING_OUTSIDE_STR,
    ),
)
WITHDRAWING_SETTINGS = build_test_settings(
    horizon_years_int=10,
    withdrawal=WithdrawalSettings(
        is_enabled_bool=True,
        start_month_index_int=60,
        mode_str=WITHDRAWAL_MODE_FIXED_STR,
        fixed_amount_float=3000.0,
    ),
)


def build_two_fund_result(settings) -> SimulationResult:
    """Run a two-fund simulation for ledger tests.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(
        [
            build_test_fund("Fund-A", 5000.0, 14.0),
            build_test_fund("Fund-B", 5000.0, 8.0),
        ],
        settings,
    ).run()


# ------------------------------------------------------------------
# Ledgers
# ------------------------------------------------------------------
def test_rebalance_ledger_has_one_row_per_event() -> None:
    """Every executed trade must appear exactly once.

    REFERENCE: G4-SYNTHETIC. Ten years, yearly, gives ten rows.
    """
    simulation_result = build_two_fund_result(REBALANCED_SETTINGS)
    ledger_dataframe = build_rebalance_ledger_dataframe(
        simulation_result
    )
    assert len(ledger_dataframe) == len(
        simulation_result.rebalance_events_list
    )
    assert len(ledger_dataframe) == 10


def test_rebalance_ledger_is_empty_for_a_passive_run() -> None:
    """No trades means an empty ledger, not a crash.

    REFERENCE: G4-SYNTHETIC. Degenerate branch.
    """
    simulation_result = build_two_fund_result(
        build_test_settings(horizon_years_int=5)
    )
    assert build_rebalance_ledger_dataframe(
        simulation_result
    ).empty


def test_withdrawal_ledger_lists_only_requested_months() -> None:
    """Months without a request must not appear in the ledger.

    REFERENCE: G4-SYNTHETIC. Withdrawals start at month 60 of a
    120-month run, so exactly 60 rows are expected.
    """
    simulation_result = build_two_fund_result(WITHDRAWING_SETTINGS)
    ledger_dataframe = build_withdrawal_ledger_dataframe(
        simulation_result
    )
    assert len(ledger_dataframe) == 60


def test_annual_summary_has_one_row_per_year() -> None:
    """A ten-year run must summarise into ten rows.

    REFERENCE: G4-SYNTHETIC. Blocking invariant.
    """
    simulation_result = build_two_fund_result(
        build_test_settings(horizon_years_int=10)
    )
    summary_dataframe = build_annual_summary_dataframe(
        simulation_result
    )
    assert len(summary_dataframe) == 10
    assert summary_dataframe.iloc[0]["Opening value"] == 0.0


def test_annual_contributions_sum_to_the_total_principal(
) -> None:
    """Yearly contributions must add up to the reported total.

    REFERENCE: G1-ANALYTIC. Accounting identity.
    """
    simulation_result = build_two_fund_result(
        build_test_settings(horizon_years_int=10)
    )
    summary_dataframe = build_annual_summary_dataframe(
        simulation_result
    )
    assert summary_dataframe["Contributed"].sum() == pytest.approx(
        simulation_result.ending_invested_float
    )


def test_fund_history_has_one_row_per_fund_per_month() -> None:
    """History must cover every fund in every month.

    REFERENCE: G4-SYNTHETIC. 120 months times two funds.
    """
    simulation_result = build_two_fund_result(
        build_test_settings(horizon_years_int=10)
    )
    history_dataframe = build_fund_history_dataframe(
        simulation_result
    )
    assert len(history_dataframe) == 240
    assert set(history_dataframe["Fund"]) == {"Fund-A", "Fund-B"}


def test_fund_history_weights_sum_to_one_hundred() -> None:
    """Monthly weights must always add up to a full portfolio.

    REFERENCE: G1-ANALYTIC. Definition of a weight.
    """
    simulation_result = build_two_fund_result(
        build_test_settings(horizon_years_int=3)
    )
    history_dataframe = build_fund_history_dataframe(
        simulation_result
    )
    weight_sum_series = history_dataframe.groupby("Date")[
        "Weight %"
    ].sum()
    for weight_sum_float in weight_sum_series:
        assert weight_sum_float == pytest.approx(100.0)


def test_weight_formatter_renders_two_decimals() -> None:
    """Weight strings must be readable and rounded.

    REFERENCE: G4-SYNTHETIC. Display contract.
    """
    assert (
        format_weight_dict_str({"A": 33.333, "B": 66.667})
        == "A 33.33, B 66.67"
    )


# ------------------------------------------------------------------
# Invariants
# ------------------------------------------------------------------
def test_every_invariant_passes_on_a_full_featured_run() -> None:
    """A complex run must satisfy every accounting invariant.

    REFERENCE: G1-ANALYTIC. These are the identities that any
    correct cash-flow engine must satisfy.
    """
    settings = build_test_settings(
        horizon_years_int=15,
        rebalance=RebalanceSettings(
            is_enabled_bool=True,
            interval_months_int=12,
            method_str=REBALANCE_METHOD_FULL_STR,
            target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
            tax_funding_str=TAX_FUNDING_OUTSIDE_STR,
        ),
        withdrawal=WithdrawalSettings(
            is_enabled_bool=True,
            start_month_index_int=120,
            mode_str=WITHDRAWAL_MODE_FIXED_STR,
            fixed_amount_float=5000.0,
        ),
    )
    simulation_result = build_two_fund_result(settings)
    outcome_list = run_all_invariants_list(
        simulation_result, settings
    )
    failing_list = [
        outcome.name_str
        for outcome in outcome_list
        if not outcome.is_passing_bool
    ]
    assert failing_list == []


def test_depletion_is_reported_as_a_failed_invariant() -> None:
    """An unaffordable withdrawal plan must fail its check.

    REFERENCE: G4-SYNTHETIC. Planning failure, not engine failure.
    """
    simulation_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=100.0)],
        build_test_settings(
            horizon_years_int=5,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=5000.0,
            ),
        ),
    ).run()
    outcome = check_withdrawal_feasibility(simulation_result)
    assert outcome.is_passing_bool is False
    assert "shortfall" in outcome.detail_str


def test_rebalance_check_fails_if_events_appear_when_off(
) -> None:
    """The off-switch check must actually be able to fail.

    REFERENCE: G4-SYNTHETIC. Negative test of the checker itself,
    built from a hand-made result rather than a simulation.
    """
    real_result = build_two_fund_result(REBALANCED_SETTINGS)
    disabled_settings = build_test_settings(horizon_years_int=10)
    outcome = check_no_rebalance_when_disabled(
        real_result, disabled_settings
    )
    assert outcome.is_passing_bool is False


def test_invariant_dataframe_labels_pass_and_fail() -> None:
    """The validation table must be human readable.

    REFERENCE: G4-SYNTHETIC. Presentation contract.
    """
    simulation_result = build_two_fund_result(
        build_test_settings(horizon_years_int=5)
    )
    invariant_dataframe = build_invariant_dataframe(
        run_all_invariants_list(
            simulation_result,
            build_test_settings(horizon_years_int=5),
        )
    )
    assert set(invariant_dataframe["Result"]) <= {"PASS", "FAIL"}
    assert len(invariant_dataframe) == 7


# ------------------------------------------------------------------
# Fund building from the editor table
# ------------------------------------------------------------------
def test_duplicate_fund_names_are_made_unique() -> None:
    """Two funds may not share a name, because names are keys.

    REFERENCE: G4-SYNTHETIC. Without this the second fund would
    silently overwrite the first in every mapping.
    """
    unique_list = deduplicate_fund_names_list(
        [
            build_test_fund("Same"),
            build_test_fund("Same"),
            build_test_fund("Same"),
        ]
    )
    assert [fund.name_str for fund in unique_list] == [
        "Same",
        "Same (2)",
        "Same (3)",
    ]


def test_equity_preset_applies_statutory_rates() -> None:
    """The equity preset must carry the statutory rates.

    REFERENCE: G2-STATUTORY. Sections 111A and 112A as amended
    by the Finance (No. 2) Act 2024.
    """
    preset_dataframe = apply_tax_presets_to_dataframe(
        build_default_fund_dataframe(date(2026, 1, 1)),
        PLAUSIBLE_SLAB_RATE_PERCENT_FLOAT,
    )
    first_row = preset_dataframe.iloc[0]
    assert first_row[COLUMN_SHORT_TERM_TAX_STR] == (
        STATUTORY_EQUITY_SHORT_TERM_PERCENT_FLOAT
    )
    assert first_row[COLUMN_LONG_TERM_TAX_STR] == (
        STATUTORY_EQUITY_LONG_TERM_PERCENT_FLOAT
    )


def test_debt_preset_uses_the_slab_rate() -> None:
    """Debt funds must be taxed at the investor's slab rate.

    REFERENCE: G2-STATUTORY. Section 50AA for specified mutual
    funds acquired on or after 1 April 2023.
    """
    fund_dataframe = build_default_fund_dataframe(date(2026, 1, 1))
    fund_dataframe.loc[0, COLUMN_PRESET_STR] = PRESET_DEBT_STR
    preset_dataframe = apply_tax_presets_to_dataframe(
        fund_dataframe, PLAUSIBLE_SLAB_RATE_PERCENT_FLOAT
    )
    assert preset_dataframe.iloc[0][
        COLUMN_SHORT_TERM_TAX_STR
    ] == pytest.approx(PLAUSIBLE_SLAB_RATE_PERCENT_FLOAT)
    assert preset_dataframe.iloc[0][
        COLUMN_EXEMPTION_AMOUNT_STR
    ] == 0.0


def test_override_flag_preserves_manual_tax_values() -> None:
    """Ticking override must stop the preset from overwriting.

    REFERENCE: G4-SYNTHETIC. Branch of the preset writer.
    """
    fund_dataframe = build_default_fund_dataframe(date(2026, 1, 1))
    fund_dataframe.loc[0, COLUMN_OVERRIDE_PRESET_STR] = True
    fund_dataframe.loc[0, COLUMN_SHORT_TERM_TAX_STR] = 5.0
    preset_dataframe = apply_tax_presets_to_dataframe(
        fund_dataframe, PLAUSIBLE_SLAB_RATE_PERCENT_FLOAT
    )
    assert preset_dataframe.iloc[0][
        COLUMN_SHORT_TERM_TAX_STR
    ] == 5.0


def test_empty_fund_table_returns_no_funds() -> None:
    """An empty table must not raise.

    REFERENCE: G4-SYNTHETIC. Degenerate branch.
    """
    empty_dataframe = build_default_fund_dataframe(
        date(2026, 1, 1)
    ).iloc[0:0]
    assert (
        build_fund_configurations_list(
            empty_dataframe, date(2026, 1, 1)
        )
        == []
    )
    assert apply_tax_presets_to_dataframe(
        empty_dataframe, 30.0
    ).empty


def test_blank_fund_name_gets_a_placeholder() -> None:
    """A blank name must not become an empty dictionary key.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    fund_dataframe = build_default_fund_dataframe(date(2026, 1, 1))
    fund_dataframe.loc[0, COLUMN_FUND_NAME_STR] = "   "
    fund_list = build_fund_configurations_list(
        fund_dataframe, date(2026, 1, 1)
    )
    assert fund_list[0].name_str == "Unnamed MF"


@pytest.mark.parametrize(
    "cell_value, expected_float",
    [(12.5, 12.5), ("7.25", 7.25), (None, 3.0), ("abc", 3.0)],
)
def test_numeric_reader_falls_back_on_bad_input(
    cell_value,
    expected_float: float,
) -> None:
    """Editor cells may hold blanks or text; both must be safe.

    REFERENCE: G4-SYNTHETIC. All branches of the reader.
    """
    assert read_float_value(cell_value, 3.0) == pytest.approx(
        expected_float
    )


def test_numeric_reader_handles_missing_values() -> None:
    """A pandas missing value must fall back, not raise.

    REFERENCE: G4-SYNTHETIC. Branch for NaN input.
    """
    assert read_float_value(pd.NA, 9.0) == pytest.approx(9.0)


@pytest.mark.parametrize(
    "cell_value, expected_date",
    [
        (date(2027, 5, 1), date(2027, 5, 1)),
        (pd.Timestamp("2027-05-01"), date(2027, 5, 1)),
        (None, date(2026, 1, 1)),
        ("not a date", date(2026, 1, 1)),
    ],
)
def test_date_reader_covers_every_input_shape(
    cell_value,
    expected_date: date,
) -> None:
    """Dates may arrive as timestamps, dates, blanks or text.

    REFERENCE: G4-SYNTHETIC. All branches of the reader.
    """
    assert (
        read_date_value(cell_value, date(2026, 1, 1))
        == expected_date
    )


def test_preset_name_survives_the_build() -> None:
    """The preset label must reach the fund configuration.

    REFERENCE: G4-SYNTHETIC. Round trip through the builder.
    """
    fund_list = build_fund_configurations_list(
        build_default_fund_dataframe(date(2026, 1, 1)),
        date(2026, 1, 1),
    )
    assert fund_list[0].preset_str == PRESET_EQUITY_STR
    assert fund_list[0].is_always_short_term_bool is False
