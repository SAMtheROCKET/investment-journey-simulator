"""Typed data containers describing funds, settings and results."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from investment_journey_simulator.constants import (
    EXEMPTION_LEVEL_FUND_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    FINANCIAL_YEAR_START_MONTH_INT,
    MONEY_TOLERANCE_FLOAT,
    MONTHS_IN_YEAR_INT,
    REBALANCE_TRIGGER_CALENDAR_STR,
    STEPUP_MODE_OFF_STR,
    SURCHARGE_MODE_MANUAL_STR,
    SURCHARGE_REGIME_NEW_STR,
    TAX_FUNDING_PORTFOLIO_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)
from investment_journey_simulator.returns import (
    calculate_monthly_rate_after_expense_float,
    convert_monthly_to_annual_percent_float,
    convert_nominal_to_real_percent_float,
)


@dataclass(frozen=True)
class InvestmentLot:
    """One purchased parcel of units tracked for FIFO taxation."""

    principal_float: float
    purchase_month_index_int: int
    bought_at_month_start_bool: bool

    def count_months_held_int(
        self,
        valuation_month_index_int: int,
    ) -> int:
        """Count months this lot has compounded by a given month.

        Brief:
            Start-of-month purchases earn one extra month of growth
            compared with end-of-month purchases.

        Arguments:
            valuation_month_index_int (int): Month being valued.

        Returns:
            int: Months held, possibly negative before purchase.

        Warning:
            Callers must clamp negatives before compounding.
        """
        bonus_month_int = 1 if self.bought_at_month_start_bool else 0
        return (
            int(valuation_month_index_int)
            - self.purchase_month_index_int
            + bonus_month_int
        )


@dataclass
class FundConfiguration:
    """Complete definition of a single mutual fund in the plan."""

    name_str: str
    preset_str: str
    monthly_sip_float: float
    stepup_percent_float: float
    gross_return_percent_float: float
    expense_percent_float: float
    start_date: date
    target_allocation_percent_float: float
    short_term_tax_percent_float: float
    long_term_tax_percent_float: float
    long_term_threshold_months_int: int
    exemption_amount_float: float
    exemption_scope_str: str
    is_always_short_term_bool: bool
    expense_model_str: str = EXPENSE_MODEL_SIMPLE_STR
    initial_investment_float: float = 0.0
    exit_load_percent_float: float = 0.0
    exit_load_within_months_int: int = 0
    transaction_tax_percent_float: float = 0.0
    monthly_rate_override_float: float | None = None
    monthly_rate_path_list: list[float] | None = None

    @property
    def monthly_rate_float(self) -> float:
        """Effective monthly rate this fund compounds at.

        Brief:
            Honours the expense model, or an explicit override used
            by experiments that inject a rate directly.

        Arguments:
            None.

        Returns:
            float: Effective monthly rate as a decimal fraction.

        Warning:
            Recomputed on every access; cache it in tight loops.
        """
        if self.monthly_rate_override_float is not None:
            return float(self.monthly_rate_override_float)
        return calculate_monthly_rate_after_expense_float(
            self.gross_return_percent_float,
            self.expense_percent_float,
            self.expense_model_str,
        )

    @property
    def net_return_percent_float(self) -> float:
        """Annualised return actually used for compounding.

        Brief:
            Reporting figure derived from the monthly rate so that
            both expense models report what they really apply.

        Arguments:
            None.

        Returns:
            float: Effective net annual return in percent.

        Warning:
            Differs from gross minus expense under the accrual
            model, which is the point of that model.
        """
        return convert_monthly_to_annual_percent_float(
            self.monthly_rate_float
        )

    def build_rate_adjusted_copy(
        self,
        annual_rate_percent_float: float,
    ) -> FundConfiguration:
        """Copy this fund with an explicitly forced return rate.

        Brief:
            Used by experiments that need a fund to compound at a
            chosen rate regardless of its gross and expense inputs.

        Arguments:
            annual_rate_percent_float (float): Annual rate to force.

        Returns:
            FundConfiguration: Copy compounding at that rate.

        Warning:
            Do not use this to produce inflation-adjusted reports;
            deflate nominal results with `inflation.py` instead,
            because tax law applies to nominal gains.
        """
        from investment_journey_simulator.returns import (
            convert_annual_to_monthly_rate_float,
        )

        return replace(
            self,
            monthly_rate_override_float=(
                convert_annual_to_monthly_rate_float(
                    annual_rate_percent_float
                )
            ),
        )

    def build_real_rate_copy(
        self,
        inflation_percent_float: float,
    ) -> FundConfiguration:
        """Copy this fund compounding at its real return rate.

        Brief:
            Kept for sensitivity experiments where the user wants
            every rate expressed in real terms from the start.

        Arguments:
            inflation_percent_float (float): Annual inflation.

        Returns:
            FundConfiguration: Copy with a deflated return.

        Warning:
            Not the correct way to report inflation-adjusted
            results, because it taxes real gains; use `inflation.py`.
        """
        return self.build_rate_adjusted_copy(
            convert_nominal_to_real_percent_float(
                self.net_return_percent_float,
                inflation_percent_float,
            )
        )


@dataclass(frozen=True)
class PauseRange:
    """Inclusive date window during which cash flows are stopped."""

    start_date: date
    end_date: date
    scope_str: str


@dataclass(frozen=True)
class StepUpSettings:
    """Rules controlling yearly escalation of contributions."""

    mode_str: str = STEPUP_MODE_OFF_STR
    global_stepup_percent_float: float = 0.0
    interval_months_int: int = MONTHS_IN_YEAR_INT
    first_stepup_month_index_int: int = 0
    fixed_increment_amount_float: float = 0.0


@dataclass(frozen=True)
class WithdrawalSettings:
    """Rules controlling systematic withdrawals from the corpus."""

    is_enabled_bool: bool = False
    start_month_index_int: int = 0
    mode_str: str = WITHDRAWAL_MODE_FIXED_STR
    fixed_amount_float: float = 0.0
    monthly_schedule_list: list[float] = field(default_factory=list)
    annual_change_percent_float: float = 0.0
    monthly_change_percent_list: list[float] = field(
        default_factory=list
    )
    portfolio_percent_float: float = 0.0


@dataclass(frozen=True)
class PauseSettings:
    """Recurring and one-off pauses for contributions and exits."""

    sip_pause_months_list: list[int] = field(default_factory=list)
    withdrawal_pause_months_list: list[int] = field(
        default_factory=list
    )
    pause_ranges_list: list[PauseRange] = field(default_factory=list)


@dataclass(frozen=True)
class RebalanceSettings:
    """Rules controlling periodic realignment to target weights."""

    is_enabled_bool: bool = False
    interval_months_int: int = 0
    method_str: str = ""
    target_mode_str: str = ""
    tax_funding_str: str = TAX_FUNDING_PORTFOLIO_STR
    maximum_events_int: int = 0
    trigger_str: str = REBALANCE_TRIGGER_CALENDAR_STR
    drift_band_percent_float: float = 0.0
    use_contribution_steering_bool: bool = False
    rebalance_month_index_tuple: tuple = ()

    @property
    def needs_target_weights_bool(self) -> bool:
        """Whether any feature of this run consumes target weights.

        Brief:
            Contribution steering needs targets even when no
            selling trade will ever be executed.

        Arguments:
            None.

        Returns:
            bool: True when target weights must be resolved.

        Warning:
            When False the engine must keep every target at zero so
            a passive run can never be influenced by them.
        """
        return bool(
            self.is_enabled_bool
            or self.use_contribution_steering_bool
        )


@dataclass(frozen=True)
class TaxSettings:
    """Portfolio level taxation choices.

    ``income_by_year_tuple`` holds ``(financial_year, income)``
    pairs describing an income that changes over a lifetime. The
    entry in force is the latest one at or before the year of the
    sale; with none, ``total_income_float`` applies throughout. It
    is a tuple rather than a dict so the settings stay hashable and
    survive a round trip through a saved scenario.

    ``tax_year_start_month_int`` decides when the annual exemption
    resets and when a carried-forward loss expires. It defaults to
    April, which is India's, and is the one field here that has to
    change for any other jurisdiction: leaving it at four while
    modelling a calendar-year country moves both boundaries by a
    quarter and quietly reports the wrong tax.
    """

    exemption_level_str: str = EXEMPTION_LEVEL_FUND_STR
    portfolio_exemption_amount_float: float = 0.0
    apply_final_liquidation_tax_bool: bool = False
    surcharge_percent_float: float = 0.0
    cess_percent_float: float = 0.0
    allow_loss_set_off_bool: bool = True
    surcharge_mode_str: str = SURCHARGE_MODE_MANUAL_STR
    surcharge_regime_str: str = SURCHARGE_REGIME_NEW_STR
    total_income_float: float = 0.0
    apply_grandfathering_bool: bool = True
    income_by_year_tuple: tuple = ()
    tax_year_start_month_int: int = FINANCIAL_YEAR_START_MONTH_INT


@dataclass(frozen=True)
class InstalmentOverride:
    """A change to the monthly instalment from a given month.

    Resets the base amount *and* the escalation clock: telling the
    plan "my SIP is now thirty thousand" means thirty thousand this
    month, not thirty thousand multiplied by every step-up that has
    happened since the fund started. Any later step-up then grows
    from the new figure.
    """

    month_index_int: int
    amount_float: float
    fund_name_str: str = ""


@dataclass(frozen=True)
class OneOffContribution:
    """An extra investment made in one specific month.

    Distinct from a fund's opening lump sum, which is always
    invested in month zero. This one carries its own month, so a
    bonus received in year eight compounds for the years that
    actually remain rather than for the whole horizon.
    """

    month_index_int: int
    amount_float: float
    fund_name_str: str = ""


@dataclass(frozen=True)
class SimulationSettings:
    """Every portfolio-level input needed to run a simulation."""

    horizon_years_int: int
    portfolio_start_date: date
    sip_at_month_start_bool: bool
    stepup: StepUpSettings
    withdrawal: WithdrawalSettings
    pauses: PauseSettings
    rebalance: RebalanceSettings
    tax: TaxSettings = field(default_factory=TaxSettings)
    one_off_contributions_list: list[OneOffContribution] = field(
        default_factory=list
    )
    instalment_override_list: list[InstalmentOverride] = field(
        default_factory=list
    )

    @property
    def total_months_int(self) -> int:
        """Total simulated months implied by the horizon.

        Brief:
            Single source of truth for the length of every series.

        Arguments:
            None.

        Returns:
            int: Number of months to simulate.

        Warning:
            A zero horizon produces empty result series.
        """
        return max(0, int(self.horizon_years_int)) * (
            MONTHS_IN_YEAR_INT
        )


@dataclass(frozen=True)
class RealizedGainBreakdown:
    """Tax outcome of one realized gain chunk."""

    tax_amount_float: float
    short_term_gain_float: float
    long_term_gain_float: float
    realized_loss_float: float = 0.0
    offset_loss_float: float = 0.0


@dataclass(frozen=True)
class SaleOutcome:
    """Proceeds, tax and charges from selling one fund."""

    proceeds_float: float
    tax_amount_float: float
    charges_float: float = 0.0


@dataclass(frozen=True)
class FundMonthlyState:
    """State of one fund at the close of one simulated month."""

    name_str: str
    value_float: float
    cost_basis_float: float
    contributed_float: float
    withdrawn_float: float
    tax_float: float
    charges_float: float = 0.0


@dataclass(frozen=True)
class MonthlySnapshot:
    """Portfolio state recorded at the close of one month."""

    month_date: date
    portfolio_value_float: float
    invested_amount_float: float
    withdrawn_amount_float: float
    tax_paid_float: float
    monthly_sip_float: float
    monthly_withdrawal_float: float
    requested_withdrawal_float: float = 0.0
    unmet_withdrawal_float: float = 0.0
    monthly_tax_float: float = 0.0
    monthly_charges_float: float = 0.0
    fund_states_list: list[FundMonthlyState] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class RebalanceEvent:
    """Audit record of one executed rebalancing transaction."""

    month_date: date
    value_before_float: float
    value_after_float: float
    tax_amount_float: float
    weights_before_dict: dict[str, float]
    weights_after_dict: dict[str, float]
    trigger_reason_str: str = REBALANCE_TRIGGER_CALENDAR_STR


@dataclass(frozen=True)
class FundOutcome:
    """End-of-horizon result for a single fund."""

    name_str: str
    preset_str: str
    start_date: date
    net_return_percent_float: float
    invested_amount_float: float
    withdrawn_amount_float: float
    ending_value_float: float
    tax_paid_float: float
    short_term_gain_float: float
    long_term_gain_float: float
    cost_basis_float: float = 0.0
    final_liquidation_tax_float: float = 0.0
    final_liquidation_charges_float: float = 0.0
    realized_loss_float: float = 0.0
    charges_paid_float: float = 0.0

    @property
    def wealth_generated_float(self) -> float:
        """Ending value plus everything already withdrawn.

        Brief:
            Withdrawals must be added back to compare funds that
            were partially liquidated with funds that were not.

        Arguments:
            None.

        Returns:
            float: Gross wealth created by this fund.

        Warning:
            Withdrawals are counted gross, before tax.
        """
        return self.ending_value_float + self.withdrawn_amount_float

    @property
    def gain_amount_float(self) -> float:
        """Wealth generated in excess of the invested principal.

        Brief:
            The headline profit figure shown in the gains donut.

        Arguments:
            None.

        Returns:
            float: Gain over principal, negative when at a loss.

        Warning:
            Realized taxes are not subtracted from this figure.
        """
        return self.wealth_generated_float - self.invested_amount_float

    @property
    def realized_gain_float(self) -> float:
        """Gain already crystallised by selling units.

        Brief:
            Sum of the short and long term gains booked by exits
            and by rebalancing trades.

        Arguments:
            None.

        Returns:
            float: Total realized gain of this fund.

        Warning:
            Realized gains are gross of the tax charged on them.
        """
        return (
            self.short_term_gain_float + self.long_term_gain_float
        )

    @property
    def unrealized_gain_float(self) -> float:
        """Gain still sitting inside the units held today.

        Brief:
            Difference between current value and the cost basis of
            the lots that have not been sold.

        Arguments:
            None.

        Returns:
            float: Unrealized gain, negative when under water.

        Warning:
            This becomes taxable only when the units are sold.
        """
        return self.ending_value_float - self.cost_basis_float


@dataclass(frozen=True)
class SimulationResult:
    """Full output of one portfolio simulation run."""

    monthly_snapshots_list: list[MonthlySnapshot]
    fund_outcomes_list: list[FundOutcome]
    rebalance_events_list: list[RebalanceEvent] = field(
        default_factory=list
    )

    @property
    def rebalance_tax_float(self) -> float:
        """Tax realized specifically by rebalancing trades.

        Brief:
            Separating this from the total makes the cost of a
            rebalancing policy visible on its own.

        Arguments:
            None.

        Returns:
            float: Tax accrued across all rebalancing events.

        Warning:
            Counted gross, even when funded from outside the
            portfolio rather than by selling more units.
        """
        return sum(
            rebalance_event.tax_amount_float
            for rebalance_event in self.rebalance_events_list
        )

    @property
    def withdrawal_tax_float(self) -> float:
        """Tax realized by withdrawals rather than rebalancing.

        Brief:
            Complement of the rebalancing tax within the total.

        Arguments:
            None.

        Returns:
            float: Tax attributable to systematic withdrawals.

        Warning:
            Never negative; rounding is absorbed at zero.
        """
        return max(
            0.0, self.ending_tax_paid_float - self.rebalance_tax_float
        )

    @property
    def final_liquidation_tax_float(self) -> float:
        """Tax that selling everything on the last day would cost.

        Brief:
            Turns a paper corpus into a spendable one, because
            unrealized gains are still taxable on exit.

        Arguments:
            None.

        Returns:
            float: Tax due on a full redemption at the horizon.

        Warning:
            Zero unless the final liquidation setting was enabled.
        """
        return sum(
            fund_outcome.final_liquidation_tax_float
            for fund_outcome in self.fund_outcomes_list
        )

    @property
    def final_liquidation_charges_float(self) -> float:
        """Exit load and transaction tax of a full redemption.

        Brief:
            Charges are not tax, so they are reported separately
            even though both reduce what you can spend.

        Arguments:
            None.

        Returns:
            float: Charges due on a full exit at the horizon.

        Warning:
            Zero unless the final liquidation setting is enabled.
        """
        return sum(
            fund_outcome.final_liquidation_charges_float
            for fund_outcome in self.fund_outcomes_list
        )

    @property
    def total_exit_cost_float(self) -> float:
        """Everything a full exit at the horizon would cost.

        Brief:
            Tax plus exit load plus transaction tax.

        Arguments:
            None.

        Returns:
            float: Total cost of liquidating on the last day.

        Warning:
            Zero unless the final liquidation setting is enabled.
        """
        return (
            self.final_liquidation_tax_float
            + self.final_liquidation_charges_float
        )

    @property
    def charges_paid_float(self) -> float:
        """Exit load and transaction tax already incurred.

        Brief:
            Accumulated by withdrawals and rebalancing trades.

        Arguments:
            None.

        Returns:
            float: Charges paid across the horizon.

        Warning:
            Separate from, and additional to, capital gains tax.
        """
        return sum(
            fund_outcome.charges_paid_float
            for fund_outcome in self.fund_outcomes_list
        )

    @property
    def realized_loss_float(self) -> float:
        """Capital losses booked over the horizon.

        Brief:
            Available to set off against later gains.

        Arguments:
            None.

        Returns:
            float: Total realized loss, as a positive magnitude.

        Warning:
            Only arises when a fund is sold below its cost basis.
        """
        return sum(
            fund_outcome.realized_loss_float
            for fund_outcome in self.fund_outcomes_list
        )

    @property
    def post_tax_ending_value_float(self) -> float:
        """Corpus left after a hypothetical full redemption.

        Brief:
            The number an investor can actually spend.

        Arguments:
            None.

        Returns:
            float: Ending value minus tax and exit charges.

        Warning:
            Equals the ending value when the final liquidation
            setting is disabled.
        """
        return self.ending_value_float - self.total_exit_cost_float

    @property
    def total_unmet_withdrawal_float(self) -> float:
        """Withdrawals the portfolio could not fund.

        Brief:
            Non-zero means the plan ran out of money before the
            horizon ended.

        Arguments:
            None.

        Returns:
            float: Sum of every shortfall across the horizon.

        Warning:
            A non-zero value invalidates the withdrawal plan.
        """
        return sum(
            snapshot.unmet_withdrawal_float
            for snapshot in self.monthly_snapshots_list
        )

    @property
    def depletion_month_date(self) -> date | None:
        """First month in which a withdrawal could not be paid.

        Brief:
            Marks the point at which the corpus was exhausted.

        Arguments:
            None.

        Returns:
            Optional[date]: Month of first shortfall, or None.

        Warning:
            None also means the plan simply never withdrew.
        """
        for snapshot in self.monthly_snapshots_list:
            if snapshot.unmet_withdrawal_float > (
                MONEY_TOLERANCE_FLOAT
            ):
                return snapshot.month_date
        return None

    @property
    def ending_value_float(self) -> float:
        """Portfolio value at the final simulated month.

        Brief:
            Reads the last snapshot so callers never index lists.

        Arguments:
            None.

        Returns:
            float: Closing portfolio value, zero when empty.

        Warning:
            Returns zero for an empty horizon.
        """
        if not self.monthly_snapshots_list:
            return 0.0
        return self.monthly_snapshots_list[-1].portfolio_value_float

    @property
    def ending_invested_float(self) -> float:
        """Cumulative principal contributed over the horizon.

        Brief:
            Counts contributions only, never internal rebalance
            purchases.

        Arguments:
            None.

        Returns:
            float: Total invested principal, zero when empty.

        Warning:
            Returns zero for an empty horizon.
        """
        if not self.monthly_snapshots_list:
            return 0.0
        return self.monthly_snapshots_list[-1].invested_amount_float

    @property
    def ending_withdrawn_float(self) -> float:
        """Cumulative gross withdrawals over the horizon.

        Brief:
            Measured before tax, matching the withdrawal series.

        Arguments:
            None.

        Returns:
            float: Total gross withdrawals, zero when empty.

        Warning:
            Returns zero for an empty horizon.
        """
        if not self.monthly_snapshots_list:
            return 0.0
        return self.monthly_snapshots_list[-1].withdrawn_amount_float

    @property
    def ending_tax_paid_float(self) -> float:
        """Cumulative realized tax over the horizon.

        Brief:
            Accrued whenever a sale realizes a taxable gain.

        Arguments:
            None.

        Returns:
            float: Total realized tax, zero when empty.

        Warning:
            Excludes the final liquidation tax, which is reported
            separately because it has not been incurred yet.
        """
        if not self.monthly_snapshots_list:
            return 0.0
        return self.monthly_snapshots_list[-1].tax_paid_float
