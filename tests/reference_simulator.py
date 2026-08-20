"""A second simulator, written to disagree with the first.

The engine values a portfolio by keeping a book of lots: every
contribution is a parcel with its own purchase month, each parcel
compounds from its own date, and a sale walks the book oldest
first, splitting parcels as it goes. That machinery exists because
capital gains tax needs it - which lot was sold decides what is
taxed.

This module answers the same question a different way. It carries
one number per fund and rolls it forward:

    value = value * (1 + rate) + money in - money out

No lots, no purchase dates, no first-in-first-out. The two
algorithms have almost nothing in common, which is the point: a
mistake in the lot book - a parcel split wrongly, a holding period
counted from the wrong month, dust dropped on a partial sale -
cannot also be made here, because there is nothing here to make it
in.

The price of that independence is that this simulator cannot model
tax, exit loads or the securities transaction tax, all of which
need to know *which* units were sold. So it is used with tax off,
where its answer must match the engine's to floating point. The
taxed runs are held to invariants instead, in the fuzz that follows.

WHAT THIS ENCODES

The order of events inside one month, which is a convention rather
than a truth and is therefore worth stating plainly:

    1. opening lump sums, in month zero only
    2. one-off contributions dated to this month
    3. the instalment, if instalments are paid at month start
    4. the withdrawal
    5. the rebalance
    6. the instalment, if instalments are paid at month end

Everything is valued at the close of the month, so an instalment
paid at the start has already earned that month's growth by the
time the withdrawal is taken, and one paid at the end has not.
Money bought back by a rebalance is treated as bought at month end,
so it does not earn the month it was bought in.

If the engine and this module ever disagree, one of three things is
true: the engine is wrong, this is wrong, or the convention above
was never really decided. All three are worth knowing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

MONTHS_IN_YEAR_INT: int = 12
PERCENT_TOTAL_FLOAT: float = 100.0
MONEY_TOLERANCE_FLOAT: float = 1e-9
RATIO_TOLERANCE_FLOAT: float = 1e-6


@dataclass
class ReferenceOutcome:
    """What one reference run produced."""

    value_by_fund_dict: dict = field(default_factory=dict)
    invested_by_fund_dict: dict = field(default_factory=dict)
    withdrawn_by_fund_dict: dict = field(default_factory=dict)
    monthly_value_list: list = field(default_factory=list)
    monthly_contribution_list: list = field(default_factory=list)
    monthly_withdrawal_list: list = field(default_factory=list)
    rebalance_month_list: list = field(default_factory=list)

    @property
    def ending_value_float(self) -> float:
        """Closing value of the whole portfolio."""
        return sum(self.value_by_fund_dict.values())

    @property
    def invested_float(self) -> float:
        """External principal paid in over the whole run."""
        return sum(self.invested_by_fund_dict.values())

    @property
    def withdrawn_float(self) -> float:
        """Gross proceeds taken out over the whole run."""
        return sum(self.withdrawn_by_fund_dict.values())


MINIMUM_RETURN_PERCENT_FLOAT: float = -99.99
MAXIMUM_EXPENSE_PERCENT_FLOAT: float = 99.99
ACCRUAL_MODEL_STR: str = "CONTINUOUS_ACCRUAL"


def clamp_return_float(annual_percent_float: float) -> float:
    """A return of minus a hundred per cent makes roots undefined."""
    return max(
        MINIMUM_RETURN_PERCENT_FLOAT, float(annual_percent_float)
    )


def clamp_expense_float(expense_percent_float: float) -> float:
    """An expense ratio lives between nothing and everything."""
    return min(
        MAXIMUM_EXPENSE_PERCENT_FLOAT,
        max(0.0, float(expense_percent_float)),
    )


def twelfth_root_rate_float(annual_percent_float: float) -> float:
    """The monthly rate whose twelve steps make the annual one."""
    return (
        1.0
        + clamp_return_float(annual_percent_float)
        / PERCENT_TOTAL_FLOAT
    ) ** (1.0 / MONTHS_IN_YEAR_INT) - 1.0


def monthly_rate_float(
    annual_percent_float: float,
    expense_percent_float: float = 0.0,
    expense_model_str: str = "SIMPLE_SUBTRACTION",
) -> float:
    """The monthly rate a fund compounds at, from scratch.

    Two models, and the difference between them is real money over
    a long horizon.

    *Simple subtraction* takes the expense ratio off the annual
    return and converts what is left. It is a planning
    approximation: a 12 per cent fund charging 1 per cent is
    treated as an 11 per cent fund.

    *Continuous accrual* is what a real fund does. The expense is
    charged against the net asset value as it grows, so the two
    factors multiply rather than subtract:

        (1 + gross) ** (1/12)  *  (1 - expense) ** (1/12)

    The gap between them is roughly the product of the return and
    the ratio - small in one month, and compounding for as long as
    the plan runs.
    """
    if expense_model_str != ACCRUAL_MODEL_STR:
        return twelfth_root_rate_float(
            clamp_return_float(annual_percent_float)
            - clamp_expense_float(expense_percent_float)
        )
    gross_factor_float = 1.0 + twelfth_root_rate_float(
        annual_percent_float
    )
    expense_factor_float = (
        1.0
        - clamp_expense_float(expense_percent_float)
        / PERCENT_TOTAL_FLOAT
    ) ** (1.0 / MONTHS_IN_YEAR_INT)
    return gross_factor_float * expense_factor_float - 1.0


def build_rate_path_list(fund, total_months_int: int) -> list:
    """One rate per month, whether stated or derived.

    A fund normally compounds at one constant rate. A stochastic
    run instead hands it a path - a realised rate for every month -
    and that is what makes the order of good and bad years matter
    rather than only their average.
    """
    if fund.monthly_rate_path_list:
        path_list = [
            float(rate_float)
            for rate_float in fund.monthly_rate_path_list
        ]
        if len(path_list) < total_months_int:
            path_list += [path_list[-1]] * (
                total_months_int - len(path_list)
            )
        return path_list[:total_months_int]
    if fund.monthly_rate_override_float is not None:
        return [
            float(fund.monthly_rate_override_float)
        ] * total_months_int
    return [
        monthly_rate_float(
            fund.gross_return_percent_float,
            fund.expense_percent_float,
            fund.expense_model_str,
        )
    ] * total_months_int


def month_date_at(start_date: date, month_index_int: int) -> date:
    """The calendar month one index along the grid."""
    zero_based_int = (
        start_date.month - 1 + int(month_index_int)
    )
    return date(
        start_date.year + zero_based_int // MONTHS_IN_YEAR_INT,
        zero_based_int % MONTHS_IN_YEAR_INT + 1,
        1,
    )


def count_months_between_int(
    start_date: date, end_date: date
) -> int:
    """Whole calendar months from one month to another."""
    return (
        end_date.year - start_date.year
    ) * MONTHS_IN_YEAR_INT + (end_date.month - start_date.month)


def is_month_in_range_bool(
    candidate_date: date,
    start_date: date,
    end_date: date,
) -> bool:
    """Inclusive of both boundary months, by year and month."""
    return (
        (start_date.year, start_date.month)
        <= (candidate_date.year, candidate_date.month)
        <= (end_date.year, end_date.month)
    )


class ReferencePauses:
    """Whether a flow is stopped in a given month."""

    def __init__(self, pause_settings) -> None:
        """Index the two ways a pause can be expressed."""
        self._sip_month_set = {
            int(month_int)
            for month_int in pause_settings.sip_pause_months_list
        }
        self._withdrawal_month_set = {
            int(month_int)
            for month_int in (
                pause_settings.withdrawal_pause_months_list
            )
        }
        self._range_list = list(pause_settings.pause_ranges_list)

    def _covers_bool(
        self, month_date: date, scope_str: str
    ) -> bool:
        """Any range whose scope matches and whose window covers."""
        for pause_range in self._range_list:
            if pause_range.start_date is None:
                continue
            if pause_range.end_date is None:
                continue
            range_scope_str = (
                str(pause_range.scope_str).upper().strip()
            )
            if range_scope_str not in (scope_str, "BOTH"):
                continue
            if is_month_in_range_bool(
                month_date,
                pause_range.start_date,
                pause_range.end_date,
            ):
                return True
        return False

    def is_sip_paused_bool(self, month_date: date) -> bool:
        """Contributions stopped this month."""
        if month_date.month in self._sip_month_set:
            return True
        return self._covers_bool(month_date, "SIP")

    def is_withdrawal_paused_bool(self, month_date: date) -> bool:
        """Withdrawals stopped this month."""
        if month_date.month in self._withdrawal_month_set:
            return True
        return self._covers_bool(month_date, "SWP")


def escalation_periods_int(
    months_since_origin_int: int,
    interval_months_int: int,
    first_month_int: int,
) -> int:
    """How many escalations have already happened."""
    if interval_months_int <= 0:
        return 0
    if first_month_int <= 0:
        return months_since_origin_int // interval_months_int
    if months_since_origin_int < first_month_int:
        return 0
    return (
        months_since_origin_int - first_month_int
    ) // interval_months_int + 1


def escalate_float(
    base_float: float,
    percent_float: float,
    periods_int: int,
) -> float:
    """Whole-period compounding of a percentage change."""
    return float(base_float) * (
        (1.0 + float(percent_float) / PERCENT_TOTAL_FLOAT)
        ** max(0, int(periods_int))
    )


class ReferenceContributions:
    """The instalment one fund owes in one month."""

    def __init__(
        self,
        stepup_settings,
        pauses: ReferencePauses,
        portfolio_start_date: date,
        override_list: list,
        share_dict: dict,
    ) -> None:
        """Bind the escalation and override rules."""
        self._stepup = stepup_settings
        self._pauses = pauses
        self._start_date = portfolio_start_date
        self._override_list = sorted(
            override_list or [],
            key=lambda override: int(override.month_index_int),
        )
        self._share_dict = dict(share_dict or {})

    def _origin_month_int(self, fund) -> int:
        """First month this fund can invest in."""
        return max(
            0,
            count_months_between_int(
                self._start_date, fund.start_date
            ),
        )

    def _base_tuple(self, fund, month_index_int: int) -> tuple:
        """The instalment in force and when it took effect."""
        base_float = float(fund.monthly_sip_float)
        origin_int = self._origin_month_int(fund)
        for override in self._override_list:
            if int(override.month_index_int) > int(month_index_int):
                break
            if override.fund_name_str not in ("", fund.name_str):
                continue
            if override.fund_name_str:
                base_float = float(override.amount_float)
            else:
                base_float = float(
                    override.amount_float
                ) * float(self._share_dict.get(fund.name_str, 1.0))
            origin_int = max(
                self._origin_month_int(fund),
                int(override.month_index_int),
            )
        return base_float, origin_int

    def instalment_float(
        self, fund, month_index_int: int, month_date: date
    ) -> float:
        """Rupees this fund receives this month."""
        if self._pauses.is_sip_paused_bool(month_date):
            return 0.0
        base_float, origin_int = self._base_tuple(
            fund, month_index_int
        )
        if int(month_index_int) < origin_int:
            return 0.0
        periods_int = escalation_periods_int(
            int(month_index_int) - origin_int,
            int(self._stepup.interval_months_int),
            int(self._stepup.first_stepup_month_index_int),
        )
        amount_float = base_float
        if self._stepup.mode_str in ("GLOBAL", "BOTH"):
            amount_float = escalate_float(
                amount_float,
                self._stepup.global_stepup_percent_float,
                periods_int,
            )
        if self._stepup.mode_str in ("PER_FUND", "BOTH"):
            amount_float = escalate_float(
                amount_float,
                fund.stepup_percent_float,
                periods_int,
            )
        amount_float += (
            float(self._stepup.fixed_increment_amount_float)
            * periods_int
        )
        return max(0.0, amount_float)


class ReferenceWithdrawals:
    """The withdrawal one plan asks for in one month."""

    def __init__(
        self, withdrawal_settings, pauses: ReferencePauses
    ) -> None:
        """Bind the withdrawal rules to the pause calendar."""
        self._settings = withdrawal_settings
        self._pauses = pauses

    def requested_float(
        self,
        month_index_int: int,
        month_date: date,
        portfolio_value_float: float,
    ) -> float:
        """Rupees asked for, before the corpus is consulted."""
        settings = self._settings
        if not settings.is_enabled_bool:
            return 0.0
        start_int = int(settings.start_month_index_int)
        if int(month_index_int) < start_int:
            return 0.0
        if self._pauses.is_withdrawal_paused_bool(month_date):
            return 0.0
        elapsed_years_int = (
            int(month_index_int) - start_int
        ) // MONTHS_IN_YEAR_INT
        if settings.mode_str == "PERCENT_OF_CORPUS":
            return max(
                0.0,
                portfolio_value_float
                * float(settings.portfolio_percent_float)
                / PERCENT_TOTAL_FLOAT,
            )
        if settings.mode_str == "FIXED":
            return max(
                0.0,
                escalate_float(
                    settings.fixed_amount_float,
                    settings.annual_change_percent_float,
                    elapsed_years_int,
                ),
            )
        return self._scheduled_float(month_date, elapsed_years_int)

    def _scheduled_float(
        self, month_date: date, elapsed_years_int: int
    ) -> float:
        """The twelve-entry calendar schedule, escalated."""
        schedule_list = list(self._settings.monthly_schedule_list)
        if len(schedule_list) < MONTHS_IN_YEAR_INT:
            return 0.0
        amount_float = escalate_float(
            float(schedule_list[month_date.month - 1]),
            self._settings.annual_change_percent_float,
            elapsed_years_int,
        )
        change_list = list(
            self._settings.monthly_change_percent_list
        )
        if len(change_list) < MONTHS_IN_YEAR_INT:
            return max(0.0, amount_float)
        return max(
            0.0,
            escalate_float(
                amount_float,
                float(change_list[month_date.month - 1]),
                elapsed_years_int,
            ),
        )


def build_target_weight_dict(fund_list: list, rebalance) -> dict:
    """The weights a rebalance aims at, normalised to one hundred.

    Off, every weight is zero, so a passive run can never be
    steered by a column nobody asked it to read.
    """
    if not (
        rebalance.is_enabled_bool
        or rebalance.use_contribution_steering_bool
    ):
        return {fund.name_str: 0.0 for fund in fund_list}
    if rebalance.target_mode_str == "INITIAL_SIP_SPLIT":
        raw_dict = {
            fund.name_str: max(0.0, float(fund.monthly_sip_float))
            for fund in fund_list
        }
    else:
        raw_dict = {
            fund.name_str: max(
                0.0,
                float(fund.target_allocation_percent_float),
            )
            for fund in fund_list
        }
        if sum(raw_dict.values()) <= 0.0:
            raw_dict = {
                fund.name_str: max(
                    0.0, float(fund.monthly_sip_float)
                )
                for fund in fund_list
            }
    total_float = sum(raw_dict.values())
    if total_float <= 0.0:
        even_float = PERCENT_TOTAL_FLOAT / len(raw_dict)
        return dict.fromkeys(raw_dict, even_float)
    return {
        name_str: PERCENT_TOTAL_FLOAT * weight_float / total_float
        for name_str, weight_float in raw_dict.items()
    }


def build_share_dict(fund_list: list) -> dict:
    """Each fund's share of an instalment that names no fund."""
    weight_dict = {
        fund.name_str: max(
            0.0, float(fund.target_allocation_percent_float)
        )
        for fund in fund_list
    }
    total_float = sum(weight_dict.values())
    if total_float <= 0.0:
        return dict.fromkeys(weight_dict, 1.0 / len(weight_dict))
    return {
        name_str: weight_float / total_float
        for name_str, weight_float in weight_dict.items()
    }


def build_one_off_share_dict(fund_list: list, contribution) -> dict:
    """How one dated contribution is split between the funds."""
    if contribution.fund_name_str:
        return {contribution.fund_name_str: 1.0}
    return build_share_dict(fund_list)


class ReferenceSimulator:
    """One number per fund, rolled forward month by month."""

    def __init__(self, fund_list: list, settings) -> None:
        """Prepare the schedules this run will consult."""
        self._fund_list = list(fund_list)
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
        self._rate_path_dict = {
            fund.name_str: build_rate_path_list(
                fund, int(settings.total_months_int)
            )
            for fund in fund_list
        }
        self._month_index_int = 0
        self._value_dict = {
            fund.name_str: 0.0 for fund in fund_list
        }
        self._invested_dict = {
            fund.name_str: 0.0 for fund in fund_list
        }
        self._withdrawn_dict = {
            fund.name_str: 0.0 for fund in fund_list
        }
        self._outcome = ReferenceOutcome()

    def run(self) -> ReferenceOutcome:
        """Simulate the whole horizon."""
        for month_index_int in range(
            int(self._settings.total_months_int)
        ):
            self._run_one_month(month_index_int)
        self._outcome.value_by_fund_dict = dict(self._value_dict)
        self._outcome.invested_by_fund_dict = dict(
            self._invested_dict
        )
        self._outcome.withdrawn_by_fund_dict = dict(
            self._withdrawn_dict
        )
        return self._outcome

    def _rate_float(self, fund_name_str: str) -> float:
        """This fund's rate for the month being simulated."""
        return self._rate_path_dict[fund_name_str][
            self._month_index_int
        ]

    def _run_one_month(self, month_index_int: int) -> None:
        """Grow, then work through the month in order."""
        self._month_index_int = month_index_int
        month_date = month_date_at(
            self._settings.portfolio_start_date, month_index_int
        )
        self._grow_one_month()
        contributed_float = self._pay_in_at_start(
            month_index_int, month_date
        )
        withdrawn_float = self._withdraw(
            month_index_int, month_date
        )
        self._rebalance_if_due(month_index_int)
        contributed_float += self._pay_in_at_end(
            month_index_int, month_date
        )
        self._outcome.monthly_value_list.append(
            sum(self._value_dict.values())
        )
        self._outcome.monthly_contribution_list.append(
            contributed_float
        )
        self._outcome.monthly_withdrawal_list.append(
            withdrawn_float
        )

    def _grow_one_month(self) -> None:
        """Everything already held earns this month's return."""
        for fund in self._fund_list:
            self._value_dict[fund.name_str] *= 1.0 + self._rate_float(
                fund.name_str
            )

    def _pay_in_at_start(
        self, month_index_int: int, month_date: date
    ) -> float:
        """Lump sums, one-offs and start-of-month instalments.

        Money paid in at the start of a month has earned that
        month's growth by the time the month closes, so it is
        credited with one month of compounding as it lands.
        """
        contributed_float = self._seed_lump_sums(month_index_int)
        contributed_float += self._pay_one_offs(month_index_int)
        if self._settings.sip_at_month_start_bool:
            contributed_float += self._pay_instalments(
                month_index_int, month_date, True
            )
        return contributed_float

    def _pay_in_at_end(
        self, month_index_int: int, month_date: date
    ) -> float:
        """End-of-month instalments, which earn nothing yet."""
        if self._settings.sip_at_month_start_bool:
            return 0.0
        return self._pay_instalments(
            month_index_int, month_date, False
        )

    def _credit(
        self,
        fund_name_str: str,
        amount_float: float,
        grows_this_month_bool: bool,
    ) -> None:
        """Add external principal to one fund."""
        if amount_float <= 0.0:
            return
        growth_float = (
            1.0 + self._rate_float(fund_name_str)
            if grows_this_month_bool
            else 1.0
        )
        self._value_dict[fund_name_str] += (
            amount_float * growth_float
        )
        self._invested_dict[fund_name_str] += amount_float

    def _seed_lump_sums(self, month_index_int: int) -> float:
        """Opening balances, in month zero only."""
        if month_index_int != 0:
            return 0.0
        seeded_float = 0.0
        for fund in self._fund_list:
            amount_float = float(fund.initial_investment_float)
            if amount_float <= 0.0:
                continue
            self._credit(fund.name_str, amount_float, True)
            seeded_float += amount_float
        return seeded_float

    def _pay_one_offs(self, month_index_int: int) -> float:
        """Every dated contribution that lands this month."""
        paid_float = 0.0
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
                self._fund_list, contribution
            )
            for fund in self._fund_list:
                share_float = amount_float * share_dict.get(
                    fund.name_str, 0.0
                )
                if share_float <= 0.0:
                    continue
                self._credit(fund.name_str, share_float, True)
                paid_float += share_float
        return paid_float

    def _pay_instalments(
        self,
        month_index_int: int,
        month_date: date,
        at_start_bool: bool,
    ) -> float:
        """This month's instalment, fund by fund."""
        amount_dict = {
            fund.name_str: self._contributions.instalment_float(
                fund, month_index_int, month_date
            )
            for fund in self._fund_list
        }
        total_float = sum(amount_dict.values())
        if total_float <= 0.0:
            return 0.0
        if self._settings.rebalance.use_contribution_steering_bool:
            amount_dict = self._steer(total_float, amount_dict)
        for fund in self._fund_list:
            self._credit(
                fund.name_str,
                amount_dict.get(fund.name_str, 0.0),
                at_start_bool,
            )
        return total_float

    def _steer(
        self, total_float: float, fallback_dict: dict
    ) -> dict:
        """Send this month's money to the underweight funds."""
        projected_float = (
            sum(self._value_dict.values()) + total_float
        )
        shortfall_dict = {}
        for fund in self._fund_list:
            desired_float = (
                projected_float
                * self._target_dict.get(fund.name_str, 0.0)
                / PERCENT_TOTAL_FLOAT
            )
            gap_float = (
                desired_float - self._value_dict[fund.name_str]
            )
            if gap_float > MONEY_TOLERANCE_FLOAT:
                shortfall_dict[fund.name_str] = gap_float
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
    ) -> float:
        """Take the scheduled amount out, pro rata by fund value."""
        total_float = sum(self._value_dict.values())
        requested_float = self._withdrawals.requested_float(
            month_index_int, month_date, total_float
        )
        if requested_float <= 0.0 or total_float <= 0.0:
            return 0.0
        paid_float = 0.0
        for fund in self._fund_list:
            share_float = (
                self._value_dict[fund.name_str] / total_float
            )
            taken_float = min(
                requested_float * share_float,
                self._value_dict[fund.name_str],
            )
            self._value_dict[fund.name_str] -= taken_float
            self._withdrawn_dict[fund.name_str] += taken_float
            paid_float += taken_float
        return paid_float

    def _is_calendar_due_bool(self, month_index_int: int) -> bool:
        """The interval has elapsed, counting from month zero."""
        interval_int = int(
            self._settings.rebalance.interval_months_int
        )
        if interval_int <= 0:
            return False
        return (month_index_int + 1) % interval_int == 0

    def _is_band_breached_bool(self) -> bool:
        """Some fund sits at least a band away from its target."""
        band_float = float(
            self._settings.rebalance.drift_band_percent_float
        )
        if band_float <= 0.0:
            return False
        total_float = sum(self._value_dict.values())
        if total_float <= MONEY_TOLERANCE_FLOAT:
            return False
        for fund in self._fund_list:
            actual_float = (
                PERCENT_TOTAL_FLOAT
                * self._value_dict[fund.name_str]
                / total_float
            )
            drift_float = abs(
                actual_float
                - self._target_dict.get(fund.name_str, 0.0)
            )
            if drift_float >= band_float:
                return True
        return False

    def _should_rebalance_bool(self, month_index_int: int) -> bool:
        """Whether a trade fires this month, and by which rule."""
        rebalance = self._settings.rebalance
        if not rebalance.is_enabled_bool:
            return False
        maximum_int = int(rebalance.maximum_events_int)
        if 0 < maximum_int <= len(
            self._outcome.rebalance_month_list
        ):
            return False
        if sum(self._value_dict.values()) <= MONEY_TOLERANCE_FLOAT:
            return False
        # A month named by hand fires whatever the mode says,
        # because the reader asked for it explicitly.
        if month_index_int in {
            int(named_int)
            for named_int in rebalance.rebalance_month_index_tuple
        }:
            return True
        calendar_bool = self._is_calendar_due_bool(month_index_int)
        if rebalance.trigger_str == "DRIFT_BAND":
            return self._is_band_breached_bool()
        if rebalance.trigger_str == "CALENDAR_AND_BAND":
            return calendar_bool and self._is_band_breached_bool()
        return calendar_bool

    def _rebalance_if_due(self, month_index_int: int) -> None:
        """Realign to the target weights when a trigger fires.

        Both methods are modelled, but only because this simulator
        is used with tax and charges off. With either of those on,
        the cash a sale raises depends on what was deducted from
        it, and that needs the lot book this module refuses to
        keep.
        """
        if not self._should_rebalance_bool(month_index_int):
            return
        if self._settings.rebalance.method_str.startswith("Full"):
            self._rebalance_fully()
        else:
            self._rebalance_partially()
        self._outcome.rebalance_month_list.append(month_index_int)

    def _rebalance_fully(self) -> None:
        """Sell everything and buy back exactly at target."""
        total_float = sum(self._value_dict.values())
        for fund in self._fund_list:
            self._value_dict[fund.name_str] = (
                total_float
                * self._target_dict.get(fund.name_str, 0.0)
                / PERCENT_TOTAL_FLOAT
            )

    def _rebalance_partially(self) -> None:
        """Trim only what is overweight and hand it to the rest.

        Cheaper in tax than a full liquidation, because the gain
        inside the units that were already at target is never
        realised.
        """
        total_float = sum(self._value_dict.values())
        desired_dict = {
            fund.name_str: total_float
            * self._target_dict.get(fund.name_str, 0.0)
            / PERCENT_TOTAL_FLOAT
            for fund in self._fund_list
        }
        cash_float = 0.0
        for fund in self._fund_list:
            excess_float = (
                self._value_dict[fund.name_str]
                - desired_dict[fund.name_str]
            )
            if excess_float <= RATIO_TOLERANCE_FLOAT:
                continue
            self._value_dict[fund.name_str] -= excess_float
            cash_float += excess_float
        shortfall_dict = {}
        for fund in self._fund_list:
            gap_float = (
                desired_dict[fund.name_str]
                - self._value_dict[fund.name_str]
            )
            if gap_float > RATIO_TOLERANCE_FLOAT:
                shortfall_dict[fund.name_str] = gap_float
        shortfall_total_float = sum(shortfall_dict.values())
        if cash_float <= 0.0 or shortfall_total_float <= 0.0:
            return
        for name_str, gap_float in shortfall_dict.items():
            self._value_dict[name_str] += (
                cash_float * gap_float / shortfall_total_float
            )


def run_reference(fund_list: list, settings) -> ReferenceOutcome:
    """Run the reference simulator over one plan."""
    return ReferenceSimulator(fund_list, settings).run()
