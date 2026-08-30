"""Month-by-month portfolio simulation engine."""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.allocation import resolve_target_weight_dict
from investment_journey_simulator.constants import (
    MONEY_TOLERANCE_FLOAT,
    PERCENT_TOTAL_FLOAT,
    RATIO_TOLERANCE_FLOAT,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TRIGGER_BAND_STR,
    REBALANCE_TRIGGER_BOTH_STR,
    REBALANCE_TRIGGER_CALENDAR_STR,
    REBALANCE_TRIGGER_DATED_STR,
    TAX_FUNDING_OUTSIDE_STR,
)
from investment_journey_simulator.holdings import FundHoldings
from investment_journey_simulator.models import (
    FundConfiguration,
    FundMonthlyState,
    FundOutcome,
    MonthlySnapshot,
    OneOffContribution,
    RebalanceEvent,
    SimulationResult,
    SimulationSettings,
)
from investment_journey_simulator.schedules import (
    ContributionPlan,
    PauseCalendar,
    WithdrawalPlan,
    build_portfolio_share_dict,
)
from investment_journey_simulator.taxation import (
    CapitalGainsTaxPolicy,
    ExemptionLedger,
    LossLedger,
)
from investment_journey_simulator.time_utils import (
    build_month_start_dates_list,
)


def calculate_weight_dict(
    value_dict: dict[str, float],
) -> dict[str, float]:
    """Convert fund values into percentage portfolio weights.

    Brief:
        Used by the rebalancing ledger and the drift-band trigger.

    Arguments:
        value_dict (Dict[str, float]): Fund name to value mapping.

    Returns:
        Dict[str, float]: Fund name to weight percent mapping.

    Warning:
        An empty portfolio yields zero weights for every fund.
    """
    total_value_float = sum(value_dict.values())
    if total_value_float <= MONEY_TOLERANCE_FLOAT:
        return dict.fromkeys(value_dict, 0.0)
    return {
        fund_name_str: (
            PERCENT_TOTAL_FLOAT * value_float / total_value_float
        )
        for fund_name_str, value_float in value_dict.items()
    }


def _build_empty_totals_dict() -> dict[str, float]:
    """Build a zeroed baseline for the monthly delta counters.

    Brief:
        Used for a fund's very first recorded month.

    Arguments:
        None.

    Returns:
        Dict[str, float]: Zero for every tracked counter.

    Warning:
        Keys must match the counters read in the state builder.
    """
    return {
        "invested": 0.0,
        "withdrawn": 0.0,
        "tax": 0.0,
        "charges": 0.0,
    }


def _read_totals_dict(holdings: FundHoldings) -> dict[str, float]:
    """Read a fund's cumulative counters into one mapping.

    Brief:
        Paired with the zeroed baseline to compute monthly deltas.

    Arguments:
        holdings (FundHoldings): Fund being read.

    Returns:
        Dict[str, float]: Current value of every counter.

    Warning:
        Keys must match the zeroed baseline exactly.
    """
    return {
        "invested": holdings.contributed_amount_float,
        "withdrawn": holdings.withdrawn_amount_float,
        "tax": holdings.tax_paid_amount_float,
        "charges": holdings.charges_paid_amount_float,
    }


def _build_shared_dry_run_tuple_from(
    holdings_list: list[FundHoldings],
) -> tuple:
    """Build one throwaway ledger pair for a whole-portfolio exit.

    Brief:
        Every fund's exit estimate must draw on the same throwaway
        shelter, because the section 112A exemption belongs to the
        taxpayer and not to each scheme. Giving each fund a private
        copy lets a two-fund plan claim the allowance twice.

    Arguments:
        holdings_list (List[FundHoldings]): Funds in the run.

    Returns:
        tuple: Shared exemption and loss ledgers, empty when the
            portfolio holds no funds at all.

    Warning:
        The pair is consumed in fund order, so the estimate is
        order dependent exactly as a real sequence of sales is.
    """
    if not holdings_list:
        return ()
    return holdings_list[
        0
    ].build_shared_dry_run_ledgers_tuple()


def _build_holdings_list(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
) -> list[FundHoldings]:
    """Create one lot book per fund on a shared tax ledger.

    Brief:
        The shared ledger is what lets the exemption be tracked
        across the whole portfolio rather than per fund.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio level rules.

    Returns:
        List[FundHoldings]: One holding per configured fund.

    Warning:
        Duplicate fund names would share dictionary keys later.
    """
    exemption_ledger = ExemptionLedger()
    loss_ledger = LossLedger()
    return [
        FundHoldings(
            fund_configuration=fund_configuration,
            tax_policy=CapitalGainsTaxPolicy(
                fund_configuration,
                exemption_ledger,
                settings.tax,
                loss_ledger,
            ),
            portfolio_start_date=settings.portfolio_start_date,
            apply_grandfathering_bool=(
                settings.tax.apply_grandfathering_bool
            ),
        )
        for fund_configuration in fund_configurations_list
    ]


class PortfolioSimulator:
    """Simulates contributions, withdrawals, tax and rebalancing."""

    def __init__(
        self,
        fund_configurations_list: list[FundConfiguration],
        settings: SimulationSettings,
    ) -> None:
        """Wire funds, schedules and tax ledger into one engine.

        Brief:
            Builds one holding per fund and precomputes the month
            grid so the run loop stays free of setup work.

        Arguments:
            fund_configurations_list (List[FundConfiguration]):
                Funds taking part in the simulation.
            settings (SimulationSettings): Portfolio level rules.

        Returns:
            None: A ready-to-run simulator is initialised.

        Warning:
            One simulator instance supports a single run only.
        """
        self._settings = settings
        self._month_dates_list = build_month_start_dates_list(
            settings.portfolio_start_date, settings.total_months_int
        )
        self._holdings_list = _build_holdings_list(
            fund_configurations_list, settings
        )
        self._target_weight_dict = resolve_target_weight_dict(
            fund_configurations_list, settings.rebalance
        )
        pause_calendar = PauseCalendar(settings.pauses)
        self._contribution_plan = ContributionPlan(
            settings.stepup,
            pause_calendar,
            settings.portfolio_start_date,
            settings.instalment_override_list,
            build_portfolio_share_dict(fund_configurations_list),
        )
        self._withdrawal_plan = WithdrawalPlan(
            settings.withdrawal, pause_calendar
        )
        self._snapshots_list: list[MonthlySnapshot] = []
        self._rebalance_events_list: list[RebalanceEvent] = []
        self._previous_totals_dict: dict[str, dict[str, float]] = {}

    def run(self) -> SimulationResult:
        """Simulate every month of the configured horizon.

        Brief:
            Executes contributions, withdrawals and rebalancing in
            calendar order and records a snapshot per month.

        Arguments:
            None.

        Returns:
            SimulationResult: Snapshots, outcomes and the ledger.

        Warning:
            Call once per simulator instance.
        """
        for month_index_int in range(self._settings.total_months_int):
            self._simulate_single_month(month_index_int)
        return SimulationResult(
            monthly_snapshots_list=list(self._snapshots_list),
            fund_outcomes_list=self._build_fund_outcomes_list(),
            rebalance_events_list=list(self._rebalance_events_list),
        )

    def _simulate_single_month(self, month_index_int: int) -> None:
        """Run one month of contributions, exits and rebalancing.

        Brief:
            Start-of-month instalments are invested before the
            withdrawal, end-of-month instalments after it.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            None: One snapshot is appended to the result series.

        Warning:
            Rebalancing happens after the withdrawal so that the
            target weights hold on the post-withdrawal corpus. A
            closure happens after everything else, because the
            plan ends at the close of that month rather than at
            its start.
        """
        month_date = self._month_dates_list[month_index_int]
        invests_at_start_bool = self._settings.sip_at_month_start_bool
        contributed_float = self._pay_money_in_float(
            month_index_int, month_date, invests_at_start_bool
        )
        withdrawal_tuple = self._take_money_out_tuple(
            month_index_int, month_date
        )
        self._rebalance_if_due(month_index_int, month_date)
        if not invests_at_start_bool:
            contributed_float += self._contribute_instalments_float(
                month_index_int, month_date, False
            )
        withdrawal_tuple = self._close_plan_if_due(
            withdrawal_tuple, month_index_int, month_date
        )
        self._record_snapshot(
            month_index_int,
            month_date,
            contributed_float,
            withdrawal_tuple,
        )

    def _pay_money_in_float(
        self,
        month_index_int: int,
        month_date: date,
        invests_at_start_bool: bool,
    ) -> float:
        """Every rupee that goes in before the withdrawal does.

        Brief:
            Opening balances, dated lump sums, and the instalment
            when instalments are paid at the start of a month.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.
            invests_at_start_bool (bool): Instalment timing.

        Returns:
            float: Total external principal paid in.

        Warning:
            An end-of-month instalment is not included here; it
            lands after the withdrawal and the rebalance.
        """
        contributed_float = self._seed_initial_corpus_float(
            month_index_int
        )
        contributed_float += self._invest_one_offs_float(
            month_index_int
        )
        if invests_at_start_bool:
            contributed_float += self._contribute_instalments_float(
                month_index_int, month_date, True
            )
        return contributed_float

    def _take_money_out_tuple(
        self,
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float, float]:
        """The standing withdrawal, then any lump sums.

        Brief:
            Both can fall in one month, and both are met from the
            same corpus, so they are raised in one place.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            Tuple[float, float, float]: Asked for, raised, paid.

        Warning:
            The closure is deliberately not here. It runs after
            the rebalance and the end-of-month instalment, because
            it ends the month rather than being part of its
            ordinary business.
        """
        return self._add_one_off_withdrawals(
            self._withdraw_proportionally(
                month_index_int, month_date
            ),
            month_index_int,
            month_date,
        )

    def _liquidate_every_fund(
        self,
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float]:
        """Empty every lot book and pay the proceeds out.

        Brief:
            Selling the balance and selling everything are not the
            same operation. The first compares a running total
            against each lot and can leave a fraction behind; the
            second empties the book, so the plan afterwards holds
            exactly nothing rather than nearly nothing.

        Arguments:
            month_index_int (int): Month index of the exit.
            month_date (date): Calendar date of the exit.

        Returns:
            Tuple[float, float]: Proceeds, and what was paid out.

        Warning:
            Irreversible within a run. Every holding period ends
            here, so the tax is whatever those lots had accrued.
        """
        raised_float = 0.0
        received_float = 0.0
        for holdings in self._holdings_list:
            sale_outcome = holdings.sell_everything(
                month_index_int, month_date
            )
            paid_float = max(
                0.0,
                sale_outcome.proceeds_float
                - sale_outcome.charges_float,
            )
            holdings.register_withdrawal(paid_float)
            raised_float += sale_outcome.proceeds_float
            received_float += paid_float
        return raised_float, received_float

    def _add_one_off_withdrawals(
        self,
        withdrawal_tuple: tuple[float, float, float],
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float, float]:
        """Take out every lump sum dated to this month.

        Brief:
            A car, a deposit, a medical bill. Added to whatever the
            standing withdrawal already took, so a month can carry
            both.

        Arguments:
            withdrawal_tuple (tuple): Asked for, raised and paid so
                far this month.
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            tuple: The same three figures with the lump sums added.

        Warning:
            The standing withdrawal is met first, because it is the
            arrangement already running; a lump sum is the
            exceptional act and takes what is left. Either can go
            unmet when the corpus cannot cover it.
        """
        requested_float, proceeds_float, paid_float = (
            withdrawal_tuple
        )
        for withdrawal in self._settings.one_off_withdrawals_list:
            if int(withdrawal.month_index_int) != int(
                month_index_int
            ):
                continue
            amount_float = float(withdrawal.amount_float)
            if amount_float <= 0.0:
                continue
            raised_float, received_float = self._sell_for_amount(
                amount_float,
                withdrawal.fund_name_str,
                month_index_int,
                month_date,
            )
            requested_float += amount_float
            proceeds_float += raised_float
            paid_float += received_float
        return requested_float, proceeds_float, paid_float

    def _sell_for_amount(
        self,
        amount_float: float,
        fund_name_str: str,
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float]:
        """Raise one amount, from one fund or from all of them.

        Brief:
            Naming no fund spreads the sale across the portfolio in
            proportion to what each holds, which leaves the weights
            where they were. Naming one takes the whole amount from
            that fund, which does not.

        Arguments:
            amount_float (float): Rupees to raise.
            fund_name_str (str): Fund to sell, or empty for all.
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            Tuple[float, float]: Gross proceeds raised, and the
                money that reached the investor after charges.

        Warning:
            A name that matches no fund raises nothing, rather than
            falling back to the portfolio. Silently taking money
            from somewhere the reader did not name would be worse
            than an amount that visibly went unmet.
        """
        value_dict = self._build_value_dict(month_index_int)
        if fund_name_str:
            if fund_name_str not in value_dict:
                return 0.0, 0.0
            value_dict = {
                fund_name_str: value_dict[fund_name_str]
            }
        total_value_float = sum(value_dict.values())
        if total_value_float <= MONEY_TOLERANCE_FLOAT:
            return 0.0, 0.0
        return self._raise_from_each_fund(
            min(amount_float, total_value_float),
            value_dict,
            total_value_float,
            month_index_int,
            month_date,
        )

    def _close_plan_if_due(
        self,
        withdrawal_tuple: tuple[float, float, float],
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float, float]:
        """Sell everything, if this is the month the plan closes.

        Brief:
            The whole corpus is realised at once, which is
            normally the most tax a plan ever pays in one month.

        Arguments:
            withdrawal_tuple (tuple): Asked for, raised and paid.
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            tuple: The same three figures with the exit added.

        Warning:
            Runs last, so a closing month invests and rebalances
            exactly as any other does. Nothing here stops the
            months that follow: selling every lot leaves nothing
            to grow, and the compiler pauses both flows until the
            reader restarts one. A closed plan is flat at zero
            because it is empty, not because the engine stopped.
        """
        closure_month_int = self._settings.liquidation_month_index_int
        if closure_month_int is None:
            return withdrawal_tuple
        if int(month_index_int) != int(closure_month_int):
            return withdrawal_tuple
        total_value_float = self._calculate_total_value_float(
            month_index_int
        )
        if total_value_float <= MONEY_TOLERANCE_FLOAT:
            return withdrawal_tuple
        raised_float, received_float = self._liquidate_every_fund(
            month_index_int, month_date
        )
        return (
            withdrawal_tuple[0] + total_value_float,
            withdrawal_tuple[1] + raised_float,
            withdrawal_tuple[2] + received_float,
        )

    def _seed_initial_corpus_float(
        self,
        month_index_int: int,
    ) -> float:
        """Invest each fund's opening lump sum in month zero.

        Brief:
            A lump sum is external principal like any instalment,
            invested at the start of the first month so that it
            compounds for the whole horizon.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            float: Total lump sum invested this month.

        Warning:
            Only month zero seeds; later months return zero.
        """
        if month_index_int != 0:
            return 0.0
        seeded_total_float = 0.0
        for holdings in self._holdings_list:
            amount_float = float(
                holdings.fund_configuration.initial_investment_float
            )
            if amount_float <= 0.0:
                continue
            holdings.add_contribution(amount_float, 0, True)
            seeded_total_float += amount_float
        return seeded_total_float

    def _invest_one_offs_float(self, month_index_int: int) -> float:
        """Invest every one-off dated to this month.

        Brief:
            A one-off is external principal like an instalment, but
            it compounds only from the month it actually arrived,
            which is what separates it from an opening lump sum.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            float: Total one-off principal invested this month.

        Warning:
            Several one-offs may share a month; all of them apply.
        """
        invested_float = 0.0
        for contribution in (
            self._settings.one_off_contributions_list
        ):
            if int(contribution.month_index_int) != int(
                month_index_int
            ):
                continue
            invested_float += self._invest_single_one_off_float(
                contribution, month_index_int
            )
        return invested_float

    def _invest_single_one_off_float(
        self,
        contribution: OneOffContribution,
        month_index_int: int,
    ) -> float:
        """Place one dated contribution into the funds.

        Brief:
            Splits the amount across funds by the weights the
            resolver chooses, then books each share as principal.

        Arguments:
            contribution (OneOffContribution): Contribution to make.
            month_index_int (int): Month index being simulated.

        Returns:
            float: Principal actually invested, zero if unroutable.

        Warning:
            An amount naming a fund that does not exist invests
            nothing rather than silently landing elsewhere.
        """
        amount_float = float(contribution.amount_float)
        if amount_float <= 0.0:
            return 0.0
        weight_dict = self._resolve_one_off_weight_dict(contribution)
        invested_float = 0.0
        for holdings in self._holdings_list:
            share_float = amount_float * weight_dict.get(
                holdings.fund_configuration.name_str, 0.0
            )
            if share_float <= 0.0:
                continue
            holdings.add_contribution(
                share_float, month_index_int, True
            )
            invested_float += share_float
        return invested_float

    def _resolve_one_off_weight_dict(
        self,
        contribution: OneOffContribution,
    ) -> dict[str, float]:
        """Decide which funds a one-off is split between.

        Brief:
            A named fund takes the whole amount. An unnamed one is
            split by target allocation, which is what "I added this
            to my portfolio" means when several funds exist.

        Arguments:
            contribution (OneOffContribution): Contribution to route.

        Returns:
            Dict[str, float]: Fund name to share of the amount.

        Warning:
            Falls back to an equal split when every target weight
            is zero, so the money is never silently dropped.
        """
        if contribution.fund_name_str:
            return {contribution.fund_name_str: 1.0}
        target_dict = {
            holdings.fund_configuration.name_str: max(
                0.0,
                float(
                    holdings.fund_configuration
                    .target_allocation_percent_float
                ),
            )
            for holdings in self._holdings_list
        }
        total_float = sum(target_dict.values())
        if total_float > 0.0:
            return {
                name_str: weight_float / total_float
                for name_str, weight_float in target_dict.items()
            }
        if not target_dict:
            return {}
        return dict.fromkeys(
            target_dict, 1.0 / len(target_dict)
        )

    def _contribute_instalments_float(
        self,
        month_index_int: int,
        month_date: date,
        at_month_start_bool: bool,
    ) -> float:
        """Invest this month's instalment into the funds.

        Brief:
            Contribution steering redirects the same total towards
            the funds that sit below their target weight.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.
            at_month_start_bool (bool): Start-of-month timing flag.

        Returns:
            float: Total rupees contributed across all funds.

        Warning:
            Steering never changes the total invested, only which
            fund receives it.
        """
        instalment_dict = {
            holdings.fund_configuration.name_str: (
                self._contribution_plan.calculate_instalment_float(
                    holdings.fund_configuration,
                    month_index_int,
                    month_date,
                )
            )
            for holdings in self._holdings_list
        }
        total_float = sum(instalment_dict.values())
        if total_float <= 0.0:
            return 0.0
        if self._settings.rebalance.use_contribution_steering_bool:
            instalment_dict = self._build_steered_allocation_dict(
                total_float, month_index_int, instalment_dict
            )
        for holdings in self._holdings_list:
            amount_float = instalment_dict.get(
                holdings.fund_configuration.name_str, 0.0
            )
            holdings.add_contribution(
                amount_float, month_index_int, at_month_start_bool
            )
        return total_float

    def _build_steered_allocation_dict(
        self,
        total_contribution_float: float,
        month_index_int: int,
        fallback_dict: dict[str, float],
    ) -> dict[str, float]:
        """Send this month's money to the underweight funds.

        Brief:
            Cash-flow rebalancing corrects drift without selling
            anything, so it realizes no gain and costs no tax.

        Arguments:
            total_contribution_float (float): Rupees to allocate.
            month_index_int (int): Month index being simulated.
            fallback_dict (Dict[str, float]): Plain instalment
                split used when nothing is underweight.

        Returns:
            Dict[str, float]: Fund name to contribution mapping.

        Warning:
            Steering alone cannot fix large drift once the corpus
            dwarfs the monthly instalment.
        """
        value_dict = self._build_value_dict(month_index_int)
        shortfall_dict = self._build_projected_shortfall_dict(
            value_dict, total_contribution_float
        )
        shortfall_total_float = sum(shortfall_dict.values())
        if shortfall_total_float <= MONEY_TOLERANCE_FLOAT:
            return dict(fallback_dict)
        return {
            fund_name_str: (
                total_contribution_float
                * shortfall_float
                / shortfall_total_float
            )
            for fund_name_str, shortfall_float in (
                shortfall_dict.items()
            )
        }

    def _build_projected_shortfall_dict(
        self,
        value_dict: dict[str, float],
        total_contribution_float: float,
    ) -> dict[str, float]:
        """Measure the gap to target once this month is invested.

        Brief:
            Targets are applied to the corpus the portfolio will
            have after the instalment lands, not before.

        Arguments:
            value_dict (Dict[str, float]): Current fund values.
            total_contribution_float (float): Money about to land.

        Returns:
            Dict[str, float]: Fund name to shortfall mapping.

        Warning:
            Funds already at or above target are omitted.
        """
        projected_total_float = (
            sum(value_dict.values()) + total_contribution_float
        )
        shortfall_dict: dict[str, float] = {}
        for holdings in self._holdings_list:
            fund_name_str = holdings.fund_configuration.name_str
            desired_float = (
                projected_total_float
                * self._target_weight_float(holdings)
                / PERCENT_TOTAL_FLOAT
            )
            shortfall_float = (
                desired_float - value_dict[fund_name_str]
            )
            if shortfall_float > MONEY_TOLERANCE_FLOAT:
                shortfall_dict[fund_name_str] = shortfall_float
        return shortfall_dict

    def _withdraw_proportionally(
        self,
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float, float]:
        """Withdraw the scheduled amount across all funds pro rata.

        Brief:
            Each fund funds the withdrawal in proportion to its own
            share of the portfolio, keeping weights undisturbed.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            Tuple[float, float, float]: Amount asked for, the gross
                proceeds the sale raised, and the money that
                actually reached the investor.

        Warning:
            The last two differ by the exit load and the securities
            transaction tax, which the fund house deducts at source
            - so the units leave the portfolio at their full value
            while the investor receives less. Capital gains tax is
            different again: it is accrued and reported, but never
            deducted here, because a resident settles it at filing
            time out of their own pocket rather than at redemption.
        """
        value_dict = self._build_value_dict(month_index_int)
        total_value_float = sum(value_dict.values())
        requested_float = (
            self._withdrawal_plan.calculate_withdrawal_float(
                month_index_int, month_date, total_value_float
            )
        )
        if requested_float <= 0.0:
            return 0.0, 0.0, 0.0
        if total_value_float <= MONEY_TOLERANCE_FLOAT:
            return requested_float, 0.0, 0.0
        proceeds_float, paid_float = self._raise_from_each_fund(
            requested_float,
            value_dict,
            total_value_float,
            month_index_int,
            month_date,
        )
        return requested_float, proceeds_float, paid_float

    def _raise_from_each_fund(
        self,
        requested_float: float,
        value_dict: dict[str, float],
        total_value_float: float,
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float]:
        """Sell every fund's share and pay the investor the net.

        Brief:
            Each fund gives up its own share, so the weights are
            unchanged by the sale.

        Arguments:
            requested_float (float): Rupees the plan asked for.
            value_dict (Dict[str, float]): Values before the sale.
            total_value_float (float): Their total.
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            Tuple[float, float]: Proceeds, and what was paid out.
        """
        total_proceeds_float = 0.0
        total_paid_float = 0.0
        for holdings in self._holdings_list:
            fund_name_str = holdings.fund_configuration.name_str
            # Raising from one named fund passes a mapping with
            # only that fund in it; the rest are absent, not zero.
            if fund_name_str not in value_dict:
                continue
            # Share first, then multiply. The other grouping,
            # (requested * value) / total, is the same in algebra
            # and not in floating point, and it moves the last bit
            # of every withdrawal.
            fund_share_float = (
                value_dict[fund_name_str] / total_value_float
            )
            proceeds_float, paid_float = self._sell_one_fund(
                holdings,
                requested_float * fund_share_float,
                month_index_int,
                month_date,
            )
            total_proceeds_float += proceeds_float
            total_paid_float += paid_float
        return total_proceeds_float, total_paid_float

    def _sell_one_fund(
        self,
        holdings: FundHoldings,
        amount_float: float,
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float]:
        """Raise one amount from one fund and book the payout.

        Brief:
            The single place a sale becomes a withdrawal, so the
            charges come off the payout exactly once.

        Arguments:
            holdings (FundHoldings): Fund being sold.
            amount_float (float): Rupees to raise from it.
            month_index_int (int): Month index of the sale.
            month_date (date): Calendar date of the sale.

        Returns:
            Tuple[float, float]: Proceeds, and what was paid out.

        Warning:
            Used for investor withdrawals only. A rebalance sells
            through the same holdings but reinvests the proceeds,
            so it must never book a withdrawal here.
        """
        sale_outcome = holdings.sell_for_proceeds(
            amount_float, month_index_int, month_date
        )
        paid_float = max(
            0.0,
            sale_outcome.proceeds_float
            - sale_outcome.charges_float,
        )
        holdings.register_withdrawal(paid_float)
        return sale_outcome.proceeds_float, paid_float

    def _rebalance_if_due(
        self,
        month_index_int: int,
        month_date: date,
    ) -> None:
        """Rebalance when the configured trigger fires.

        Brief:
            Dispatches to full liquidation or partial trades and
            records an audit entry for the executed trade.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            None: Holdings are realigned in place.

        Warning:
            Rebalancing realizes gains and therefore triggers tax
            unless it is funded from outside the portfolio.
        """
        trigger_reason_str = self._resolve_trigger_reason_str(
            month_index_int
        )
        if not trigger_reason_str:
            return
        values_before_dict = self._build_value_dict(month_index_int)
        if (
            self._settings.rebalance.method_str
            == REBALANCE_METHOD_FULL_STR
        ):
            tax_amount_float = self._rebalance_by_full_liquidation(
                month_index_int, month_date
            )
        else:
            tax_amount_float = self._rebalance_by_partial_trades(
                month_index_int, month_date
            )
        self._record_rebalance_event(
            month_index_int,
            month_date,
            values_before_dict,
            tax_amount_float,
            trigger_reason_str,
        )

    def _resolve_trigger_reason_str(
        self,
        month_index_int: int,
    ) -> str:
        """Decide whether and why a rebalance runs this month.

        Brief:
            Combines the calendar interval with the drift band
            according to the configured trigger mode.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            str: Trigger reason, or an empty string for no trade.

        Warning:
            An event cap of zero means unlimited rebalances. A month
            named explicitly fires whatever the trigger mode says,
            because the user asked for it by hand.
        """
        rebalance_settings = self._settings.rebalance
        if not rebalance_settings.is_enabled_bool:
            return ""
        maximum_events_int = int(rebalance_settings.maximum_events_int)
        if 0 < maximum_events_int <= len(self._rebalance_events_list):
            return ""
        if self._calculate_total_value_float(month_index_int) <= (
            MONEY_TOLERANCE_FLOAT
        ):
            return ""
        if int(month_index_int) in {
            int(named_month_int)
            for named_month_int in (
                rebalance_settings.rebalance_month_index_tuple
            )
        }:
            return REBALANCE_TRIGGER_DATED_STR
        return self._match_trigger_mode_str(
            rebalance_settings.trigger_str,
            self._is_calendar_due_bool(month_index_int),
            self._is_band_breached_bool(month_index_int),
        )

    @staticmethod
    def _match_trigger_mode_str(
        trigger_str: str,
        is_calendar_due_bool: bool,
        is_band_breached_bool: bool,
    ) -> str:
        """Combine the calendar and band signals by trigger mode.

        Brief:
            Pure decision table, kept separate so it can be tested
            without running a simulation.

        Arguments:
            trigger_str (str): Configured trigger mode.
            is_calendar_due_bool (bool): Interval has elapsed.
            is_band_breached_bool (bool): A fund is out of band.

        Returns:
            str: Trigger reason, or an empty string for no trade.

        Warning:
            Unknown trigger modes fall back to calendar behaviour.
        """
        if trigger_str == REBALANCE_TRIGGER_BAND_STR:
            return (
                REBALANCE_TRIGGER_BAND_STR
                if is_band_breached_bool
                else ""
            )
        if trigger_str == REBALANCE_TRIGGER_BOTH_STR:
            return (
                REBALANCE_TRIGGER_BOTH_STR
                if (is_calendar_due_bool and is_band_breached_bool)
                else ""
            )
        return (
            REBALANCE_TRIGGER_CALENDAR_STR
            if is_calendar_due_bool
            else ""
        )

    def _is_calendar_due_bool(self, month_index_int: int) -> bool:
        """Check the fixed-interval part of the trigger.

        Brief:
            Counts months from the start of the portfolio, firing
            on the last month of every interval.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            bool: True when the interval has elapsed.

        Warning:
            A non-positive interval never fires.
        """
        interval_months_int = int(
            self._settings.rebalance.interval_months_int
        )
        if interval_months_int <= 0:
            return False
        return (month_index_int + 1) % interval_months_int == 0

    def _is_band_breached_bool(self, month_index_int: int) -> bool:
        """Check whether any fund has drifted past its band.

        Brief:
            Measures the largest absolute gap between an actual
            weight and its target weight in percentage points.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            bool: True when at least one fund is outside the band.

        Warning:
            A non-positive band width never fires.
        """
        band_width_float = float(
            self._settings.rebalance.drift_band_percent_float
        )
        if band_width_float <= 0.0:
            return False
        actual_weight_dict = calculate_weight_dict(
            self._build_value_dict(month_index_int)
        )
        for holdings in self._holdings_list:
            fund_name_str = holdings.fund_configuration.name_str
            drift_float = abs(
                actual_weight_dict[fund_name_str]
                - self._target_weight_float(holdings)
            )
            if drift_float >= band_width_float:
                return True
        return False

    def _rebalance_by_full_liquidation(
        self,
        month_index_int: int,
        month_date: date,
    ) -> float:
        """Sell everything and rebuy exactly at target weights.

        Brief:
            Guarantees an exact split at the cost of realizing the
            entire unrealized gain of the portfolio.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            float: Gross tax realized by the liquidation.

        Warning:
            This is the most tax-expensive rebalancing method.
        """
        cash_float = 0.0
        gross_tax_float = 0.0
        for holdings in self._holdings_list:
            sale_outcome = holdings.sell_for_proceeds(
                holdings.calculate_value_float(month_index_int),
                month_index_int,
                month_date,
            )
            cash_float += (
                sale_outcome.proceeds_float
                - sale_outcome.charges_float
            )
            gross_tax_float += sale_outcome.tax_amount_float
        net_cash_float = max(
            0.0,
            cash_float - self._chargeable_tax_float(gross_tax_float),
        )
        for holdings in self._holdings_list:
            holdings.add_internal_purchase(
                net_cash_float
                * self._target_weight_float(holdings)
                / PERCENT_TOTAL_FLOAT,
                month_index_int,
            )
        return gross_tax_float

    def _rebalance_by_partial_trades(
        self,
        month_index_int: int,
        month_date: date,
    ) -> float:
        """Trim overweight funds and top up underweight funds.

        Brief:
            Realizes far less gain than full liquidation because
            only the drift above target is sold.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            float: Gross tax realized by the trimming trades.

        Warning:
            Tax funded from the portfolio shrinks the cash pool, so
            the final split can stay slightly under target.
        """
        desired_value_dict = self._build_desired_value_dict(
            month_index_int
        )
        gross_tax_float, net_cash_float = self._sell_overweight_funds(
            desired_value_dict, month_index_int, month_date
        )
        shortfall_dict = self._build_shortfall_dict(
            desired_value_dict, month_index_int
        )
        shortfall_total_float = sum(shortfall_dict.values())
        if net_cash_float <= 0.0 or shortfall_total_float <= 0.0:
            return gross_tax_float
        for holdings in self._holdings_list:
            fund_name_str = holdings.fund_configuration.name_str
            if fund_name_str not in shortfall_dict:
                continue
            holdings.add_internal_purchase(
                net_cash_float
                * shortfall_dict[fund_name_str]
                / shortfall_total_float,
                month_index_int,
            )
        return gross_tax_float

    def _build_desired_value_dict(
        self,
        month_index_int: int,
    ) -> dict[str, float]:
        """Compute the rupee value each fund should hold.

        Brief:
            Applies the resolved target weights to the current
            portfolio value.

        Arguments:
            month_index_int (int): Month index being simulated.

        Returns:
            Dict[str, float]: Fund name to desired value mapping.

        Warning:
            Based on the value before any rebalancing trade.
        """
        total_value_float = self._calculate_total_value_float(
            month_index_int
        )
        return {
            holdings.fund_configuration.name_str: (
                total_value_float
                * self._target_weight_float(holdings)
                / PERCENT_TOTAL_FLOAT
            )
            for holdings in self._holdings_list
        }

    def _sell_overweight_funds(
        self,
        desired_value_dict: dict[str, float],
        month_index_int: int,
        month_date: date,
    ) -> tuple[float, float]:
        """Sell the excess of every fund above its target value.

        Brief:
            Collects the proceeds into a single cash pool net of
            the tax that the sales triggered.

        Arguments:
            desired_value_dict (Dict[str, float]): Target values.
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.

        Returns:
            Tuple[float, float]: Gross tax realized and the cash
                available to top up underweight funds.

        Warning:
            Cash is zero when tax exceeds the raised proceeds.
        """
        cash_float = 0.0
        gross_tax_float = 0.0
        for holdings in self._holdings_list:
            fund_name_str = holdings.fund_configuration.name_str
            excess_float = (
                holdings.calculate_value_float(month_index_int)
                - desired_value_dict[fund_name_str]
            )
            if excess_float <= RATIO_TOLERANCE_FLOAT:
                continue
            sale_outcome = holdings.sell_for_proceeds(
                excess_float, month_index_int, month_date
            )
            cash_float += (
                sale_outcome.proceeds_float
                - sale_outcome.charges_float
            )
            gross_tax_float += sale_outcome.tax_amount_float
        net_cash_float = max(
            0.0,
            cash_float - self._chargeable_tax_float(gross_tax_float),
        )
        return gross_tax_float, net_cash_float

    def _build_shortfall_dict(
        self,
        desired_value_dict: dict[str, float],
        month_index_int: int,
    ) -> dict[str, float]:
        """Measure how far each fund still sits below target.

        Brief:
            Evaluated after the overweight sales so the shortfalls
            reflect the post-trade balances.

        Arguments:
            desired_value_dict (Dict[str, float]): Target values.
            month_index_int (int): Month index being simulated.

        Returns:
            Dict[str, float]: Fund name to shortfall mapping.

        Warning:
            Funds at or above target are omitted from the mapping.
        """
        shortfall_dict: dict[str, float] = {}
        for holdings in self._holdings_list:
            fund_name_str = holdings.fund_configuration.name_str
            shortfall_float = (
                desired_value_dict[fund_name_str]
                - holdings.calculate_value_float(month_index_int)
            )
            if shortfall_float > RATIO_TOLERANCE_FLOAT:
                shortfall_dict[fund_name_str] = shortfall_float
        return shortfall_dict

    def _chargeable_tax_float(self, tax_amount_float: float) -> float:
        """Apply the tax funding choice to a realized tax amount.

        Brief:
            Tax funded from outside the portfolio is still owed and
            still reported, but it does not shrink the corpus.

        Arguments:
            tax_amount_float (float): Tax the sale accrued.

        Returns:
            float: Tax deducted from the rebalancing cash pool.

        Warning:
            Funding from outside does not make the tax disappear.
        """
        if (
            self._settings.rebalance.tax_funding_str
            == TAX_FUNDING_OUTSIDE_STR
        ):
            return 0.0
        return float(tax_amount_float)

    def _target_weight_float(self, holdings: FundHoldings) -> float:
        """Look up the target weight of one fund.

        Brief:
            Missing funds fall back to a zero weight so they are
            never topped up by mistake.

        Arguments:
            holdings (FundHoldings): Holding being weighted.

        Returns:
            float: Target weight of that fund in percent.

        Warning:
            Weights are zero for every fund when no feature of the
            run consumes target weights.
        """
        return float(
            self._target_weight_dict.get(
                holdings.fund_configuration.name_str, 0.0
            )
        )

    def _build_value_dict(
        self,
        month_index_int: int,
    ) -> dict[str, float]:
        """Value every fund at the end of a given month.

        Brief:
            Shared by withdrawal, steering and rebalancing.

        Arguments:
            month_index_int (int): Month index being valued.

        Returns:
            Dict[str, float]: Fund name to market value mapping.

        Warning:
            Duplicate fund names overwrite each other.
        """
        return {
            holdings.fund_configuration.name_str: (
                holdings.calculate_value_float(month_index_int)
            )
            for holdings in self._holdings_list
        }

    def _calculate_total_value_float(
        self,
        month_index_int: int,
    ) -> float:
        """Add up the market value of every fund.

        Brief:
            Convenience wrapper over the per-fund value mapping.

        Arguments:
            month_index_int (int): Month index being valued.

        Returns:
            float: Total portfolio value for that month.

        Warning:
            Recomputes every lot, so avoid repeated calls in tight
            inner loops.
        """
        return sum(self._build_value_dict(month_index_int).values())

    def _record_rebalance_event(
        self,
        month_index_int: int,
        month_date: date,
        values_before_dict: dict[str, float],
        tax_amount_float: float,
        trigger_reason_str: str,
    ) -> None:
        """Store the before and after picture of one rebalance.

        Brief:
            The ledger proves that an exact rebalance really landed
            on the requested weights and shows what it cost.

        Arguments:
            month_index_int (int): Month index being simulated.
            month_date (date): Calendar month being simulated.
            values_before_dict (Dict[str, float]): Pre-trade values.
            tax_amount_float (float): Tax the trade realized.
            trigger_reason_str (str): What fired the rebalance.

        Returns:
            None: One event is appended to the ledger.

        Warning:
            Values are captured after the withdrawal of the month.
        """
        values_after_dict = self._build_value_dict(month_index_int)
        self._rebalance_events_list.append(
            RebalanceEvent(
                month_date=month_date,
                value_before_float=sum(values_before_dict.values()),
                value_after_float=sum(values_after_dict.values()),
                tax_amount_float=tax_amount_float,
                weights_before_dict=calculate_weight_dict(
                    values_before_dict
                ),
                weights_after_dict=calculate_weight_dict(
                    values_after_dict
                ),
                trigger_reason_str=trigger_reason_str,
            )
        )

    def _build_fund_state_list(
        self,
        month_index_int: int,
    ) -> list[FundMonthlyState]:
        """Capture the per-fund state of the closing month.

        Brief:
            Monthly flows are derived as deltas of the cumulative
            counters, which keeps the holdings class simple.

        Arguments:
            month_index_int (int): Month index being recorded.

        Returns:
            List[FundMonthlyState]: One state record per fund.

        Warning:
            Must be called exactly once per simulated month, in
            order, because it advances the delta baseline.
        """
        return [
            self._build_single_fund_state(holdings, month_index_int)
            for holdings in self._holdings_list
        ]

    def _build_single_fund_state(
        self,
        holdings: FundHoldings,
        month_index_int: int,
    ) -> FundMonthlyState:
        """Capture one fund's closing state and monthly flows.

        Brief:
            Flows are deltas of the cumulative counters.

        Arguments:
            holdings (FundHoldings): Fund being captured.
            month_index_int (int): Month index being recorded.

        Returns:
            FundMonthlyState: Closing state of that fund.

        Warning:
            Advances the delta baseline; call once a month.
        """
        fund_name_str = holdings.fund_configuration.name_str
        previous_dict = self._previous_totals_dict.get(
            fund_name_str, _build_empty_totals_dict()
        )
        current_dict = _read_totals_dict(holdings)
        self._previous_totals_dict[fund_name_str] = current_dict
        return FundMonthlyState(
            name_str=fund_name_str,
            value_float=holdings.calculate_value_float(
                month_index_int
            ),
            cost_basis_float=holdings.calculate_cost_basis_float(),
            contributed_float=(
                current_dict["invested"] - previous_dict["invested"]
            ),
            withdrawn_float=(
                current_dict["withdrawn"]
                - previous_dict["withdrawn"]
            ),
            tax_float=(
                current_dict["tax"] - previous_dict["tax"]
            ),
            charges_float=(
                current_dict["charges"] - previous_dict["charges"]
            ),
        )

    def _record_snapshot(
        self,
        month_index_int: int,
        month_date: date,
        contributed_float: float,
        withdrawal_tuple: tuple[float, float, float],
    ) -> None:
        """Store the closing state of one simulated month.

        Brief:
            Cumulative figures come from the fund accumulators.

        Arguments:
            month_index_int (int): Month being recorded.
            month_date (date): Calendar month being recorded.
            contributed_float (float): Contributions this month.
            withdrawal_tuple (tuple): Amount asked for, proceeds
                raised and money paid to the investor.

        Returns:
            None: One snapshot is appended.

        Warning:
            Recorded after every cash flow of the month.
        """
        self._snapshots_list.append(
            self._build_month_snapshot(
                self._build_fund_state_list(month_index_int),
                month_date,
                contributed_float,
                withdrawal_tuple,
            )
        )

    def _build_month_snapshot(
        self,
        fund_state_list: list[FundMonthlyState],
        month_date: date,
        contributed_float: float,
        withdrawal_tuple: tuple[float, float, float],
    ) -> MonthlySnapshot:
        """Assemble the immutable record of one closing month.

        Brief:
            Totals are summed from the fund states, so they can
            never disagree with the per-fund table.

        Arguments:
            fund_state_list (List[FundMonthlyState]): Fund states.
            month_date (date): Month being recorded.
            contributed_float (float): Contributions this month.
            withdrawal_tuple (tuple): Asked for, raised, and paid.

        Returns:
            MonthlySnapshot: Closing record.

        Warning:
            A shortfall means the corpus could not raise the money,
            never that the fund house charged for it.
        """
        requested_float, proceeds_float, paid_float = withdrawal_tuple
        totals_dict = self._build_cumulative_totals_dict()
        return MonthlySnapshot(
            month_date=month_date,
            portfolio_value_float=sum(
                state.value_float for state in fund_state_list
            ),
            invested_amount_float=totals_dict["invested"],
            withdrawn_amount_float=totals_dict["withdrawn"],
            tax_paid_float=totals_dict["tax"],
            monthly_sip_float=contributed_float,
            monthly_withdrawal_float=paid_float,
            requested_withdrawal_float=requested_float,
            unmet_withdrawal_float=max(
                0.0, requested_float - proceeds_float
            ),
            monthly_tax_float=sum(
                state.tax_float for state in fund_state_list
            ),
            monthly_charges_float=sum(
                state.charges_float for state in fund_state_list
            ),
            fund_states_list=fund_state_list,
        )


    def _build_cumulative_totals_dict(self) -> dict[str, float]:
        """Total the cumulative counters across every fund.

        Brief:
            Guarantees the portfolio totals always reconcile with
            the per-fund summary table.

        Arguments:
            None.

        Returns:
            Dict[str, float]: Invested, withdrawn and tax totals.

        Warning:
            Recomputed on every recorded month.
        """
        return {
            "invested": sum(
                holdings.contributed_amount_float
                for holdings in self._holdings_list
            ),
            "withdrawn": sum(
                holdings.withdrawn_amount_float
                for holdings in self._holdings_list
            ),
            "tax": sum(
                holdings.tax_paid_amount_float
                for holdings in self._holdings_list
            ),
        }

    def _build_fund_outcomes_list(self) -> list[FundOutcome]:
        """Summarise every fund at the end of the horizon.

        Brief:
            Optionally prices the tax of a full redemption on the
            last day so the corpus can be reported post tax.

        Arguments:
            None.

        Returns:
            List[FundOutcome]: One summary record per fund.

        Warning:
            Returns empty summaries when the horizon is zero.
        """
        final_month_index_int = max(
            0, self._settings.total_months_int - 1
        )
        final_date = (
            self._month_dates_list[final_month_index_int]
            if self._month_dates_list
            else self._settings.portfolio_start_date
        )
        shared_ledger_tuple = _build_shared_dry_run_tuple_from(
            self._holdings_list
        )
        return [
            holdings.build_fund_outcome(
                final_month_index_int,
                *self._estimate_exit_cost_tuple(
                    holdings,
                    final_month_index_int,
                    final_date,
                    shared_ledger_tuple,
                ),
            )
            for holdings in self._holdings_list
        ]

    def _estimate_exit_cost_tuple(
        self,
        holdings: FundHoldings,
        final_month_index_int: int,
        final_date: date,
        shared_ledger_tuple: tuple,
    ) -> tuple[float, float]:
        """Price the tax and charges of exiting one fund.

        Brief:
            Returns a pair of zeros when the exit-cost switch is
            off, so the headline corpus stays gross.

        Arguments:
            holdings (FundHoldings): Fund being priced.
            final_month_index_int (int): Last simulated month.
            final_date (date): Date of the notional redemption.
            shared_ledger_tuple (tuple): Throwaway ledgers shared
                across every fund of this estimate.

        Returns:
            Tuple[float, float]: Exit tax and exit charges.

        Warning:
            Consumes the shared throwaway exemption, so calling
            this out of fund order changes which fund shelters.
        """
        if not self._settings.tax.apply_final_liquidation_tax_bool:
            return 0.0, 0.0
        return (
            holdings.estimate_liquidation_tax_float(
                final_month_index_int,
                final_date,
                *shared_ledger_tuple,
            ),
            holdings.estimate_liquidation_charges_float(
                final_month_index_int
            ),
        )
