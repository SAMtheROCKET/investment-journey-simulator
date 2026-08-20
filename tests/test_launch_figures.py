"""The figures quoted publicly must still be what the engine says.

Every number in the README, the launch post and the worked
comparisons came out of this engine. Nothing stops them drifting
apart afterwards - a refactor changes a figure, the documents keep
the old one, and the first person to check finds the discrepancy
instead of us.

So the headline claims are recomputed here. If one moves, this
fails, and the documents get corrected rather than quietly
falsified.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

from investment_journey_simulator.attribution import (
    CAUSE_STEPUP_STR,
    attribute_gap,
)
from investment_journey_simulator.constants import (
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.models import FundConfiguration
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.scenario_set import run_journey_outcome
from investment_journey_simulator.timeline import (
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    TimelineEvent,
    TimelinePlan,
)

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent
DOCUMENT_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent / "docs" / "launch"
)
README_PATH: Path = (
    Path(__file__).resolve().parent.parent / "README.md"
)

RETURN_PERCENT_FLOAT: float = 12.0
EXPENSE_PERCENT_FLOAT: float = 1.0
INFLATION_PERCENT_FLOAT: float = 6.0
MONTHLY_AMOUNT_FLOAT: float = 25000.0
PLAN_START_DATE: date = date(2026, 1, 1)

# A rupee either way on figures in the crores. The documents quote
# these exactly, so anything looser would let a real change through.
TOLERANCE_FLOAT: float = 1.0


def build_asset() -> FundConfiguration:
    """The single equity asset every worked figure uses."""
    return FundConfiguration(
        name_str="Equity fund",
        preset_str=PRESET_EQUITY_STR,
        monthly_sip_float=0.0,
        stepup_percent_float=0.0,
        gross_return_percent_float=RETURN_PERCENT_FLOAT,
        expense_percent_float=EXPENSE_PERCENT_FLOAT,
        start_date=PLAN_START_DATE,
        target_allocation_percent_float=100.0,
        short_term_tax_percent_float=20.0,
        long_term_tax_percent_float=12.5,
        long_term_threshold_months_int=12,
        exemption_amount_float=125000.0,
        exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
        is_always_short_term_bool=False,
        expense_model_str=EXPENSE_MODEL_SIMPLE_STR,
    )


def build_journey(
    name_str: str,
    horizon_years_int: int,
    event_list: list,
) -> PlanScenario:
    """One named journey on the shared assumptions."""
    return PlanScenario(
        plan=TimelinePlan(
            PLAN_START_DATE, horizon_years_int, list(event_list)
        ),
        fund_list=[build_asset()],
        inflation_percent_float=INFLATION_PERCENT_FLOAT,
        name_str=name_str,
    )


def read_document_str(file_name_str: str) -> str:
    """Read one launch document."""
    return (DOCUMENT_DIRECTORY_PATH / file_name_str).read_text(
        encoding="utf-8"
    )


def flatten_str(text_str: str) -> str:
    """Collapse whitespace so a wrapped phrase still matches.

    Brief:
        These documents are hand-wrapped prose. A phrase split
        across two lines is the same phrase, and a check that says
        otherwise is testing the line breaks rather than the words.

    Arguments:
        text_str (str): Document text.

    Returns:
        str: The same text with runs of whitespace collapsed.

    Warning:
        Also strips the markdown quote markers that wrapping puts
        at the start of continuation lines.
    """
    return re.sub(r"\s+", " ", text_str.replace("\n>", " "))


def contains_amount_bool(text_str: str, amount_float: float) -> bool:
    """Whether a document quotes this amount, grouped Indian-style."""
    digit_str = f"{int(round(amount_float))}"
    grouped_str = re.sub(
        r"(?<=\d)(?=(\d\d)+\d$)", ",", digit_str
    )
    return grouped_str in text_str


# --- The matched-totals comparison --------------------------------


def test_starting_ten_years_earlier_is_worth_what_we_claim():
    """Same money in, same finish date - the strongest claim.

    It works precisely because there is no "but they invested
    more" objection available. If the totals ever stop matching,
    the comparison stops being honest and this fails.
    """
    early = build_journey(
        "early",
        20,
        [
            TimelineEvent(
                EVENT_START_SIP_STR, PLAN_START_DATE, 15000.0
            )
        ],
    )
    late = build_journey(
        "late",
        20,
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2036, 1, 1), 30000.0
            )
        ],
    )
    early_outcome = run_journey_outcome(early)
    late_outcome = run_journey_outcome(late)
    assert early_outcome.invested_float == pytest.approx(
        late_outcome.invested_float, abs=TOLERANCE_FLOAT
    )
    assert early_outcome.invested_float == pytest.approx(
        3600000.0, abs=TOLERANCE_FLOAT
    )
    assert early_outcome.final_value_float == pytest.approx(
        12234109.0, abs=TOLERANCE_FLOAT
    )
    assert late_outcome.final_value_float == pytest.approx(
        6372892.0, abs=TOLERANCE_FLOAT
    )


# --- The pause hook -----------------------------------------------


def build_steady_journey() -> PlanScenario:
    """Thirty years, no interruption, no step-up."""
    return build_journey(
        "Steady",
        30,
        [
            TimelineEvent(
                EVENT_START_SIP_STR,
                PLAN_START_DATE,
                MONTHLY_AMOUNT_FLOAT,
            )
        ],
    )


def build_paused_journey() -> PlanScenario:
    """The same plan with three years off in the middle."""
    return build_journey(
        "Paused three years",
        30,
        [
            TimelineEvent(
                EVENT_START_SIP_STR,
                PLAN_START_DATE,
                MONTHLY_AMOUNT_FLOAT,
            ),
            TimelineEvent(EVENT_PAUSE_STR, date(2031, 1, 1)),
            TimelineEvent(EVENT_RESUME_STR, date(2033, 12, 1)),
        ],
    )


def test_the_pause_hook_is_still_true():
    """The single most quotable fact in the launch material."""
    steady_float = run_journey_outcome(
        build_steady_journey()
    ).final_value_float
    paused_float = run_journey_outcome(
        build_paused_journey()
    ).final_value_float
    gap_float = steady_float - paused_float
    skipped_float = MONTHLY_AMOUNT_FLOAT * 36
    assert skipped_float == 900000.0
    assert gap_float == pytest.approx(
        10543672.0, abs=TOLERANCE_FLOAT
    )
    assert gap_float / skipped_float == pytest.approx(11.7, abs=0.1)


def test_the_documents_quote_the_pause_figures():
    """README and the launch text must agree with the engine."""
    for text_str in (
        README_PATH.read_text(encoding="utf-8"),
        read_document_str("post.md"),
        read_document_str("comparative_journeys.md"),
    ):
        assert "1.05 crore" in text_str


# --- The step-up, the largest number quoted -----------------------


def test_the_step_up_gap_is_still_what_we_publish():
    """The biggest figure in the post, and the least expected."""
    stepped = build_journey(
        "A. Never interrupted",
        30,
        [
            TimelineEvent(
                EVENT_START_SIP_STR,
                PLAN_START_DATE,
                MONTHLY_AMOUNT_FLOAT,
            ),
            TimelineEvent(
                EVENT_STEPUP_STR,
                date(2027, 1, 1),
                percent_float=10.0,
            ),
        ],
    )
    flat = build_journey(
        "D. Never stepped up",
        30,
        [
            TimelineEvent(
                EVENT_START_SIP_STR,
                PLAN_START_DATE,
                MONTHLY_AMOUNT_FLOAT,
            )
        ],
    )
    attribution = attribute_gap(stepped, flat)
    assert [
        cause.cause_str for cause in attribution.cause_list
    ] == [CAUSE_STEPUP_STR]
    assert attribution.gap_float == pytest.approx(
        -109653859.0, abs=TOLERANCE_FLOAT
    )
    assert abs(attribution.residual_float) < TOLERANCE_FLOAT


def test_the_documents_quote_the_step_up_figure():
    """The headline of the README opener."""
    for text_str in (
        README_PATH.read_text(encoding="utf-8"),
        read_document_str("post.md"),
        read_document_str("comparative_journeys.md"),
    ):
        assert contains_amount_bool(text_str, 109653859.0)


# --- The documents themselves -------------------------------------


def test_the_launch_documents_exist():
    """They are what the posts are written from."""
    for file_name_str in (
        "post.md",
        "comparative_journeys.md",
        "demo_script.md",
    ):
        assert (
            DOCUMENT_DIRECTORY_PATH / file_name_str
        ).is_file()


def test_the_post_states_the_assumption_limit():
    """The honesty line is not optional material."""
    post_str = flatten_str(read_document_str("post.md"))
    assert "does not predict markets" in post_str
    assert "steady monthly rate" in post_str


def test_the_post_makes_no_boast_it_cannot_back():
    """Claims about the whole field are neither modest nor provable.

    A reader who doubts "the first of its kind" argues with the
    claim instead of trying the tool. The post is written to make
    only claims the test suite can stand behind.
    """
    post_str = flatten_str(read_document_str("post.md"))
    assert "Don't claim to be first" in post_str
    assert "Never name another product" in post_str
    for boast_str in (
        "nobody has built",
        "the first of its kind",
        "no other tool",
        "the only tool",
        "world's first",
    ):
        assert boast_str.lower() not in post_str.lower()


# --- The figure in the README -------------------------------------
#
# assets/journey_comparison.png is generated, not drawn, and it
# quotes four outcomes. If the generator drifts from the documents
# the picture starts lying at the top of the README, where it is
# read most and checked least.

FOUR_PANEL_EXPECTED_DICT: dict = {
    "A · Never interrupted": 172860910.0,
    "B · Withdrew early": 165911835.0,
    "C · Paused two years": 160620654.0,
    "D · Never stepped up": 63207052.0,
}


def test_the_readme_figure_still_shows_the_published_numbers():
    """The four panels agree with the four documented journeys.

    REFERENCE: G4-SYNTHETIC. Same engine, same figures as
    comparative_journeys.md section 2.
    """
    sys.path.insert(0, str(PROJECT_ROOT_PATH / "tools"))
    from render_journey_comparison import (
        build_journey_specification_list,
        read_trajectory_tuple,
    )

    for title_str, _subtitle_str, scenario in (
        build_journey_specification_list()
    ):
        _years, _values, final_float = read_trajectory_tuple(
            scenario
        )
        assert final_float == pytest.approx(
            FOUR_PANEL_EXPECTED_DICT[title_str], abs=TOLERANCE_FLOAT
        ), f"panel {title_str} drifted"


def test_the_four_panels_share_one_vertical_scale():
    """The one property the figure exists for.

    REFERENCE: G4-SYNTHETIC. Independently scaled panels would draw
    ₹6.32 crore as tall as ₹17.29 crore and quietly reverse the
    point the picture is making.
    """
    sys.path.insert(0, str(PROJECT_ROOT_PATH / "tools"))
    from render_journey_comparison import render_figure

    figure = render_figure()
    axis_range_list = []
    for key_str in dir(figure.layout):
        if not key_str.startswith("yaxis"):
            continue
        axis = getattr(figure.layout, key_str)
        if axis is not None and axis.range is not None:
            axis_range_list.append(tuple(axis.range))
    assert axis_range_list, "no y axis ranges were set at all"
    assert len(set(axis_range_list)) == 1, (
        f"the panels do not share a scale: {axis_range_list}"
    )
