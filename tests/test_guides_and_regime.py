"""The guides, and the honesty about which tax rules are modelled.

The regime tests carry weight beyond the interface: they are what
lets the product be described as global without overclaiming. If a
reader can pick the United Kingdom and see nothing warning them,
the description becomes false.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest

from conftest import SOURCE_DIRECTORY_PATH, build_test_fund
from investment_journey_simulator.pages import guides_page
from investment_journey_simulator.pages.guides_page import (
    GUIDE_PACKAGE_STR,
    GUIDE_SPECIFICATION_TUPLE,
    MISSING_GUIDE_MESSAGE_STR,
    read_guide_str,
)
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    PresentationPreferences,
)
from investment_journey_simulator.portal_state import SCENARIO_STATE_KEY_STR
from investment_journey_simulator.regimes import (
    REGIME_INDIA_STR,
    REGIME_TUPLE,
    resolve_regime,
)
from investment_journey_simulator.timeline import TimelinePlan
from investment_journey_simulator.ui.regime_notice import (
    APPROXIMATE_HEADING_STR,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning"
)

PAGE_TIMEOUT_SECONDS_INT: int = 600


# --- The guides ---------------------------------------------------


def test_every_declared_guide_exists():
    """A tab that renders an apology is worse than no tab."""
    for _title_str, file_name_str, _summary in (
        GUIDE_SPECIFICATION_TUPLE
    ):
        assert read_guide_str(file_name_str) != (
            MISSING_GUIDE_MESSAGE_STR
        )


def test_the_guides_live_as_markdown_inside_the_package():
    """So the same words go into the README and the posts.

    They are package data rather than repository files, because a
    wheel does not carry the repository - see
    tests/test_packaging.py for what that cost.
    """
    from importlib import resources

    guide_directory = resources.files(GUIDE_PACKAGE_STR)
    assert guide_directory.is_dir()
    markdown_list = [
        entry
        for entry in guide_directory.iterdir()
        if entry.name.endswith(".md")
    ]
    assert len(markdown_list) >= 3


def test_a_missing_guide_degrades_rather_than_raises():
    """A packaging slip costs one tab, not the whole page."""
    assert read_guide_str("no_such_guide.md") == (
        MISSING_GUIDE_MESSAGE_STR
    )


def test_every_guide_carries_a_verify_before_relying_notice():
    """None of this is advice, and each guide must say so."""
    for _title_str, file_name_str, _summary in (
        GUIDE_SPECIFICATION_TUPLE
    ):
        assert "Verify before relying" in read_guide_str(
            file_name_str
        )


def test_the_starting_guide_assumes_no_country():
    """It is the global one; naming a country would break that."""
    guide_str = read_guide_str("starting_investments.md")
    assert "assumes no country" in guide_str


def test_the_nri_guide_covers_the_steps_that_block_others():
    """The ordering is the whole value of that checklist."""
    guide_str = read_guide_str("nri_investment.md")
    for topic_str in (
        "NRE",
        "NRO",
        "attestation",
        "FATCA",
        "KYC",
    ):
        assert topic_str in guide_str


def test_the_guides_page_renders_a_tab_for_each():
    """Three guides, plus the money-flow tab that leads them.

    The diagram tab is deliberately first. Every one of these
    guides answers the same underlying question, and that question
    is spatial: where is the money now, and what does it pass
    through next. A reader who can see that answers half of each
    checklist for themselves.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import guides_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    ).run()
    assert not app_test.exception
    assert app_test.title[0].value == guides_page.TITLE_STR
    assert (
        len(app_test.tabs) == len(GUIDE_SPECIFICATION_TUPLE) + 1
    )


def test_the_guides_page_says_it_is_not_advice():
    """Once, at the top, where it cannot be missed."""
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import guides_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    ).run()
    assert any(
        "not advice" in info.value for info in app_test.info
    )


# --- Regime honesty -----------------------------------------------


def build_scenario(regime_code_str: str) -> PlanScenario:
    """A scenario under one tax regime."""
    from datetime import date

    return PlanScenario(
        plan=TimelinePlan(
            start_date=date(2026, 1, 1), horizon_years_int=20
        ),
        fund_list=[build_test_fund(name_str="Equity")],
        presentation=PresentationPreferences(
            regime_code_str=regime_code_str
        ),
    )


def run_reports_page(scenario) -> AppTest:
    """Render Reports & Audit, which carries the notice.

    REFERENCE: harness only.
    """
    script_str = (
        "import sys\n"
        f"sys.path.insert(0, r{str(SOURCE_DIRECTORY_PATH)!r})\n"
        "from investment_journey_simulator.pages import reports_page as page\n"
        "page.render()\n"
    )
    app_test = AppTest.from_string(
        script_str, default_timeout=PAGE_TIMEOUT_SECONDS_INT
    )
    app_test.session_state[SCENARIO_STATE_KEY_STR] = scenario
    return app_test.run()


def test_exactly_one_regime_claims_to_be_fully_modelled():
    """The claim is India's alone, and must stay that way."""
    modelled_list = [
        regime.code_str
        for regime in REGIME_TUPLE
        if regime.is_fully_modelled_bool
    ]
    assert modelled_list == [REGIME_INDIA_STR]


def test_a_reader_is_warned_when_the_regime_is_approximate():
    """Without this, calling the product global would be false."""
    scenario = build_scenario("GB")
    scenario = replace(
        scenario,
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                monthly_sip_float=25000.0,
            )
        ],
    )
    app_test = run_reports_page(scenario)
    assert not app_test.exception
    assert any(
        APPROXIMATE_HEADING_STR in warning.value
        for warning in app_test.warning
    )


def test_the_fully_modelled_regime_does_not_shout():
    """Repeating a reassurance as loudly as a caveat kills both."""
    scenario = replace(
        build_scenario(REGIME_INDIA_STR),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                monthly_sip_float=25000.0,
            )
        ],
    )
    app_test = run_reports_page(scenario)
    assert not any(
        APPROXIMATE_HEADING_STR in warning.value
        for warning in app_test.warning
    )


@pytest.mark.parametrize(
    "regime", REGIME_TUPLE, ids=lambda r: r.code_str
)
def test_every_regime_labels_its_own_depth(regime):
    """The menu itself says which one is which."""
    assert regime.name_str in regime.label_str
    if regime.is_fully_modelled_bool:
        assert "fully modelled" in regime.label_str
    else:
        assert "fully modelled" not in regime.label_str


def test_an_unknown_regime_falls_back_to_the_modelled_one():
    """A stale code must not silently select an approximate set."""
    assert (
        resolve_regime("ZZ").code_str == REGIME_INDIA_STR
    )
