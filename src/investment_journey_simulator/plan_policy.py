"""Rule shapes that sit beside the events, not on them.

A timeline records what happened on a day. "I rebalanced in March
2031" belongs there. "I rebalance whenever equity drifts five points
from its target" does not - it has no date and never will, and
pushing it onto the rail would corrupt the one thing a rail is good
at.

So the standing rules live here instead. Every field below was found
by auditing what `compile_settings` could not reach while another
front end offered it; see `docs/design/scenario_gap_table.md` for the
trace and `docs/design/plan_scenario.md` for the shape this fits
into.

The defaults reproduce exactly what the timeline compiled before
this module existed, so a plan that never mentions a policy behaves
as it always did.
"""

from __future__ import annotations

from dataclasses import dataclass

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    REBALANCE_METHOD_PARTIAL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    REBALANCE_TRIGGER_DATED_STR,
    TAX_FUNDING_PORTFOLIO_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)


@dataclass(frozen=True)
class PlanPolicy:
    """Standing rules a timeline cannot express as dated events.

    Grouped by the settings object each field ends up in, because
    that is how `compile_settings` consumes them.

    ``sip_at_month_start_bool`` decides whether an instalment
    compounds for the month it is paid in. It is the one field here
    that changes a headline figure without changing a single input
    the reader typed, which is why it is first.
    """

    sip_at_month_start_bool: bool = True

    stepup_interval_months_int: int = MONTHS_IN_YEAR_INT
    stepup_fixed_increment_float: float = 0.0

    withdrawal_mode_str: str = WITHDRAWAL_MODE_FIXED_STR
    withdrawal_portfolio_percent_float: float = 0.0
    withdrawal_annual_change_percent_float: float = 0.0
    withdrawal_schedule_tuple: tuple = ()
    withdrawal_change_percent_tuple: tuple = ()

    rebalance_trigger_str: str = REBALANCE_TRIGGER_DATED_STR
    rebalance_interval_months_int: int = 0
    rebalance_drift_band_percent_float: float = 0.0
    rebalance_method_str: str = REBALANCE_METHOD_PARTIAL_STR
    rebalance_target_mode_str: str = REBALANCE_TARGET_COLUMN_STR
    rebalance_tax_funding_str: str = TAX_FUNDING_PORTFOLIO_STR
    rebalance_maximum_events_int: int = 0
    use_contribution_steering_bool: bool = False

    default_fund_name_str: str = ""

    @property
    def is_rule_driven_rebalance_bool(self) -> bool:
        """Whether rebalancing runs on a rule rather than by hand.

        Brief:
            A dated trigger means the reader placed each rebalance
            on the rail. Anything else is a standing rule that can
            fire without an event ever being placed.

        Arguments:
            None.

        Returns:
            bool: True when a rule drives the rebalancing.

        Warning:
            True does not imply rebalancing is on; the rule still
            needs an interval or a band to act on.
        """
        return (
            self.rebalance_trigger_str
            != REBALANCE_TRIGGER_DATED_STR
        )

    @property
    def has_rebalance_rule_input_bool(self) -> bool:
        """Whether a rule-driven rebalance has anything to act on.

        Brief:
            A calendar trigger needs an interval and a band trigger
            needs a band. Neither is assumed, because guessing one
            would start selling a portfolio nobody asked to sell.

        Arguments:
            None.

        Returns:
            bool: True when the rule can actually fire.

        Warning:
            Contribution steering is deliberately not counted here;
            it steers new money and never sells.
        """
        return bool(
            self.rebalance_interval_months_int > 0
            or self.rebalance_drift_band_percent_float > 0.0
        )


DEFAULT_PLAN_POLICY: PlanPolicy = PlanPolicy()
