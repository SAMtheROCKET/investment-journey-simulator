"""A second opinion on the tax, kept apart from the first.

`reference_simulator` deliberately has no lot book, which is what
makes it independent evidence about *value* - and also what stops
it saying anything at all about *tax*. Tax needs to know which
units were sold, when they were bought and in which financial year
the sale fell.

So this module keeps a lot book of its own, written from the rules
rather than from `taxation.py`:

  * units are consumed oldest first, and a part-sold parcel keeps
    its original purchase month, so a partial sale never restarts a
    holding period;
  * a gain is long term once the units have been held for the
    fund's threshold, and a fund outside section 112A - a specified
    debt fund - is short term however long it was held;
  * the exemption is annual and belongs to the taxpayer, so it is
    tracked per financial year, which begins in April, and shared
    across every fund when the level says so;
  * the exit load and the transaction tax are deducted at source,
    so they come out of the payout, while capital gains tax is
    accrued and settled by the investor later.

What it does not model, and what is therefore switched off in the
runs that use it: loss set-off and carry-forward, surcharge, cess,
grandfathering, and explicit return paths. Each of those is held by
its own tests; the point of this module is the machinery that
decides *which gain is taxed at which rate in which year*, which
nothing else checked.

The value arithmetic here is lot-based, like the engine's. That is
the honest position: this module is evidence about tax, and
`reference_simulator` is evidence about value. Neither is evidence
about both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from reference_simulator import (
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
    ReferenceContributions,
    ReferencePauses,
    ReferenceWithdrawals,
    build_one_off_share_dict,
    build_rate_path_list,
    build_share_dict,
    build_target_weight_dict,
    month_date_at,
)

MONEY_TOLERANCE_FLOAT: float = 1e-9
FINANCIAL_YEAR_START_MONTH_INT: int = 4
PORTFOLIO_LEVEL_STR: str = "PER_TAXPAYER"
LONG_TERM_ONLY_STR: str = "LTCG_ONLY"


def financial_year_int(sale_date: date) -> int:
    """The tax year a sale falls in, which opens in April."""
    if sale_date.month >= FINANCIAL_YEAR_START_MONTH_INT:
        return sale_date.year
    return sale_date.year - 1


@dataclass
class ReferenceLot:
    """One parcel of units bought on one month."""

    principal_float: float
    month_index_int: int
    at_month_start_bool: bool

    def months_held_int(self, month_index_int: int) -> int:
        """How long this parcel has been compounding."""
        bonus_int = 1 if self.at_month_start_bool else 0
        return (
            int(month_index_int) - self.month_index_int + bonus_int
        )


@dataclass
class ReferenceSale:
    """What one sale raised and what it cost."""

    proceeds_float: float = 0.0
    tax_float: float = 0.0
    charges_float: float = 0.0


class ReferenceExemption:
    """The annual allowance, tracked by bucket and by year."""

    def __init__(self, tax_settings) -> None:
        """Read the level once; the buckets follow from it."""
        self._settings = tax_settings
        self._consumed_dict: dict = {}

    def _bucket_str(self, fund_name_str: str) -> str:
        """Whose allowance this is: one fund's, or the person's."""
        if (
            self._settings.exemption_level_str
            == PORTFOLIO_LEVEL_STR
        ):
            return ""
        return fund_name_str

    def _limit_float(self, fund) -> float:
        """How much allowance that bucket gets in a year."""
        if (
            self._settings.exemption_level_str
            == PORTFOLIO_LEVEL_STR
        ):
            return max(
                0.0,
                float(
                    self._settings.portfolio_exemption_amount_float
                ),
            )
        return max(0.0, float(fund.exemption_amount_float))

    def shelter_float(
        self, fund, gain_float: float, sale_date: date
    ) -> float:
        """What is left of a gain once the allowance is applied."""
        limit_float = self._limit_float(fund)
        if limit_float <= 0.0 or gain_float <= 0.0:
            return max(0.0, gain_float)
        key_tuple = (
            self._bucket_str(fund.name_str),
            financial_year_int(sale_date),
            fund.exemption_scope_str,
        )
        used_float = self._consumed_dict.get(key_tuple, 0.0)
        available_float = max(0.0, limit_float - used_float)
        applied_float = min(available_float, gain_float)
        self._consumed_dict[key_tuple] = used_float + applied_float
        return gain_float - applied_float


CARRY_FORWARD_YEARS_INT: int = 8


class ReferenceLosses:
    """Realised losses, pooled by kind and by year of origin.

    Two rules decide what a loss may shelter. A short term loss
    may be set against any later gain. A long term loss may be set
    only against a long term gain - so a long term gain draws on
    the long term pool first and falls back to the short term one,
    while a short term gain may touch the short term pool alone.

    A loss also has a life: eight assessment years after the year
    it arose, and then it lapses. Pooling losses into one running
    total instead of dating them would let a loss booked in year
    one shelter a gain thirty years later.
    """

    def __init__(self) -> None:
        """Two empty pools, keyed by kind and year."""
        self._pool_dict: dict = {}

    def record(
        self,
        loss_float: float,
        is_long_term_bool: bool,
        year_int: int,
    ) -> None:
        """Book a loss against the year it was computed in."""
        if loss_float <= 0.0:
            return
        key_tuple = (
            "LONG_TERM" if is_long_term_bool else "SHORT_TERM",
            int(year_int),
        )
        self._pool_dict[key_tuple] = (
            self._pool_dict.get(key_tuple, 0.0) + loss_float
        )

    def _expire(self, year_int: int) -> None:
        """Drop anything past its carry-forward window."""
        earliest_int = int(year_int) - CARRY_FORWARD_YEARS_INT
        self._pool_dict = {
            key_tuple: amount_float
            for key_tuple, amount_float in self._pool_dict.items()
            if key_tuple[1] >= earliest_int
        }

    def _spend_bucket_float(
        self, bucket_str: str, gain_float: float
    ) -> float:
        """Spend one pool against a gain, oldest year first.

        Oldest first is both the taxpayer-favourable order and the
        one that wastes the least, because the oldest losses are
        the ones about to lapse.
        """
        year_list = sorted(
            year_int
            for pool_str, year_int in self._pool_dict
            if pool_str == bucket_str
        )
        for year_int in year_list:
            if gain_float <= 0.0:
                break
            key_tuple = (bucket_str, year_int)
            applied_float = min(
                self._pool_dict[key_tuple], gain_float
            )
            self._pool_dict[key_tuple] -= applied_float
            if self._pool_dict[key_tuple] <= 0.0:
                del self._pool_dict[key_tuple]
            gain_float -= applied_float
        return gain_float

    def offset_float(
        self,
        gain_float: float,
        is_long_term_bool: bool,
        year_int: int,
    ) -> float:
        """What is left of a gain after the pools are spent."""
        self._expire(year_int)
        remaining_float = max(0.0, gain_float)
        bucket_tuple = (
            ("LONG_TERM", "SHORT_TERM")
            if is_long_term_bool
            else ("SHORT_TERM",)
        )
        for bucket_str in bucket_tuple:
            if remaining_float <= 0.0:
                break
            remaining_float = self._spend_bucket_float(
                bucket_str, remaining_float
            )
        return remaining_float


class ReferenceFund:
    """One fund's lot book, and the tax its sales realise."""

    def __init__(
        self,
        fund,
        exemption: ReferenceExemption,
        losses: ReferenceLosses,
        tax_settings,
        total_months_int: int,
    ) -> None:
        """Bind a fund's rules to an empty book of parcels."""
        self.fund = fund
        self._exemption = exemption
        self._losses = losses
        self._tax_settings = tax_settings
        self.realised_loss_float = 0.0
        self._path_list = build_rate_path_list(
            fund, total_months_int
        )
        self._cumulative_list = [1.0]
        for rate_float in self._path_list:
            self._cumulative_list.append(
                self._cumulative_list[-1] * (1.0 + rate_float)
            )
        self._lot_list: list[ReferenceLot] = []
        self.invested_float = 0.0
        self.withdrawn_float = 0.0
        self.tax_float = 0.0
        self.charges_float = 0.0

    def _growth_float(
        self, month_index_int: int, months_held_int: int
    ) -> float:
        """The multiplier over one holding period.

        With one constant rate this depends only on how long the
        money was held. With a path it also depends on *when* -
        which is the whole point of a path, and the reason a run
        that falls early is not the same as one that falls late.
        """
        if months_held_int <= 0:
            return 1.0
        end_int = min(
            int(month_index_int) + 1, len(self._cumulative_list) - 1
        )
        start_int = max(0, end_int - int(months_held_int))
        return (
            self._cumulative_list[end_int]
            / self._cumulative_list[start_int]
        )

    def _lot_value_float(
        self, lot: ReferenceLot, month_index_int: int
    ) -> float:
        """What one parcel is worth at the close of a month."""
        return lot.principal_float * self._growth_float(
            month_index_int, lot.months_held_int(month_index_int)
        )

    def value_float(self, month_index_int: int) -> float:
        """What the whole holding is worth."""
        return sum(
            self._lot_value_float(lot, month_index_int)
            for lot in self._lot_list
        )

    def buy(
        self,
        amount_float: float,
        month_index_int: int,
        at_month_start_bool: bool,
        is_external_bool: bool = True,
    ) -> None:
        """Add a parcel, external money or a rebalancing purchase."""
        if amount_float <= (
            0.0 if is_external_bool else MONEY_TOLERANCE_FLOAT
        ):
            return
        self._lot_list.append(
            ReferenceLot(
                amount_float, month_index_int, at_month_start_bool
            )
        )
        if is_external_bool:
            self.invested_float += amount_float

    def _charges_float(
        self, sold_float: float, months_held_int: int
    ) -> float:
        """The exit load and transaction tax on one slice."""
        load_float = 0.0
        if months_held_int < int(
            self.fund.exit_load_within_months_int
        ):
            load_float = (
                sold_float
                * float(self.fund.exit_load_percent_float)
                / PERCENT_TOTAL_FLOAT
            )
        return load_float + (
            sold_float
            * float(self.fund.transaction_tax_percent_float)
            / PERCENT_TOTAL_FLOAT
        )

    def _is_long_term_bool(self, months_held_int: int) -> bool:
        """Whether the units qualify for the long term rate.

        Section 2(42A) calls an asset short term when it was held
        for *not more than* the threshold, so the comparison is
        strict: twelve whole months is still short term, and the
        thirteenth is what earns the lower rate. A specified debt
        fund never qualifies however long it was held.
        """
        if self.fund.is_always_short_term_bool:
            return False
        return months_held_int > int(
            self.fund.long_term_threshold_months_int
        )

    def _tax_float(
        self,
        gain_float: float,
        months_held_int: int,
        sale_date: date,
    ) -> float:
        """Tax one realised gain, in the order the Act sets out.

        Losses are set off first, then the annual exemption is
        applied to what survives, then the rate, and finally the
        surcharge and the cess - the cess being charged on the tax
        *and* the surcharge, not on the tax alone.
        """
        is_long_bool = self._is_long_term_bool(months_held_int)
        year_int = financial_year_int(sale_date)
        if gain_float < 0.0:
            self.realised_loss_float += abs(gain_float)
            if self._tax_settings.allow_loss_set_off_bool:
                self._losses.record(
                    abs(gain_float), is_long_bool, year_int
                )
            return 0.0
        if gain_float == 0.0:
            return 0.0
        taxable_float = gain_float
        if self._tax_settings.allow_loss_set_off_bool:
            taxable_float = self._losses.offset_float(
                taxable_float, is_long_bool, year_int
            )
        scope_str = self.fund.exemption_scope_str
        if is_long_bool or scope_str != LONG_TERM_ONLY_STR:
            taxable_float = self._exemption.shelter_float(
                self.fund, taxable_float, sale_date
            )
        rate_float = (
            self.fund.long_term_tax_percent_float
            if is_long_bool
            else self.fund.short_term_tax_percent_float
        )
        return self._levy_float(
            taxable_float * float(rate_float) / PERCENT_TOTAL_FLOAT
        )

    def _levy_float(self, base_tax_float: float) -> float:
        """Gross a base tax up by surcharge and then by cess."""
        surcharge_float = (
            float(self._tax_settings.surcharge_percent_float)
            / PERCENT_TOTAL_FLOAT
        )
        cess_float = (
            float(self._tax_settings.cess_percent_float)
            / PERCENT_TOTAL_FLOAT
        )
        return (
            base_tax_float
            * (1.0 + surcharge_float)
            * (1.0 + cess_float)
        )

    def sell(
        self,
        requested_float: float,
        month_index_int: int,
        sale_date: date,
    ) -> ReferenceSale:
        """Raise money by consuming the oldest parcels first."""
        outcome = ReferenceSale()
        if requested_float <= 0.0:
            return outcome
        remaining_float = requested_float
        surviving_list: list[ReferenceLot] = []
        for lot in self._lot_list:
            if remaining_float <= MONEY_TOLERANCE_FLOAT:
                surviving_list.append(lot)
                continue
            lot_value_float = self._lot_value_float(
                lot, month_index_int
            )
            if lot_value_float <= MONEY_TOLERANCE_FLOAT:
                continue
            taken_float = min(lot_value_float, remaining_float)
            leftover_lot = self._consume_slice(
                lot,
                lot_value_float,
                taken_float,
                month_index_int,
                sale_date,
                outcome,
            )
            remaining_float -= taken_float
            if leftover_lot is not None:
                surviving_list.append(leftover_lot)
        self._lot_list = surviving_list
        return outcome

    def _consume_slice(
        self,
        lot: ReferenceLot,
        lot_value_float: float,
        taken_float: float,
        month_index_int: int,
        sale_date: date,
        outcome: ReferenceSale,
    ) -> ReferenceLot | None:
        """Sell part of one parcel and price what that realised.

        The remainder keeps the original purchase month, so a
        partial sale never restarts a holding period.
        """
        months_held_int = max(
            0, lot.months_held_int(month_index_int)
        )
        growth_float = self._growth_float(
            month_index_int, months_held_int
        )
        charge_float = self._charges_float(
            taken_float, months_held_int
        )
        tax_float = self._tax_float(
            taken_float - taken_float / growth_float,
            months_held_int,
            sale_date,
        )
        outcome.proceeds_float += taken_float
        outcome.charges_float += charge_float
        outcome.tax_float += tax_float
        self.charges_float += charge_float
        self.tax_float += tax_float
        leftover_float = (
            lot_value_float - taken_float
        ) / growth_float
        if leftover_float <= MONEY_TOLERANCE_FLOAT:
            return None
        return ReferenceLot(
            leftover_float,
            lot.month_index_int,
            lot.at_month_start_bool,
        )


class ReferenceTaxRun:
    """The whole plan again, this time with parcels and tax."""

    def __init__(self, fund_list: list, settings) -> None:
        """Prepare the schedules and one lot book per fund."""
        self._settings = settings
        pauses = ReferencePauses(settings.pauses)
        self._contributions = ReferenceContributions(
            settings.stepup,
            pauses,
            settings.portfolio_start_date,
            settings.instalment_override_list,
            build_share_dict(fund_list),
        )
        self._withdrawals = ReferenceWithdrawals(
            settings.withdrawal, pauses
        )
        self._target_dict = build_target_weight_dict(
            fund_list, settings.rebalance
        )
        exemption = ReferenceExemption(settings.tax)
        losses = ReferenceLosses()
        self._book_list = [
            ReferenceFund(
                fund,
                exemption,
                losses,
                settings.tax,
                int(settings.total_months_int),
            )
            for fund in fund_list
        ]
        self._rebalance_count_int = 0

    @property
    def ending_value_float(self) -> float:
        """The corpus at the close of the last month."""
        last_month_int = max(
            0, int(self._settings.total_months_int) - 1
        )
        return sum(
            book.value_float(last_month_int)
            for book in self._book_list
        )

    @property
    def tax_float(self) -> float:
        """Capital gains tax realised over the whole run."""
        return sum(book.tax_float for book in self._book_list)

    @property
    def charges_float(self) -> float:
        """Exit load and transaction tax over the whole run."""
        return sum(book.charges_float for book in self._book_list)

    @property
    def invested_float(self) -> float:
        """External principal paid in."""
        return sum(book.invested_float for book in self._book_list)

    @property
    def withdrawn_float(self) -> float:
        """Money that reached the investor."""
        return sum(
            book.withdrawn_float for book in self._book_list
        )

    def run(self) -> ReferenceTaxRun:
        """Simulate every month of the horizon."""
        for month_index_int in range(
            int(self._settings.total_months_int)
        ):
            self._run_one_month(month_index_int)
        return self

    def _run_one_month(self, month_index_int: int) -> None:
        """The same order of events the engine uses."""
        month_date = month_date_at(
            self._settings.portfolio_start_date, month_index_int
        )
        self._seed_lump_sums(month_index_int)
        self._pay_one_offs(month_index_int)
        if self._settings.sip_at_month_start_bool:
            self._pay_instalments(
                month_index_int, month_date, True
            )
        self._withdraw(month_index_int, month_date)
        self._rebalance_if_due(month_index_int, month_date)
        if not self._settings.sip_at_month_start_bool:
            self._pay_instalments(
                month_index_int, month_date, False
            )

    def _seed_lump_sums(self, month_index_int: int) -> None:
        """Opening balances, in month zero only."""
        if month_index_int != 0:
            return
        for book in self._book_list:
            book.buy(
                float(book.fund.initial_investment_float), 0, True
            )

    def _pay_one_offs(self, month_index_int: int) -> None:
        """Every dated lump sum landing this month."""
        for contribution in (
            self._settings.one_off_contributions_list
        ):
            if int(contribution.month_index_int) != int(
                month_index_int
            ):
                continue
            amount_float = float(contribution.amount_float)
            if amount_float <= 0.0:
                continue
            share_dict = build_one_off_share_dict(
                [book.fund for book in self._book_list],
                contribution,
            )
            for book in self._book_list:
                book.buy(
                    amount_float
                    * share_dict.get(book.fund.name_str, 0.0),
                    month_index_int,
                    True,
                )

    def _pay_instalments(
        self,
        month_index_int: int,
        month_date: date,
        at_start_bool: bool,
    ) -> None:
        """This month's instalment, steered if the plan says so."""
        amount_dict = {
            book.fund.name_str: (
                self._contributions.instalment_float(
                    book.fund, month_index_int, month_date
                )
            )
            for book in self._book_list
        }
        total_float = sum(amount_dict.values())
        if total_float <= 0.0:
            return
        if self._settings.rebalance.use_contribution_steering_bool:
            amount_dict = self._steer_dict(
                total_float, month_index_int, amount_dict
            )
        for book in self._book_list:
            book.buy(
                amount_dict.get(book.fund.name_str, 0.0),
                month_index_int,
                at_start_bool,
            )

    def _steer_dict(
        self,
        total_float: float,
        month_index_int: int,
        fallback_dict: dict,
    ) -> dict:
        """Send this month's money where the plan is short."""
        value_dict = {
            book.fund.name_str: book.value_float(month_index_int)
            for book in self._book_list
        }
        projected_float = sum(value_dict.values()) + total_float
        shortfall_dict = {}
        for book in self._book_list:
            desired_float = (
                projected_float
                * self._target_dict.get(book.fund.name_str, 0.0)
                / PERCENT_TOTAL_FLOAT
            )
            gap_float = (
                desired_float - value_dict[book.fund.name_str]
            )
            if gap_float > MONEY_TOLERANCE_FLOAT:
                shortfall_dict[book.fund.name_str] = gap_float
        shortfall_total_float = sum(shortfall_dict.values())
        if shortfall_total_float <= MONEY_TOLERANCE_FLOAT:
            return dict(fallback_dict)
        return {
            name_str: total_float
            * gap_float
            / shortfall_total_float
            for name_str, gap_float in shortfall_dict.items()
        }

    def _withdraw(
        self, month_index_int: int, month_date: date
    ) -> None:
        """Take the scheduled money out, pro rata by fund value."""
        value_dict = {
            book.fund.name_str: book.value_float(month_index_int)
            for book in self._book_list
        }
        total_float = sum(value_dict.values())
        requested_float = self._withdrawals.requested_float(
            month_index_int, month_date, total_float
        )
        if (
            requested_float <= 0.0
            or total_float <= MONEY_TOLERANCE_FLOAT
        ):
            return
        for book in self._book_list:
            share_float = (
                value_dict[book.fund.name_str] / total_float
            )
            outcome = book.sell(
                requested_float * share_float,
                month_index_int,
                month_date,
            )
            book.withdrawn_float += max(
                0.0,
                outcome.proceeds_float - outcome.charges_float,
            )

    def _is_calendar_due_bool(self, month_index_int: int) -> bool:
        """The rebalancing interval has elapsed."""
        interval_int = int(
            self._settings.rebalance.interval_months_int
        )
        if interval_int <= 0:
            return False
        return (month_index_int + 1) % interval_int == 0

    def _is_band_breached_bool(self, month_index_int: int) -> bool:
        """Some fund has drifted a whole band from its target."""
        band_float = float(
            self._settings.rebalance.drift_band_percent_float
        )
        if band_float <= 0.0:
            return False
        value_dict = {
            book.fund.name_str: book.value_float(month_index_int)
            for book in self._book_list
        }
        total_float = sum(value_dict.values())
        if total_float <= MONEY_TOLERANCE_FLOAT:
            return False
        for book in self._book_list:
            actual_float = (
                PERCENT_TOTAL_FLOAT
                * value_dict[book.fund.name_str]
                / total_float
            )
            if (
                abs(
                    actual_float
                    - self._target_dict.get(
                        book.fund.name_str, 0.0
                    )
                )
                >= band_float
            ):
                return True
        return False

    def _should_rebalance_bool(self, month_index_int: int) -> bool:
        """Whether a trade fires this month."""
        rebalance = self._settings.rebalance
        if not rebalance.is_enabled_bool:
            return False
        maximum_int = int(rebalance.maximum_events_int)
        if 0 < maximum_int <= self._rebalance_count_int:
            return False
        total_float = sum(
            book.value_float(month_index_int)
            for book in self._book_list
        )
        if total_float <= MONEY_TOLERANCE_FLOAT:
            return False
        if month_index_int in {
            int(named_int)
            for named_int in rebalance.rebalance_month_index_tuple
        }:
            return True
        calendar_bool = self._is_calendar_due_bool(month_index_int)
        if rebalance.trigger_str == "DRIFT_BAND":
            return self._is_band_breached_bool(month_index_int)
        if rebalance.trigger_str == "CALENDAR_AND_BAND":
            return calendar_bool and self._is_band_breached_bool(
                month_index_int
            )
        return calendar_bool

    def _chargeable_tax_float(self, tax_float: float) -> float:
        """Tax funded from outside does not shrink the corpus."""
        if self._settings.rebalance.tax_funding_str == "OUTSIDE":
            return 0.0
        return tax_float

    def _rebalance_if_due(
        self, month_index_int: int, month_date: date
    ) -> None:
        """Realign the weights, realising gains as it goes."""
        if not self._should_rebalance_bool(month_index_int):
            return
        if self._settings.rebalance.method_str.startswith("Full"):
            self._rebalance_fully(month_index_int, month_date)
        else:
            self._rebalance_partially(month_index_int, month_date)
        self._rebalance_count_int += 1

    def _rebalance_fully(
        self, month_index_int: int, month_date: date
    ) -> None:
        """Sell the lot and buy back at the target weights."""
        cash_float = 0.0
        tax_float = 0.0
        for book in self._book_list:
            outcome = book.sell(
                book.value_float(month_index_int),
                month_index_int,
                month_date,
            )
            cash_float += (
                outcome.proceeds_float - outcome.charges_float
            )
            tax_float += outcome.tax_float
        net_float = max(
            0.0, cash_float - self._chargeable_tax_float(tax_float)
        )
        for book in self._book_list:
            book.buy(
                net_float
                * self._target_dict.get(book.fund.name_str, 0.0)
                / PERCENT_TOTAL_FLOAT,
                month_index_int,
                False,
                False,
            )

    def _rebalance_partially(
        self, month_index_int: int, month_date: date
    ) -> None:
        """Trim the overweight funds and top up the rest."""
        total_float = sum(
            book.value_float(month_index_int)
            for book in self._book_list
        )
        desired_dict = {
            book.fund.name_str: total_float
            * self._target_dict.get(book.fund.name_str, 0.0)
            / PERCENT_TOTAL_FLOAT
            for book in self._book_list
        }
        cash_float, tax_float = self._sell_overweight_tuple(
            desired_dict, month_index_int, month_date
        )
        net_float = max(
            0.0, cash_float - self._chargeable_tax_float(tax_float)
        )
        shortfall_dict = {}
        for book in self._book_list:
            gap_float = desired_dict[
                book.fund.name_str
            ] - book.value_float(month_index_int)
            if gap_float > 1e-6:
                shortfall_dict[book.fund.name_str] = gap_float
        shortfall_total_float = sum(shortfall_dict.values())
        if net_float <= 0.0 or shortfall_total_float <= 0.0:
            return
        for book in self._book_list:
            if book.fund.name_str not in shortfall_dict:
                continue
            book.buy(
                net_float
                * shortfall_dict[book.fund.name_str]
                / shortfall_total_float,
                month_index_int,
                False,
                False,
            )

    def _sell_overweight_tuple(
        self,
        desired_dict: dict,
        month_index_int: int,
        month_date: date,
    ) -> tuple:
        """Sell what each fund holds above its target."""
        cash_float = 0.0
        tax_float = 0.0
        for book in self._book_list:
            excess_float = (
                book.value_float(month_index_int)
                - desired_dict[book.fund.name_str]
            )
            if excess_float <= 1e-6:
                continue
            outcome = book.sell(
                excess_float, month_index_int, month_date
            )
            cash_float += (
                outcome.proceeds_float - outcome.charges_float
            )
            tax_float += outcome.tax_float
        return cash_float, tax_float


def run_reference_tax(fund_list: list, settings) -> ReferenceTaxRun:
    """Run the taxed reference over one plan."""
    return ReferenceTaxRun(fund_list, settings).run()


def count_months_in_year_int() -> int:
    """Exposed so importers need not reach into the other module."""
    return MONTHS_IN_YEAR_INT
