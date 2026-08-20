"""The one object every screen of the portal reads and writes.

Three front ends grew up separately - the classic dashboard, the
event rail and the studio - and each built its own engine settings
from its own widgets. That is why moving between them meant typing
everything again, and why two screens could quietly disagree about
what a plan was worth.

A `PlanScenario` is the whole plan in one place: the dated events,
the standing rules beside them, the funds, the tax rules, and how it
should all be displayed. Every screen edits this object. Every run
goes through `compile_scenario`. Nothing else builds a
`SimulationSettings`.

See `docs/design/plan_scenario.md` for the reasoning, and
`docs/design/scenario_gap_table.md` for the audit that shaped it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from investment_journey_simulator.currency import (
    DEFAULT_CURRENCY_CODE_STR,
    Currency,
    resolve_currency,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationSettings,
    TaxSettings,
)
from investment_journey_simulator.plan_policy import PlanPolicy
from investment_journey_simulator.regimes import (
    DEFAULT_REGIME_CODE_STR,
    TaxRegime,
    resolve_regime,
)
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_STR,
    EVENT_SETS_INSTALMENT_TUPLE,
    TimelinePlan,
    apply_plan_to_fund,
    collect_inflation_schedule_tuple,
    compile_settings,
)

UNSET_INFLATION_FLOAT: float = -1.0
DEFAULT_SCENARIO_NAME_STR: str = "My plan"

# Which side of the scenario supplies the contributions. The rail
# expresses every rupee as a dated event; the classic dashboard
# gives each fund a standing instalment. Both are valid, and mixing
# them would count the same money twice.
#
# AUTO infers it from the events, which is what a reader building a
# plan on screen wants. A migrated file states it outright instead,
# because a v2.1 scenario carries dated lump sums *and* standing
# instalments, and inferring from the lump sums alone would silently
# delete its SIP.
AMOUNTS_SOURCE_AUTO_STR: str = "AUTO"
AMOUNTS_SOURCE_FUNDS_STR: str = "FUNDS"
AMOUNTS_SOURCE_TIMELINE_STR: str = "TIMELINE"


@dataclass(frozen=True)
class PresentationPreferences:
    """How a scenario should be displayed, not what it is worth.

    Nothing here changes a single figure the engine produces. It is
    kept on the scenario anyway so that moving between screens does
    not reset the reader's currency to rupees or their charts to
    light mode.
    """

    currency_code_str: str = DEFAULT_CURRENCY_CODE_STR
    regime_code_str: str = DEFAULT_REGIME_CODE_STR
    is_dark_mode_bool: bool = False

    @property
    def currency(self) -> Currency:
        """The currency object this preference names.

        Brief:
            Resolved rather than stored so a scenario saved with a
            currency this build no longer knows falls back safely.

        Arguments:
            None.

        Returns:
            Currency: Resolved currency, never None.

        Warning:
            An unknown code silently yields the default currency.
        """
        return resolve_currency(self.currency_code_str)

    @property
    def regime(self) -> TaxRegime:
        """The tax regime this preference names.

        Brief:
            Only the opening values; see `regimes.py` for why one
            regime is modelled in full and the rest are not.

        Arguments:
            None.

        Returns:
            TaxRegime: Resolved regime, never None.

        Warning:
            An unknown code silently yields the default regime.
        """
        return resolve_regime(self.regime_code_str)


@dataclass(frozen=True)
class CompiledPlan:
    """Everything the engine and the reports need, in one bundle.

    The inflation schedule travels with the settings deliberately.
    It used to be a second call the caller had to remember, and two
    screens forgetting it in different ways would have reported
    different real-terms figures with nothing on screen to explain
    the difference.
    """

    settings: SimulationSettings
    fund_list: list[FundConfiguration]
    inflation_percent_float: float
    inflation_schedule_tuple: tuple
    currency: Currency
    regime: TaxRegime


@dataclass(frozen=True)
class PlanScenario:
    """A whole plan, as every screen of the portal sees it."""

    plan: TimelinePlan
    fund_list: list[FundConfiguration] = field(default_factory=list)
    policy: PlanPolicy = field(default_factory=PlanPolicy)
    tax: TaxSettings = field(default_factory=TaxSettings)
    presentation: PresentationPreferences = field(
        default_factory=PresentationPreferences
    )
    inflation_percent_float: float = UNSET_INFLATION_FLOAT
    name_str: str = DEFAULT_SCENARIO_NAME_STR
    amounts_source_str: str = AMOUNTS_SOURCE_AUTO_STR

    @property
    def timeline_owns_amounts_bool(self) -> bool:
        """Whether the events, not the funds, supply the money.

        Brief:
            The rail expresses every rupee as a dated event, so its
            funds must contribute nothing on their own. The classic
            dashboard is the other way round: its funds carry a
            standing instalment. Both are valid, and this is what
            tells them apart.

        Arguments:
            None.

        Returns:
            bool: True when events supply the contributions.

        Warning:
            Inferred only when the source is AUTO. A migrated file
            states its source outright, because a v2.1 scenario
            holds dated lump sums beside a standing instalment and
            inference would read that as the rail's shape.
        """
        if self.amounts_source_str == AMOUNTS_SOURCE_TIMELINE_STR:
            return True
        if self.amounts_source_str == AMOUNTS_SOURCE_FUNDS_STR:
            return False
        return any(
            event.event_type_str in EVENT_SETS_INSTALMENT_TUPLE
            or event.event_type_str == EVENT_LUMPSUM_STR
            for event in self.plan.event_list
        )

    @property
    def resolved_inflation_percent_float(self) -> float:
        """The inflation rate to report real values against.

        Brief:
            Falls back to the currency's own default, because a
            sensible assumption in Mumbai is not a sensible one in
            Tokyo, and neither is a hardcoded number.

        Arguments:
            None.

        Returns:
            float: Annual inflation rate in percent.

        Warning:
            A rate the reader has explicitly set to zero is
            honoured; only an unset rate falls back.
        """
        if self.inflation_percent_float >= 0.0:
            return self.inflation_percent_float
        return (
            self.presentation.currency
        ).default_inflation_percent_float


def build_scenario_fund_list(
    scenario: PlanScenario,
) -> list[FundConfiguration]:
    """Fit the funds to whichever source owns the amounts.

    Brief:
        When the timeline supplies the money, each fund is stripped
        of its standing instalment so the same rupee is not counted
        twice. When it does not, the funds are left exactly as the
        reader configured them.

    Arguments:
        scenario (PlanScenario): Scenario being compiled.

    Returns:
        List[FundConfiguration]: Funds ready for the engine.

    Warning:
        Returns copies whenever the timeline owns the amounts; the
        scenario's own fund list is never mutated.
    """
    if not scenario.timeline_owns_amounts_bool:
        return list(scenario.fund_list)
    return [
        apply_plan_to_fund(fund_configuration, scenario.plan)
        for fund_configuration in scenario.fund_list
    ]


def compile_scenario(scenario: PlanScenario) -> CompiledPlan:
    """Turn a scenario into everything a run needs.

    Brief:
        The single compile path. No screen may build a
        `SimulationSettings` of its own; `test_plan_scenario.py`
        enforces that rather than leaving it to convention.

    Arguments:
        scenario (PlanScenario): Scenario being compiled.

    Returns:
        CompiledPlan: Settings, funds, inflation and presentation.

    Warning:
        Deterministic and free of side effects, so two screens
        compiling the same scenario can never disagree.
    """
    return CompiledPlan(
        settings=compile_settings(
            scenario.plan, scenario.tax, scenario.policy
        ),
        fund_list=build_scenario_fund_list(scenario),
        inflation_percent_float=(
            scenario.resolved_inflation_percent_float
        ),
        inflation_schedule_tuple=collect_inflation_schedule_tuple(
            scenario.plan
        ),
        currency=scenario.presentation.currency,
        regime=scenario.presentation.regime,
    )


def apply_regime_to_tax(
    scenario: PlanScenario,
    regime_code_str: str,
) -> PlanScenario:
    """Adopt a regime's opening values as the scenario's tax rules.

    Brief:
        Choosing a country fills in its headline rates. It does not
        teach the program that country's tax code, and the
        interface says so rather than letting a reader assume
        otherwise.

    Arguments:
        scenario (PlanScenario): Scenario being changed.
        regime_code_str (str): Regime code to adopt.

    Returns:
        PlanScenario: Copy carrying the regime's opening values.

    Warning:
        Overwrites per-fund rates the reader may have edited, which
        is why this is an explicit action and not a side effect of
        changing the display currency.
    """
    regime = resolve_regime(regime_code_str)
    return replace(
        scenario,
        presentation=replace(
            scenario.presentation, regime_code_str=regime.code_str
        ),
        fund_list=[
            replace(
                fund_configuration,
                short_term_tax_percent_float=(
                    regime.short_term_percent_float
                ),
                long_term_tax_percent_float=(
                    regime.long_term_percent_float
                ),
                long_term_threshold_months_int=(
                    regime.long_term_threshold_months_int
                ),
                exemption_amount_float=regime.annual_exemption_float,
            )
            for fund_configuration in scenario.fund_list
        ],
        tax=replace(
            scenario.tax, cess_percent_float=regime.cess_percent_float
        ),
    )
