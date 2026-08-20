"""The third front end: a form dashboard that speaks your currency.

Two things matter here. It must render at all, and it must honour
the currency and regime it was given - a page that silently shows
rupees under a dollar setting would be worse than one that refused
to switch.
"""

from __future__ import annotations

from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from conftest import build_launch_script_str
from investment_journey_simulator.currency import resolve_currency
from investment_journey_simulator.regimes import resolve_regime
from investment_journey_simulator.studio_app import (
    CURRENCY_KEY_STR,
    EQUITY_KEY_STR,
    MONTHLY_KEY_STR,
    REGIME_KEY_STR,
    build_fund_list,
    build_settings,
)
from investment_journey_simulator.ui.studio_view import (
    build_growth_figure,
    build_year_row_list,
    compact_money_str,
)
from investment_journey_simulator.ui.value_input import (
    INPUT_MODE_STATE_KEY_STR,
    INPUT_MODE_TYPED_STR,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

STUDIO_SCRIPT_STR: str = build_launch_script_str("studio_app")
APP_TIMEOUT_SECONDS_INT: int = 240
FORM_TUPLE: tuple = (25_000.0, 100_000.0, 60.0, 12.0, 7.0, 0.5)


def run_studio_app(
    currency_code_str: str = "INR",
    regime_code_str: str = "IN",
) -> AppTest:
    """Execute the studio script once, headlessly.

    REFERENCE: harness only.
    """
    app_test = AppTest.from_string(
        STUDIO_SCRIPT_STR,
        default_timeout=APP_TIMEOUT_SECONDS_INT,
    )
    app_test.session_state[CURRENCY_KEY_STR] = currency_code_str
    app_test.session_state[REGIME_KEY_STR] = regime_code_str
    app_test.session_state[INPUT_MODE_STATE_KEY_STR] = (
        INPUT_MODE_TYPED_STR
    )
    return app_test.run()


# ------------------------------------------------------------------
# The page renders
# ------------------------------------------------------------------
def test_the_studio_renders_without_exceptions() -> None:
    """A third front end needs its own smoke test.

    REFERENCE: G4-SYNTHETIC. A break here must not be discovered
    only by a user.
    """
    app_test = run_studio_app()
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]


def test_the_studio_draws_its_chart_cards_and_table() -> None:
    """The page must actually answer, not only accept inputs.

    REFERENCE: G4-SYNTHETIC. Seven cards from the quick plan, plus
    charts and tables from both tabs - the full dashboard tab
    brings its own, so these are lower bounds rather than exact
    counts.
    """
    app_test = run_studio_app()
    assert app_test.get("plotly_chart")
    assert app_test.dataframe
    card_list = [
        element.value
        for element in app_test.markdown
        if '<div class="tl-card">' in element.value
    ]
    assert len(card_list) == 7


def test_the_studio_offers_currency_and_regime_choices() -> None:
    """Both choices have to be reachable from the page.

    REFERENCE: G4-SYNTHETIC.
    """
    app_test = run_studio_app()
    key_set = {widget.key for widget in app_test.selectbox}
    assert CURRENCY_KEY_STR in key_set
    assert REGIME_KEY_STR in key_set


def test_the_studio_honours_the_input_style_choice() -> None:
    """The style control must work here as it does on the rail.

    REFERENCE: G4-SYNTHETIC. In typed mode the studio's own
    controls are boxes. The full dashboard tab keeps whatever
    controls it always had, because it is the classic dashboard's
    code reused unchanged rather than restyled.
    """
    app_test = run_studio_app()
    studio_key_tuple = (
        f"{MONTHLY_KEY_STR}__box",
        f"{EQUITY_KEY_STR}__box",
    )
    box_key_set = {
        widget.key for widget in app_test.number_input
    }
    for key_str in studio_key_tuple:
        assert key_str in box_key_set
    assert not [
        widget
        for widget in app_test.slider
        if widget.key
        and widget.key.startswith(("studio_", "chooser_"))
    ]


def test_the_full_dashboard_tab_carries_the_classic_pipeline(
) -> None:
    """Every classic feature must be reachable from the studio.

    REFERENCE: G4-SYNTHETIC. The classic sidebar, its fund table
    and its export section are the load-bearing pieces; if they
    render, the pipeline behind them ran.
    """
    app_test = run_studio_app()
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]
    assert app_test.sidebar
    assert app_test.tabs
    assert len(app_test.dataframe) > 1


def test_the_ported_sections_honour_the_chosen_currency() -> None:
    """The classic renderers must speak the studio's currency.

    REFERENCE: G4-SYNTHETIC. These sections used to format in
    rupees whatever was chosen, and the page carried a warning
    admitting it. They now take the currency the studio was given,
    so the honest thing is to check they use it - and that the
    studio no longer offers a second, conflicting picker.
    """
    app_test = run_studio_app("USD")
    assert not app_test.exception, [
        exception.value for exception in app_test.exception
    ]
    rendered_str = " ".join(
        str(element.value) for element in app_test.markdown
    )
    assert "₹" not in rendered_str
    currency_picker_list = [
        widget
        for widget in app_test.selectbox
        if "Show every amount in" in str(widget.label)
    ]
    assert currency_picker_list == []


def test_a_typed_amount_reaches_the_studio() -> None:
    """The form has to be usable by keyboard.

    REFERENCE: G4-SYNTHETIC. 33,333 is not a multiple of the step.
    """
    app_test = run_studio_app()
    monthly_input = [
        widget
        for widget in app_test.number_input
        if widget.key == f"{MONTHLY_KEY_STR}__box"
    ][0]
    monthly_input.set_value(33_333.0).run()
    assert app_test.session_state[MONTHLY_KEY_STR] == (
        pytest.approx(33_333.0)
    )


# ------------------------------------------------------------------
# The currency is honoured
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("currency_code_str", "expected_symbol_str"),
    [("INR", "₹"), ("USD", "$"), ("JPY", "¥"), ("GBP", "£")],
)
def test_the_chosen_currency_reaches_the_cards(
    currency_code_str: str,
    expected_symbol_str: str,
) -> None:
    """A page showing rupees under a dollar setting would lie.

    REFERENCE: G4-SYNTHETIC. The symbol has to appear on the
    headline cards, which is where a reader looks first.
    """
    app_test = run_studio_app(currency_code_str)
    card_text_str = " ".join(
        element.value
        for element in app_test.markdown
        if '<div class="tl-card">' in element.value
    )
    assert expected_symbol_str in card_text_str


@pytest.mark.parametrize(
    ("currency_code_str", "expected_prefix_str"),
    [("INR", "₹"), ("USD", "$"), ("JPY", "¥"), ("GBP", "£")],
)
def test_the_chart_axis_carries_the_currency_symbol(
    currency_code_str: str,
    expected_prefix_str: str,
) -> None:
    """A chart read in the wrong denomination is a wrong chart.

    REFERENCE: G4-SYNTHETIC. The value axis is prefixed with the
    symbol, so the denomination travels with the picture.
    """
    figure = build_growth_figure(
        [date(2026, 1, 1), date(2026, 2, 1)],
        [1000.0, 2000.0],
        [1000.0, 1900.0],
        resolve_currency(currency_code_str),
    )
    assert figure.layout.yaxis.tickprefix == expected_prefix_str


@pytest.mark.parametrize(
    ("currency_code_str", "amount_float", "expected_str"),
    [
        ("INR", 12_400_000.0, "₹1.24Cr"),
        ("INR", 470_000.0, "₹4.70L"),
        ("USD", 1_240_000.0, "$1.24M"),
        ("USD", 2_400_000_000.0, "$2.40B"),
        ("JPY", 4_500_000.0, "¥4.50M"),
    ],
)
def test_compact_figures_use_their_own_currency_suffixes(
    currency_code_str: str,
    amount_float: float,
    expected_str: str,
) -> None:
    """"L" means lakh and is meaningless against a dollar.

    REFERENCE: G4-SYNTHETIC. The suffix belongs to the currency,
    exactly as the long magnitude names do.
    """
    assert (
        compact_money_str(
            amount_float, resolve_currency(currency_code_str)
        )
        == expected_str
    )


def test_the_yearly_table_is_denominated_too() -> None:
    """Every figure on the page follows one choice, not most.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_settings(3, 0.0, resolve_regime("US"))
    from investment_journey_simulator.engine import PortfolioSimulator

    result = PortfolioSimulator(
        build_fund_list(FORM_TUPLE, resolve_regime("US")), settings
    ).run()
    row_list = build_year_row_list(
        list(result.monthly_snapshots_list), resolve_currency("USD")
    )
    assert len(row_list) == 3
    # The heading is "Value", not "Corpus": the word is Indian
    # financial English and this table is shown to every reader.
    assert row_list[0]["Value"].startswith("$")


# ------------------------------------------------------------------
# The regime is honoured
# ------------------------------------------------------------------
def test_the_regime_sets_the_funds_tax_rates() -> None:
    """Choosing a country must reach the funds, not just a label.

    REFERENCE: G2-STATUTORY. Japan is a flat 20.315% on listed
    shares whatever the holding period.
    """
    fund_list = build_fund_list(FORM_TUPLE, resolve_regime("JP"))
    equity_fund = fund_list[0]
    assert equity_fund.short_term_tax_percent_float == (
        pytest.approx(20.315)
    )
    assert equity_fund.long_term_tax_percent_float == (
        pytest.approx(20.315)
    )


def test_a_zero_tax_regime_leaves_the_corpus_whole() -> None:
    """Singapore levies no capital gains tax on investments.

    REFERENCE: G2-STATUTORY. The exit cost must be nil, which is
    the strongest check that the regime really reached the engine.
    """
    from investment_journey_simulator.engine import PortfolioSimulator

    regime = resolve_regime("SG")
    result = PortfolioSimulator(
        build_fund_list(FORM_TUPLE, regime),
        build_settings(5, 0.0, regime),
    ).run()
    assert result.total_exit_cost_float == pytest.approx(0.0)


def test_only_india_charges_a_cess_in_the_studio() -> None:
    """Cess is an Indian mechanism and must not travel.

    REFERENCE: G2-STATUTORY.
    """
    assert build_settings(
        10, 0.0, resolve_regime("IN")
    ).tax.cess_percent_float == pytest.approx(4.0)
    for code_str in ("JP", "GB", "US", "SG", "AE"):
        assert build_settings(
            10, 0.0, resolve_regime(code_str)
        ).tax.cess_percent_float == pytest.approx(0.0)


def test_debt_is_always_short_term_only_under_india() -> None:
    """Section 50AA has no counterpart abroad.

    REFERENCE: G2-STATUTORY. Applying it elsewhere would invent a
    rule that does not exist in that country.
    """
    indian_debt = build_fund_list(
        FORM_TUPLE, resolve_regime("IN")
    )[1]
    assert indian_debt.is_always_short_term_bool is True
    for code_str in ("JP", "GB", "US", "SG", "AE"):
        foreign_debt = build_fund_list(
            FORM_TUPLE, resolve_regime(code_str)
        )[1]
        assert foreign_debt.is_always_short_term_bool is False


def test_the_split_routes_both_the_instalment_and_the_lump_sum(
) -> None:
    """The portfolio must open at its target mix, not drift there.

    REFERENCE: G4-SYNTHETIC. 60/40 of 25,000 and 100,000.
    """
    equity_fund, debt_fund = build_fund_list(
        FORM_TUPLE, resolve_regime("IN")
    )
    assert equity_fund.monthly_sip_float == pytest.approx(15_000.0)
    assert debt_fund.monthly_sip_float == pytest.approx(10_000.0)
    assert equity_fund.initial_investment_float == (
        pytest.approx(60_000.0)
    )
    assert debt_fund.initial_investment_float == (
        pytest.approx(40_000.0)
    )


def test_a_hundred_percent_equity_still_builds_both_funds(
) -> None:
    """One code path has to serve every split.

    REFERENCE: G4-SYNTHETIC. Guard branch; the debt fund simply
    receives nothing.
    """
    fund_list = build_fund_list(
        (25_000.0, 0.0, 100.0, 12.0, 7.0, 0.5),
        resolve_regime("IN"),
    )
    assert len(fund_list) == 2
    assert fund_list[1].monthly_sip_float == pytest.approx(0.0)


def test_the_equity_share_can_be_typed_in_the_studio() -> None:
    """A 5% step would make 62.5% impossible to express here too.

    REFERENCE: G4-SYNTHETIC.
    """
    app_test = run_studio_app()
    equity_input = [
        widget
        for widget in app_test.number_input
        if widget.key == f"{EQUITY_KEY_STR}__box"
    ][0]
    equity_input.set_value(62.5).run()
    assert app_test.session_state[EQUITY_KEY_STR] == (
        pytest.approx(62.5)
    )
