"""A plan expressed as a timeline of events.

The classic dashboard asks for a plan as a form: an instalment, a
horizon, a step-up rule, a pause range. That is precise but it is
not how anyone thinks. People think in events - *I start in March, I
get a raise in year three, I pause for the wedding, I buy a car in
year eight, I retire in year twenty.*

This module is the model behind that idea. A plan is a list of dated
events; the compiler below turns them into the settings the existing
engine already understands. Nothing here re-implements any finance:
it is a translation layer, so the timeline and the classic dashboard
can never disagree about what a plan is worth.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from investment_journey_simulator.constants import (
    FINANCIAL_YEAR_START_MONTH_INT,
    MONTHS_IN_YEAR_INT,
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
    REBALANCE_TRIGGER_DATED_STR,
    STEPUP_MODE_GLOBAL_STR,
    SURCHARGE_MODE_SLAB_STR,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    InstalmentOverride,
    OneOffContribution,
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    SimulationSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.plan_policy import (
    DEFAULT_PLAN_POLICY,
    PlanPolicy,
)
from investment_journey_simulator.time_utils import (
    count_months_between_dates_int,
    derive_financial_year_int,
)

EVENT_START_SIP_STR: str = "Start investing"
EVENT_CHANGE_SIP_STR: str = "Change the monthly amount"
EVENT_STEPUP_STR: str = "Start yearly step-up"
EVENT_PAUSE_STR: str = "Pause contributions"
EVENT_RESUME_STR: str = "Resume contributions"
EVENT_LUMPSUM_STR: str = "One-off investment"
EVENT_WITHDRAW_STR: str = "Start withdrawing"
EVENT_RETIRE_STR: str = "Retire (stop investing, start income)"
EVENT_INCOME_STR: str = "Salary starts or changes"
EVENT_REBALANCE_STR: str = "Rebalance back to target"
EVENT_INFLATION_STR: str = "Inflation changes"
EVENT_STOP_WITHDRAW_STR: str = "Stop withdrawing"
EVENT_NOTE_STR: str = "Note to self"

EVENT_TYPE_TUPLE: tuple = (
    EVENT_START_SIP_STR,
    EVENT_CHANGE_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_LUMPSUM_STR,
    EVENT_WITHDRAW_STR,
    EVENT_RETIRE_STR,
    EVENT_INCOME_STR,
    EVENT_REBALANCE_STR,
    EVENT_INFLATION_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_NOTE_STR,
)

# The chooser groups events by the *verb* a reader has in mind at
# the moment they click a month: am I starting something here, am I
# ending something, or am I recording something about the world.
#
# An earlier grouping used areas - money in, money out, breaks,
# portfolio - which reads well in documentation and badly at the
# point of use. Someone who has clicked March 2031 already knows
# which area they are in; what they have not decided is whether
# this is a beginning or an end.
EVENT_GROUP_TUPLE: tuple = (
    (
        "Start something",
        (
            EVENT_START_SIP_STR,
            EVENT_LUMPSUM_STR,
            EVENT_STEPUP_STR,
            EVENT_WITHDRAW_STR,
            EVENT_REBALANCE_STR,
        ),
    ),
    (
        "Stop or change something",
        (
            EVENT_CHANGE_SIP_STR,
            EVENT_PAUSE_STR,
            EVENT_RESUME_STR,
            EVENT_STOP_WITHDRAW_STR,
            EVENT_RETIRE_STR,
        ),
    ),
    (
        "Record something about your life",
        (
            EVENT_INCOME_STR,
            EVENT_INFLATION_STR,
            EVENT_NOTE_STR,
        ),
    ),
)

EVENT_EXPLANATION_DICT: dict[str, str] = {
    EVENT_START_SIP_STR: (
        "The month your first instalment leaves your account. "
        "Everything before this is empty runway."
    ),
    EVENT_CHANGE_SIP_STR: (
        "Raise or cut the monthly amount from this month on. Use "
        "it for a promotion, a new EMI, or a change of plan."
    ),
    EVENT_STEPUP_STR: (
        "Increase the instalment by a fixed percentage every year "
        "from here. Most people's salaries grow; a flat SIP "
        "quietly assumes yours will not."
    ),
    EVENT_PAUSE_STR: (
        "Stop contributing without closing the plan. The money "
        "already invested keeps compounding."
    ),
    EVENT_RESUME_STR: (
        "Start contributing again after a pause, at the amount "
        "that was running before it."
    ),
    EVENT_LUMPSUM_STR: (
        "A single extra investment - a bonus, a maturity, a gift. "
        "It compounds from this month."
    ),
    EVENT_WITHDRAW_STR: (
        "Begin taking a fixed amount out every month. The plan "
        "reports the exact month the money would run out."
    ),
    EVENT_RETIRE_STR: (
        "Stop investing and start drawing an income in the same "
        "month. A pause and a withdrawal in one event."
    ),
    EVENT_INCOME_STR: (
        "Your total annual income from this year on. It does not "
        "fund the plan - it decides the surcharge on your capital "
        "gains, including the marginal relief near a threshold."
    ),
    EVENT_REBALANCE_STR: (
        "Sell whatever has grown past its target share and buy "
        "what has lagged. This realises gains, so it is taxed - "
        "the report shows what the trade cost you."
    ),
    EVENT_INFLATION_STR: (
        "The rate prices rise at, from this month on. It changes "
        "nothing about the value - only what that value is "
        "worth in today's money."
    ),
    EVENT_STOP_WITHDRAW_STR: (
        "End the monthly withdrawal from this month on. What is "
        "left keeps compounding instead of being drawn down."
    ),
    EVENT_NOTE_STR: (
        "A marker for something that mattered - a house, a job, a "
        "child. It changes no number at all; it is there so the "
        "report reads like your life and not just a plan."
    ),
}

# Events that record something without changing what the plan is
# worth. Kept explicit so the interface can say so out loud rather
# than letting a reader assume a marker moved the money.
EVENT_ANNOTATION_TUPLE: tuple = (EVENT_NOTE_STR,)

EVENT_NEEDS_AMOUNT_TUPLE: tuple = (
    EVENT_START_SIP_STR,
    EVENT_CHANGE_SIP_STR,
    EVENT_LUMPSUM_STR,
    EVENT_WITHDRAW_STR,
    EVENT_RETIRE_STR,
    EVENT_INCOME_STR,
)
EVENT_SETS_INSTALMENT_TUPLE: tuple = (
    EVENT_START_SIP_STR,
    EVENT_CHANGE_SIP_STR,
)
EVENT_NEEDS_PERCENT_TUPLE: tuple = (
    EVENT_STEPUP_STR,
    EVENT_INFLATION_STR,
)


@dataclass(frozen=True)
class TimelineEvent:
    """One dated thing that happens to a plan."""

    event_type_str: str
    event_date: date
    amount_float: float = 0.0
    percent_float: float = 0.0
    note_str: str = ""
    fund_name_str: str = ""

    @property
    def explanation_str(self) -> str:
        """Plain-language description of this kind of event.

        Brief:
            Shown on hover, so the reader never has to guess what
            an option would do before choosing it.

        Arguments:
            None.

        Returns:
            str: One or two sentences of explanation.

        Warning:
            Unknown event types describe themselves as unknown
            rather than raising.
        """
        return EVENT_EXPLANATION_DICT.get(
            self.event_type_str, "Unrecognised event."
        )


@dataclass(frozen=True)
class TimelinePlan:
    """A whole plan expressed as dated events."""

    start_date: date
    horizon_years_int: int
    event_list: list[TimelineEvent] = field(default_factory=list)

    @property
    def ordered_event_list(self) -> list[TimelineEvent]:
        """Events in calendar order.

        Brief:
            The compiler depends on order, and the user is free to
            add events in any sequence.

        Arguments:
            None.

        Returns:
            List[TimelineEvent]: Chronologically sorted events.

        Warning:
            Two events in the same month keep their insertion
            order relative to each other.
        """
        return sorted(
            self.event_list, key=lambda event: event.event_date
        )

    @property
    def end_date(self) -> date:
        """Last month the plan covers.

        Brief:
            Used to lay out the axis of the timeline.

        Arguments:
            None.

        Returns:
            date: Month the horizon ends in.

        Warning:
            Derived from the horizon, not from the last event, so
            the axis does not jump as events are added.
        """
        total_months_int = (
            self.horizon_years_int * MONTHS_IN_YEAR_INT
        )
        zero_based_int = (
            self.start_date.month - 1 + total_months_int
        )
        return date(
            self.start_date.year
            + zero_based_int // MONTHS_IN_YEAR_INT,
            zero_based_int % MONTHS_IN_YEAR_INT + 1,
            1,
        )


def _month_index_int(plan: TimelinePlan, event_date: date) -> int:
    """Locate an event on the plan's month grid.

    Brief:
        Negative offsets are clamped to zero so an event dated
        before the plan starts is treated as happening at the
        start rather than silently dropping off the grid.

    Arguments:
        plan (TimelinePlan): Plan providing the origin.
        event_date (date): Date being located.

    Returns:
        int: Zero-based month index.

    Warning:
        Events past the horizon keep their index and are simply
        never reached by the simulation.
    """
    return max(
        0,
        count_months_between_dates_int(
            plan.start_date, event_date
        ),
    )


def _collect_pause_range_list(
    plan: TimelinePlan,
) -> list[PauseRange]:
    """Pair every pause event with the resume that follows it.

    Brief:
        A pause with no matching resume runs to the end of the
        horizon, which is what "I stop and never restart" means.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        List[PauseRange]: Inclusive pause windows.

    Warning:
        A resume with no preceding pause is ignored rather than
        treated as an error, because the timeline lets events be
        added in any order.
    """
    pause_range_list: list[PauseRange] = []
    open_pause_date: date | None = None
    for event in plan.ordered_event_list:
        if event.event_type_str in (
            EVENT_PAUSE_STR,
            EVENT_RETIRE_STR,
        ):
            open_pause_date = event.event_date
        elif (
            event.event_type_str == EVENT_RESUME_STR
            and open_pause_date is not None
        ):
            pause_range_list.append(
                PauseRange(
                    open_pause_date,
                    event.event_date,
                    PAUSE_SCOPE_SIP_STR,
                )
            )
            open_pause_date = None
    if open_pause_date is not None:
        pause_range_list.append(
            PauseRange(
                open_pause_date,
                plan.end_date,
                PAUSE_SCOPE_SIP_STR,
            )
        )
    return pause_range_list


def _collect_instalment_override_list(
    plan: TimelinePlan,
    policy: PlanPolicy,
) -> list[InstalmentOverride]:
    """Turn every instalment event into a dated override.

    Brief:
        Each "start investing" or "change the amount" event sets
        the instalment from its own month. Emitting all of them,
        rather than only the first, is what lets a plan change its
        mind as often as a real life does.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        policy (PlanPolicy): Supplies the fallback fund name.

    Returns:
        List[InstalmentOverride]: Dated instalment changes.

    Warning:
        An empty fund name means every fund, so on a multi-fund
        plan a change that names no fund moves all of them.
    """
    return [
        InstalmentOverride(
            _month_index_int(plan, event.event_date),
            float(event.amount_float),
            event.fund_name_str or policy.default_fund_name_str,
        )
        for event in plan.ordered_event_list
        if event.event_type_str in EVENT_SETS_INSTALMENT_TUPLE
    ]


def _collect_one_off_list(
    plan: TimelinePlan,
    policy: PlanPolicy,
) -> list[OneOffContribution]:
    """Turn every lump sum into a contribution on its own month.

    Brief:
        A bonus received in year eight compounds from year eight.
        Collapsing every lump sum into month zero, as the first
        version did, silently overstated the corpus.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        policy (PlanPolicy): Supplies the fallback fund name.

    Returns:
        List[OneOffContribution]: Dated one-off investments.

    Warning:
        Several lump sums may share a month; all are kept.
    """
    return [
        OneOffContribution(
            _month_index_int(plan, event.event_date),
            float(event.amount_float),
            event.fund_name_str or policy.default_fund_name_str,
        )
        for event in plan.ordered_event_list
        if event.event_type_str == EVENT_LUMPSUM_STR
    ]


def _collect_income_by_year_tuple(
    plan: TimelinePlan,
    start_month_int: int = FINANCIAL_YEAR_START_MONTH_INT,
) -> tuple:
    """Turn salary events into income by tax year.

    Brief:
        The income decides the surcharge band and the marginal
        relief on it, so it is dated by tax year rather than by
        month - which is the unit the Act works in.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        start_month_int (int): Month the tax year opens in, so a
            raise lands in the same year the gains it taxes do.

    Returns:
        tuple: Pairs of tax year and total income.

    Warning:
        Two salary events in one tax year collapse to the later of
        the two, since a year has one total income.
    """
    income_dict: dict[int, float] = {}
    for event in plan.ordered_event_list:
        if event.event_type_str != EVENT_INCOME_STR:
            continue
        income_dict[
            derive_financial_year_int(
                event.event_date, start_month_int
            )
        ] = float(event.amount_float)
    return tuple(sorted(income_dict.items()))


def _collect_withdrawal_stop_list(
    plan: TimelinePlan,
) -> list[PauseRange]:
    """Turn every "stop withdrawing" event into a closed window.

    Brief:
        Stopping an income is a pause on the withdrawal side, which
        the engine already models. Expressing it that way means no
        new mechanism has to be trusted - only a new way of asking
        for one that is already tested.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        List[PauseRange]: Withdrawal-scoped pauses to the horizon.

    Warning:
        A stop runs to the end of the plan. Starting a withdrawal
        again afterwards needs a fresh "start withdrawing" event,
        and the engine models one withdrawal rule, so the later
        event replaces rather than resumes.
    """
    return [
        PauseRange(
            event.event_date,
            plan.end_date,
            PAUSE_SCOPE_WITHDRAWAL_STR,
        )
        for event in plan.ordered_event_list
        if event.event_type_str == EVENT_STOP_WITHDRAW_STR
    ]


def collect_inflation_schedule_tuple(plan: TimelinePlan) -> tuple:
    """Read the plan's inflation changes as a dated schedule.

    Brief:
        Public because inflation is applied after the simulation
        rather than inside it: the corpus is nominal, and the rate
        only decides what that corpus is worth in today's money.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        tuple: Pairs of month index and annual percent, in order.

    Warning:
        Two changes in one month collapse to the later of the two,
        since a month has one rate.
    """
    schedule_dict: dict[int, float] = {}
    for event in plan.ordered_event_list:
        if event.event_type_str != EVENT_INFLATION_STR:
            continue
        schedule_dict[_month_index_int(plan, event.event_date)] = (
            float(event.percent_float)
        )
    return tuple(sorted(schedule_dict.items()))


def _collect_rebalance_month_tuple(plan: TimelinePlan) -> tuple:
    """Find every month the reader placed a rebalance in.

    Brief:
        Duplicates collapse, because rebalancing twice in one month
        is one trade.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        Tuple: Month indices, ascending.

    Warning:
        Empty when the reader placed none, which is not the same as
        rebalancing being off - a policy rule may still act.
    """
    return tuple(
        sorted(
            {
                _month_index_int(plan, event.event_date)
                for event in plan.event_list
                if event.event_type_str == EVENT_REBALANCE_STR
            }
        )
    )


def _resolve_rebalance(
    plan: TimelinePlan,
    policy: PlanPolicy,
) -> RebalanceSettings:
    """Turn rebalance events and the standing rule into settings.

    Brief:
        A rebalance the reader placed by hand is not a rule with an
        interval - it happens in the month it was placed and in no
        other. Naming the months keeps it that way. A policy may
        additionally run a calendar or drift rule, which fires with
        no event ever being placed.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        policy (PlanPolicy): Standing rules beside the events.

    Returns:
        RebalanceSettings: Rules, off when neither source acts.

    Warning:
        Realigns to each fund's target allocation and sells only
        what is overweight, so the trade realises the smallest gain
        that still restores the target.
    """
    month_index_tuple = _collect_rebalance_month_tuple(plan)
    # A month the reader placed by hand is an instruction, not a
    # preference. A standing rule may only drive the trigger when
    # no such instruction exists, so adding a calendar rule can
    # never quietly move a rebalance someone dated deliberately.
    is_rule_bool = (
        not month_index_tuple
        and policy.is_rule_driven_rebalance_bool
        and policy.has_rebalance_rule_input_bool
    )
    if not month_index_tuple and not is_rule_bool:
        return RebalanceSettings(
            use_contribution_steering_bool=(
                policy.use_contribution_steering_bool
            ),
        )
    return _build_rebalance_settings(
        policy, month_index_tuple, is_rule_bool
    )


def _build_rebalance_settings(
    policy: PlanPolicy,
    month_index_tuple: tuple,
    is_rule_bool: bool,
) -> RebalanceSettings:
    """Assemble the settings for a rebalance that will happen.

    Brief:
        Reached only once something is known to act, so every field
        here describes how rather than whether.

    Arguments:
        policy (PlanPolicy): Standing rules beside the events.
        month_index_tuple (tuple): Months placed by hand.
        is_rule_bool (bool): Whether a standing rule drives it.

    Returns:
        RebalanceSettings: Rules the engine can apply.

    Warning:
        Hand-placed months win the trigger, so adding a policy rule
        cannot silently move a rebalance the reader dated.
    """
    return RebalanceSettings(
        is_enabled_bool=True,
        method_str=policy.rebalance_method_str,
        target_mode_str=policy.rebalance_target_mode_str,
        trigger_str=(
            policy.rebalance_trigger_str
            if is_rule_bool
            else REBALANCE_TRIGGER_DATED_STR
        ),
        interval_months_int=policy.rebalance_interval_months_int,
        drift_band_percent_float=(
            policy.rebalance_drift_band_percent_float
        ),
        tax_funding_str=policy.rebalance_tax_funding_str,
        maximum_events_int=policy.rebalance_maximum_events_int,
        use_contribution_steering_bool=(
            policy.use_contribution_steering_bool
        ),
        rebalance_month_index_tuple=month_index_tuple,
    )


def _resolve_stepup(
    plan: TimelinePlan,
    policy: PlanPolicy,
) -> StepUpSettings:
    """Build the step-up rule from the first step-up event.

    Brief:
        Only one step-up rule is supported, because the engine
        models one. A second step-up event is ignored, and the
        interface says so rather than pretending otherwise. The
        event supplies the rate and the date; the policy supplies
        the shape - how often it repeats and whether it rises by a
        percentage or by a flat sum.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        policy (PlanPolicy): Standing rules beside the events.

    Returns:
        StepUpSettings: Escalation rule, off when none was added.

    Warning:
        The delay is measured from the most recent instalment
        change, so changing the amount restarts the escalation
        clock - the next rise lands a year after the change.
    """
    for event in plan.ordered_event_list:
        if event.event_type_str != EVENT_STEPUP_STR:
            continue
        stepup_month_int = _month_index_int(plan, event.event_date)
        return StepUpSettings(
            mode_str=STEPUP_MODE_GLOBAL_STR,
            global_stepup_percent_float=event.percent_float,
            interval_months_int=policy.stepup_interval_months_int,
            fixed_increment_amount_float=(
                policy.stepup_fixed_increment_float
            ),
            first_stepup_month_index_int=max(
                0,
                stepup_month_int
                - _resolve_escalation_origin_int(
                    plan, stepup_month_int
                ),
            ),
        )
    return StepUpSettings()


def _resolve_escalation_origin_int(
    plan: TimelinePlan,
    month_index_int: int,
) -> int:
    """Find the month the instalment last changed.

    Brief:
        The engine counts step-up periods from the latest change
        to the instalment, so a delay expressed on the timeline
        has to be measured from the same origin.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        month_index_int (int): Month the step-up starts in.

    Returns:
        int: Month index the escalation clock runs from.

    Warning:
        Returns zero when no instalment event precedes the
        step-up, which matches the engine's own default.
    """
    origin_month_int = 0
    for event in plan.ordered_event_list:
        if event.event_type_str not in EVENT_SETS_INSTALMENT_TUPLE:
            continue
        event_month_int = _month_index_int(plan, event.event_date)
        if event_month_int > int(month_index_int):
            break
        origin_month_int = event_month_int
    return origin_month_int


def _resolve_withdrawal(
    plan: TimelinePlan,
    policy: PlanPolicy,
) -> WithdrawalSettings:
    """Build the withdrawal rule from the first exit event.

    Brief:
        Retiring and starting a withdrawal are the same thing to
        the engine; the difference is that retiring also pauses
        contributions, which the pause collector handles. The event
        supplies the date and the amount; the policy supplies the
        shape, which is what lets "four percent of the corpus a
        year" be expressed at all.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        policy (PlanPolicy): Standing rules beside the events.

    Returns:
        WithdrawalSettings: Exit rule, off when none was added.

    Warning:
        Only the first withdrawal event is used.
    """
    for event in plan.ordered_event_list:
        if event.event_type_str not in (
            EVENT_WITHDRAW_STR,
            EVENT_RETIRE_STR,
        ):
            continue
        return _build_withdrawal_settings(
            policy,
            float(event.amount_float),
            _month_index_int(plan, event.event_date),
        )
    return WithdrawalSettings()


def _build_withdrawal_settings(
    policy: PlanPolicy,
    amount_float: float,
    start_month_index_int: int,
) -> WithdrawalSettings:
    """Combine the event's amount with the policy's shape.

    Brief:
        The event says when and how much; the policy says what kind
        of withdrawal it is. Separating them is what lets a single
        "start withdrawing" event mean a fixed sum on one plan and
        four percent of the corpus on another.

    Arguments:
        policy (PlanPolicy): Standing rules beside the events.
        amount_float (float): Amount the event carried.
        start_month_index_int (int): Month the exit begins in.

    Returns:
        WithdrawalSettings: Exit rule for the engine.

    Warning:
        The amount is ignored by modes that compute their own, but
        it is kept so switching modes does not lose what was typed.
    """
    return WithdrawalSettings(
        is_enabled_bool=True,
        mode_str=policy.withdrawal_mode_str,
        fixed_amount_float=amount_float,
        monthly_schedule_list=list(
            policy.withdrawal_schedule_tuple
        ),
        annual_change_percent_float=(
            policy.withdrawal_annual_change_percent_float
        ),
        monthly_change_percent_list=list(
            policy.withdrawal_change_percent_tuple
        ),
        portfolio_percent_float=(
            policy.withdrawal_portfolio_percent_float
        ),
        start_month_index_int=start_month_index_int,
    )


def compile_settings(
    plan: TimelinePlan,
    tax: TaxSettings | None = None,
    policy: PlanPolicy | None = None,
) -> SimulationSettings:
    """Translate a timeline into engine settings.

    Brief:
        Every dated rule the engine understands is derived from the
        events, and every standing rule from the policy, so the
        timeline never needs its own maths.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        tax (Optional[TaxSettings]): Portfolio tax rules.
        policy (Optional[PlanPolicy]): Standing rules beside the
            events. Omitting it reproduces the behaviour this
            compiler had before policies existed.

    Returns:
        SimulationSettings: Settings the engine can run.

    Warning:
        Nothing is contributed until an instalment event says so,
        so a plan that starts investing in year three really is
        empty for three years.
    """
    active_policy = policy or DEFAULT_PLAN_POLICY
    return SimulationSettings(
        horizon_years_int=plan.horizon_years_int,
        portfolio_start_date=plan.start_date,
        sip_at_month_start_bool=(
            active_policy.sip_at_month_start_bool
        ),
        stepup=_resolve_stepup(plan, active_policy),
        withdrawal=_resolve_withdrawal(plan, active_policy),
        pauses=_resolve_pauses(plan),
        rebalance=_resolve_rebalance(plan, active_policy),
        tax=_apply_income_to_tax(plan, tax or TaxSettings()),
        one_off_contributions_list=_collect_one_off_list(
            plan, active_policy
        ),
        instalment_override_list=(
            _collect_instalment_override_list(plan, active_policy)
        ),
    )


def _resolve_pauses(plan: TimelinePlan) -> PauseSettings:
    """Gather every window in which a cash flow stops.

    Brief:
        Contribution breaks and withdrawal stops are the same idea
        to the engine - a dated range with a scope - so they are
        collected together.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        PauseSettings: Every pause window the plan describes.

    Warning:
        The explicit month lists stay empty; the timeline expresses
        every break as a range.
    """
    return PauseSettings(
        pause_ranges_list=(
            _collect_pause_range_list(plan)
            + _collect_withdrawal_stop_list(plan)
        )
    )


def _apply_income_to_tax(
    plan: TimelinePlan,
    tax: TaxSettings,
) -> TaxSettings:
    """Attach the plan's salary history to the tax rules.

    Brief:
        Leaves the caller's tax settings untouched when the
        timeline carries no salary events, so a plan that never
        mentions income behaves exactly as it did before.

    Arguments:
        plan (TimelinePlan): Plan being compiled.
        tax (TaxSettings): Tax rules to extend.

    Returns:
        TaxSettings: Rules carrying the dated income.

    Warning:
        Returns a copy; the caller's settings are unchanged.
    """
    income_by_year_tuple = _collect_income_by_year_tuple(
        plan, tax.tax_year_start_month_int
    )
    if not income_by_year_tuple:
        return tax
    return replace(
        tax,
        surcharge_mode_str=SURCHARGE_MODE_SLAB_STR,
        income_by_year_tuple=income_by_year_tuple,
    )


def resolve_monthly_amount_float(plan: TimelinePlan) -> float:
    """Find the instalment the plan starts at.

    Brief:
        The first start or change event sets it. A plan with no
        such event invests nothing, which the interface reports
        rather than silently assuming a number.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        float: Opening monthly instalment.

    Warning:
        Later change events are applied by the caller, because the
        engine models one instalment per fund.
    """
    for event in plan.ordered_event_list:
        if event.event_type_str in (
            EVENT_START_SIP_STR,
            EVENT_CHANGE_SIP_STR,
        ):
            return float(event.amount_float)
    return 0.0


def resolve_one_off_total_float(plan: TimelinePlan) -> float:
    """Total the one-off investments in the plan.

    Brief:
        Reported by the interface so the reader can see how much
        of the principal arrived as lump sums rather than as
        instalments. The engine is told the dates, not this total.

    Arguments:
        plan (TimelinePlan): Plan being compiled.

    Returns:
        float: Sum of every one-off investment.

    Warning:
        A display figure only; each lump sum compounds from its
        own month, not from the start of the plan.
    """
    return sum(
        float(event.amount_float)
        for event in plan.event_list
        if event.event_type_str == EVENT_LUMPSUM_STR
    )


def apply_plan_to_fund(
    fund_configuration: FundConfiguration,
    plan: TimelinePlan,
) -> FundConfiguration:
    """Fit a fund to the amounts the timeline describes.

    Brief:
        Keeps the fund's return, expense and tax settings and
        clears the amounts, because every rupee the timeline
        invests now arrives as a dated override or a dated one-off
        rather than as a standing instalment on the fund.

    Arguments:
        fund_configuration (FundConfiguration): Fund to adapt.
        plan (TimelinePlan): Plan being compiled.

    Returns:
        FundConfiguration: Fund carrying the timeline's amounts.

    Warning:
        Returns a copy; the caller's fund is untouched.
    """
    return replace(
        fund_configuration,
        monthly_sip_float=0.0,
        initial_investment_float=0.0,
        start_date=plan.start_date,
    )
