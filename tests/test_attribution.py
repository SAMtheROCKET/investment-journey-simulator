"""Splitting the gap between two journeys.

The property that everything else rests on is **exactness**: the
causes must sum to the whole gap, with nothing quietly absorbed.
That is the Shapley efficiency axiom, and it is checked here rather
than trusted.

The pause case gets its own tests because it is the number most
likely to be quoted publicly and the one people find hardest to
believe.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.attribution import (
    CAUSE_CONTRIBUTION_STR,
    CAUSE_FEE_STR,
    CAUSE_LABEL_DICT,
    CAUSE_PAUSE_STR,
    CAUSE_RETURN_STR,
    CAUSE_STEPUP_STR,
    MAXIMUM_CAUSE_COUNT_INT,
    attribute_gap,
    build_hybrid_scenario,
    compute_shapley_dict,
    find_differing_cause_list,
)
from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.scenario_edits import build_named_copy
from investment_journey_simulator.scenario_set import run_journey_outcome
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
)
from investment_journey_simulator.timeline_app import build_fund_list

PLAN_START_DATE: date = date(2026, 1, 1)
HORIZON_YEARS_INT: int = 30
MONTHLY_AMOUNT_FLOAT: float = 25000.0

# The gap must reconcile to within a rupee on a corpus of crores,
# which is far tighter than any figure the interface ever shows.
RECONCILIATION_TOLERANCE_FLOAT: float = 1.0


def build_journey(
    name_str: str,
    *event_tuple: TimelineEvent,
) -> PlanScenario:
    """Build a named journey with one equity fund."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=HORIZON_YEARS_INT,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR,
                    PLAN_START_DATE,
                    MONTHLY_AMOUNT_FLOAT,
                ),
                *event_tuple,
            ],
        ),
        fund_list=[build_test_fund(name_str="Equity")],
        name_str=name_str,
    )


def build_steady_journey() -> PlanScenario:
    """Invest the same amount every month, never stopping."""
    return build_journey("Steady")


def build_paused_journey() -> PlanScenario:
    """The same plan, with three years off in the middle."""
    return build_journey(
        "Paused for three years",
        TimelineEvent(EVENT_PAUSE_STR, date(2031, 1, 1)),
        TimelineEvent(EVENT_RESUME_STR, date(2034, 1, 1)),
    )


# --- Exactness: the property everything rests on ------------------


def test_the_causes_sum_to_the_whole_gap():
    """Nothing is absorbed and nothing is invented."""
    attribution = attribute_gap(
        build_steady_journey(), build_paused_journey()
    )
    attributed_float = sum(
        cause.amount_float for cause in attribution.cause_list
    )
    assert attributed_float == pytest.approx(
        attribution.gap_float, abs=RECONCILIATION_TOLERANCE_FLOAT
    )


def test_the_residual_is_reported_and_is_zero():
    """A residual is a bug worth seeing, not one worth hiding."""
    attribution = attribute_gap(
        build_steady_journey(), build_paused_journey()
    )
    assert abs(attribution.residual_float) < (
        RECONCILIATION_TOLERANCE_FLOAT
    )


def test_exactness_holds_with_several_causes_at_once():
    """Interactions are exactly where a naive split goes wrong."""
    baseline = build_journey(
        "Everything right",
        TimelineEvent(
            EVENT_STEPUP_STR, date(2027, 1, 1), percent_float=10.0
        ),
    )
    variant = replace(
        build_paused_journey(),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                expense_percent_float=2.0,
            )
        ],
    )
    attribution = attribute_gap(baseline, variant)
    assert len(attribution.cause_list) >= 3
    assert sum(
        cause.amount_float for cause in attribution.cause_list
    ) == pytest.approx(
        attribution.gap_float, abs=RECONCILIATION_TOLERANCE_FLOAT
    )


def test_identical_journeys_have_nothing_to_explain():
    """No differences means no causes and no gap."""
    steady = build_steady_journey()
    attribution = attribute_gap(
        steady, build_named_copy(steady, "A copy")
    )
    assert attribution.cause_list == []
    assert attribution.gap_float == pytest.approx(0.0)


# --- Order independence -------------------------------------------


def test_the_split_does_not_depend_on_cause_order():
    """Which is the whole reason for using Shapley values."""
    baseline = build_journey(
        "Everything right",
        TimelineEvent(
            EVENT_STEPUP_STR, date(2027, 1, 1), percent_float=10.0
        ),
    )
    variant = build_paused_journey()
    cause_list = find_differing_cause_list(baseline, variant)
    forward_dict = compute_shapley_dict(
        baseline, variant, cause_list
    )
    reversed_dict = compute_shapley_dict(
        baseline, variant, list(reversed(cause_list))
    )
    for cause_str, amount_float in forward_dict.items():
        assert reversed_dict[cause_str] == pytest.approx(
            amount_float, abs=RECONCILIATION_TOLERANCE_FLOAT
        )


# --- The pause: the number people will quote ----------------------


def test_a_pause_is_attributed_to_the_pause():
    """The obvious thing, worth pinning down."""
    attribution = attribute_gap(
        build_steady_journey(), build_paused_journey()
    )
    assert [cause.cause_str for cause in attribution.cause_list] == [
        CAUSE_PAUSE_STR
    ]


def test_a_pause_costs_more_than_the_instalments_skipped():
    """The counter-intuitive claim, made checkable.

    Three years off at twenty-five thousand a month is nine lakh
    of instalments. The cost is far larger, because that money
    also never earned anything for the twenty-two years that
    remained. If this ever fails, the headline claim of the whole
    Compare screen is wrong.
    """
    attribution = attribute_gap(
        build_steady_journey(), build_paused_journey()
    )
    skipped_float = MONTHLY_AMOUNT_FLOAT * 36
    pause_cost_float = abs(attribution.cause_list[0].amount_float)
    assert pause_cost_float > skipped_float * 2.0


def test_a_pause_makes_the_journey_worse_not_better():
    """A sign error here would invert the entire message."""
    attribution = attribute_gap(
        build_steady_journey(), build_paused_journey()
    )
    assert attribution.gap_float < 0.0
    assert attribution.cause_list[0].is_cost_bool is True


def test_a_longer_pause_costs_more():
    """Monotonic in the thing that causes it."""
    short_journey = build_journey(
        "Paused one year",
        TimelineEvent(EVENT_PAUSE_STR, date(2031, 1, 1)),
        TimelineEvent(EVENT_RESUME_STR, date(2031, 12, 1)),
    )
    short_float = abs(
        attribute_gap(
            build_steady_journey(), short_journey
        ).gap_float
    )
    long_float = abs(
        attribute_gap(
            build_steady_journey(), build_paused_journey()
        ).gap_float
    )
    assert long_float > short_float


def test_an_earlier_pause_costs_more_than_a_later_one():
    """Time in the market is the mechanism, so timing matters."""
    early_journey = build_journey(
        "Paused early",
        TimelineEvent(EVENT_PAUSE_STR, date(2027, 1, 1)),
        TimelineEvent(EVENT_RESUME_STR, date(2029, 12, 1)),
    )
    late_journey = build_journey(
        "Paused late",
        TimelineEvent(EVENT_PAUSE_STR, date(2050, 1, 1)),
        TimelineEvent(EVENT_RESUME_STR, date(2052, 12, 1)),
    )
    early_float = abs(
        attribute_gap(
            build_steady_journey(), early_journey
        ).gap_float
    )
    late_float = abs(
        attribute_gap(
            build_steady_journey(), late_journey
        ).gap_float
    )
    assert early_float > late_float


# --- Which causes are detected ------------------------------------


def test_a_fee_difference_is_detected():
    """A percentage a year, on the whole balance, for thirty years."""
    variant = replace(
        build_named_copy(build_steady_journey(), "Costlier fund"),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                expense_percent_float=2.5,
            )
        ],
    )
    cause_list = find_differing_cause_list(
        build_steady_journey(), variant
    )
    assert cause_list == [CAUSE_FEE_STR]


def test_a_return_difference_is_flagged_as_not_behaviour():
    """A comparison across returns is not about decisions."""
    variant = replace(
        build_named_copy(build_steady_journey(), "Lower return"),
        fund_list=[
            replace(
                build_test_fund(name_str="Equity"),
                gross_return_percent_float=8.0,
            )
        ],
    )
    assert find_differing_cause_list(
        build_steady_journey(), variant
    ) == [CAUSE_RETURN_STR]


def test_a_stepup_difference_is_detected():
    """The raise that never happened."""
    variant = build_journey(
        "With a step-up",
        TimelineEvent(
            EVENT_STEPUP_STR, date(2027, 1, 1), percent_float=10.0
        ),
    )
    assert find_differing_cause_list(
        build_steady_journey(), variant
    ) == [CAUSE_STEPUP_STR]


def test_a_contribution_difference_is_detected():
    """Different instalments are different contributions."""
    variant = replace(
        build_steady_journey(),
        plan=replace(
            build_steady_journey().plan,
            event_list=[
                TimelineEvent(
                    EVENT_START_SIP_STR, PLAN_START_DATE, 10000.0
                )
            ],
        ),
        name_str="Smaller instalment",
    )
    assert find_differing_cause_list(
        build_steady_journey(), variant
    ) == [CAUSE_CONTRIBUTION_STR]


def test_the_cause_count_is_capped():
    """Two to the power of the count is the cost of the split."""
    assert MAXIMUM_CAUSE_COUNT_INT <= 6


def test_every_cause_has_a_label_and_an_explanation():
    """A waterfall of bare keys would explain nothing."""
    from investment_journey_simulator.attribution import CAUSE_EXPLANATION_DICT

    for cause_str in CAUSE_LABEL_DICT:
        assert CAUSE_LABEL_DICT[cause_str]
        assert CAUSE_EXPLANATION_DICT[cause_str]


# --- The hybrids the split is built from --------------------------


def test_the_empty_subset_is_the_baseline():
    """Reverting nothing must leave the reference journey."""
    baseline = build_steady_journey()
    hybrid = build_hybrid_scenario(
        baseline, build_paused_journey(), frozenset()
    )
    assert run_journey_outcome(
        hybrid
    ).final_value_float == pytest.approx(
        run_journey_outcome(baseline).final_value_float
    )


def test_the_full_subset_is_the_variant():
    """Reverting everything must reach the journey being explained."""
    variant = build_paused_journey()
    cause_list = find_differing_cause_list(
        build_steady_journey(), variant
    )
    hybrid = build_hybrid_scenario(
        build_steady_journey(), variant, frozenset(cause_list)
    )
    assert run_journey_outcome(
        hybrid
    ).final_value_float == pytest.approx(
        run_journey_outcome(variant).final_value_float
    )


def test_a_hybrid_keeps_events_outside_every_cause():
    """Notes and inflation changes must not drift between runs."""
    baseline = build_journey(
        "With a note",
        TimelineEvent(
            "Note to self", date(2030, 1, 1), note_str="house"
        ),
    )
    hybrid = build_hybrid_scenario(
        baseline, build_paused_journey(), frozenset()
    )
    assert any(
        event.note_str == "house"
        for event in hybrid.plan.event_list
    )


# --- The four-cause case, which is the one that matters -----------
#
# A single changed decision proves nothing about the method: every
# attribution scheme agrees when there is only one cause. The
# figures below back the worked example in
# docs/launch/comparative_journeys.md section 2b, and they are
# pinned here so the document cannot quietly drift away from what
# the engine actually produces.

MESSY_START_DATE: date = date(2026, 1, 1)
MESSY_HORIZON_YEARS_INT: int = 30
MESSY_EQUITY_PERCENT_FLOAT: float = 70.0
MESSY_RETURN_PERCENT_FLOAT: float = 12.0
MESSY_EXPENSE_PERCENT_FLOAT: float = 0.6

# Rupee figures quoted in the document. A corpus of fourteen crore
# is compared to the rupee, which is far tighter than anything the
# interface displays.
MESSY_INTENDED_FLOAT: float = 146_517_397.0
MESSY_ACTUAL_FLOAT: float = 25_523_470.0
MESSY_SHAPLEY_DICT: dict = {
    "contributions": -45_302_707.0,
    "stepup": -40_800_147.0,
    "withdrawals": -24_069_421.0,
    "pauses": -10_821_652.0,
}
MESSY_NAIVE_SUM_FLOAT: float = -167_124_890.0
RUPEE_TOLERANCE_FLOAT: float = 1.0


def build_messy_journey_pair() -> tuple:
    """The plan somebody meant to follow, and the one they did."""
    fund_list = build_fund_list(
        MESSY_EQUITY_PERCENT_FLOAT,
        MESSY_RETURN_PERCENT_FLOAT,
        MESSY_EXPENSE_PERCENT_FLOAT,
    )

    def build(name_str: str, event_list: list) -> PlanScenario:
        return PlanScenario(
            plan=TimelinePlan(
                start_date=MESSY_START_DATE,
                horizon_years_int=MESSY_HORIZON_YEARS_INT,
                event_list=event_list,
            ),
            fund_list=list(fund_list),
            name_str=name_str,
        )

    return (
        build("Intended", build_intended_event_list()),
        build("What happened", build_actual_event_list()),
    )


def build_intended_event_list() -> list:
    """Thirty thousand a month, rising eight per cent a year."""
    return [
        TimelineEvent(
            EVENT_START_SIP_STR, MESSY_START_DATE, 30000.0
        ),
        TimelineEvent(
            EVENT_STEPUP_STR, MESSY_START_DATE, percent_float=8.0
        ),
    ]


def build_actual_event_list() -> list:
    """The same plan after four things went differently."""
    return [
        TimelineEvent(
            EVENT_START_SIP_STR, MESSY_START_DATE, 30000.0
        ),
        TimelineEvent(
            EVENT_STEPUP_STR, MESSY_START_DATE, percent_float=3.0
        ),
        TimelineEvent(
            EVENT_CHANGE_SIP_STR, date(2029, 1, 1), 18000.0
        ),
        TimelineEvent(EVENT_PAUSE_STR, date(2033, 1, 1)),
        TimelineEvent(EVENT_RESUME_STR, date(2036, 1, 1)),
        TimelineEvent(
            EVENT_WITHDRAW_STR, date(2038, 1, 1), 40000.0
        ),
    ]


def test_four_causes_are_found_in_the_messy_pair():
    """All four differences are recognised, and nothing else.

    REFERENCE: G4-SYNTHETIC. If a cause stopped being detected the
    split below would still sum correctly while silently answering
    a different question.
    """
    intended, actual = build_messy_journey_pair()
    assert sorted(find_differing_cause_list(intended, actual)) == [
        "contributions",
        "pauses",
        "stepup",
        "withdrawals",
    ]


def test_the_documented_four_cause_figures_still_hold():
    """The worked example, to the rupee.

    REFERENCE: G4-SYNTHETIC. Backs section 2b of
    docs/launch/comparative_journeys.md. A document that quotes
    engine output has to fail when the engine stops producing it.
    """
    intended, actual = build_messy_journey_pair()
    attribution = attribute_gap(intended, actual)
    assert attribution.baseline_value_float == pytest.approx(
        MESSY_INTENDED_FLOAT, abs=RUPEE_TOLERANCE_FLOAT
    )
    assert attribution.variant_value_float == pytest.approx(
        MESSY_ACTUAL_FLOAT, abs=RUPEE_TOLERANCE_FLOAT
    )
    for cause in attribution.cause_list:
        assert cause.amount_float == pytest.approx(
            MESSY_SHAPLEY_DICT[cause.cause_str],
            abs=RUPEE_TOLERANCE_FLOAT,
        ), f"{cause.cause_str} moved"


def test_four_causes_still_sum_to_the_whole_gap():
    """The efficiency property, where it is actually tested.

    REFERENCE: G1-ANALYTIC. With one cause this is trivially true.
    With four interacting ones it is the entire claim.
    """
    intended, actual = build_messy_journey_pair()
    attribution = attribute_gap(intended, actual)
    attributed_float = sum(
        cause.amount_float for cause in attribution.cause_list
    )
    assert attributed_float == pytest.approx(
        attribution.gap_float, abs=RECONCILIATION_TOLERANCE_FLOAT
    )
    assert attribution.residual_float == pytest.approx(
        0.0, abs=RECONCILIATION_TOLERANCE_FLOAT
    )


def test_the_naive_split_overshoots_the_gap_it_explains():
    """Why the obvious method was not used.

    REFERENCE: G4-SYNTHETIC. Reverting each cause on its own and
    adding the drops counts every interaction once per cause that
    shares it, so the parts come to more than the whole. Here they
    overshoot by over four crore, which is the number section 2b
    quotes as unaccounted for.
    """
    intended, actual = build_messy_journey_pair()
    baseline_float = run_journey_outcome(intended).final_value_float
    naive_total_float = 0.0
    for cause_str in find_differing_cause_list(intended, actual):
        alone = build_hybrid_scenario(
            intended, actual, frozenset({cause_str})
        )
        naive_total_float += (
            run_journey_outcome(alone).final_value_float
            - baseline_float
        )
    assert naive_total_float == pytest.approx(
        MESSY_NAIVE_SUM_FLOAT, abs=RUPEE_TOLERANCE_FLOAT
    )
    gap_float = (
        run_journey_outcome(actual).final_value_float
        - baseline_float
    )
    assert abs(naive_total_float) > abs(gap_float)
    assert abs(naive_total_float - gap_float) > 40_000_000.0
