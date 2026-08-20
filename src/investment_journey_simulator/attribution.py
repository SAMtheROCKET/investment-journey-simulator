"""Why two journeys ended up so far apart.

Showing four corpus figures side by side is easy and not very
useful. The number a reader actually wants is *why*: how much of the
gap was money never invested, how much was compounding lost to a
pause, how much went in tax, how much in fees.

## How the split is computed

Naively you would revert one behaviour at a time and record the
drop. That works but the answer depends on the order you revert in,
because the effects interact - a pause costs more when the
contribution is larger. Quoting an order-dependent number as if it
were a fact would be exactly the kind of false precision this
program avoids elsewhere.

So each cause is given its **Shapley value**: its average marginal
effect across every possible order. That is the one split which is

* **order-independent** - no arbitrary choice of which cause to
  revert first, and
* **exact** - the causes sum to the whole gap, with nothing left
  over. This is the efficiency property of the Shapley value, and
  `test_attribution.py` checks it rather than trusting it.

The cost is 2^n simulations for n differing causes. With the causes
capped at six that is at most sixty-four runs of a plan, which is
fast enough to do on demand and is why the cap exists.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from math import factorial

from investment_journey_simulator.plan_scenario import PlanScenario
from investment_journey_simulator.scenario_set import run_journey_outcome
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_RETIRE_STR,
    EVENT_SETS_INSTALMENT_TUPLE,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_WITHDRAW_STR,
)

CAUSE_CONTRIBUTION_STR: str = "contributions"
CAUSE_STEPUP_STR: str = "stepup"
CAUSE_PAUSE_STR: str = "pauses"
CAUSE_WITHDRAWAL_STR: str = "withdrawals"
CAUSE_LUMPSUM_STR: str = "lump sums"
CAUSE_FEE_STR: str = "fees"
CAUSE_RETURN_STR: str = "return assumption"

MAXIMUM_CAUSE_COUNT_INT: int = 6

# Which event types each cause owns. A cause with no entry here is
# carried on the funds rather than on the timeline.
CAUSE_EVENT_TYPE_DICT: dict[str, tuple] = {
    CAUSE_CONTRIBUTION_STR: EVENT_SETS_INSTALMENT_TUPLE,
    CAUSE_STEPUP_STR: (EVENT_STEPUP_STR,),
    CAUSE_PAUSE_STR: (EVENT_PAUSE_STR, EVENT_RESUME_STR),
    CAUSE_WITHDRAWAL_STR: (
        EVENT_WITHDRAW_STR,
        EVENT_RETIRE_STR,
        EVENT_STOP_WITHDRAW_STR,
    ),
    CAUSE_LUMPSUM_STR: (EVENT_LUMPSUM_STR,),
}

CAUSE_LABEL_DICT: dict[str, str] = {
    CAUSE_CONTRIBUTION_STR: "Contributions never made",
    CAUSE_STEPUP_STR: "The raise that never happened",
    CAUSE_PAUSE_STR: "Compounding lost to the pause",
    CAUSE_WITHDRAWAL_STR: "Money taken out early",
    CAUSE_LUMPSUM_STR: "Lump sums not invested",
    CAUSE_FEE_STR: "Higher costs",
    CAUSE_RETURN_STR: "A different return assumption",
}

CAUSE_EXPLANATION_DICT: dict[str, str] = {
    CAUSE_CONTRIBUTION_STR: (
        "Money that went in on one plan and not the other, plus "
        "everything it would have earned."
    ),
    CAUSE_STEPUP_STR: (
        "Raising the instalment with your salary. It looks small "
        "in year one and compounds for every year after it."
    ),
    CAUSE_PAUSE_STR: (
        "This is the one that surprises people. A pause costs far "
        "more than the instalments you skipped, because the money "
        "you did not invest also never earned anything for the "
        "whole remaining horizon."
    ),
    CAUSE_WITHDRAWAL_STR: (
        "Taking money out stops it compounding, and may realise a "
        "tax charge that reduces the balance further."
    ),
    CAUSE_LUMPSUM_STR: (
        "A bonus invested in year eight compounds for the years "
        "that remain, not for the whole horizon."
    ),
    CAUSE_FEE_STR: (
        "A percentage a year, charged on the whole balance, for "
        "every year of the plan."
    ),
    CAUSE_RETURN_STR: (
        "Not a behaviour at all - the two plans assumed different "
        "markets. Treat this line as a warning that the "
        "comparison is not purely about decisions."
    ),
}


@dataclass(frozen=True)
class AttributedCause:
    """One named reason two journeys differ, and by how much."""

    cause_str: str
    amount_float: float

    @property
    def label_str(self) -> str:
        """Plain-language name of this cause."""
        return CAUSE_LABEL_DICT.get(self.cause_str, self.cause_str)

    @property
    def explanation_str(self) -> str:
        """Why this cause moves the number as much as it does."""
        return CAUSE_EXPLANATION_DICT.get(self.cause_str, "")

    @property
    def is_cost_bool(self) -> bool:
        """Whether this cause reduced the final corpus."""
        return self.amount_float < 0.0


@dataclass(frozen=True)
class Attribution:
    """The whole gap between two journeys, split by cause."""

    baseline_name_str: str
    variant_name_str: str
    baseline_value_float: float
    variant_value_float: float
    cause_list: list[AttributedCause]
    residual_float: float

    @property
    def gap_float(self) -> float:
        """The difference the causes have to account for."""
        return self.variant_value_float - self.baseline_value_float

    @property
    def ranked_cause_list(self) -> list[AttributedCause]:
        """Causes ordered by how much they moved the number."""
        return sorted(
            self.cause_list,
            key=lambda cause: abs(cause.amount_float),
            reverse=True,
        )


def _select_event_list(
    scenario: PlanScenario,
    cause_str: str,
) -> list:
    """The events of one cause, taken from one scenario."""
    type_tuple = CAUSE_EVENT_TYPE_DICT.get(cause_str, ())
    return [
        event
        for event in scenario.plan.event_list
        if event.event_type_str in type_tuple
    ]


def _differs_bool(
    baseline: PlanScenario,
    variant: PlanScenario,
    cause_str: str,
) -> bool:
    """Whether two journeys actually differ in this cause."""
    if cause_str == CAUSE_FEE_STR:
        return _fund_field_tuple(
            baseline, "expense_percent_float"
        ) != _fund_field_tuple(variant, "expense_percent_float")
    if cause_str == CAUSE_RETURN_STR:
        return _fund_field_tuple(
            baseline, "gross_return_percent_float"
        ) != _fund_field_tuple(
            variant, "gross_return_percent_float"
        )
    return sorted(
        _describe_event_list(baseline, cause_str)
    ) != sorted(_describe_event_list(variant, cause_str))


def _describe_event_list(
    scenario: PlanScenario,
    cause_str: str,
) -> list:
    """Comparable descriptions of one cause's events."""
    return [
        (
            event.event_type_str,
            event.event_date,
            event.amount_float,
            event.percent_float,
        )
        for event in _select_event_list(scenario, cause_str)
    ]


def _fund_field_tuple(
    scenario: PlanScenario,
    field_name_str: str,
) -> tuple:
    """One numeric field, read off every fund in order."""
    return tuple(
        getattr(fund_configuration, field_name_str)
        for fund_configuration in scenario.fund_list
    )


def find_differing_cause_list(
    baseline: PlanScenario,
    variant: PlanScenario,
) -> list[str]:
    """List the causes on which two journeys actually differ.

    Brief:
        Only differing causes enter the split, which keeps the
        run count down and stops the chart showing rows of zero.

    Arguments:
        baseline (PlanScenario): The reference journey.
        variant (PlanScenario): The journey being explained.

    Returns:
        List[str]: Differing causes, in a stable order.

    Warning:
        Truncated at `MAXIMUM_CAUSE_COUNT_INT`, because the split
        costs two to the power of this number in simulations.
    """
    cause_list = [
        cause_str
        for cause_str in CAUSE_LABEL_DICT
        if _differs_bool(baseline, variant, cause_str)
    ]
    return cause_list[:MAXIMUM_CAUSE_COUNT_INT]


def build_hybrid_scenario(
    baseline: PlanScenario,
    variant: PlanScenario,
    cause_set: frozenset,
) -> PlanScenario:
    """Build the journey that is baseline except for these causes.

    Brief:
        The workhorse of the split. Taking the variant's version of
        some causes and the baseline's version of the rest is what
        isolates each one's effect.

    Arguments:
        baseline (PlanScenario): The reference journey.
        variant (PlanScenario): The journey being explained.
        cause_set (frozenset): Causes taken from the variant.

    Returns:
        PlanScenario: The hybrid journey.

    Warning:
        Events outside every named cause - notes and inflation
        changes - always come from the baseline, so they never
        drift between hybrids.
    """
    owned_type_set: set = set()
    for type_tuple in CAUSE_EVENT_TYPE_DICT.values():
        owned_type_set |= set(type_tuple)
    event_list = [
        event
        for event in baseline.plan.event_list
        if event.event_type_str not in owned_type_set
    ]
    for cause_str in CAUSE_EVENT_TYPE_DICT:
        source = (
            variant if cause_str in cause_set else baseline
        )
        event_list.extend(_select_event_list(source, cause_str))
    return replace(
        baseline,
        plan=replace(baseline.plan, event_list=event_list),
        fund_list=_build_hybrid_fund_list(
            baseline, variant, cause_set
        ),
    )


def _build_hybrid_fund_list(
    baseline: PlanScenario,
    variant: PlanScenario,
    cause_set: frozenset,
) -> list:
    """Take fees and returns from whichever journey owns them."""
    fund_list = []
    for index_int, fund_configuration in enumerate(
        baseline.fund_list
    ):
        changed = fund_configuration
        if CAUSE_FEE_STR in cause_set:
            changed = replace(
                changed,
                expense_percent_float=_read_fund_field_float(
                    variant,
                    index_int,
                    "expense_percent_float",
                    fund_configuration.expense_percent_float,
                ),
            )
        if CAUSE_RETURN_STR in cause_set:
            changed = replace(
                changed,
                gross_return_percent_float=(
                    _read_fund_field_float(
                        variant,
                        index_int,
                        "gross_return_percent_float",
                        (
                            fund_configuration
                        ).gross_return_percent_float,
                    )
                ),
            )
        fund_list.append(changed)
    return fund_list


def _read_fund_field_float(
    scenario: PlanScenario,
    index_int: int,
    field_name_str: str,
    fallback_float: float,
) -> float:
    """Read one fund's field, tolerating a shorter fund list."""
    if index_int >= len(scenario.fund_list):
        return fallback_float
    return float(
        getattr(scenario.fund_list[index_int], field_name_str)
    )


def _build_value_reader(
    baseline: PlanScenario,
    variant: PlanScenario,
):
    """Build a memoised final-value function over cause subsets.

    Brief:
        The Shapley computation asks for the same subset many
        times, so each one is simulated once and remembered.

    Arguments:
        baseline (PlanScenario): The reference journey.
        variant (PlanScenario): The journey being explained.

    Returns:
        Callable: Maps a frozenset of causes to a final value.

    Warning:
        Memoised per call, so the cache never outlives the one
        comparison it was built for.
    """
    cache_dict: dict[frozenset, float] = {}

    def read_value_float(cause_set: frozenset) -> float:
        if cause_set not in cache_dict:
            cache_dict[cause_set] = run_journey_outcome(
                build_hybrid_scenario(
                    baseline, variant, cause_set
                )
            ).final_value_float
        return cache_dict[cause_set]

    return read_value_float


def _build_weight_float(
    subset_size_int: int,
    total_count_int: int,
) -> float:
    """The Shapley weight of one subset size."""
    return (
        factorial(subset_size_int)
        * factorial(total_count_int - subset_size_int - 1)
        / factorial(total_count_int)
    )


def compute_shapley_dict(
    baseline: PlanScenario,
    variant: PlanScenario,
    cause_list: list[str],
) -> dict[str, float]:
    """Split the gap between two journeys, cause by cause.

    Brief:
        Each cause is credited with its average marginal effect
        across every order the causes could be applied in, which is
        the one split that is both order-independent and exact.

    Arguments:
        baseline (PlanScenario): The reference journey.
        variant (PlanScenario): The journey being explained.
        cause_list (List[str]): Causes to split the gap between.

    Returns:
        Dict[str, float]: Amount attributed to each cause.

    Warning:
        Runs two to the power of the cause count simulations.
    """
    read_value_float = _build_value_reader(baseline, variant)
    total_count_int = len(cause_list)
    shapley_dict = dict.fromkeys(cause_list, 0.0)
    for cause_str in cause_list:
        other_list = [
            other_str
            for other_str in cause_list
            if other_str != cause_str
        ]
        for subset_size_int in range(len(other_list) + 1):
            weight_float = _build_weight_float(
                subset_size_int, total_count_int
            )
            for subset_tuple in combinations(
                other_list, subset_size_int
            ):
                without_set = frozenset(subset_tuple)
                with_set = without_set | {cause_str}
                shapley_dict[cause_str] += weight_float * (
                    read_value_float(with_set)
                    - read_value_float(without_set)
                )
    return shapley_dict


def attribute_gap(
    baseline: PlanScenario,
    variant: PlanScenario,
) -> Attribution:
    """Explain why one journey ended up worth less than another.

    Brief:
        The headline of the whole comparison. Returns the gap, the
        causes it splits into, and any residual left unexplained.

    Arguments:
        baseline (PlanScenario): The reference journey.
        variant (PlanScenario): The journey being explained.

    Returns:
        Attribution: The gap, split by cause.

    Warning:
        The residual is reported rather than absorbed into the
        largest cause. It should be zero to within floating-point
        error; anything else is a bug worth seeing.
    """
    cause_list = find_differing_cause_list(baseline, variant)
    baseline_float = run_journey_outcome(
        baseline
    ).final_value_float
    variant_float = run_journey_outcome(variant).final_value_float
    shapley_dict = (
        compute_shapley_dict(baseline, variant, cause_list)
        if cause_list
        else {}
    )
    attributed_float = sum(shapley_dict.values())
    return Attribution(
        baseline_name_str=baseline.name_str,
        variant_name_str=variant.name_str,
        baseline_value_float=baseline_float,
        variant_value_float=variant_float,
        cause_list=[
            AttributedCause(cause_str, amount_float)
            for cause_str, amount_float in shapley_dict.items()
        ],
        residual_float=(
            variant_float - baseline_float - attributed_float
        ),
    )
