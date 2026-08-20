"""What the plan currently comes to, said the same way everywhere.

Nine screens all want to show some version of "and this is where the
plan stands". Left to themselves they would each run the engine
slightly differently, format the figure slightly differently, and
disagree by a rounding rule - which is exactly the class of bug that
destroys trust in a number, because the reader has no way to tell
which screen is wrong.

So there is one projection here, one set of assumption chips, and one
pulse. A screen that wants to show the plan's standing calls this.

The assumption chips are the part worth defending. They are rendered
inline, never inside an expander, because a projection whose
assumptions take a click to find is a projection most readers will
take for a forecast - and this program's whole claim is that it is
not one.
"""

from __future__ import annotations

from dataclasses import dataclass

from investment_journey_simulator.currency import format_money_str
from investment_journey_simulator.dashboard_run import (
    simulate_nominal_run,
)
from investment_journey_simulator.inflation import (
    deflate_amount_float,
)
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.ui.chrome import (
    render_assumption_bar,
    render_plan_pulse,
)

MONTHS_IN_YEAR_INT: int = 12


@dataclass(frozen=True)
class PlanProjection:
    """One run of a plan, in the three figures a reader needs.

    Arguments:
        final_str (str): Ending value, formatted.
        invested_str (str): Total paid in, formatted.
        real_str (str): Ending value in today's money, formatted.
        growth_share_float (float): Percent of the ending value
            that is growth rather than contribution.
        is_runnable_bool (bool): False when the plan covers no
            months at all, in which case the strings are empty.
    """

    final_str: str
    invested_str: str
    real_str: str
    growth_share_float: float
    is_runnable_bool: bool


EMPTY_PROJECTION: PlanProjection = PlanProjection(
    "", "", "", 0.0, False
)


def project_scenario(scenario: PlanScenario) -> PlanProjection:
    """Run a plan and format what it comes to.

    Brief:
        Returns formatted strings rather than floats on purpose.
        Every screen showing a total then shows it identically,
        and the lakh-crore grouping is decided in one place.

    Arguments:
        scenario (PlanScenario): Plan to run.

    Returns:
        PlanProjection: The figures, or `EMPTY_PROJECTION` when
            the plan runs for no months.

    Warning:
        Runs the engine on every call. Screens that call this
        alongside their own run are paying twice; those pass their
        run's figures to the pulse directly instead.
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
        return EMPTY_PROJECTION
    final_snapshot = snapshot_list[-1]
    final_float = final_snapshot.portfolio_value_float
    invested_float = final_snapshot.invested_amount_float
    real_float = deflate_amount_float(
        final_float,
        compiled.inflation_percent_float,
        scenario.plan.horizon_years_int * MONTHS_IN_YEAR_INT,
    )
    share_float = (
        100.0 * (final_float - invested_float) / final_float
        if final_float > 0.0
        else 0.0
    )
    return PlanProjection(
        format_money_str(final_float, compiled.currency),
        format_money_str(invested_float, compiled.currency),
        format_money_str(real_float, compiled.currency),
        share_float,
        True,
    )


def assumption_chip_tuple(scenario: PlanScenario) -> tuple:
    """List every assumption standing behind the plan's figures.

    Brief:
        The tax chip is a caveat rather than a fact, because
        nothing is sold in the nominal run and a reader who takes
        the figure for post-tax has been misled by omission.

    Arguments:
        scenario (PlanScenario): Plan the figures came from.

    Returns:
        Tuple: `(text, is_warning)` pairs for the assumption bar.
    """
    compiled = compile_scenario(scenario)
    fund_count_int = len(scenario.fund_list)
    return (
        (f"{scenario.plan.horizon_years_int} years", False),
        (compiled.currency.code_str, False),
        (
            f"{fund_count_int} asset"
            f"{'' if fund_count_int == 1 else 's'}",
            False,
        ),
        (
            f"{compiled.inflation_percent_float:g}% inflation",
            False,
        ),
        (f"Tax rules: {compiled.regime.label_str}", False),
        ("Nothing sold, so no tax in this figure", True),
    )


def render_scenario_assumptions(scenario: PlanScenario) -> None:
    """Draw the assumption bar for one plan."""
    render_assumption_bar(assumption_chip_tuple(scenario))


def render_scenario_pulse(
    scenario: PlanScenario,
    projection: PlanProjection | None = None,
    label_str: str = "Plan pulse",
) -> bool:
    """Show where a plan stands, and on what basis.

    Brief:
        Takes an already-computed projection when the caller has
        one, so a screen that has just run the engine does not run
        it a second time to draw its own summary.

    Arguments:
        scenario (PlanScenario): Plan being summarised.
        projection (Optional[PlanProjection]): A run, if the caller
            already has one.
        label_str (str): Mark above the plate.

    Returns:
        bool: True when a pulse was drawn.

    Warning:
        Draws nothing and reports False for a plan running no
        months. It does not invent a zero: zero is a real answer
        and "no plan yet" is not.
    """
    resolved = (
        projection
        if projection is not None
        else project_scenario(scenario)
    )
    if not resolved.is_runnable_bool:
        return False
    render_plan_pulse(
        resolved.final_str,
        f"Projected value of {scenario.name_str} after "
        f"{scenario.plan.horizon_years_int} years, on the "
        "assumptions below.",
        (
            ("You pay in", resolved.invested_str),
            ("Today's money", resolved.real_str),
            ("Growth share", f"{resolved.growth_share_float:.0f}%"),
        ),
        label_str=label_str,
    )
    render_scenario_assumptions(scenario)
    return True
