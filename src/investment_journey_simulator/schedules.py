"""Contribution, withdrawal and pause schedules of the plan."""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    PAUSE_SCOPE_BOTH_STR,
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
    PERCENT_TOTAL_FLOAT,
    STEPUP_MODE_BOTH_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODE_PER_FUND_STR,
    WITHDRAWAL_MODE_FIXED_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    PauseSettings,
    StepUpSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.returns import (
    apply_annual_growth_factor_float,
)
from investment_journey_simulator.time_utils import (
    count_months_between_dates_int,
    is_month_within_range_bool,
)


class PauseCalendar:
    """Answers whether cash flows are paused in a given month."""

    def __init__(self, pause_settings: PauseSettings) -> None:
        """Index recurring months and one-off ranges for lookups.

        Brief:
            Recurring months repeat every year, while ranges cover
            an explicit window such as a sabbatical.

        Arguments:
            pause_settings (PauseSettings): Configured pauses.

        Returns:
            None: A queryable calendar is initialised.

        Warning:
            Ranges are inclusive of both boundary months.
        """
        self._sip_pause_months_set = {
            int(month_int)
            for month_int in (
                pause_settings.sip_pause_months_list
            )
        }
        self._withdrawal_pause_months_set = {
            int(month_int)
            for month_int in (
                pause_settings.withdrawal_pause_months_list
            )
        }
        self._pause_ranges_list = list(
            pause_settings.pause_ranges_list
        )

    def is_sip_paused_bool(self, month_date: date) -> bool:
        """Check whether contributions stop in a given month.

        Brief:
            Combines the recurring month list with any matching
            explicit pause range.

        Arguments:
            month_date (date): Month being simulated.

        Returns:
            bool: True when no contribution should be made.

        Warning:
            A pause suppresses the instalment entirely; it is never
            carried forward to a later month.
        """
        if month_date.month in self._sip_pause_months_set:
            return True
        return self._matches_any_range_bool(
            month_date, PAUSE_SCOPE_SIP_STR
        )

    def is_withdrawal_paused_bool(self, month_date: date) -> bool:
        """Check whether withdrawals stop in a given month.

        Brief:
            Mirrors the contribution rule for the withdrawal side.

        Arguments:
            month_date (date): Month being simulated.

        Returns:
            bool: True when no withdrawal should be made.

        Warning:
            Skipped withdrawals are not paid out later.
        """
        if month_date.month in self._withdrawal_pause_months_set:
            return True
        return self._matches_any_range_bool(
            month_date, PAUSE_SCOPE_WITHDRAWAL_STR
        )

    def _matches_any_range_bool(
        self,
        month_date: date,
        scope_str: str,
    ) -> bool:
        """Test the month against every configured pause range.

        Brief:
            A range applies when its scope matches the requested
            flow or when it was declared for both flows.

        Arguments:
            month_date (date): Month being simulated.
            scope_str (str): Flow scope being tested.

        Returns:
            bool: True when at least one range covers the month.

        Warning:
            Ranges with missing dates are skipped silently.
        """
        for pause_range in self._pause_ranges_list:
            if pause_range.start_date is None:
                continue
            if pause_range.end_date is None:
                continue
            range_scope_str = str(pause_range.scope_str).upper().strip()
            is_scope_match_bool = range_scope_str in (
                scope_str,
                PAUSE_SCOPE_BOTH_STR,
            )
            if not is_scope_match_bool:
                continue
            if is_month_within_range_bool(
                month_date,
                pause_range.start_date,
                pause_range.end_date,
            ):
                return True
        return False


class ContributionPlan:
    """Computes the stepped-up instalment due from each fund."""

    def __init__(
        self,
        stepup_settings: StepUpSettings,
        pause_calendar: PauseCalendar,
        portfolio_start_date: date,
        instalment_override_list: list | None = None,
        portfolio_share_dict: dict | None = None,
    ) -> None:
        """Bind escalation rules to the portfolio timeline.

        Escalation is measured from each fund's own start date, so
        staggered funds step up on their own anniversaries.

        Arguments:
            stepup_settings (StepUpSettings): Escalation rules.
            pause_calendar (PauseCalendar): Pause lookup.
            portfolio_start_date (date): First simulated month.
            instalment_override_list (Optional[list]): Dated changes
                to the instalment, in any order.
            portfolio_share_dict (Optional[dict]): Each fund's share
                of an override that names no fund. Absent, every
                fund takes the whole amount, which is right for a
                single-fund plan and wrong for any other - see
                `_resolve_base_tuple`.

        Returns:
            None: A configured contribution plan is initialised.

        Warning:
            Funds starting before the portfolio are clamped to the
            portfolio start month.
        """
        self._stepup_settings = stepup_settings
        self._pause_calendar = pause_calendar
        self._portfolio_start_date = portfolio_start_date
        self._portfolio_share_dict = dict(
            portfolio_share_dict or {}
        )
        self._override_list = sorted(
            instalment_override_list or [],
            key=lambda override: int(override.month_index_int),
        )

    def calculate_instalment_float(
        self,
        fund_configuration: FundConfiguration,
        month_index_int: int,
        month_date: date,
    ) -> float:
        """Compute the rupees a fund receives in one month.

        Brief:
            Returns zero before the fund starts or while paused,
            otherwise escalates the base instalment by whole years.

        Arguments:
            fund_configuration (FundConfiguration): Fund rules.
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            float: Instalment due from this fund, never negative.

        Warning:
            Both escalation modes multiply when the mode is BOTH.
        """
        if self._pause_calendar.is_sip_paused_bool(month_date):
            return 0.0
        base_float, origin_month_int = self._resolve_base_tuple(
            fund_configuration, month_index_int
        )
        if int(month_index_int) < origin_month_int:
            return 0.0
        return self._escalate_instalment_float(
            fund_configuration,
            base_float,
            self._count_elapsed_periods_int(
                int(month_index_int) - origin_month_int
            ),
        )

    def _resolve_base_tuple(
        self,
        fund_configuration: FundConfiguration,
        month_index_int: int,
    ) -> tuple[float, int]:
        """Find the instalment in force and when it took effect.

        Brief:
            The latest override at or before this month wins. With
            none, the fund's own instalment applies from the month
            the fund starts.

        Arguments:
            fund_configuration (FundConfiguration): Fund rules.
            month_index_int (int): Month index being simulated.

        Returns:
            Tuple[float, int]: Base instalment and the month the
                escalation clock restarts from.

        An override naming none is a *portfolio* instalment and is
        divided by target weight; see
        `_resolve_override_amount_float`.
        """
        offset_months_int = self._calculate_start_offset_int(
            fund_configuration
        )
        base_float = float(fund_configuration.monthly_sip_float)
        origin_month_int = offset_months_int
        for override in self._override_list:
            if int(override.month_index_int) > int(month_index_int):
                break
            if override.fund_name_str not in (
                "",
                fund_configuration.name_str,
            ):
                continue
            base_float = self._resolve_override_amount_float(
                override, fund_configuration
            )
            origin_month_int = max(
                offset_months_int, int(override.month_index_int)
            )
        return base_float, origin_month_int

    def _resolve_override_amount_float(
        self,
        override,
        fund_configuration: FundConfiguration,
    ) -> float:
        """The share of one override this fund actually receives.

        A fund-specific override is taken whole. A portfolio-level
        one is multiplied by this fund's share, which the engine
        derives from the target weights.
        """
        amount_float = float(override.amount_float)
        if override.fund_name_str:
            return amount_float
        return amount_float * float(
            self._portfolio_share_dict.get(
                fund_configuration.name_str, 1.0
            )
        )

    def _calculate_start_offset_int(
        self,
        fund_configuration: FundConfiguration,
    ) -> int:
        """Find the first month index in which a fund invests.

        Brief:
            Converts the fund start date into a month offset from
            the portfolio start date.

        Arguments:
            fund_configuration (FundConfiguration): Fund rules.

        Returns:
            int: Non-negative month offset of the first instalment.

        Warning:
            Earlier start dates are clamped to zero.
        """
        return max(
            0,
            count_months_between_dates_int(
                self._portfolio_start_date,
                fund_configuration.start_date,
            ),
        )

    def _escalate_instalment_float(
        self,
        fund_configuration: FundConfiguration,
        base_instalment_float: float,
        elapsed_years_int: int,
    ) -> float:
        """Apply the active escalation modes to the instalment.

        Brief:
            Global escalation lifts every fund, per-fund escalation
            lifts only that fund, and BOTH multiplies the two.

        Arguments:
            fund_configuration (FundConfiguration): Fund rules.
            base_instalment_float (float): Instalment before growth.
            elapsed_years_int (int): Completed investing years.

        Returns:
            float: Escalated instalment for this month.

        Warning:
            Escalation compounds yearly, not monthly.
        """
        mode_str = self._stepup_settings.mode_str
        instalment_float = float(base_instalment_float)
        if mode_str in (STEPUP_MODE_GLOBAL_STR, STEPUP_MODE_BOTH_STR):
            instalment_float = apply_annual_growth_factor_float(
                instalment_float,
                self._stepup_settings.global_stepup_percent_float,
                elapsed_years_int,
            )
        if mode_str in (
            STEPUP_MODE_PER_FUND_STR,
            STEPUP_MODE_BOTH_STR,
        ):
            instalment_float = apply_annual_growth_factor_float(
                instalment_float,
                fund_configuration.stepup_percent_float,
                elapsed_years_int,
            )
        instalment_float += (
            float(self._stepup_settings.fixed_increment_amount_float)
            * elapsed_years_int
        )
        return max(0.0, instalment_float)

    def _count_elapsed_periods_int(
        self,
        months_since_start_int: int,
    ) -> int:
        """Count completed step-up periods since a fund started.

        Brief:
            Supports escalation every N months and an optional
            delay before the very first increase.

        Arguments:
            months_since_start_int (int): Months invested so far.

        Returns:
            int: Number of step-ups already applied.

        Warning:
            A non-positive interval disables escalation entirely.
        """
        interval_months_int = int(
            self._stepup_settings.interval_months_int
        )
        if interval_months_int <= 0:
            return 0
        first_month_int = int(
            self._stepup_settings.first_stepup_month_index_int
        )
        if first_month_int <= 0:
            return months_since_start_int // interval_months_int
        if months_since_start_int < first_month_int:
            return 0
        return (
            months_since_start_int - first_month_int
        ) // interval_months_int + 1


class WithdrawalPlan:
    """Computes the systematic withdrawal due in each month."""

    def __init__(
        self,
        withdrawal_settings: WithdrawalSettings,
        pause_calendar: PauseCalendar,
    ) -> None:
        """Bind withdrawal rules to the pause calendar.

        Brief:
            Supports a flat monthly amount or a repeating twelve
            month schedule, both escalating once a year.

        Arguments:
            withdrawal_settings (WithdrawalSettings): Exit rules.
            pause_calendar (PauseCalendar): Pause lookup.

        Returns:
            None: A configured withdrawal plan is initialised.

        Warning:
            The plan never checks whether the corpus can fund the
            requested amount; the engine caps it at the balance.
        """
        self._withdrawal_settings = withdrawal_settings
        self._pause_calendar = pause_calendar

    def calculate_withdrawal_float(
        self,
        month_index_int: int,
        month_date: date,
        portfolio_value_float: float = 0.0,
    ) -> float:
        """Compute the rupees to withdraw in one month.

        Brief:
            Returns zero before the start month, while disabled or
            while paused, otherwise escalates the base amount.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.
            portfolio_value_float (float): Corpus available, used
                by the percentage-of-corpus mode.

        Returns:
            float: Requested withdrawal, never negative.

        Warning:
            Escalation is measured from the withdrawal start month.
        """
        settings = self._withdrawal_settings
        if not settings.is_enabled_bool:
            return 0.0
        if int(month_index_int) < int(settings.start_month_index_int):
            return 0.0
        if self._pause_calendar.is_withdrawal_paused_bool(month_date):
            return 0.0
        elapsed_years_int = (
            int(month_index_int) - int(settings.start_month_index_int)
        ) // MONTHS_IN_YEAR_INT
        if settings.mode_str == WITHDRAWAL_MODE_PERCENT_STR:
            return max(
                0.0,
                float(portfolio_value_float)
                * float(settings.portfolio_percent_float)
                / PERCENT_TOTAL_FLOAT,
            )
        if settings.mode_str == WITHDRAWAL_MODE_FIXED_STR:
            return apply_annual_growth_factor_float(
                settings.fixed_amount_float,
                settings.annual_change_percent_float,
                elapsed_years_int,
            )
        return self._calculate_scheduled_amount_float(
            month_date, elapsed_years_int
        )

    def _calculate_scheduled_amount_float(
        self,
        month_date: date,
        elapsed_years_int: int,
    ) -> float:
        """Escalate the calendar-month entry of the schedule.

        Brief:
            Each calendar month may carry its own base amount and
            its own yearly change rate.

        Arguments:
            month_date (date): Calendar month being simulated.
            elapsed_years_int (int): Completed withdrawal years.

        Returns:
            float: Escalated withdrawal for that calendar month.

        Warning:
            A schedule shorter than twelve entries yields zero for
            the missing months.
        """
        settings = self._withdrawal_settings
        schedule_list = list(settings.monthly_schedule_list)
        if len(schedule_list) < MONTHS_IN_YEAR_INT:
            return 0.0
        base_amount_float = float(schedule_list[month_date.month - 1])
        global_amount_float = apply_annual_growth_factor_float(
            base_amount_float,
            settings.annual_change_percent_float,
            elapsed_years_int,
        )
        change_list = list(settings.monthly_change_percent_list)
        if len(change_list) < MONTHS_IN_YEAR_INT:
            return global_amount_float
        return apply_annual_growth_factor_float(
            global_amount_float,
            float(change_list[month_date.month - 1]),
            elapsed_years_int,
        )


def build_portfolio_share_dict(
    fund_configurations_list: list,
) -> dict:
    """Divide one portfolio instalment between the funds.

    A rail event says "invest 25,000 a month". That is a statement
    about the plan, not about each fund in it, so it has to be
    divided before it reaches them. The division follows the target
    weights the reader set, because that is the only statement of
    intent available about how the money should be spread.

    Arguments:
        fund_configurations_list (list): Every fund in the plan.

    Returns:
        dict: Fund name mapped to its share, summing to one.

    Warning:
        Weights that are all zero - which some presets leave -
        would divide by nothing, so those plans split evenly. That
        is a guess, but an even split of the right total is far
        closer than handing every fund the whole amount.
    """
    if not fund_configurations_list:
        return {}
    weight_dict = {
        fund_configuration.name_str: max(
            0.0,
            float(
                fund_configuration.target_allocation_percent_float
            ),
        )
        for fund_configuration in fund_configurations_list
    }
    total_float = sum(weight_dict.values())
    if total_float <= 0.0:
        even_float = 1.0 / len(fund_configurations_list)
        return dict.fromkeys(weight_dict, even_float)
    return {
        name_str: weight_float / total_float
        for name_str, weight_float in weight_dict.items()
    }
