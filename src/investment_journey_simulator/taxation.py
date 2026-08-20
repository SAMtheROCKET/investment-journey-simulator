"""Capital gains taxation, loss set-off and exit charges."""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.constants import (
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXEMPTION_SCOPE_TOTAL_GAINS_STR,
    LOSS_BUCKET_LONG_TERM_STR,
    LOSS_BUCKET_SHORT_TERM_STR,
    LOSS_CARRY_FORWARD_YEARS_INT,
    MAXIMUM_CAPITAL_GAINS_SURCHARGE_PERCENT_FLOAT,
    NEW_REGIME_INCOME_TAX_SLABS_TUPLE,
    NEW_REGIME_SURCHARGE_SLABS_TUPLE,
    OLD_REGIME_INCOME_TAX_SLABS_TUPLE,
    OLD_REGIME_SURCHARGE_SLABS_TUPLE,
    PERCENT_TOTAL_FLOAT,
    PORTFOLIO_LEDGER_KEY_STR,
    SURCHARGE_MODE_SLAB_STR,
    SURCHARGE_REGIME_OLD_STR,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    RealizedGainBreakdown,
    TaxSettings,
)
from investment_journey_simulator.time_utils import derive_financial_year_int

ExemptionKeyTuple = tuple[str, int, str]
LossKeyTuple = tuple[str, int]


def _select_surcharge_slab_tuple(surcharge_regime_str: str) -> tuple:
    """Pick the surcharge slab table for a regime.

    Brief:
        The new regime, default since FY 2023-24, caps the
        surcharge at twenty-five percent; the old regime retains
        the thirty-seven percent band above five crore.

    Arguments:
        surcharge_regime_str (str): Regime identifier.

    Returns:
        tuple: Entries of (income floor, surcharge percent).

    Warning:
        Any regime other than the old one is treated as the new
        one, which is the safe default.
    """
    if surcharge_regime_str == SURCHARGE_REGIME_OLD_STR:
        return OLD_REGIME_SURCHARGE_SLABS_TUPLE
    return NEW_REGIME_SURCHARGE_SLABS_TUPLE


def _resolve_surcharge_band_index_int(
    total_income_float: float,
    slab_tuple: tuple,
) -> int:
    """Find which surcharge band a total income falls in.

    Brief:
        A band applies when the income is strictly above its floor,
        so an income exactly at a floor stays in the band below.

    Arguments:
        total_income_float (float): Total income for the year.
        slab_tuple (tuple): Entries of (income floor, percent).

    Returns:
        int: Index of the applicable band, zero when none applies.

    Warning:
        The table must be ordered by ascending income floor.
    """
    band_index_int = 0
    for index_int, (income_floor_float, _) in enumerate(slab_tuple):
        if float(total_income_float) > income_floor_float:
            band_index_int = index_int
    return band_index_int


def resolve_surcharge_slab_percent_float(
    total_income_float: float,
    surcharge_regime_str: str,
) -> float:
    """Look up the surcharge rate a total income attracts.

    Brief:
        Walks the statutory slab table and returns the rate of the
        highest band the income reaches.

    Arguments:
        total_income_float (float): Total income for the year.
        surcharge_regime_str (str): Regime identifier.

    Returns:
        float: Surcharge percent applicable to that income.

    Warning:
        This is the raw band rate before marginal relief. Just
        above a boundary the rate actually collected is lower; see
        resolve_relieved_surcharge_percent_float.
    """
    slab_tuple = _select_surcharge_slab_tuple(surcharge_regime_str)
    band_index_int = _resolve_surcharge_band_index_int(
        total_income_float, slab_tuple
    )
    return float(slab_tuple[band_index_int][1])


def calculate_income_tax_float(
    total_income_float: float,
    surcharge_regime_str: str,
) -> float:
    """Income tax on a total income, before surcharge and cess.

    Brief:
        Applies each slab rate to the slice of income lying inside
        that slab. This exists to support marginal relief, which
        cannot be computed without the tax at the slab floor.

    Arguments:
        total_income_float (float): Total income for the year.
        surcharge_regime_str (str): Regime identifier.

    Returns:
        float: Income tax before surcharge and cess.

    Warning:
        Deductions, the section 87A rebate and the senior citizen
        exemption are not modelled. See the slab constants for why
        that is safe at the incomes where relief can apply.
    """
    slab_tuple = (
        OLD_REGIME_INCOME_TAX_SLABS_TUPLE
        if surcharge_regime_str == SURCHARGE_REGIME_OLD_STR
        else NEW_REGIME_INCOME_TAX_SLABS_TUPLE
    )
    income_float = max(0.0, float(total_income_float))
    last_index_int = len(slab_tuple) - 1
    tax_float = 0.0
    for index_int, (floor_float, rate_float) in enumerate(slab_tuple):
        ceiling_float = (
            income_float
            if index_int == last_index_int
            else slab_tuple[index_int + 1][0]
        )
        slice_float = min(income_float, ceiling_float) - floor_float
        if slice_float > 0.0:
            tax_float += (
                slice_float * rate_float / PERCENT_TOTAL_FLOAT
            )
    return tax_float


def resolve_relieved_surcharge_percent_float(
    total_income_float: float,
    surcharge_regime_str: str,
) -> float:
    """Surcharge rate after marginal relief, as a percent of tax.

    Brief:
        Crossing a surcharge threshold by one rupee must never cost
        more than one rupee. Relief is the amount by which the tax
        and surcharge at this income exceed the tax and surcharge
        at the threshold plus the income earned above it, and it is
        returned as the effective rate the surcharge collects.

    Arguments:
        total_income_float (float): Total income for the year.
        surcharge_regime_str (str): Regime identifier.

    Returns:
        float: Effective surcharge percent, at most the band rate.

    Warning:
        Relief is computed on total income. Attributing the relieved
        rate to the capital gains component is an apportionment, not
        a rule stated in the Act.
    """
    slab_tuple = _select_surcharge_slab_tuple(surcharge_regime_str)
    band_index_int = _resolve_surcharge_band_index_int(
        total_income_float, slab_tuple
    )
    band_percent_float = float(slab_tuple[band_index_int][1])
    tax_float = calculate_income_tax_float(
        total_income_float, surcharge_regime_str
    )
    if band_percent_float <= 0.0 or tax_float <= 0.0:
        return band_percent_float
    surcharge_float = (
        tax_float * band_percent_float / PERCENT_TOTAL_FLOAT
    )
    relief_float = max(
        0.0,
        (tax_float + surcharge_float)
        - _threshold_liability_float(
            total_income_float, slab_tuple, band_index_int,
            surcharge_regime_str,
        ),
    )
    payable_float = max(0.0, surcharge_float - relief_float)
    return payable_float / tax_float * PERCENT_TOTAL_FLOAT


def _threshold_liability_float(
    total_income_float: float,
    slab_tuple: tuple,
    band_index_int: int,
    surcharge_regime_str: str,
) -> float:
    """What the taxpayer would owe if relief bound exactly.

    Brief:
        The comparison the Act makes is against the liability at
        the threshold plus every rupee earned above it. At a second
        or higher threshold that liability already carries the band
        below, so its surcharge counts too.

    Arguments:
        total_income_float (float): Total income for the year.
        slab_tuple (tuple): Surcharge slab table for the regime.
        band_index_int (int): Index of the applicable band.
        surcharge_regime_str (str): Regime identifier.

    Returns:
        float: Tax, surcharge and excess income at the threshold.

    Warning:
        Assumes the band index is one the income actually reaches.
    """
    threshold_float = float(slab_tuple[band_index_int][0])
    previous_percent_float = (
        float(slab_tuple[band_index_int - 1][1])
        if band_index_int > 0
        else 0.0
    )
    tax_at_threshold_float = calculate_income_tax_float(
        threshold_float, surcharge_regime_str
    )
    liability_float = tax_at_threshold_float * (
        1.0 + previous_percent_float / PERCENT_TOTAL_FLOAT
    )
    return liability_float + (
        float(total_income_float) - threshold_float
    )


def resolve_total_income_float(
    tax_settings: TaxSettings,
    financial_year_int: int | None = None,
) -> float:
    """Find the income in force in one financial year.

    Brief:
        An income that changes over a lifetime is described as
        dated entries; the one in force is the latest at or before
        the year asked about. A plan with no entries keeps the
        single income figure it was given.

    Arguments:
        tax_settings (TaxSettings): Portfolio tax rules.
        financial_year_int (Optional[int]): Year of the sale.

    Returns:
        float: Total income to judge the surcharge against.

    Warning:
        Entries dated after the year asked about are ignored, so a
        future raise never inflates today's surcharge.
    """
    if not tax_settings.income_by_year_tuple:
        return float(tax_settings.total_income_float)
    income_float = float(tax_settings.total_income_float)
    for year_int, year_income_float in sorted(
        tax_settings.income_by_year_tuple
    ):
        if (
            financial_year_int is not None
            and int(year_int) > int(financial_year_int)
        ):
            break
        income_float = float(year_income_float)
    return income_float


def resolve_surcharge_percent_float(
    tax_settings: TaxSettings,
    financial_year_int: int | None = None,
) -> float:
    """Choose between the manual rate and the statutory slabs.

    Brief:
        The manual mode preserves the older behaviour where the
        user types one rate; the slab mode derives it from the
        taxpayer's income in that year, after marginal relief.

    Arguments:
        tax_settings (TaxSettings): Portfolio tax rules.
        financial_year_int (Optional[int]): Year of the sale.

    Returns:
        float: Surcharge percent before any capital gains cap.

    Warning:
        The capital gains cap is applied by the policy, not here.
        A manually typed rate is used exactly as typed, since no
        income is known to compute relief from.
    """
    if tax_settings.surcharge_mode_str != SURCHARGE_MODE_SLAB_STR:
        return float(tax_settings.surcharge_percent_float)
    return resolve_relieved_surcharge_percent_float(
        resolve_total_income_float(
            tax_settings, financial_year_int
        ),
        tax_settings.surcharge_regime_str,
    )


class ExemptionLedger:
    """Tracks exemption already consumed per bucket and per year."""

    def __init__(self) -> None:
        """Create an empty exemption usage ledger.

        Brief:
            One ledger is shared by every fund of a single run so
            that repeated sales cannot reuse the same exemption.

        Arguments:
            None.

        Returns:
            None: A fresh ledger instance is initialised.

        Warning:
            Never share a ledger between two simulation runs.
        """
        self._consumed_amount_dict: dict[ExemptionKeyTuple, float] = {}

    def build_copy(self) -> ExemptionLedger:
        """Clone the ledger so a dry run cannot consume it.

        Brief:
            The final liquidation estimate must not spend exemption
            that the real simulation still needs.

        Arguments:
            None.

        Returns:
            ExemptionLedger: Independent copy of the usage state.

        Warning:
            The copy diverges as soon as either side consumes.
        """
        copied_ledger = ExemptionLedger()
        copied_ledger._consumed_amount_dict = dict(
            self._consumed_amount_dict
        )
        return copied_ledger

    def consume_exemption_float(
        self,
        fund_name_str: str,
        financial_year_int: int,
        scope_str: str,
        gain_float: float,
        exemption_limit_float: float,
    ) -> float:
        """Reduce a gain by the exemption still available to it.

        Brief:
            Applies as much unused exemption as possible and books
            the consumed amount against the bucket and year.

        Arguments:
            fund_name_str (str): Bucket realizing the gain.
            financial_year_int (int): Financial year of the sale.
            scope_str (str): Exemption scope bucket being used.
            gain_float (float): Gross gain being taxed.
            exemption_limit_float (float): Yearly exemption cap.

        Returns:
            float: Taxable gain remaining after the exemption.

        Warning:
            The exemption is annual, so it resets every April.
        """
        exemption_limit_float = max(0.0, float(exemption_limit_float))
        ledger_key_tuple: ExemptionKeyTuple = (
            fund_name_str,
            int(financial_year_int),
            scope_str,
        )
        consumed_amount_float = self._consumed_amount_dict.get(
            ledger_key_tuple, 0.0
        )
        available_amount_float = max(
            0.0, exemption_limit_float - consumed_amount_float
        )
        applied_amount_float = min(
            available_amount_float, max(0.0, float(gain_float))
        )
        self._consumed_amount_dict[ledger_key_tuple] = (
            consumed_amount_float + applied_amount_float
        )
        return max(0.0, float(gain_float) - applied_amount_float)


class LossLedger:
    """Pools realized capital losses available for set-off.

    Losses are held per bucket *and per financial year of origin*,
    because a capital loss may only be carried forward for eight
    assessment years after the year it was computed in. Pooling
    them into a single running total, as an earlier version did,
    lets a loss booked in year one shelter a gain thirty years
    later and understates the tax due.
    """

    def __init__(self) -> None:
        """Create empty short and long term loss pools.

        Brief:
            Each pool is keyed by the financial year the loss was
            booked in so that stale losses can expire.

        Arguments:
            None.

        Returns:
            None: A fresh loss ledger is initialised.

        Warning:
            Losses expire only when an offset or an expiry sweep
            is requested; the ledger has no clock of its own.
        """
        self._available_loss_dict: dict[LossKeyTuple, float] = {}

    def build_copy(self) -> LossLedger:
        """Clone the pools so a dry run cannot consume them.

        Brief:
            Mirrors the exemption ledger so exit estimates stay
            free of side effects.

        Arguments:
            None.

        Returns:
            LossLedger: Independent copy of the pools.

        Warning:
            The copy diverges as soon as either side consumes.
        """
        copied_ledger = LossLedger()
        copied_ledger._available_loss_dict = dict(
            self._available_loss_dict
        )
        return copied_ledger

    @property
    def available_loss_float(self) -> float:
        """Total loss still available for future set-off.

        Brief:
            Reported so the dashboard can show unused shelter.

        Arguments:
            None.

        Returns:
            float: Sum of every unexpired pool.

        Warning:
            Includes losses that have expired but not yet been
            swept; call expire_stale_losses first for an exact
            figure at a given financial year.
        """
        return sum(self._available_loss_dict.values())

    def expire_stale_losses(self, financial_year_int: int) -> float:
        """Drop losses older than the carry-forward window.

        Brief:
            A loss computed in a financial year may be set off in
            that year and in the eight that follow it. Anything
            older lapses and can never shelter a gain again.

        Arguments:
            financial_year_int (int): Financial year of the sale
                whose set-off is being considered.

        Returns:
            float: Total loss written off by this sweep.

        Warning:
            Expiry is irreversible; the amount is returned purely
            so callers can report it.

        """
        earliest_usable_year_int = (
            int(financial_year_int) - LOSS_CARRY_FORWARD_YEARS_INT
        )
        expired_total_float = 0.0
        surviving_dict: dict[LossKeyTuple, float] = {}
        for loss_key_tuple, amount_float in (
            self._available_loss_dict.items()
        ):
            if loss_key_tuple[1] < earliest_usable_year_int:
                expired_total_float += amount_float
                continue
            surviving_dict[loss_key_tuple] = amount_float
        self._available_loss_dict = surviving_dict
        return expired_total_float

    def record_loss(
        self,
        loss_float: float,
        is_long_term_bool: bool,
        financial_year_int: int,
    ) -> None:
        """Add a realized loss to the matching pool and year.

        Brief:
            Short and long term losses are pooled separately
            because the law restricts what each may offset, and
            each pool is dated so it can expire on schedule.

        Arguments:
            loss_float (float): Positive magnitude of the loss.
            is_long_term_bool (bool): Long term classification.
            financial_year_int (int): Year the loss was computed.

        Returns:
            None: The pool is increased in place.

        Warning:
            Non-positive values are ignored.
        """
        if float(loss_float) <= 0.0:
            return
        bucket_str = (
            LOSS_BUCKET_LONG_TERM_STR
            if is_long_term_bool
            else LOSS_BUCKET_SHORT_TERM_STR
        )
        loss_key_tuple: LossKeyTuple = (
            bucket_str,
            int(financial_year_int),
        )
        self._available_loss_dict[loss_key_tuple] = (
            self._available_loss_dict.get(loss_key_tuple, 0.0)
            + float(loss_float)
        )

    def _consume_bucket_float(
        self,
        bucket_str: str,
        remaining_gain_float: float,
    ) -> tuple[float, float]:
        """Spend one bucket's losses, oldest year first.

        Brief:
            Oldest first is both the taxpayer-favourable order and
            the order that wastes the least shelter, since the
            oldest losses are the ones about to expire.

        Arguments:
            bucket_str (str): Loss bucket being consumed.
            remaining_gain_float (float): Gain still to shelter.

        Returns:
            Tuple[float, float]: Gain left and the loss applied.

        Warning:
            Mutates the pool; callers must not retry a sale.
        """
        applied_total_float = 0.0
        year_list = sorted(
            year_int
            for pool_bucket_str, year_int in (
                self._available_loss_dict
            )
            if pool_bucket_str == bucket_str
        )
        for year_int in year_list:
            if remaining_gain_float <= 0.0:
                break
            loss_key_tuple: LossKeyTuple = (bucket_str, year_int)
            applied_float = min(
                self._available_loss_dict[loss_key_tuple],
                remaining_gain_float,
            )
            self._available_loss_dict[loss_key_tuple] -= (
                applied_float
            )
            if self._available_loss_dict[loss_key_tuple] <= 0.0:
                del self._available_loss_dict[loss_key_tuple]
            remaining_gain_float -= applied_float
            applied_total_float += applied_float
        return remaining_gain_float, applied_total_float

    def offset_gain_float(
        self,
        gain_float: float,
        is_long_term_bool: bool,
        financial_year_int: int,
    ) -> tuple[float, float]:
        """Set available losses against a realized gain.

        Brief:
            Expires losses beyond the carry-forward window, then
            lets a long term gain absorb long term losses before
            short term ones; a short term gain may absorb short
            term losses only.

        Arguments:
            gain_float (float): Gross realized gain.
            is_long_term_bool (bool): Long term classification.
            financial_year_int (int): Financial year of the sale.

        Returns:
            Tuple[float, float]: Remaining gain and the loss used.

        Warning:
            Set-off happens before the yearly exemption, which is
            the order the law prescribes.
        """
        self.expire_stale_losses(financial_year_int)
        remaining_gain_float = max(0.0, float(gain_float))
        used_loss_float = 0.0
        bucket_order_tuple = (
            (LOSS_BUCKET_LONG_TERM_STR, LOSS_BUCKET_SHORT_TERM_STR)
            if is_long_term_bool
            else (LOSS_BUCKET_SHORT_TERM_STR,)
        )
        for bucket_str in bucket_order_tuple:
            if remaining_gain_float <= 0.0:
                break
            (
                remaining_gain_float,
                applied_float,
            ) = self._consume_bucket_float(
                bucket_str, remaining_gain_float
            )
            used_loss_float += applied_float
        return remaining_gain_float, used_loss_float


class CapitalGainsTaxPolicy:
    """Applies one fund's tax rules to each realized gain chunk."""

    def __init__(
        self,
        fund_configuration: FundConfiguration,
        exemption_ledger: ExemptionLedger,
        tax_settings: TaxSettings | None = None,
        loss_ledger: LossLedger | None = None,
    ) -> None:
        """Bind a fund's tax parameters to the shared ledgers.

        Brief:
            Keeps rate lookup, loss set-off and exemption
            bookkeeping in one object.

        Arguments:
            fund_configuration (FundConfiguration): Fund rules.
            exemption_ledger (ExemptionLedger): Shared exemption.
            tax_settings (Optional[TaxSettings]): Portfolio rules.
            loss_ledger (Optional[LossLedger]): Shared loss pools.

        Returns:
            None: A configured policy instance is initialised.

        Warning:
            Exit load and transaction tax are charged by the
            holding, not here.
        """
        self._fund_configuration = fund_configuration
        self._exemption_ledger = exemption_ledger
        self._tax_settings = tax_settings or TaxSettings()
        self._loss_ledger = loss_ledger or LossLedger()

    def build_dry_run_copy(
        self,
        shared_exemption_ledger: ExemptionLedger | None = None,
        shared_loss_ledger: LossLedger | None = None,
    ) -> CapitalGainsTaxPolicy:
        """Clone this policy against throwaway ledgers.

        Brief:
            Lets the engine price a hypothetical full redemption
            without spending the shelter of the real run. When the
            caller supplies ledgers, every fund's estimate draws on
            the *same* throwaway shelter, which is what makes a
            per-taxpayer exemption behave like one allowance rather
            than one per fund.

        Arguments:
            shared_exemption_ledger (Optional[ExemptionLedger]):
                Ledger shared across a whole-portfolio estimate.
            shared_loss_ledger (Optional[LossLedger]): Loss pools
                shared across a whole-portfolio estimate.

        Returns:
            CapitalGainsTaxPolicy: Policy on throwaway ledgers.

        Warning:
            Omitting the shared ledgers gives every fund its own
            private copy, which double counts a portfolio-level
            exemption across funds.
        """
        return CapitalGainsTaxPolicy(
            self._fund_configuration,
            shared_exemption_ledger
            or self._exemption_ledger.build_copy(),
            self._tax_settings,
            shared_loss_ledger or self._loss_ledger.build_copy(),
        )

    def build_shared_dry_run_ledgers_tuple(
        self,
    ) -> tuple[ExemptionLedger, LossLedger]:
        """Copy this policy's ledgers for a shared dry run.

        Brief:
            The engine builds one pair of throwaway ledgers and
            hands the same pair to every fund, so the estimates
            consume one shelter between them.

        Arguments:
            None.

        Returns:
            Tuple[ExemptionLedger, LossLedger]: Fresh copies.

        Warning:
            Copies diverge from the real ledgers immediately; they
            must never be booked back to the run.
        """
        return (
            self._exemption_ledger.build_copy(),
            self._loss_ledger.build_copy(),
        )

    def _derive_tax_year_int(self, sale_date: date) -> int:
        """Label the tax year a sale falls in.

        Brief:
            Every dated bucket in this module - exemption consumed,
            losses booked, losses expiring - is keyed by this, so
            the jurisdiction's tax year has to be asked for in one
            place rather than assumed in four.

        Arguments:
            sale_date (date): Calendar date of the sale.

        Returns:
            int: Calendar year the tax year opened in.

        Warning:
            Changing the start month mid-run would strand shelter
            already booked under the old boundary; the setting is
            fixed for the life of a simulation.
        """
        return derive_financial_year_int(
            sale_date,
            self._tax_settings.tax_year_start_month_int,
        )

    def is_long_term_holding_bool(self, months_held_int: int) -> bool:
        """Decide whether a holding period qualifies as long term.

        Brief:
            Section 2(42A) defines a short-term capital asset as one
            held for *not more than* the threshold, so a holding of
            exactly the threshold is short term. Debt style funds are
            flagged as always short term and never qualify at all.

        Arguments:
            months_held_int (int): Months the lot was held.

        Returns:
            bool: True when long term treatment applies.

        Warning:
            The comparison is strict. Twelve whole months is short
            term; the thirteenth month is what earns the long term
            rate.
        """
        if self._fund_configuration.is_always_short_term_bool:
            return False
        return int(months_held_int) > int(
            self._fund_configuration.long_term_threshold_months_int
        )

    def calculate_tax_breakdown(
        self,
        gain_float: float,
        months_held_int: int,
        sale_date: date,
    ) -> RealizedGainBreakdown:
        """Compute tax and classification for one sale chunk.

        Brief:
            Classifies the gain, books losses, sets off any pooled
            loss, consumes exemption, applies the rate and finally
            adds surcharge and cess.

        Arguments:
            gain_float (float): Realized gain, negative for a loss.
            months_held_int (int): Months the lot was held.
            sale_date (date): Calendar date of the sale.

        Returns:
            RealizedGainBreakdown: Tax, classification and set-off.

        Warning:
            Losses reduce future tax only while set-off is enabled.
        """
        is_long_term_bool = self.is_long_term_holding_bool(
            months_held_int
        )
        if float(gain_float) < 0.0:
            return self._book_loss(
                gain_float, is_long_term_bool, sale_date
            )
        if float(gain_float) == 0.0:
            return RealizedGainBreakdown(0.0, 0.0, 0.0)
        taxable_gain_float, used_loss_float = self._apply_set_off(
            gain_float, is_long_term_bool, sale_date
        )
        tax_amount_float = self._apply_surcharge_and_cess_float(
            self._apply_exemption_float(
                taxable_gain_float, is_long_term_bool, sale_date
            )
            * self._select_tax_rate_float(is_long_term_bool)
            / PERCENT_TOTAL_FLOAT,
            sale_date,
        )
        return RealizedGainBreakdown(
            tax_amount_float,
            0.0 if is_long_term_bool else float(gain_float),
            float(gain_float) if is_long_term_bool else 0.0,
            offset_loss_float=used_loss_float,
        )

    def _book_loss(
        self,
        gain_float: float,
        is_long_term_bool: bool,
        sale_date: date,
    ) -> RealizedGainBreakdown:
        """Record a realized loss and return a zero-tax outcome.

        Brief:
            Losses are pooled for set-off against later gains and
            stamped with the financial year they arose in, which
            is what starts the carry-forward clock.

        Arguments:
            gain_float (float): Negative realized gain.
            is_long_term_bool (bool): Long term classification.
            sale_date (date): Calendar date of the sale.

        Returns:
            RealizedGainBreakdown: Zero tax and the booked loss.

        Warning:
            Losses are ignored entirely when set-off is disabled.
        """
        loss_float = abs(float(gain_float))
        if self._tax_settings.allow_loss_set_off_bool:
            self._loss_ledger.record_loss(
                loss_float,
                is_long_term_bool,
                self._derive_tax_year_int(sale_date),
            )
        return RealizedGainBreakdown(
            0.0, 0.0, 0.0, realized_loss_float=loss_float
        )

    def _apply_set_off(
        self,
        gain_float: float,
        is_long_term_bool: bool,
        sale_date: date,
    ) -> tuple[float, float]:
        """Set pooled losses against a gain when allowed.

        Brief:
            Skipped entirely when the set-off switch is off, which
            models a purely gross planning view.

        Arguments:
            gain_float (float): Gross realized gain.
            is_long_term_bool (bool): Long term classification.
            sale_date (date): Calendar date of the sale.

        Returns:
            Tuple[float, float]: Remaining gain and loss consumed.

        Warning:
            Consumes the shared pool, so order of sales matters.
        """
        if not self._tax_settings.allow_loss_set_off_bool:
            return float(gain_float), 0.0
        return self._loss_ledger.offset_gain_float(
            gain_float,
            is_long_term_bool,
            self._derive_tax_year_int(sale_date),
        )

    def _resolve_surcharge_percent_float(
        self,
        sale_date: date,
    ) -> float:
        """Cap the surcharge at the rate capital gains attract.

        Brief:
            Surcharge on gains taxed under sections 111A and 112A
            is capped at fifteen percent, even for taxpayers whose
            other income attracts a higher rate. Gains on specified
            funds are taxed as ordinary slab income instead, so
            they carry the taxpayer's own surcharge uncapped.

        Arguments:
            sale_date (date): Date of the sale being taxed.

        Returns:
            float: Surcharge percent that actually applies.

        Warning:
            The rate arriving here already carries marginal relief
            in slab mode, so the cap is applied to the relieved
            rate rather than to the raw band rate.
        """
        requested_percent_float = resolve_surcharge_percent_float(
            self._tax_settings,
            self._derive_tax_year_int(sale_date),
        )
        if self._fund_configuration.is_always_short_term_bool:
            return requested_percent_float
        return min(
            requested_percent_float,
            MAXIMUM_CAPITAL_GAINS_SURCHARGE_PERCENT_FLOAT,
        )

    def _apply_surcharge_and_cess_float(
        self,
        base_tax_float: float,
        sale_date: date,
    ) -> float:
        """Gross a base tax up by surcharge and cess.

        Brief:
            Cess is charged on tax plus surcharge, which is the
            order the Income-tax Act prescribes.

        Arguments:
            base_tax_float (float): Tax before additional levies.
            sale_date (date): Date of the sale being taxed.

        Returns:
            float: Tax including surcharge and cess.

        Warning:
            The surcharge is capped for capital gains; see the
            resolver for the rule.
        """
        surcharge_rate_float = (
            self._resolve_surcharge_percent_float(sale_date)
            / PERCENT_TOTAL_FLOAT
        )
        cess_rate_float = (
            float(self._tax_settings.cess_percent_float)
            / PERCENT_TOTAL_FLOAT
        )
        tax_with_surcharge_float = float(base_tax_float) * (
            1.0 + surcharge_rate_float
        )
        return tax_with_surcharge_float * (1.0 + cess_rate_float)

    def _select_tax_rate_float(
        self,
        is_long_term_bool: bool,
    ) -> float:
        """Pick the rate matching the gain classification.

        Brief:
            Small helper that keeps the public method short.

        Arguments:
            is_long_term_bool (bool): Long term classification.

        Returns:
            float: Applicable tax rate in percent.

        Warning:
            Returns the configured value without validation.
        """
        if is_long_term_bool:
            return float(
                self._fund_configuration.long_term_tax_percent_float
            )
        return float(
            self._fund_configuration.short_term_tax_percent_float
        )

    def _resolve_exemption_key_str(self) -> str:
        """Choose the bucket that exemption is tracked against.

        Brief:
            Indian law grants the exemption per taxpayer, so the
            portfolio bucket is the legally correct default.

        Arguments:
            None.

        Returns:
            str: Ledger key identifying the exemption bucket.

        Warning:
            The per-fund bucket understates the tax due.
        """
        if (
            self._tax_settings.exemption_level_str
            == EXEMPTION_LEVEL_PORTFOLIO_STR
        ):
            return PORTFOLIO_LEDGER_KEY_STR
        return self._fund_configuration.name_str

    def _resolve_exemption_limit_float(self) -> float:
        """Choose the exemption cap that applies to this sale.

        Brief:
            The portfolio bucket uses one shared yearly cap; the
            per-fund bucket uses each fund's own cap.

        Arguments:
            None.

        Returns:
            float: Yearly exemption cap in rupees.

        Warning:
            A zero cap disables the exemption entirely.
        """
        if (
            self._tax_settings.exemption_level_str
            == EXEMPTION_LEVEL_PORTFOLIO_STR
        ):
            return float(
                self._tax_settings.portfolio_exemption_amount_float
            )
        return float(self._fund_configuration.exemption_amount_float)

    def _apply_exemption_float(
        self,
        gain_float: float,
        is_long_term_bool: bool,
        sale_date: date,
    ) -> float:
        """Consume exemption when the configured scope allows it.

        Brief:
            A long-term-only scope shields long term gains alone,
            while a total-gains scope shields every realized gain.

        Arguments:
            gain_float (float): Gain remaining after set-off.
            is_long_term_bool (bool): Long term classification.
            sale_date (date): Calendar date of the sale.

        Returns:
            float: Taxable gain after exemption is applied.

        Warning:
            Exemption is consumed per bucket and financial year.
        """
        scope_str = str(self._fund_configuration.exemption_scope_str)
        is_total_scope_bool = (
            scope_str == EXEMPTION_SCOPE_TOTAL_GAINS_STR
        )
        is_long_term_scope_bool = (
            scope_str == EXEMPTION_SCOPE_LONG_TERM_STR
            and is_long_term_bool
        )
        if not (is_total_scope_bool or is_long_term_scope_bool):
            return float(gain_float)
        return self._exemption_ledger.consume_exemption_float(
            fund_name_str=self._resolve_exemption_key_str(),
            financial_year_int=self._derive_tax_year_int(sale_date),
            scope_str=scope_str,
            gain_float=gain_float,
            exemption_limit_float=(
                self._resolve_exemption_limit_float()
            ),
        )


def calculate_exit_charges_float(
    fund_configuration: FundConfiguration,
    sale_value_float: float,
    months_held_int: int,
) -> float:
    """Price the exit load and transaction tax of one sale.

    Brief:
        Exit load applies only inside the fund's own window, while
        the securities transaction tax applies to every redemption.

    Arguments:
        fund_configuration (FundConfiguration): Fund rules.
        sale_value_float (float): Value of the units sold.
        months_held_int (int): Months those units were held.

    Returns:
        float: Total charges deducted from the redemption.

    Warning:
        Charges are not tax; they are not deductible here and are
        reported separately from the capital gains tax.
    """
    if float(sale_value_float) <= 0.0:
        return 0.0
    exit_load_float = 0.0
    if int(months_held_int) < int(
        fund_configuration.exit_load_within_months_int
    ):
        exit_load_float = (
            float(sale_value_float)
            * float(fund_configuration.exit_load_percent_float)
            / PERCENT_TOTAL_FLOAT
        )
    transaction_tax_float = (
        float(sale_value_float)
        * float(
            fund_configuration.transaction_tax_percent_float
        )
        / PERCENT_TOTAL_FLOAT
    )
    return exit_load_float + transaction_tax_float
