"""Three experience levels over one scenario.

Quick, Guided and Expert are not three programs and not three input
paths. They are three *declarations* over the same `PlanScenario`:
each names the settings it puts on screen, and everything it does
not name keeps whatever the scenario already holds.

That distinction is the whole design. It is what makes switching
modes free, and it is what stops Quick from quietly running a plan
that had eight events and a drift-band rebalance configured in
Expert.

The rule this module exists to enforce:

    **Lossy in display. Never lossy in data.**

A mode may decline to *show* a setting. No mode may *discard* one.
`describe_hidden_setting_list` is how a screen keeps that promise
out loud rather than silently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from investment_journey_simulator.plan_policy import PlanPolicy
from investment_journey_simulator.plan_scenario import (
    UNSET_INFLATION_FLOAT,
    PlanScenario,
    PresentationPreferences,
)
from investment_journey_simulator.timeline import (
    EVENT_ANNOTATION_TUPLE,
    EVENT_INCOME_STR,
    EVENT_INFLATION_STR,
    EVENT_LUMPSUM_STR,
    EVENT_PAUSE_STR,
    EVENT_REBALANCE_STR,
    EVENT_RESUME_STR,
    EVENT_RETIRE_STR,
    EVENT_SETS_INSTALMENT_TUPLE,
    EVENT_STEPUP_STR,
    EVENT_STOP_WITHDRAW_STR,
    EVENT_WITHDRAW_STR,
)

MODE_QUICK_STR: str = "QUICK"
MODE_GUIDED_STR: str = "GUIDED"
MODE_EXPERT_STR: str = "EXPERT"
MODE_ORDER_TUPLE: tuple = (
    MODE_QUICK_STR,
    MODE_GUIDED_STR,
    MODE_EXPERT_STR,
)

SETTING_HORIZON_STR: str = "horizon"
SETTING_CONTRIBUTION_STR: str = "contribution"
SETTING_RETURN_STR: str = "return"
SETTING_CURRENCY_STR: str = "currency"
SETTING_STEPUP_STR: str = "stepup"
SETTING_PAUSE_STR: str = "pause"
SETTING_WITHDRAWAL_STR: str = "withdrawal"
SETTING_LUMPSUM_STR: str = "lumpsum"
SETTING_INFLATION_STR: str = "inflation"
SETTING_NOTES_STR: str = "notes"
SETTING_MULTI_FUND_STR: str = "multi_fund"
SETTING_EXPENSE_STR: str = "expense"
SETTING_REBALANCE_STR: str = "rebalance"
SETTING_TAX_STR: str = "tax"
SETTING_INCOME_STR: str = "income"
SETTING_EXIT_LOAD_STR: str = "exit_load"
SETTING_TIMING_STR: str = "timing"
SETTING_WITHDRAWAL_SHAPE_STR: str = "withdrawal_shape"
SETTING_STEPUP_SHAPE_STR: str = "stepup_shape"
SETTING_FUND_TARGET_STR: str = "fund_target"
SETTING_REGIME_STR: str = "regime"


@dataclass(frozen=True)
class ScenarioSetting:
    """One thing a reader can configure, and how to describe it.

    A setting is not a field. It is a *question a reader would
    recognise* - "do you pause at any point" rather than
    "pauses.pause_ranges_list" - which is why the label reads as
    plain language and the description reports the current answer.
    """

    key_str: str
    label_str: str
    group_str: str
    is_active_callable: Callable[[PlanScenario], bool]
    describe_callable: Callable[[PlanScenario], str]

    def is_active_bool(self, scenario: PlanScenario) -> bool:
        """Whether this setting is doing anything on this plan.

        Brief:
            Only active settings are worth warning about when a
            mode hides them. A step-up nobody switched on is not
            hidden configuration; it is simply absent.

        Arguments:
            scenario (PlanScenario): Scenario being inspected.

        Returns:
            bool: True when the setting would change the answer.

        Warning:
            Active means "differs from the default", not "is
            correct".
        """
        return bool(self.is_active_callable(scenario))

    def describe_str(self, scenario: PlanScenario) -> str:
        """Report what this setting is currently set to."""
        return self.describe_callable(scenario)


def count_events_int(
    scenario: PlanScenario,
    *event_type_str: str,
) -> int:
    """Count the plan's events of the given types."""
    wanted_set = set(event_type_str)
    return sum(
        1
        for event in scenario.plan.event_list
        if event.event_type_str in wanted_set
    )


def _describe_count_str(count_int: int, noun_str: str) -> str:
    """Phrase a count with its noun, pluralised."""
    suffix_str = "" if count_int == 1 else "s"
    return f"{count_int} {noun_str}{suffix_str}"


def _default_policy_differs_bool(
    scenario: PlanScenario,
    *field_name_str: str,
) -> bool:
    """Whether any named policy field departs from its default."""
    default_policy = PlanPolicy()
    return any(
        getattr(scenario.policy, name_str)
        != getattr(default_policy, name_str)
        for name_str in field_name_str
    )


def _build_plan_shape_setting_list() -> list[ScenarioSetting]:
    """The settings every reader meets, in every mode."""
    return [
        ScenarioSetting(
            SETTING_HORIZON_STR,
            "How long the plan runs",
            "The plan",
            lambda scenario: True,
            lambda scenario: (
                f"{scenario.plan.horizon_years_int} years from "
                f"{scenario.plan.start_date:%B %Y}"
            ),
        ),
        ScenarioSetting(
            SETTING_CONTRIBUTION_STR,
            "What you invest each month",
            "Money in",
            lambda scenario: bool(
                count_events_int(
                    scenario, *EVENT_SETS_INSTALMENT_TUPLE
                )
            ),
            lambda scenario: _describe_count_str(
                count_events_int(
                    scenario, *EVENT_SETS_INSTALMENT_TUPLE
                ),
                "instalment change",
            ),
        ),
        ScenarioSetting(
            SETTING_RETURN_STR,
            "The return you expect",
            "The funds",
            lambda scenario: True,
            lambda scenario: _describe_returns_str(scenario),
        ),
        ScenarioSetting(
            SETTING_CURRENCY_STR,
            "Currency",
            "Display",
            lambda scenario: (
                scenario.presentation.currency_code_str
                != PresentationPreferences().currency_code_str
            ),
            lambda scenario: scenario.presentation.currency.name_str,
        ),
    ]


def _describe_returns_str(scenario: PlanScenario) -> str:
    """Report the gross return of each fund in the plan."""
    if not scenario.fund_list:
        return "no funds configured"
    return ", ".join(
        f"{fund.name_str} at "
        f"{fund.gross_return_percent_float:g}%"
        for fund in scenario.fund_list
    )


def _build_life_event_setting_list() -> list[ScenarioSetting]:
    """The settings a guided reader is asked about in words."""
    return (
        _build_money_in_setting_list()
        + _build_money_out_setting_list()
        + _build_world_setting_list()
    )


def _build_money_in_setting_list() -> list[ScenarioSetting]:
    """Ways more money arrives after the plan has started."""
    return [
        ScenarioSetting(
            SETTING_STEPUP_STR,
            "Raising the amount as your salary grows",
            "Money in",
            lambda scenario: bool(
                count_events_int(scenario, EVENT_STEPUP_STR)
            ),
            lambda scenario: _describe_count_str(
                count_events_int(scenario, EVENT_STEPUP_STR),
                "step-up",
            ),
        ),
        ScenarioSetting(
            SETTING_LUMPSUM_STR,
            "One-off investments",
            "Money in",
            lambda scenario: bool(
                count_events_int(scenario, EVENT_LUMPSUM_STR)
            ),
            lambda scenario: _describe_count_str(
                count_events_int(scenario, EVENT_LUMPSUM_STR),
                "lump sum",
            ),
        ),
    ]


def _build_money_out_setting_list() -> list[ScenarioSetting]:
    """Breaks in contribution, and money taken back out."""
    return [
        ScenarioSetting(
            SETTING_PAUSE_STR,
            "Years you pause contributions",
            "Breaks",
            lambda scenario: bool(
                count_events_int(
                    scenario, EVENT_PAUSE_STR, EVENT_RESUME_STR
                )
            ),
            lambda scenario: _describe_count_str(
                count_events_int(
                    scenario, EVENT_PAUSE_STR, EVENT_RESUME_STR
                ),
                "pause or resume",
            ),
        ),
        ScenarioSetting(
            SETTING_WITHDRAWAL_STR,
            "Money you take out",
            "Money out",
            lambda scenario: bool(
                count_events_int(
                    scenario,
                    EVENT_WITHDRAW_STR,
                    EVENT_RETIRE_STR,
                    EVENT_STOP_WITHDRAW_STR,
                )
            ),
            lambda scenario: _describe_count_str(
                count_events_int(
                    scenario,
                    EVENT_WITHDRAW_STR,
                    EVENT_RETIRE_STR,
                    EVENT_STOP_WITHDRAW_STR,
                ),
                "withdrawal event",
            ),
        ),
    ]


def _build_world_setting_list() -> list[ScenarioSetting]:
    """Things outside the plan that change what it is worth."""
    return [
        ScenarioSetting(
            SETTING_INFLATION_STR,
            "What prices do to your money",
            "The world",
            lambda scenario: (
                scenario.inflation_percent_float
                != UNSET_INFLATION_FLOAT
                or bool(
                    count_events_int(scenario, EVENT_INFLATION_STR)
                )
            ),
            lambda scenario: (
                f"{scenario.resolved_inflation_percent_float:g}% a "
                "year"
            ),
        ),
        ScenarioSetting(
            SETTING_NOTES_STR,
            "Markers for what mattered",
            "The world",
            lambda scenario: bool(
                count_events_int(scenario, *EVENT_ANNOTATION_TUPLE)
            ),
            lambda scenario: _describe_count_str(
                count_events_int(scenario, *EVENT_ANNOTATION_TUPLE),
                "note",
            ),
        ),
    ]


def _build_expert_setting_list() -> list[ScenarioSetting]:
    """The controls only the expert screen puts on show."""
    return (
        _build_fund_setting_list()
        + _build_portfolio_setting_list()
        + _build_tax_setting_list()
        + _build_convention_setting_list()
    )


def _build_fund_setting_list() -> list[ScenarioSetting]:
    """What the funds themselves cost and how many there are."""
    return [
        ScenarioSetting(
            SETTING_MULTI_FUND_STR,
            "More than one fund",
            "The funds",
            lambda scenario: len(scenario.fund_list) > 1,
            lambda scenario: _describe_count_str(
                len(scenario.fund_list), "fund"
            ),
        ),
        ScenarioSetting(
            SETTING_EXPENSE_STR,
            "Expense ratio",
            "The funds",
            lambda scenario: any(
                fund.expense_percent_float
                for fund in scenario.fund_list
            ),
            lambda scenario: ", ".join(
                f"{fund.name_str} at "
                f"{fund.expense_percent_float:g}%"
                for fund in scenario.fund_list
            ),
        ),
        ScenarioSetting(
            SETTING_EXIT_LOAD_STR,
            "Exit load and transaction tax",
            "The funds",
            lambda scenario: any(
                fund.exit_load_percent_float
                or fund.transaction_tax_percent_float
                for fund in scenario.fund_list
            ),
            lambda scenario: "charged on early exits",
        ),
    ]


def _build_portfolio_setting_list() -> list[ScenarioSetting]:
    """How the portfolio is kept in shape over time."""
    return [
        ScenarioSetting(
            SETTING_REBALANCE_STR,
            "Rebalancing back to target",
            "Portfolio",
            lambda scenario: bool(
                count_events_int(scenario, EVENT_REBALANCE_STR)
            )
            or _default_policy_differs_bool(
                scenario,
                "rebalance_trigger_str",
                "rebalance_interval_months_int",
                "rebalance_drift_band_percent_float",
                "use_contribution_steering_bool",
            ),
            lambda scenario: _describe_rebalance_str(scenario),
        ),
    ]


def _build_tax_setting_list() -> list[ScenarioSetting]:
    """What the taxman takes, and under whose rules."""
    return [
        ScenarioSetting(
            SETTING_TAX_STR,
            "Capital gains tax rules",
            "Tax",
            lambda scenario: _is_tax_configured_bool(scenario),
            lambda scenario: _describe_tax_str(scenario),
        ),
        ScenarioSetting(
            SETTING_INCOME_STR,
            "Your income, for the surcharge",
            "Tax",
            lambda scenario: bool(
                scenario.tax.total_income_float
                or scenario.tax.income_by_year_tuple
                or count_events_int(scenario, EVENT_INCOME_STR)
            ),
            lambda scenario: "set, and driving the surcharge",
        ),
        ScenarioSetting(
            SETTING_REGIME_STR,
            "Which country's tax rules",
            "Tax",
            lambda scenario: (
                scenario.presentation.regime_code_str
                != PresentationPreferences().regime_code_str
            ),
            lambda scenario: (
                scenario.presentation.regime.label_str
            ),
        ),
    ]


def _build_convention_setting_list() -> list[ScenarioSetting]:
    """The rule shapes, which change answers without being seen."""
    return (
        _build_timing_setting_list()
        + _build_shape_setting_list()
    )


def _build_timing_setting_list() -> list[ScenarioSetting]:
    """When in the month money moves."""
    return [
        ScenarioSetting(
            SETTING_TIMING_STR,
            "When in the month the instalment lands",
            "Conventions",
            lambda scenario: _default_policy_differs_bool(
                scenario, "sip_at_month_start_bool"
            ),
            lambda scenario: (
                "start of month"
                if scenario.policy.sip_at_month_start_bool
                else "end of month"
            ),
        ),
    ]


def _build_shape_setting_list() -> list[ScenarioSetting]:
    """How the step-up and withdrawal rules are shaped."""
    return [
        ScenarioSetting(
            SETTING_STEPUP_SHAPE_STR,
            "How the step-up is shaped",
            "Conventions",
            lambda scenario: _default_policy_differs_bool(
                scenario,
                "stepup_interval_months_int",
                "stepup_fixed_increment_float",
            ),
            lambda scenario: (
                "every "
                f"{scenario.policy.stepup_interval_months_int} "
                "months"
            ),
        ),
        ScenarioSetting(
            SETTING_WITHDRAWAL_SHAPE_STR,
            "How the withdrawal is shaped",
            "Conventions",
            lambda scenario: _default_policy_differs_bool(
                scenario,
                "withdrawal_mode_str",
                "withdrawal_portfolio_percent_float",
                "withdrawal_annual_change_percent_float",
                "withdrawal_schedule_tuple",
                "withdrawal_change_percent_tuple",
            ),
            lambda scenario: scenario.policy.withdrawal_mode_str,
        ),
        ScenarioSetting(
            SETTING_FUND_TARGET_STR,
            "Which fund a change applies to",
            "Conventions",
            lambda scenario: _default_policy_differs_bool(
                scenario, "default_fund_name_str"
            )
            or any(
                event.fund_name_str
                for event in scenario.plan.event_list
            ),
            lambda scenario: "some changes target one fund",
        ),
    ]


def _describe_rebalance_str(scenario: PlanScenario) -> str:
    """Report how this plan rebalances, if it does."""
    dated_int = count_events_int(scenario, EVENT_REBALANCE_STR)
    if dated_int:
        return _describe_count_str(dated_int, "dated rebalance")
    if scenario.policy.use_contribution_steering_bool:
        return "new money steered towards target"
    return f"on a {scenario.policy.rebalance_trigger_str} rule"


def _is_tax_configured_bool(scenario: PlanScenario) -> bool:
    """Whether any tax field departs from the plain default."""
    from investment_journey_simulator.models import TaxSettings

    return scenario.tax != TaxSettings()


def _describe_tax_str(scenario: PlanScenario) -> str:
    """Report the headline tax choices in one phrase."""
    part_list = []
    if scenario.tax.surcharge_percent_float:
        part_list.append(
            f"{scenario.tax.surcharge_percent_float:g}% surcharge"
        )
    if scenario.tax.cess_percent_float:
        part_list.append(
            f"{scenario.tax.cess_percent_float:g}% cess"
        )
    if scenario.tax.portfolio_exemption_amount_float:
        part_list.append("a portfolio exemption")
    return ", ".join(part_list) or "configured"


SCENARIO_SETTING_TUPLE: tuple = tuple(
    _build_plan_shape_setting_list()
    + _build_life_event_setting_list()
    + _build_expert_setting_list()
)
SETTING_BY_KEY_DICT: dict[str, ScenarioSetting] = {
    setting.key_str: setting
    for setting in SCENARIO_SETTING_TUPLE
}


QUICK_SETTING_KEY_TUPLE: tuple = (
    SETTING_HORIZON_STR,
    SETTING_CONTRIBUTION_STR,
    SETTING_RETURN_STR,
    SETTING_CURRENCY_STR,
)
GUIDED_SETTING_KEY_TUPLE: tuple = QUICK_SETTING_KEY_TUPLE + (
    SETTING_STEPUP_STR,
    SETTING_LUMPSUM_STR,
    SETTING_PAUSE_STR,
    SETTING_WITHDRAWAL_STR,
    SETTING_INFLATION_STR,
    SETTING_NOTES_STR,
)
EXPERT_SETTING_KEY_TUPLE: tuple = tuple(
    setting.key_str for setting in SCENARIO_SETTING_TUPLE
)


@dataclass(frozen=True)
class ModeProjection:
    """One experience level, as the settings it puts on screen."""

    mode_str: str
    label_str: str
    promise_str: str
    setting_key_tuple: tuple

    def shows_bool(self, key_str: str) -> bool:
        """Whether this mode puts the given setting on screen."""
        return key_str in self.setting_key_tuple

    @property
    def setting_list(self) -> list[ScenarioSetting]:
        """The settings this mode shows, in registry order."""
        return [
            setting
            for setting in SCENARIO_SETTING_TUPLE
            if self.shows_bool(setting.key_str)
        ]


QUICK_PROJECTION: ModeProjection = ModeProjection(
    MODE_QUICK_STR,
    "Quick",
    "An answer in under a minute.",
    QUICK_SETTING_KEY_TUPLE,
)
GUIDED_PROJECTION: ModeProjection = ModeProjection(
    MODE_GUIDED_STR,
    "Guided",
    "Plain questions about how your life will actually go.",
    GUIDED_SETTING_KEY_TUPLE,
)
EXPERT_PROJECTION: ModeProjection = ModeProjection(
    MODE_EXPERT_STR,
    "Expert",
    "Every control, including the ones that need explaining.",
    EXPERT_SETTING_KEY_TUPLE,
)
PROJECTION_BY_MODE_DICT: dict[str, ModeProjection] = {
    QUICK_PROJECTION.mode_str: QUICK_PROJECTION,
    GUIDED_PROJECTION.mode_str: GUIDED_PROJECTION,
    EXPERT_PROJECTION.mode_str: EXPERT_PROJECTION,
}


def resolve_projection(mode_str: str) -> ModeProjection:
    """Find the projection for a mode name.

    Brief:
        An unknown mode falls back to Guided rather than raising,
        because a stale bookmark should not cost a reader their
        plan.

    Arguments:
        mode_str (str): Mode name to resolve.

    Returns:
        ModeProjection: The projection, never None.

    Warning:
        The fallback is deliberately the middle mode, not Expert,
        so a mistake never dumps a beginner into every control.
    """
    return PROJECTION_BY_MODE_DICT.get(
        mode_str, GUIDED_PROJECTION
    )


@dataclass(frozen=True)
class HiddenSetting:
    """One active setting the current mode does not show."""

    key_str: str
    label_str: str
    group_str: str
    value_str: str

    @property
    def sentence_str(self) -> str:
        """The setting phrased for a list the reader reads."""
        return f"{self.label_str}: {self.value_str}"


def describe_hidden_setting_list(
    scenario: PlanScenario,
    mode_str: str,
) -> list[HiddenSetting]:
    """List the active settings this mode is not showing.

    Brief:
        The mechanism behind "lossy in display, never lossy in
        data". A mode that hides working configuration has to say
        so, and this is what it says.

    Arguments:
        scenario (PlanScenario): Scenario being displayed.
        mode_str (str): Mode the reader is currently in.

    Returns:
        List[HiddenSetting]: Hidden settings, in registry order.

    Warning:
        Only *active* settings appear. A step-up nobody switched on
        is absent, not hidden, and warning about it would train the
        reader to ignore the warning.
    """
    projection = resolve_projection(mode_str)
    return [
        HiddenSetting(
            setting.key_str,
            setting.label_str,
            setting.group_str,
            setting.describe_str(scenario),
        )
        for setting in SCENARIO_SETTING_TUPLE
        if not projection.shows_bool(setting.key_str)
        and setting.is_active_bool(scenario)
    ]


def build_hidden_summary_str(
    scenario: PlanScenario,
    mode_str: str,
) -> str:
    """Phrase the hidden-settings warning, or say nothing.

    Brief:
        Returns an empty string when nothing is hidden, so a screen
        can render the warning unconditionally and have it vanish
        when it does not apply.

    Arguments:
        scenario (PlanScenario): Scenario being displayed.
        mode_str (str): Mode the reader is currently in.

    Returns:
        str: One sentence, or empty when nothing is hidden.

    Warning:
        Says "not shown on this screen", never "ignored" - the
        settings are still running, which is the entire point.
    """
    hidden_list = describe_hidden_setting_list(scenario, mode_str)
    if not hidden_list:
        return ""
    count_int = len(hidden_list)
    noun_str = "setting" if count_int == 1 else "settings"
    return (
        f"{count_int} advanced {noun_str} active, not shown on "
        "this screen"
    )


MODE_CHANGE_LIMIT_INT: int = 4


def describe_mode_change_str(
    previous_mode_str: str,
    next_mode_str: str,
) -> str:
    """Say what moving between two detail levels did.

    Switching used to reveal a longer list of controls and announce
    nothing, so a reader could not tell the click had worked. This
    names what appeared or went away. It describes what the mode
    *shows*, never what it does to the plan, because a mode change
    never touches the plan - and the wording has to keep that clear
    or a reader will think their settings were discarded.

    Arguments:
        previous_mode_str (str): Level being left.
        next_mode_str (str): Level being entered.

    Returns:
        str: One sentence, or empty when nothing changed.
    """
    previous = resolve_projection(previous_mode_str)
    following = resolve_projection(next_mode_str)
    if previous.mode_str == following.mode_str:
        return ""
    gained_list = [
        setting.label_str
        for setting in following.setting_list
        if not previous.shows_bool(setting.key_str)
    ]
    lost_list = [
        setting.label_str
        for setting in previous.setting_list
        if not following.shows_bool(setting.key_str)
    ]
    if gained_list:
        return (
            f"**{following.label_str}** adds "
            f"{_join_label_str(gained_list)}."
        )
    if lost_list:
        return (
            f"**{following.label_str}** hides "
            f"{_join_label_str(lost_list)}. Nothing was changed or "
            "lost; they are still running."
        )
    return f"Now showing **{following.label_str}**."


def _join_label_str(label_list: list[str]) -> str:
    """List a few setting names, then say how many more there are."""
    lowered_list = [
        label_str[0].lower() + label_str[1:]
        for label_str in label_list
    ]
    if len(lowered_list) <= MODE_CHANGE_LIMIT_INT:
        return ", ".join(lowered_list)
    shown_str = ", ".join(lowered_list[:MODE_CHANGE_LIMIT_INT])
    remaining_int = len(lowered_list) - MODE_CHANGE_LIMIT_INT
    return f"{shown_str} and {remaining_int} more"
