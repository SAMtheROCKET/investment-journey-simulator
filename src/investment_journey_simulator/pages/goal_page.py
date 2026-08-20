"""Goal Planner: the question asked backwards.

Every other screen asks "if I do this, what do I get". This one asks
"I want that - what would it take". Three answers, because there are
three things a reader can actually change: how much they put in, how
long they leave it, and what they assume the market does.

The third is deliberately last and deliberately hedged. Raising the
assumed return is not a plan; it is a wish, and the screen says so.
"""

from __future__ import annotations

import streamlit as st

from investment_journey_simulator.currency import (
    describe_money_str,
    format_money_str,
)
from investment_journey_simulator.goal_seek import (
    solve_required_horizon_years_int,
    solve_required_monthly_sip_float,
    solve_required_return_percent_float,
)
from investment_journey_simulator.pages.page_shell import (
    has_investment_bool,
    open_page,
    render_empty_state,
)
from investment_journey_simulator.plan_scenario import (
    CompiledPlan,
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.portal_state import write_scenario
from investment_journey_simulator.scenario_edits import (
    set_horizon_years,
    set_monthly_contribution,
)
from investment_journey_simulator.scenario_set import run_journey_outcome
from investment_journey_simulator.ui.chrome import render_insight
from investment_journey_simulator.ui.plan_summary import (
    render_scenario_assumptions,
)

TITLE_STR: str = "Goal Planner"
LEAD_STR: str = (
    "Name the number you want to end up with, and see what would "
    "actually reach it."
)
TARGET_STATE_KEY_STR: str = "goal_target_amount"
DEFAULT_TARGET_MULTIPLE_FLOAT: float = 2.0


def render_target_input(
    scenario: PlanScenario,
    compiled: CompiledPlan,
) -> float:
    """Ask what the reader is aiming for.

    Brief:
        Opens on twice what the current plan reaches, which is a
        stretch without being fantasy, and is immediately editable.

    Arguments:
        scenario (PlanScenario): The plan being worked on.
        compiled (CompiledPlan): Its compiled form.

    Returns:
        float: The target corpus.

    Warning:
        Nominal, not inflation-adjusted. A target set in today's
        money is a different and harder question, and the caption
        says which one this is.
    """
    current_float = run_journey_outcome(scenario).final_value_float
    default_float = max(
        current_float * DEFAULT_TARGET_MULTIPLE_FLOAT, 100000.0
    )
    target_float = st.number_input(
        "What do you want to end up with?",
        help=(
            "A figure at the end of the plan, in future money rather than "
            "today's."
        ),
        min_value=0.0,
        value=float(round(default_float, -5)),
        step=100000.0,
        key=TARGET_STATE_KEY_STR,
    )
    st.caption(
        "A figure in future money, at the end of the plan - not "
        f"in today's purchasing power. Your plan currently reaches "
        f"{format_money_str(current_float, compiled.currency)}."
    )
    return float(target_float)


def render_answers(
    scenario: PlanScenario,
    compiled: CompiledPlan,
    target_float: float,
) -> None:
    """Show what each lever would have to do, and apply it.

    Brief:
        Two of these three are things a reader can actually do, so
        each carries the button that does it. The third is not a
        lever anyone controls, and it carries no button at all -
        that absence is the point the screen is making.

    Arguments:
        scenario (PlanScenario): The plan being changed.
        compiled (CompiledPlan): Its compiled form.
        target_float (float): Corpus to reach.

    Returns:
        None: The three answers are rendered.
    """
    st.subheader("Three ways to get there")
    first, second, third = st.columns(3)
    with first:
        _render_instalment_answer(scenario, compiled, target_float)
    with second:
        _render_horizon_answer(scenario, compiled, target_float)
    with third:
        _render_return_answer(compiled, target_float)


def _render_instalment_answer(
    scenario: PlanScenario,
    compiled: CompiledPlan,
    target_float: float,
) -> None:
    """What monthly amount would reach the target, and set it."""
    st.markdown("**Invest more each month**")
    solved_float = solve_required_monthly_sip_float(
        compiled.fund_list, compiled.settings, target_float
    )
    if solved_float is None:
        st.warning(
            "No monthly amount within a sensible range reaches "
            "this. The target needs longer, or lowering."
        )
        return
    st.metric(
        "Monthly instalment needed",
        format_money_str(solved_float, compiled.currency),
        help=describe_money_str(solved_float, compiled.currency),
    )
    st.caption(
        "Every fund is scaled by the same factor, so the mix of "
        "your portfolio is unchanged - only its size."
    )
    if st.button(
        "Apply this amount to my plan",
        key="goal_apply_instalment",
        width="stretch",
    ):
        write_scenario(
            set_monthly_contribution(scenario, solved_float)
        )
        st.rerun()


def _render_horizon_answer(
    scenario: PlanScenario,
    compiled: CompiledPlan,
    target_float: float,
) -> None:
    """How long the current plan would need, and set it."""
    st.markdown("**Leave it invested for longer**")
    solved_int = solve_required_horizon_years_int(
        compiled.fund_list, compiled.settings, target_float
    )
    if solved_int is None:
        st.warning(
            "Not reachable within a working lifetime at this "
            "contribution. More has to go in."
        )
        return
    extra_int = solved_int - compiled.settings.horizon_years_int
    st.metric(
        "Years needed",
        f"{solved_int}",
        delta=f"{extra_int:+d} years" if extra_int else None,
    )
    st.caption(
        "Usually the cheapest lever there is, and the one nobody "
        "wants to use."
    )
    if st.button(
        "Apply this horizon to my plan",
        key="goal_apply_horizon",
        width="stretch",
    ):
        write_scenario(set_horizon_years(scenario, solved_int))
        st.rerun()


def _read_base_return_percent_float(
    compiled: CompiledPlan,
) -> float:
    """The gross return the plan currently assumes."""
    if not compiled.fund_list:
        return 0.0
    return float(
        compiled.fund_list[0].gross_return_percent_float
    )


def solve_required_absolute_return_float(
    compiled: CompiledPlan,
    target_float: float,
) -> float | None:
    """The return a plan would have to earn, as a rate.

    Brief:
        `solve_required_return_percent_float` answers with a
        *shift* in percentage points, which is the right shape for
        a multi-fund plan because it preserves the spread between
        an equity fund and a debt one. A reader wants the rate
        itself, so the baseline is added back here.

    Arguments:
        compiled (CompiledPlan): The plan being solved.
        target_float (float): Corpus to reach.

    Returns:
        Optional[float]: Required gross annual return, or None
            when no plausible return reaches the target.

    Warning:
        On a multi-fund plan this reports the first fund's rate
        after the shift; the others move by the same points.
    """
    shift_float = solve_required_return_percent_float(
        compiled.fund_list, compiled.settings, target_float
    )
    if shift_float is None:
        return None
    return _read_base_return_percent_float(compiled) + shift_float


def _render_return_answer(
    compiled: CompiledPlan,
    target_float: float,
) -> None:
    """What return would be required, with the caveat it needs."""
    st.markdown("**Assume a higher return**")
    solved_float = solve_required_absolute_return_float(
        compiled, target_float
    )
    if solved_float is None:
        st.warning(
            "No plausible return reaches this. Changing the "
            "assumption will not get you there."
        )
        return
    base_float = _read_base_return_percent_float(compiled)
    st.metric(
        "Gross annual return needed",
        f"{solved_float:.2f}%",
        delta=f"{solved_float - base_float:+.2f} points",
    )
    st.caption(
        "**This is not a lever you control.** It is what the "
        "market would have to do. Treat a large number here as "
        "the plan telling you the target is unrealistic, not as "
        "a fund to go looking for."
    )
    # No button here, deliberately, and the absence is the
    # argument. Offering to "apply" a required return would let a
    # reader hit their goal by editing an assumption, which is the
    # single most dangerous thing this program could make easy.
    st.button(
        "Not something you can apply",
        key="goal_apply_return",
        disabled=True,
        width="stretch",
    )


def render_gap_line(
    scenario: PlanScenario,
    compiled: CompiledPlan,
    target_float: float,
) -> None:
    """Say how far off the plan currently is, before the levers.

    Brief:
        The number a reader actually wants first. Without it the
        three answers below are solutions to a problem whose size
        has not been stated.

    Arguments:
        scenario (PlanScenario): The plan being measured.
        compiled (CompiledPlan): Its compiled form.
        target_float (float): Corpus being aimed at.

    Returns:
        None: The gap line is rendered.
    """
    current_float = run_journey_outcome(scenario).final_value_float
    gap_float = target_float - current_float
    if gap_float <= 0.0:
        render_insight(
            "Your plan already reaches this target, with "
            f"{format_money_str(-gap_float, compiled.currency)} "
            "to spare. The levers below show what it would take "
            "to get there sooner or with less.",
            title_str="You are already there",
        )
        return
    share_float = 100.0 * gap_float / target_float
    render_insight(
        f"You are "
        f"{format_money_str(gap_float, compiled.currency)} short "
        f"- about {share_float:.0f}% of the target. Each answer "
        "below closes that whole gap on its own, so you would do "
        "one of them, not all three.",
        title_str="The size of the gap",
    )


def render_reality_check(
    compiled: CompiledPlan,
    target_float: float,
) -> None:
    """Say plainly when a target is out of proportion."""
    solved_float = solve_required_absolute_return_float(
        compiled, target_float
    )
    if solved_float is None or solved_float <= 18.0:
        return
    st.warning(
        f"Reaching this target would need about "
        f"{solved_float:.0f}% a year, sustained for "
        f"{compiled.settings.horizon_years_int} years. Very few "
        "assets have ever done that over such a period. The "
        "honest reading is that the target needs more time or "
        "more money, not a better fund."
    )


def render() -> None:
    """Render the Goal Planner page."""
    scenario = open_page(TITLE_STR, LEAD_STR)
    if not has_investment_bool(scenario):
        render_empty_state(
            "Nothing is being invested yet",
            "A goal needs a plan to measure against. Set a "
            "monthly amount on Quick Projection or Guided "
            "Journey, then come back.",
        )
        return
    compiled = compile_scenario(scenario)
    render_scenario_assumptions(scenario)
    target_float = render_target_input(scenario, compiled)
    if target_float <= 0.0:
        st.info("Enter a target above.")
        return
    render_gap_line(scenario, compiled, target_float)
    st.divider()
    render_answers(scenario, compiled, target_float)
    render_reality_check(compiled, target_float)
