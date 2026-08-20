"""FIFO lot book that values, buys and sells units of one fund."""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.constants import (
    GRANDFATHER_VALUATION_MONTH_INT,
    GRANDFATHER_VALUATION_YEAR_INT,
    MONEY_TOLERANCE_FLOAT,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    FundOutcome,
    InvestmentLot,
    SaleOutcome,
)
from investment_journey_simulator.returns import calculate_growth_factor_float
from investment_journey_simulator.taxation import (
    CapitalGainsTaxPolicy,
    calculate_exit_charges_float,
)
from investment_journey_simulator.time_utils import (
    count_months_between_dates_int,
)


def _build_cumulative_growth_list(
    monthly_rate_path_list: list[float] | None,
) -> list[float] | None:
    """Turn a monthly return path into a cumulative index.

    Brief:
        Element j holds the growth from the start of the run to
        the close of month j minus one, so the growth of any span
        is one element divided by another. Element zero is one,
        representing the instant before the run begins.

    Arguments:
        monthly_rate_path_list (Optional[List[float]]): Realised
            monthly rates, one per simulated month.

    Returns:
        Optional[List[float]]: Cumulative index, or None when no
            path was supplied and the constant rate applies.

    Warning:
        A path shorter than the horizon makes later months read
        past the end of the index, so callers must supply one
        rate per simulated month.
    """
    if not monthly_rate_path_list:
        return None
    cumulative_list = [1.0]
    for monthly_rate_float in monthly_rate_path_list:
        cumulative_list.append(
            cumulative_list[-1] * (1.0 + float(monthly_rate_float))
        )
    return cumulative_list


def _derive_grandfather_month_index_int(
    portfolio_start_date: date | None,
) -> int | None:
    """Locate January 2018 on this run's month grid.

    Brief:
        The deemed cost is the fair market value at the close of
        January 2018, so grandfathering needs that month's index.

    Arguments:
        portfolio_start_date (Optional[date]): Month zero.

    Returns:
        Optional[int]: Month index of January 2018, or None when
            the run has no start date to measure from.

    Warning:
        A negative index means the run begins after the cutoff, in
        which case no lot can ever qualify.
    """
    if portfolio_start_date is None:
        return None
    return count_months_between_dates_int(
        portfolio_start_date,
        date(
            GRANDFATHER_VALUATION_YEAR_INT,
            GRANDFATHER_VALUATION_MONTH_INT,
            1,
        ),
    )


class FundHoldings:
    """Lot-wise holding of one fund with cash-flow accumulators."""

    def __init__(
        self,
        fund_configuration: FundConfiguration,
        tax_policy: CapitalGainsTaxPolicy,
        portfolio_start_date: date | None = None,
        apply_grandfathering_bool: bool = False,
    ) -> None:
        """Create an empty holding for one configured fund.

        Brief:
            Stores purchased lots in purchase order so that sales
            can consume them first in, first out.

        Arguments:
            fund_configuration (FundConfiguration): Fund rules.
            tax_policy (CapitalGainsTaxPolicy): Tax calculator.
            portfolio_start_date (Optional[date]): Month zero of
                the run, needed to date lots for grandfathering.
            apply_grandfathering_bool (bool): Apply the deemed
                cost rule to units bought before 1 February 2018.

        Returns:
            None: An empty holding is initialised.

        Warning:
            Grandfathering is skipped entirely without a start
            date, because a lot cannot be dated without one.
        """
        self.fund_configuration = fund_configuration
        self._tax_policy = tax_policy
        self._monthly_rate_float = fund_configuration.monthly_rate_float
        self._cumulative_growth_list = _build_cumulative_growth_list(
            fund_configuration.monthly_rate_path_list
        )
        self._grandfather_month_index_int = (
            _derive_grandfather_month_index_int(portfolio_start_date)
            if apply_grandfathering_bool
            else None
        )
        self._lots_list: list[InvestmentLot] = []
        self._charges_this_sale_float = 0.0
        self.contributed_amount_float = 0.0
        self.withdrawn_amount_float = 0.0
        self.tax_paid_amount_float = 0.0
        self.short_term_gain_amount_float = 0.0
        self.long_term_gain_amount_float = 0.0
        self.realized_loss_amount_float = 0.0
        self.charges_paid_amount_float = 0.0

    def _growth_factor_float(
        self,
        month_index_int: int,
        months_held_int: int,
    ) -> float:
        """Growth of one holding period on this fund's curve.

        Brief:
            Without a return path the fund compounds at a single
            constant rate and the answer depends only on how long
            the money was held. With a path it also depends on
            *when* it was held, which is what makes a stochastic
            run show sequence-of-returns risk.

        Arguments:
            month_index_int (int): Month the span ends in.
            months_held_int (int): Length of the span in months.

        Returns:
            float: Multiplier over that span.

        Warning:
            The constant-rate branch delegates unchanged, so a
            deterministic run is bit-identical to one computed
            before return paths existed.
        """
        if self._cumulative_growth_list is None:
            return calculate_growth_factor_float(
                self._monthly_rate_float, months_held_int
            )
        if int(months_held_int) <= 0:
            return 1.0
        end_index_int = min(
            int(month_index_int) + 1,
            len(self._cumulative_growth_list) - 1,
        )
        start_index_int = max(
            0, end_index_int - int(months_held_int)
        )
        return (
            self._cumulative_growth_list[end_index_int]
            / self._cumulative_growth_list[start_index_int]
        )

    def add_contribution(
        self,
        amount_float: float,
        month_index_int: int,
        bought_at_month_start_bool: bool,
    ) -> None:
        """Record an external contribution as a new lot.

        Brief:
            Contributions increase invested principal, unlike the
            internal purchases created while rebalancing.

        Arguments:
            amount_float (float): Rupees contributed this month.
            month_index_int (int): Month index of the purchase.
            bought_at_month_start_bool (bool): Start-of-month flag.

        Returns:
            None: The lot book and accumulators are updated.

        Warning:
            Non-positive amounts are ignored silently.
        """
        if float(amount_float) <= 0.0:
            return
        self._lots_list.append(
            InvestmentLot(
                principal_float=float(amount_float),
                purchase_month_index_int=int(month_index_int),
                bought_at_month_start_bool=bool(
                    bought_at_month_start_bool
                ),
            )
        )
        self.contributed_amount_float += float(amount_float)

    def add_internal_purchase(
        self,
        amount_float: float,
        month_index_int: int,
    ) -> None:
        """Record a rebalancing purchase without new principal.

        Brief:
            Money moved between funds must not inflate the invested
            principal shown in the summary tiles.

        Arguments:
            amount_float (float): Rupees bought this month.
            month_index_int (int): Month index of the purchase.

        Returns:
            None: Only the lot book is updated.

        Warning:
            The new lot restarts the holding period, so frequent
            rebalancing pushes gains toward short term treatment.
        """
        if float(amount_float) <= MONEY_TOLERANCE_FLOAT:
            return
        self._lots_list.append(
            InvestmentLot(
                principal_float=float(amount_float),
                purchase_month_index_int=int(month_index_int),
                bought_at_month_start_bool=False,
            )
        )

    def calculate_value_float(self, month_index_int: int) -> float:
        """Value every open lot at the end of a given month.

        Brief:
            Each lot compounds independently from its own purchase
            month at the fund's effective monthly rate.

        Arguments:
            month_index_int (int): Month index being valued.

        Returns:
            float: Total market value of the holding.

        Warning:
            Growth is deterministic; volatility is not modelled.
        """
        return sum(
            self._calculate_lot_value_float(lot, month_index_int)
            for lot in self._lots_list
        )

    def calculate_cost_basis_float(self) -> float:
        """Total principal still sitting in unsold lots.

        Brief:
            Subtracting this from the market value gives the gain
            that has not yet been realized or taxed.

        Arguments:
            None.

        Returns:
            float: Cost basis of the remaining holding.

        Warning:
            Internal rebalancing purchases raise the cost basis
            without raising the external principal invested.
        """
        return sum(
            lot.principal_float for lot in self._lots_list
        )

    def build_shared_dry_run_ledgers_tuple(self) -> tuple:
        """Copy this fund's ledgers for a shared exit estimate.

        Brief:
            Thin pass-through so the engine can build the shared
            pair without reaching into the tax policy itself.

        Arguments:
            None.

        Returns:
            tuple: Throwaway exemption and loss ledgers.

        Warning:
            Any fund of the run may build the pair, because all of
            them share the same underlying ledgers.
        """
        return self._tax_policy.build_shared_dry_run_ledgers_tuple()

    def estimate_liquidation_tax_float(
        self,
        month_index_int: int,
        sale_date: date,
        shared_exemption_ledger=None,
        shared_loss_ledger=None,
    ) -> float:
        """Price the tax of selling this whole fund right now.

        Brief:
            Walks the same FIFO logic as a real sale but against a
            copied tax policy, so nothing is mutated or consumed.

        Arguments:
            month_index_int (int): Month index of the valuation.
            sale_date (date): Calendar date of the hypothetical
                redemption.
            shared_exemption_ledger (Optional[ExemptionLedger]):
                Throwaway ledger shared with the other funds of
                the same estimate.
            shared_loss_ledger (Optional[LossLedger]): Throwaway
                loss pools shared with the other funds.

        Returns:
            float: Tax that a full redemption would trigger.

        Warning:
            Without the shared ledgers each fund claims the whole
            per-taxpayer exemption for itself, which understates
            the portfolio's tax.
        """
        dry_run_policy = self._tax_policy.build_dry_run_copy(
            shared_exemption_ledger, shared_loss_ledger
        )
        return sum(
            self._estimate_lot_tax_float(
                lot, month_index_int, sale_date, dry_run_policy
            )
            for lot in self._lots_list
        )

    def _estimate_lot_tax_float(
        self,
        lot: InvestmentLot,
        month_index_int: int,
        sale_date: date,
        dry_run_policy: CapitalGainsTaxPolicy,
    ) -> float:
        """Price the tax of redeeming one lot in full.

        Brief:
            Shares the grandfathering resolver with a real sale so
            the estimate can never drift from what actually
            happens when the units are sold.

        Arguments:
            lot (InvestmentLot): Lot being valued.
            month_index_int (int): Month index of the valuation.
            sale_date (date): Date of the hypothetical redemption.
            dry_run_policy (CapitalGainsTaxPolicy): Copied policy.

        Returns:
            float: Tax the lot would trigger.

        Warning:
            Consumes exemption on the copied policy, which is what
            makes the per-lot totals add up correctly.
        """
        lot_value_float = self._calculate_lot_value_float(
            lot, month_index_int
        )
        if lot_value_float <= MONEY_TOLERANCE_FLOAT:
            return 0.0
        months_held_int = max(
            0, lot.count_months_held_int(month_index_int)
        )
        growth_factor_float = self._growth_factor_float(
            month_index_int, months_held_int
        )
        return dry_run_policy.calculate_tax_breakdown(
            lot_value_float
            - self._resolve_taxable_cost_float(
                lot_value_float,
                growth_factor_float,
                months_held_int,
                lot,
            ),
            months_held_int,
            sale_date,
        ).tax_amount_float

    def estimate_liquidation_charges_float(
        self,
        month_index_int: int,
    ) -> float:
        """Price the exit load and transaction tax of a full exit.

        Brief:
            Charges depend on how long each lot has been held, so
            they are summed lot by lot like the tax estimate.

        Arguments:
            month_index_int (int): Month index of the valuation.

        Returns:
            float: Charges a full redemption would trigger.

        Warning:
            An estimate only; nothing is booked to the run.
        """
        estimated_charges_float = 0.0
        for lot in self._lots_list:
            lot_value_float = self._calculate_lot_value_float(
                lot, month_index_int
            )
            if lot_value_float <= MONEY_TOLERANCE_FLOAT:
                continue
            estimated_charges_float += calculate_exit_charges_float(
                self.fund_configuration,
                lot_value_float,
                max(0, lot.count_months_held_int(month_index_int)),
            )
        return estimated_charges_float

    def sell_for_proceeds(
        self,
        requested_proceeds_float: float,
        month_index_int: int,
        sale_date: date,
    ) -> SaleOutcome:
        """Sell lots first in, first out to raise target proceeds.

        Brief:
            Walks the lot book in purchase order and taxes the
            gain of each consumed slice.

        Arguments:
            requested_proceeds_float (float): Rupees to raise.
            month_index_int (int): Month index of the sale.
            sale_date (date): Calendar date of the sale.

        Returns:
            SaleOutcome: Proceeds, tax and charges.

        Warning:
            Proceeds are capped by the holding value.
        """
        if float(requested_proceeds_float) <= 0.0:
            return SaleOutcome(0.0, 0.0)
        self._charges_this_sale_float = 0.0
        remaining_request_float = float(requested_proceeds_float)
        total_proceeds_float = 0.0
        total_tax_float = 0.0
        surviving_lots_list: list[InvestmentLot] = []
        for lot in self._lots_list:
            if remaining_request_float <= MONEY_TOLERANCE_FLOAT:
                surviving_lots_list.append(lot)
                continue
            taken_float, tax_float, leftover_lot = self._sell_one_lot(
                lot, remaining_request_float, month_index_int,
                sale_date,
            )
            remaining_request_float -= taken_float
            total_proceeds_float += taken_float
            total_tax_float += tax_float
            if leftover_lot is not None:
                surviving_lots_list.append(leftover_lot)
        self._lots_list = surviving_lots_list
        self.tax_paid_amount_float += total_tax_float
        return SaleOutcome(
            total_proceeds_float,
            total_tax_float,
            self._charges_this_sale_float,
        )

    def register_withdrawal(self, amount_float: float) -> None:
        """Book sold proceeds as money leaving the portfolio.

        Brief:
            Separates investor withdrawals from internal selling
            done purely to rebalance between funds.

        Arguments:
            amount_float (float): Money reaching the investor.

        Returns:
            None: The withdrawal accumulator is updated.

        Warning:
            Net of the exit load and transaction tax, which the
            fund house deducts at source, but gross of capital
            gains tax, which the investor settles at filing time.
        """
        self.withdrawn_amount_float += max(0.0, float(amount_float))

    def build_fund_outcome(
        self,
        month_index_int: int,
        final_liquidation_tax_float: float = 0.0,
        final_liquidation_charges_float: float = 0.0,
    ) -> FundOutcome:
        """Summarise this fund at the end of the horizon.

        Brief:
            Packages the accumulators, the closing value and the
            cost basis into the record used by report tables.

        Arguments:
            month_index_int (int): Final simulated month index.
            final_liquidation_tax_float (float): Tax a full exit
                on the last day would cost.

        Returns:
            FundOutcome: End-of-horizon summary of this fund.

        Warning:
            Call only after the simulation loop has finished.
        """
        return FundOutcome(
            cost_basis_float=self.calculate_cost_basis_float(),
            final_liquidation_tax_float=final_liquidation_tax_float,
            final_liquidation_charges_float=(
                final_liquidation_charges_float
            ),
            realized_loss_float=self.realized_loss_amount_float,
            charges_paid_float=self.charges_paid_amount_float,
            name_str=self.fund_configuration.name_str,
            preset_str=self.fund_configuration.preset_str,
            start_date=self.fund_configuration.start_date,
            net_return_percent_float=float(
                self.fund_configuration.net_return_percent_float
            ),
            invested_amount_float=self.contributed_amount_float,
            withdrawn_amount_float=self.withdrawn_amount_float,
            ending_value_float=self.calculate_value_float(
                month_index_int
            ),
            tax_paid_float=self.tax_paid_amount_float,
            short_term_gain_float=self.short_term_gain_amount_float,
            long_term_gain_float=self.long_term_gain_amount_float,
        )

    def _calculate_lot_value_float(
        self,
        lot: InvestmentLot,
        month_index_int: int,
    ) -> float:
        """Value a single lot at the end of a given month.

        Brief:
            Multiplies the lot principal by its growth factor.

        Arguments:
            lot (InvestmentLot): Lot being valued.
            month_index_int (int): Month index being valued.

        Returns:
            float: Market value of that lot.

        Warning:
            Lots younger than one month return their principal.
        """
        months_held_int = lot.count_months_held_int(month_index_int)
        growth_factor_float = self._growth_factor_float(
            month_index_int, months_held_int
        )
        return lot.principal_float * growth_factor_float

    def _sell_one_lot(
        self,
        lot: InvestmentLot,
        remaining_request_float: float,
        month_index_int: int,
        sale_date: date,
    ) -> tuple[float, float, InvestmentLot | None]:
        """Consume as much of one lot as the request needs.

        Brief:
            Splits the lot into a sold slice and a remainder,
            taxing the gain inside the sold slice only.
        Arguments:
            lot (InvestmentLot): Oldest unsold lot.
            remaining_request_float (float): Proceeds needed.
            month_index_int (int): Month index of the sale.
            sale_date (date): Calendar date of the sale.

        Returns:
            Tuple[float, float, Optional[InvestmentLot]]: Proceeds,
                tax accrued and the lot remainder.

        Warning:
            Fully consumed lots return a None remainder.
        """
        lot_value_float = self._calculate_lot_value_float(
            lot, month_index_int
        )
        if lot_value_float <= MONEY_TOLERANCE_FLOAT:
            return 0.0, 0.0, None
        taken_float = min(lot_value_float, remaining_request_float)
        months_held_int = max(
            0, lot.count_months_held_int(month_index_int)
        )
        growth_factor_float = self._growth_factor_float(
            month_index_int, months_held_int
        )
        tax_amount_float = self._book_sale_costs_float(
            taken_float, growth_factor_float, months_held_int,
            sale_date, lot,
        )
        leftover_lot = self._build_leftover_lot(
            lot,
            (lot_value_float - taken_float) / growth_factor_float,
        )
        return taken_float, tax_amount_float, leftover_lot

    def _book_realized_gain_float(
        self,
        gain_float: float,
        months_held_int: int,
        sale_date: date,
    ) -> float:
        """Tax a realized gain and record its classification.

        Brief:
            Keeps the short and long term gain accumulators in
            step with the tax that was charged on them.

        Arguments:
            gain_float (float): Gross realized gain of the slice.
            months_held_int (int): Months the lot was held.
            sale_date (date): Calendar date of the sale.

        Returns:
            float: Tax accrued on this gain.

        Warning:
            Mutates the gain accumulators of this holding.
        """
        breakdown = self._tax_policy.calculate_tax_breakdown(
            gain_float, months_held_int, sale_date
        )
        self.short_term_gain_amount_float += (
            breakdown.short_term_gain_float
        )
        self.long_term_gain_amount_float += (
            breakdown.long_term_gain_float
        )
        self.realized_loss_amount_float += (
            breakdown.realized_loss_float
        )
        return breakdown.tax_amount_float

    def _resolve_taxable_cost_float(
        self,
        taken_float: float,
        growth_factor_float: float,
        months_held_int: int,
        lot: InvestmentLot,
    ) -> float:
        """Apply the grandfathered deemed cost where it is due.

        Brief:
            For units acquired before 1 February 2018 the cost of
            acquisition is deemed to be the higher of the actual
            cost and the lower of the 31 January 2018 fair market
            value and the sale value. The formula can only raise
            the cost, so it can only shrink a gain.

        Arguments:
            taken_float (float): Value of the units sold.
            growth_factor_float (float): Growth of those units.
            months_held_int (int): Months the units were held.
            lot (InvestmentLot): Lot the slice came from.

        Returns:
            float: Cost of acquisition to tax the slice against.

        Warning:
            The fair market value is the simulated value on the
            valuation date, not a real quoted NAV, so it is exact
            only to the extent the assumed return actually
            happened. It never applies to a fund flagged as always
            short term, which is outside section 112A.
        """
        actual_cost_float = taken_float / growth_factor_float
        cutoff_index_int = self._grandfather_month_index_int
        if cutoff_index_int is None:
            return actual_cost_float
        if not self._is_grandfathered_bool(
            cutoff_index_int, months_held_int, lot
        ):
            return actual_cost_float
        fair_value_float = (
            actual_cost_float
            * self._growth_factor_float(
                cutoff_index_int,
                max(0, lot.count_months_held_int(cutoff_index_int)),
            )
        )
        return max(
            actual_cost_float, min(fair_value_float, taken_float)
        )

    def _is_grandfathered_bool(
        self,
        cutoff_index_int: int | None,
        months_held_int: int,
        lot: InvestmentLot,
    ) -> bool:
        """Decide whether one slice qualifies for the relief.

        Brief:
            Only long term gains on section 112A units acquired on
            or before January 2018 qualify.

        Arguments:
            cutoff_index_int (Optional[int]): January 2018 index.
            months_held_int (int): Months the units were held.
            lot (InvestmentLot): Lot the slice came from.

        Returns:
            bool: True when the deemed cost rule applies.

        Warning:
            A None cutoff means grandfathering is switched off or
            the run has no start date to measure from.
        """
        if cutoff_index_int is None:
            return False
        if self.fund_configuration.is_always_short_term_bool:
            return False
        if not self._tax_policy.is_long_term_holding_bool(
            months_held_int
        ):
            return False
        return lot.purchase_month_index_int <= cutoff_index_int

    def _book_sale_costs_float(
        self,
        taken_float: float,
        growth_factor_float: float,
        months_held_int: int,
        sale_date: date,
        lot: InvestmentLot,
    ) -> float:
        """Charge exit costs and tax on one consumed slice.

        Brief:
            Exit load and transaction tax are charges, not tax, so
            they are accumulated separately from capital gains tax.

        Arguments:
            taken_float (float): Value of the units sold.
            growth_factor_float (float): Growth of those units.
            months_held_int (int): Months the units were held.
            sale_date (date): Calendar date of the sale.
            lot (InvestmentLot): Lot the slice came from.

        Returns:
            float: Capital gains tax on this slice.

        Warning:
            Mutates the charge and gain accumulators.
        """
        charges_float = calculate_exit_charges_float(
            self.fund_configuration, taken_float, months_held_int
        )
        self.charges_paid_amount_float += charges_float
        self._charges_this_sale_float += charges_float
        return self._book_realized_gain_float(
            taken_float
            - self._resolve_taxable_cost_float(
                taken_float,
                growth_factor_float,
                months_held_int,
                lot,
            ),
            months_held_int,
            sale_date,
        )

    @staticmethod
    def _build_leftover_lot(
        lot: InvestmentLot,
        leftover_principal_float: float,
    ) -> InvestmentLot | None:
        """Rebuild the unsold remainder of a partially sold lot.

        Brief:
            The remainder keeps the original purchase month so its
            holding period is never reset by a partial sale.

        Arguments:
            lot (InvestmentLot): Lot that was partially sold.
            leftover_principal_float (float): Unsold principal.

        Returns:
            Optional[InvestmentLot]: Remainder, or None when the
                lot was fully consumed.

        Warning:
            Dust below the money tolerance is discarded.
        """
        if leftover_principal_float <= MONEY_TOLERANCE_FLOAT:
            return None
        return InvestmentLot(
            principal_float=leftover_principal_float,
            purchase_month_index_int=lot.purchase_month_index_int,
            bought_at_month_start_bool=(
                lot.bought_at_month_start_bool
            ),
        )
