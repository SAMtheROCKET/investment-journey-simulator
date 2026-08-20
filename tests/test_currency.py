"""Currencies, and the number habits that come with them.

Grouping and magnitude names are not decoration: naming a dollar
figure in lakh, or writing yen to two decimals, would be worse than
saying nothing at all. These tests hold each currency to its own
conventions.
"""

from __future__ import annotations

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import SUMMARY_MONEY_COLUMNS_TUPLE
from investment_journey_simulator.currency import (
    CURRENCY_TUPLE,
    DEFAULT_CURRENCY_CODE_STR,
    GROUPING_INDIAN_STR,
    describe_money_str,
    format_money_str,
    group_digits_str,
    list_currency_code_list,
    resolve_currency,
)
from investment_journey_simulator.dashboard_run import simulate_nominal_run
from investment_journey_simulator.formatting import (
    format_money_amount_str,
)
from investment_journey_simulator.tables import format_money_columns_dataframe


# ------------------------------------------------------------------
# The registry
# ------------------------------------------------------------------
def test_the_rupee_is_the_default() -> None:
    """Every statutory rule in this program is Indian.

    REFERENCE: G4-SYNTHETIC. The default must match the only tax
    system that ships fully modelled.
    """
    assert DEFAULT_CURRENCY_CODE_STR == "INR"
    assert resolve_currency().code_str == "INR"
    assert resolve_currency("").code_str == "INR"


def test_an_unknown_code_falls_back_rather_than_raising() -> None:
    """A stale saved scenario must still open.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert resolve_currency("XYZ").code_str == "INR"
    assert resolve_currency("zzz").code_str == "INR"


def test_a_code_is_matched_whatever_its_case() -> None:
    """Codes are typed by people, and people use lower case.

    REFERENCE: G4-SYNTHETIC.
    """
    assert resolve_currency("usd").code_str == "USD"
    assert resolve_currency("Jpy").code_str == "JPY"


def test_every_currency_is_complete_and_unique() -> None:
    """A currency missing a symbol or a code is unusable.

    REFERENCE: G4-SYNTHETIC. Also guards against a duplicate code
    silently shadowing an earlier entry in the registry.
    """
    code_list = [
        currency.code_str for currency in CURRENCY_TUPLE
    ]
    assert len(code_list) == len(set(code_list))
    for currency in CURRENCY_TUPLE:
        assert len(currency.code_str) == 3
        assert currency.code_str.isupper()
        assert currency.symbol_str
        assert currency.name_str
        assert currency.display_digits_int >= 0
        assert currency.default_inflation_percent_float >= 0.0


def test_the_menu_lists_every_currency_once() -> None:
    """An entry not in the menu cannot be chosen.

    REFERENCE: G4-SYNTHETIC.
    """
    assert list_currency_code_list() == [
        currency.code_str for currency in CURRENCY_TUPLE
    ]


def test_a_currency_labels_itself_by_code_symbol_and_name(
) -> None:
    """A reader finds a currency by whichever one they know.

    REFERENCE: G4-SYNTHETIC.
    """
    label_str = resolve_currency("JPY").label_str
    assert "JPY" in label_str
    assert "¥" in label_str
    assert "円" in label_str


# ------------------------------------------------------------------
# Grouping
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("amount_float", "expected_str"),
    [
        (0.0, "0"),
        (999.0, "999"),
        (1_000.0, "1,000"),
        (99_999.0, "99,999"),
        (100_000.0, "1,00,000"),
        (1_234_567.0, "12,34,567"),
        (10_000_000.0, "1,00,00,000"),
        (-1_234_567.0, "-12,34,567"),
    ],
)
def test_indian_grouping_pairs_after_the_first_three(
    amount_float: float,
    expected_str: str,
) -> None:
    """This is the grouping every Indian reader expects.

    REFERENCE: G4-SYNTHETIC. Last three together, then pairs.
    """
    assert (
        group_digits_str(amount_float, GROUPING_INDIAN_STR, 0)
        == expected_str
    )


@pytest.mark.parametrize(
    ("amount_float", "expected_str"),
    [
        (1_000.0, "1,000"),
        (100_000.0, "100,000"),
        (1_234_567.0, "1,234,567"),
        (-1_234_567.0, "-1,234,567"),
    ],
)
def test_western_grouping_takes_three_at_a_time(
    amount_float: float,
    expected_str: str,
) -> None:
    """Everywhere outside the subcontinent groups in thousands.

    REFERENCE: G4-SYNTHETIC.
    """
    assert (
        group_digits_str(amount_float, "WESTERN", 0)
        == expected_str
    )


def test_the_new_grouper_agrees_with_the_original_rupee_one(
) -> None:
    """The rupee path must not change under the new machinery.

    REFERENCE: G3-CROSSCHECK. Every existing figure in the app is
    formatted by the original helper, so the two must agree.
    """
    currency = resolve_currency("INR")
    for amount_float in (
        0.0, 999.0, 1_00_000.0, 47_59_314.0, -12_34_567.0
    ):
        assert format_money_str(
            amount_float, currency
        ) == format_money_amount_str(amount_float)


# ------------------------------------------------------------------
# Minor units
# ------------------------------------------------------------------
def test_yen_is_never_written_with_decimals() -> None:
    """There are no sen in circulation.

    REFERENCE: G4-SYNTHETIC. Writing yen to two decimals invents a
    coin that does not exist.
    """
    formatted_str = format_money_str(
        1_234_567.89, resolve_currency("JPY")
    )
    assert formatted_str == "¥1,234,568"
    assert "." not in formatted_str


def test_the_dollar_keeps_its_cents() -> None:
    """Cents exist and are shown.

    REFERENCE: G4-SYNTHETIC.
    """
    assert (
        format_money_str(1_234.5, resolve_currency("USD"))
        == "$1,234.50"
    )


def test_the_rupee_is_shown_in_whole_units() -> None:
    """No figure in this program has ever displayed paise.

    REFERENCE: G4-SYNTHETIC. A corpus quoted to the paisa reads
    as false precision.
    """
    assert (
        format_money_str(1_234.56, resolve_currency("INR"))
        == "₹1,235"
    )


# ------------------------------------------------------------------
# Magnitude names
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code_str", "amount_float", "expected_fragment_str"),
    [
        ("INR", 200_000.0, "2.00 lakh"),
        ("INR", 47_59_314.0, "47.59 lakh"),
        ("INR", 10_000_000.0, "1.00 crore"),
        ("USD", 200_000.0, "200.00 thousand"),
        ("USD", 4_759_314.0, "4.76 million"),
        ("USD", 2_000_000_000.0, "2.00 billion"),
        ("JPY", 4_759_314.0, "4.76 million"),
        ("EUR", 1_500_000.0, "1.50 million"),
    ],
)
def test_each_currency_names_magnitudes_its_own_way(
    code_str: str,
    amount_float: float,
    expected_fragment_str: str,
) -> None:
    """Lakh is not a dollar word and million is not a rupee one.

    REFERENCE: G4-SYNTHETIC. This is the whole reason magnitude
    naming has to follow the currency rather than the number.
    """
    assert expected_fragment_str in describe_money_str(
        amount_float, resolve_currency(code_str)
    )


def test_no_currency_names_a_magnitude_from_another() -> None:
    """A dollar figure must never be described in lakh.

    REFERENCE: G4-SYNTHETIC. Guards the mapping in both
    directions at once.
    """
    dollar_str = describe_money_str(
        50_00_000.0, resolve_currency("USD")
    )
    rupee_str = describe_money_str(
        50_00_000.0, resolve_currency("INR")
    )
    assert "lakh" not in dollar_str
    assert "crore" not in dollar_str
    assert "million" not in rupee_str


def test_small_amounts_are_left_unnamed() -> None:
    """Naming a three-figure sum adds nothing.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    for code_str in ("INR", "USD", "JPY"):
        currency = resolve_currency(code_str)
        described_str = describe_money_str(999.0, currency)
        assert described_str == format_money_str(999.0, currency)


def test_a_described_amount_keeps_its_exact_digits() -> None:
    """The friendly name must not replace the figure typed.

    REFERENCE: G4-SYNTHETIC.
    """
    described_str = describe_money_str(
        234_567.0, resolve_currency("INR")
    )
    assert "2,34,567" in described_str
    assert "2.35 lakh" in described_str


# ------------------------------------------------------------------
# Inflation defaults
# ------------------------------------------------------------------
def test_inflation_defaults_differ_by_economy() -> None:
    """Six percent is sensible in Mumbai, not in Tokyo.

    REFERENCE: G5-PLAUSIBILITY. These are opening assumptions of
    the right order of magnitude, never forecasts, and every one
    is overwritable.
    """
    assert (
        resolve_currency("INR").default_inflation_percent_float
        > resolve_currency("JPY").default_inflation_percent_float
    )
    for currency in CURRENCY_TUPLE:
        assert (
            0.0
            <= currency.default_inflation_percent_float
            <= 15.0
        )


# ------------------------------------------------------------------
# The chosen currency has to survive the whole render pipeline
#
# Every leak found in the audit was a hardcoded rupee sign deep in a
# helper the picker never reached. Asserting on the top-level entry
# points is what catches that: a symbol that reappears here means the
# thread is broken somewhere below, wherever that happens to be.
# ------------------------------------------------------------------
RUPEE_SIGN_STR: str = "\u20b9"


def build_dollar_run() -> object:
    """Simulate one small plan and bundle it in US dollars.

    REFERENCE: harness only; one fund, no tax, ten years.
    """
    return simulate_nominal_run(
        [build_test_fund()],
        build_test_settings(),
        False,
        resolve_currency("USD"),
    )


def test_summary_lines_carry_the_chosen_currency() -> None:
    """The headline totals must not fall back to rupees.

    REFERENCE: G4-SYNTHETIC. These lines feed the screen, the
    workbook and the printable report from one place, so a leak
    here would reach all three.
    """
    joined_str = " ".join(build_dollar_run().summary_lines_list)
    assert "$" in joined_str
    assert RUPEE_SIGN_STR not in joined_str


def test_figure_axes_and_hovers_carry_the_chosen_currency() -> None:
    """Axis titles and hover labels must follow the currency.

    REFERENCE: G4-SYNTHETIC. The axis title was a hardcoded rupee
    sign and the hover labels went through a rupee-only helper;
    both are read straight off the built figure here.
    """
    figure_json_str = build_dollar_run().figure.to_json()
    assert RUPEE_SIGN_STR not in figure_json_str
    assert "Amount ($)" in figure_json_str


def test_money_columns_render_in_the_chosen_currency() -> None:
    """The per-fund table must not disagree with the chart.

    REFERENCE: G4-SYNTHETIC. The table and the figure beside it
    are formatted by different modules, which is exactly how they
    came to disagree before the currency travelled with the run.
    """
    dashboard_run = build_dollar_run()
    display_frame = format_money_columns_dataframe(
        dashboard_run.fund_summary_dataframe,
        SUMMARY_MONEY_COLUMNS_TUPLE,
        dashboard_run.currency,
    )
    rendered_str = display_frame.to_string()
    assert "$" in rendered_str
    assert RUPEE_SIGN_STR not in rendered_str


def test_the_default_currency_is_still_the_rupee() -> None:
    """Omitting the currency must not change what India sees.

    REFERENCE: G4-SYNTHETIC. Every caller predating the picker
    passes nothing, so the fallback is load-bearing.
    """
    default_run = simulate_nominal_run(
        [build_test_fund()], build_test_settings()
    )
    assert RUPEE_SIGN_STR in " ".join(
        default_run.summary_lines_list
    )
