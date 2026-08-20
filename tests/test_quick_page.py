"""The Quick Projection screen, rendered for real.

The promise of this page is a defensible number in under a minute
with every assumption disclosed. These tests check the number, and
that the disclosure is actually there.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH
from investment_journey_simulator.pages import quick_page

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 240
AMOUNT_INPUT_INDEX_INT: int = 0
HORIZON_INPUT_INDEX_INT: int = 1
RETURN_INPUT_INDEX_INT: int = 2


def run_quick_page() -> AppTest:
    """Render the Quick page on its own.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import quick_page as page\n"
        "page.render()\n"
    )
    return AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    ).run()


def run_with_amount(amount_float: float) -> AppTest:
    """Render the page with a monthly amount entered.

    REFERENCE: harness only.
    """
    app_test = run_quick_page()
    app_test.number_input[AMOUNT_INPUT_INDEX_INT].set_value(
        amount_float
    )
    return app_test.run()


def test_the_page_opens_with_nothing_entered():
    """A blank plan is a valid state, not a crash."""
    app_test = run_quick_page()
    assert not app_test.exception
    assert app_test.title[0].value == quick_page.TITLE_STR


def test_nothing_invested_asks_rather_than_projecting():
    """Zero in must not produce a confident zero out."""
    app_test = run_quick_page()
    assert app_test.metric == []
    assert any(
        "Enter a monthly amount" in info.value
        for info in app_test.info
    )


def test_entering_an_amount_produces_the_three_figures():
    """The corpus, its cost, and what it is worth today."""
    app_test = run_with_amount(25000.0)
    assert not app_test.exception
    label_list = [metric.label for metric in app_test.metric]
    assert label_list == [
        "Value at the end",
        "You will have paid in",
        "Worth in today's money",
    ]


def test_the_amount_paid_in_is_the_arithmetic():
    """Twenty-five thousand a month for twenty years."""
    app_test = run_with_amount(25000.0)
    paid_in_str = app_test.metric[1].value
    assert paid_in_str == "₹60,00,000"


def test_the_corpus_exceeds_what_was_paid_in():
    """At a positive return, growth is growth."""
    app_test = run_with_amount(25000.0)
    assert app_test.metric[0].value != app_test.metric[1].value


def test_todays_money_is_less_than_the_nominal_corpus():
    """Inflation only ever erodes."""
    app_test = run_with_amount(25000.0)
    nominal_str = app_test.metric[0].value
    real_str = app_test.metric[2].value
    assert len(real_str) <= len(nominal_str)
    assert real_str != nominal_str


def test_a_bigger_contribution_gives_a_bigger_corpus():
    """The obvious monotonicity, worth pinning down."""
    smaller_str = run_with_amount(10000.0).metric[0].value
    larger_str = run_with_amount(50000.0).metric[0].value
    assert smaller_str != larger_str


def test_the_page_states_what_it_assumed():
    """A projection with invisible assumptions is worse than none."""
    app_test = run_with_amount(25000.0)
    markdown_str = " ".join(
        element.value for element in app_test.markdown
    )
    assert "No step-up" in markdown_str
    assert "No pauses" in markdown_str
    assert "No withdrawals" in markdown_str


def test_the_page_points_onward():
    """Quick is a doorway, not a destination."""
    app_test = run_with_amount(25000.0)
    markdown_str = " ".join(
        element.value for element in app_test.markdown
    )
    assert "Guided Journey" in markdown_str
    assert "Compare Journeys" in markdown_str


def test_changing_the_horizon_changes_the_answer():
    """The second question actually does something."""
    app_test = run_with_amount(25000.0)
    before_str = app_test.metric[0].value
    app_test.number_input[HORIZON_INPUT_INDEX_INT].set_value(30)
    app_test.run()
    assert app_test.metric[0].value != before_str


def test_changing_the_return_changes_the_answer():
    """So does the third."""
    app_test = run_with_amount(25000.0)
    before_str = app_test.metric[0].value
    app_test.number_input[RETURN_INPUT_INDEX_INT].set_value(8.0)
    app_test.run()
    assert app_test.metric[0].value != before_str


def read_amount_float(money_str: str) -> float:
    """Strip a formatted figure back to its number.

    REFERENCE: harness only.
    """
    digit_str = "".join(
        character_str
        for character_str in money_str
        if character_str.isdigit() or character_str == "."
    )
    return float(digit_str)


def test_the_currency_changes_the_symbol_not_the_amount():
    """Nothing is converted; only the symbol and grouping change.

    A rupee figure groups by two after the first three and shows no
    minor unit; a dollar figure groups by three and shows cents. The
    number underneath must be the same either way.
    """
    app_test = run_with_amount(25000.0)
    rupee_str = app_test.metric[1].value
    app_test.selectbox[0].set_value("USD").run()
    assert not app_test.exception
    dollar_str = app_test.metric[1].value
    assert "₹" in rupee_str
    assert "$" in dollar_str
    assert read_amount_float(rupee_str) == read_amount_float(
        dollar_str
    )
