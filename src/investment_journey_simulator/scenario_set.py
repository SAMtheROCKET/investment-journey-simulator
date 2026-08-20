"""Several journeys, compared on a basis that holds.

A comparison is only honest if the things being compared differ in
the way the headline claims. "Same income, same return, same
retirement age - four different behaviours" is a strong statement
precisely because three of those are held fixed. If one journey
quietly assumes twelve percent and another eleven, the four figures
underneath say nothing about behaviour at all.

So a `ScenarioSet` does two things: it holds the journeys, and it
checks that what the comparison claims to hold constant really is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from investment_journey_simulator.dashboard_run import simulate_nominal_run
from investment_journey_simulator.inflation import deflate_amount_float
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)

MAXIMUM_JOURNEY_COUNT_INT: int = 6

BASIS_RETURN_STR: str = "expected return"
BASIS_HORIZON_STR: str = "horizon"
BASIS_START_STR: str = "start date"
BASIS_CURRENCY_STR: str = "currency"
BASIS_EXPENSE_STR: str = "expense ratio"
BASIS_INFLATION_STR: str = "inflation"


@dataclass(frozen=True)
class JourneyOutcome:
    """What one journey came to, and what it cost to get there."""

    name_str: str
    final_value_float: float
    real_value_float: float
    invested_float: float
    tax_paid_float: float

    @property
    def growth_float(self) -> float:
        """How much of the corpus was growth rather than saving."""
        return self.final_value_float - self.invested_float


@dataclass(frozen=True)
class BasisDifference:
    """One assumption that is not held constant after all."""

    basis_str: str
    value_str_list: list

    @property
    def sentence_str(self) -> str:
        """The difference, phrased as a warning a reader reads."""
        joined_str = ", ".join(self.value_str_list)
        return (
            f"The {self.basis_str} is not the same across these "
            f"journeys: {joined_str}. Differences in the final "
            "figures are not caused by behaviour alone."
        )


@dataclass(frozen=True)
class ScenarioSet:
    """Named journeys held for comparison."""

    scenario_list: list[PlanScenario] = field(default_factory=list)

    @property
    def is_comparable_bool(self) -> bool:
        """Whether there is anything to compare yet."""
        return len(self.scenario_list) >= 2

    @property
    def name_str_list(self) -> list[str]:
        """The journey names, in the order they were added."""
        return [
            scenario.name_str for scenario in self.scenario_list
        ]


def _describe_basis_values(
    scenario: PlanScenario,
) -> dict[str, str]:
    """Report the assumptions a comparison claims to hold fixed."""
    compiled = compile_scenario(scenario)
    first_fund = (
        scenario.fund_list[0] if scenario.fund_list else None
    )
    return {
        BASIS_RETURN_STR: (
            f"{first_fund.gross_return_percent_float:g}%"
            if first_fund
            else "none"
        ),
        BASIS_EXPENSE_STR: (
            f"{first_fund.expense_percent_float:g}%"
            if first_fund
            else "none"
        ),
        BASIS_HORIZON_STR: (
            f"{scenario.plan.horizon_years_int} years"
        ),
        BASIS_START_STR: f"{scenario.plan.start_date:%B %Y}",
        BASIS_CURRENCY_STR: compiled.currency.code_str,
        BASIS_INFLATION_STR: (
            f"{compiled.inflation_percent_float:g}%"
        ),
    }


def find_basis_difference_list(
    scenario_set: ScenarioSet,
) -> list[BasisDifference]:
    """Report every assumption that differs across the journeys.

    Brief:
        The guard that keeps a comparison honest. An empty result
        means the only thing that differs is behaviour, which is
        what makes the four figures worth showing.

    Arguments:
        scenario_set (ScenarioSet): Journeys being compared.

    Returns:
        List[BasisDifference]: Assumptions that are not shared.

    Warning:
        Reports rather than refuses. A reader comparing two
        returns on purpose is doing something reasonable; they
        just must not be told it was behaviour.
    """
    if not scenario_set.is_comparable_bool:
        return []
    value_dict_list = [
        _describe_basis_values(scenario)
        for scenario in scenario_set.scenario_list
    ]
    difference_list = []
    for basis_str in value_dict_list[0]:
        value_str_list = [
            value_dict[basis_str] for value_dict in value_dict_list
        ]
        if len(set(value_str_list)) > 1:
            difference_list.append(
                BasisDifference(basis_str, value_str_list)
            )
    return difference_list


def run_journey_outcome(
    scenario: PlanScenario,
) -> JourneyOutcome:
    """Run one journey and reduce it to the figures that compare.

    Brief:
        Everything a comparison needs and nothing it does not, so
        the four-up headline is cheap to draw.

    Arguments:
        scenario (PlanScenario): Journey to run.

    Returns:
        JourneyOutcome: What that journey came to.

    Warning:
        A plan running for no months reports zeroes rather than
        raising, because an empty journey is a legitimate thing to
        compare against.
    """
    compiled = compile_scenario(scenario)
    run = simulate_nominal_run(
        compiled.fund_list,
        compiled.settings,
        False,
        compiled.currency,
    )
    snapshot_list = run.result.monthly_snapshots_list
    if not snapshot_list:
        return JourneyOutcome(scenario.name_str, 0.0, 0.0, 0.0, 0.0)
    final_snapshot = snapshot_list[-1]
    return JourneyOutcome(
        name_str=scenario.name_str,
        final_value_float=final_snapshot.portfolio_value_float,
        real_value_float=deflate_amount_float(
            final_snapshot.portfolio_value_float,
            compiled.inflation_percent_float,
            len(snapshot_list),
        ),
        invested_float=final_snapshot.invested_amount_float,
        tax_paid_float=final_snapshot.tax_paid_float,
    )


def run_scenario_set(
    scenario_set: ScenarioSet,
) -> list[JourneyOutcome]:
    """Run every journey in the set, in order."""
    return [
        run_journey_outcome(scenario)
        for scenario in scenario_set.scenario_list
    ]


def find_spread_float(
    outcome_list: list[JourneyOutcome],
) -> float:
    """The gap between the best and the worst journey.

    Brief:
        The headline number of the whole comparison: what the
        difference in behaviour was worth.

    Arguments:
        outcome_list (List[JourneyOutcome]): Finished journeys.

    Returns:
        float: Best final value minus worst, zero when under two.

    Warning:
        Nominal. The real spread is smaller and often the more
        honest figure to quote.
    """
    if len(outcome_list) < 2:
        return 0.0
    value_list = [
        outcome.final_value_float for outcome in outcome_list
    ]
    return max(value_list) - min(value_list)


def add_journey(
    scenario_set: ScenarioSet,
    scenario: PlanScenario,
) -> ScenarioSet:
    """Add one journey, replacing any of the same name.

    Brief:
        Saving twice under one name means "I changed my mind about
        that journey", not "I now have two of them".

    Arguments:
        scenario_set (ScenarioSet): Set being added to.
        scenario (PlanScenario): Journey to add.

    Returns:
        ScenarioSet: A new set carrying the journey.

    Warning:
        Silently drops the oldest journey once the set is full,
        because a comparison of seven curves reads as noise.
    """
    kept_list = [
        held
        for held in scenario_set.scenario_list
        if held.name_str != scenario.name_str
    ]
    kept_list.append(scenario)
    return ScenarioSet(kept_list[-MAXIMUM_JOURNEY_COUNT_INT:])


def remove_journey(
    scenario_set: ScenarioSet,
    name_str: str,
) -> ScenarioSet:
    """Drop one journey by name."""
    return ScenarioSet(
        [
            held
            for held in scenario_set.scenario_list
            if held.name_str != name_str
        ]
    )
