"""Sidebar widgets that collect every portfolio level setting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

from investment_journey_simulator.constants import (
    DEFAULT_CESS_PERCENT_FLOAT,
    DEFAULT_DRIFT_BAND_PERCENT_FLOAT,
    DEFAULT_SURCHARGE_PERCENT_FLOAT,
    EQUITY_EXEMPTION_AMOUNT_FLOAT,
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_LEVELS_TUPLE,
    EXPENSE_MODELS_TUPLE,
    FINANCIAL_YEAR_START_MONTH_INT,
    MONTH_SHORT_NAMES_TUPLE,
    MONTHS_IN_YEAR_INT,
    PAUSE_SCOPE_BOTH_STR,
    PAUSE_SCOPES_TUPLE,
    REBALANCE_METHODS_TUPLE,
    REBALANCE_TARGET_MODES_TUPLE,
    REBALANCE_TRIGGER_CALENDAR_STR,
    REBALANCE_TRIGGERS_TUPLE,
    STEPUP_MODE_BOTH_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODES_TUPLE,
    SURCHARGE_MODE_SLAB_STR,
    SURCHARGE_MODES_TUPLE,
    SURCHARGE_REGIME_NEW_STR,
    SURCHARGE_REGIMES_TUPLE,
    TAX_FUNDING_SOURCES_TUPLE,
    WITHDRAWAL_MODE_PERCENT_STR,
    WITHDRAWAL_MODE_SCHEDULE_STR,
    WITHDRAWAL_MODES_TUPLE,
)
from investment_journey_simulator.currency import (
    DEFAULT_CURRENCY_CODE_STR,
    Currency,
    list_currency_code_list,
    resolve_currency,
)
from investment_journey_simulator.formatting import resolve_display_currency
from investment_journey_simulator.models import (
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    SimulationSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.time_utils import (
    count_months_between_dates_int,
)

MINIMUM_HORIZON_YEARS_INT: int = 1
MAXIMUM_HORIZON_YEARS_INT: int = 60
DEFAULT_HORIZON_YEARS_INT: int = 10
DEFAULT_INFLATION_PERCENT_FLOAT: float = 6.0
DEFAULT_GLOBAL_STEPUP_PERCENT_FLOAT: float = 10.0
DEFAULT_SLAB_RATE_PERCENT_FLOAT: float = 30.0
DEFAULT_REBALANCE_INTERVAL_MONTHS_INT: int = 12
DEFAULT_FIXED_WITHDRAWAL_FLOAT: float = 20000.0
SCHEDULE_COLUMN_COUNT_INT: int = 3
TIMING_OPTIONS_TUPLE: tuple = ("Start of Month", "End of Month")


@dataclass(frozen=True)
class SidebarSelections:
    """Everything the sidebar collected for one dashboard run."""

    settings: SimulationSettings
    inflation_percent_float: float
    slab_rate_percent_float: float
    is_stagger_enabled_bool: bool
    expense_model_str: str
    currency: Currency

HELP_CHANGES_HOW_AMOUNTS_ARE_STR: str = (
    "Changes how amounts are written and named. It does not "
    "convert them, and the tax rules stay exactly as you typed "
    "them."
)
HELP_APRIL_FOR_INDIA_JANUARY_STR: str = (
    "April for India, January for the United States, Japan and "
    "most of Europe, July for Australia. It decides when the "
    "yearly exemption resets and when a carried-forward loss "
    "lapses."
)
HELP_SLAB_MODE_DERIVES_THE_STR: str = (
    "Slab mode derives the rate from your total income; manual "
    "mode uses the rate you type."
)
HELP_THE_NEW_REGIME_CAPS_STR: str = (
    "The new regime caps the surcharge at 25%; the old regime "
    "keeps the 37% band."
)
HELP_APPLIES_ABOVE_THE_STATUTORY_STR: str = (
    "Applies above the statutory income thresholds. Enter the "
    "rate that applies to you."
)
HELP_ADDED_ON_TOP_OF_STR: str = (
    "Added on top of the tax and any surcharge."
)
HELP_SHORT_TERM_LOSSES_SHELTER_STR: str = (
    "Short term losses shelter any gain; long term losses shelter "
    "long term gains only."
)
HELP_CONTINUOUS_ACCRUAL_CHARGES_THE_STR: str = (
    "CONTINUOUS_ACCRUAL charges the expense ratio on the net "
    "asset value the way a real fund does. SIMPLE_SUBTRACTION "
    "just deducts it from the return."
)
HELP_PER_TAXPAYER_MATCHES_THE_STR: str = (
    "PER_TAXPAYER matches the law: one yearly exemption shared by "
    "every equity holding. PER_FUND gives each fund its own "
    "exemption, which understates the tax."
)
HELP_THE_MONTH_THE_PLAN_STR: str = (
    "The month the plan opens in. Any month, past or future."
)
HELP_GLOBAL_LIFTS_EVERY_FUND_STR: str = (
    "GLOBAL lifts every fund, PER_FUND uses each fund's own "
    "percentage and BOTH multiplies the two factors."
)
HELP_HOW_MUCH_THE_INSTALMENT_STR: str = (
    "How much the instalment rises each year. Most salaries grow; "
    "a flat amount assumes yours will not."
)
HELP_APPLIES_IN_EVERY_MODE_STR: str = (
    "Applies in every mode, including OFF, so you can raise the "
    "instalment by a fixed sum."
)
HELP_USED_ONLY_TO_RESTATE_STR: str = (
    "Used only to restate figures in today's money. It changes no "
    "cash flow."
)
HELP_LETS_EACH_FUND_BEGIN_STR: str = (
    "Lets each fund begin in its own month rather than all "
    "together."
)
HELP_TRIMS_WINNERS_BACK_TO_STR: str = (
    "Trims winners back to target on a rule. It controls risk and "
    "realises the gains it sells, which are taxed."
)
HELP_CASH_FLOW_REBALANCING_CORRECTS_STR: str = (
    "Cash-flow rebalancing: corrects drift using new instalments "
    "only. Sells nothing, so it realizes no gain and costs no "
    "tax. Works on its own, without switching rebalancing on."
)
HELP_PORTFOLIO_FUNDS_THE_TAX_STR: str = (
    "PORTFOLIO funds the tax by selling more units. OUTSIDE means "
    "you pay it from your bank account, which is what actually "
    "happens for resident investors, since equity redemptions "
    "carry no TDS. The tax is owed either way."
)
HELP_CALENDAR_TRADES_ON_EVERY_STR: str = (
    "CALENDAR trades on every interval. DRIFT_BAND trades "
    "whenever a fund strays past the band. CALENDAR_AND_BAND "
    "checks on the interval but trades only if the band is "
    "breached, which is the cheapest of the three in tax."
)
HELP_HOW_FAR_A_HOLDING_STR: str = (
    "How far a holding may drift from its target before a "
    "rebalance is triggered."
)
HELP_INITIAL_SIP_SPLIT_RESTORES_STR: str = (
    "INITIAL_SIP_SPLIT restores your original instalment "
    "proportions; TARGET_ALLOC_COLUMN uses the target allocation "
    "typed into the fund table."
)
HELP_HOW_OFTEN_THE_PLAN_STR: str = (
    "How often the plan is brought back to its target split."
)
HELP_STARTS_A_REGULAR_WITHDRAWAL_STR: str = (
    "Starts a regular withdrawal from the portfolio."
)
HELP_THE_MONTH_WITHDRAWALS_BEGIN_STR: str = (
    "The month withdrawals begin."
)
HELP_HOW_THE_WITHDRAWAL_CHANGES_STR: str = (
    "How the withdrawal changes each year. Positive keeps pace "
    "with prices."
)
HELP_SELF_ADJUSTING_WITHDRAWAL_TAKES_STR: str = (
    "Self-adjusting withdrawal: takes a fixed share of whatever "
    "the balance is worth that month."
)
HELP_HOW_LONG_THE_MONEY_STR: str = (
    "How long the money stays invested. Longer horizons compound "
    "harder than larger amounts do."
)
HELP_WHETHER_AN_INSTALMENT_EARNS_STR: str = (
    "Whether an instalment earns a return in the month it is paid."
)
HELP_FULL_SELLS_BACK_TO_STR: str = (
    "Full sells back to the exact target. Partial sells only what "
    "is overweight, realising the smaller gain."
)
HELP_A_FIXED_SUM_EACH_STR: str = (
    "A fixed sum each month, a dated schedule, or a share of the "
    "portfolio."
)
HELP_YOUR_MARGINAL_INCOME_TAX_STR: str = (
    "Your marginal income tax rate, used where gains are taxed at "
    "slab."
)


def render_sidebar_selections(
    currency: Currency | None = None,
) -> SidebarSelections:
    """Render the whole sidebar and collect its selections.

    Brief:
        Currency first, then the global, step-up, rebalancing,
        withdrawal and pause sections.

    Arguments:
        currency (Optional[Currency]): Currency already chosen
            elsewhere. Supplying it suppresses this sidebar's own
            picker, so a host page with its own cannot end up
            with two that disagree.

    Returns:
        SidebarSelections: Snapshot of every sidebar input.
    """
    with st.sidebar:
        if currency is None:
            currency = _render_currency_section()
        return _collect_sidebar_selections(currency)


def _collect_sidebar_selections(
    currency: Currency,
) -> SidebarSelections:
    """Render every section below the currency and pack them.

    Brief:
        Split from the entry point purely so each stays inside the
        house function length limit.

    Arguments:
        currency (Currency): Currency already settled on.

    Returns:
        SidebarSelections: Snapshot of every sidebar input.

    Warning:
        Must be called inside the sidebar context manager.
    """
    (
        horizon_years_int,
        portfolio_start_date,
        sip_at_month_start_bool,
    ) = _render_global_section()
    stepup_settings = _render_stepup_section(currency)
    inflation_percent_float = _render_inflation_section()
    is_stagger_enabled_bool = _render_stagger_section()
    rebalance_settings = _render_rebalance_section()
    withdrawal_settings = _render_withdrawal_section(
        portfolio_start_date, currency
    )
    pause_settings = _render_pause_section(portfolio_start_date)
    slab_rate_percent_float = _render_slab_rate_section()
    tax_settings, expense_model_str = _render_tax_section(currency)
    return SidebarSelections(
        settings=SimulationSettings(
            horizon_years_int=horizon_years_int,
            portfolio_start_date=portfolio_start_date,
            sip_at_month_start_bool=sip_at_month_start_bool,
            stepup=stepup_settings,
            withdrawal=withdrawal_settings,
            pauses=pause_settings,
            rebalance=rebalance_settings,
            tax=tax_settings,
        ),
        inflation_percent_float=inflation_percent_float,
        slab_rate_percent_float=slab_rate_percent_float,
        is_stagger_enabled_bool=is_stagger_enabled_bool,
        expense_model_str=expense_model_str,
        currency=currency,
    )


def _render_currency_section() -> Currency:
    """Collect the currency every amount is written in.

    Brief:
        Placed first because it changes how every figure below is
        grouped, named and symbolised.

    Arguments:
        None.

    Returns:
        Currency: The chosen currency.

    Warning:
        This changes presentation only. It converts nothing, and
        it does not alter the tax rules, which stay as typed.
    """
    st.subheader("Currency")
    code_list = list_currency_code_list()
    return resolve_currency(
        str(
            st.selectbox(
                "Show every amount in",
                code_list,
                index=code_list.index(DEFAULT_CURRENCY_CODE_STR),
                format_func=lambda code_str: resolve_currency(
                    code_str
                ).label_str,
                help=HELP_CHANGES_HOW_AMOUNTS_ARE_STR,
            )
        )
    )


def _render_tax_year_start_month_int() -> int:
    """Collect the month the tax year opens in.

    Brief:
        This is the boundary the annual exemption resets on and
        the one a carried-forward loss expires against, so it has
        to follow the jurisdiction rather than be assumed.

    Arguments:
        None.

    Returns:
        int: Month number, one for January to twelve for December.

    Warning:
        Resolution is a whole month, so the United Kingdom's
        6 April start cannot be expressed exactly.
    """
    return int(
        st.selectbox(
            "Tax year starts in",
            list(range(1, MONTHS_IN_YEAR_INT + 1)),
            index=FINANCIAL_YEAR_START_MONTH_INT - 1,
            format_func=lambda month_int: MONTH_SHORT_NAMES_TUPLE[
                month_int - 1
            ],
            help=HELP_APRIL_FOR_INDIA_JANUARY_STR,
        )
    )


def _render_tax_section(
    currency: Currency | None = None,
) -> tuple[TaxSettings, str]:
    """Collect portfolio level tax and expense choices.

    Brief:
        Tax year, exemption, exit tax, expense and levies.

    Arguments:
        currency (Optional[Currency]): Currency to label
            every amount in this section with.

    Returns:
        Tuple[TaxSettings, str]: Tax settings and expense model.

    Warning:
        The per-fund exemption level understates the tax due.
    """
    st.divider()
    st.subheader("Taxation & expense model")
    tax_year_start_month_int = _render_tax_year_start_month_int()
    (
        exemption_level_str,
        portfolio_exemption_amount_float,
    ) = _render_exemption_controls(currency)
    apply_final_liquidation_tax_bool = bool(
        st.toggle(
            "Show value after a full exit on the last day",
            value=True,
            help="Prices the tax and charges owed on exit.",
        )
    )
    expense_model_str = _render_expense_model_str()
    levy_tuple = _render_additional_levies(currency)
    return (
        _build_tax_settings(
            exemption_level_str,
            float(portfolio_exemption_amount_float),
            apply_final_liquidation_tax_bool,
            levy_tuple,
            tax_year_start_month_int,
        ),
        expense_model_str,
    )


def _build_tax_settings(
    exemption_level_str: str,
    portfolio_exemption_amount_float: float,
    apply_final_liquidation_tax_bool: bool,
    levy_tuple: tuple,
    tax_year_start_month_int: int = FINANCIAL_YEAR_START_MONTH_INT,
) -> TaxSettings:
    """Pack the collected tax choices into one settings object.

    Brief:
        Split out so the section renderer stays short.

    Arguments:
        exemption_level_str (str): Aggregation level.
        portfolio_exemption_amount_float (float): Cap.
        apply_final_liquidation_tax_bool (bool): Exit tax.
        levy_tuple (tuple): Output of the levies renderer.
        tax_year_start_month_int (int): Month the tax year
            opens in, which moves the exemption reset.

    Returns:
        TaxSettings: Portfolio level tax rules.
    """
    (
        surcharge_mode_str,
        surcharge_regime_str,
        total_income_float,
        surcharge_percent_float,
        cess_percent_float,
        allow_loss_set_off_bool,
    ) = levy_tuple
    return TaxSettings(
        exemption_level_str=exemption_level_str,
        portfolio_exemption_amount_float=(
            portfolio_exemption_amount_float
        ),
        apply_final_liquidation_tax_bool=(
            apply_final_liquidation_tax_bool
        ),
        surcharge_percent_float=surcharge_percent_float,
        cess_percent_float=cess_percent_float,
        allow_loss_set_off_bool=allow_loss_set_off_bool,
        surcharge_mode_str=surcharge_mode_str,
        surcharge_regime_str=surcharge_regime_str,
        total_income_float=total_income_float,
        tax_year_start_month_int=tax_year_start_month_int,
    )


def _render_surcharge_controls(
    currency: Currency | None = None,
) -> tuple[str, str, float, float]:
    """Collect the surcharge mode and its inputs.

    Brief:
        Either the taxpayer's own rate, or the statutory slab
        derived from total income under the chosen regime.

    Arguments:
        None.

    Returns:
        Tuple[str, str, float, float]: Mode, regime, total income
            and the manually entered surcharge percent.

    Warning:
        Marginal relief is not modelled, so a total income just
        over a slab floor is charged the full band rate.
    """
    surcharge_mode_str = str(
        st.radio(
            "Surcharge",
            list(SURCHARGE_MODES_TUPLE),
            horizontal=True,
            help=HELP_SLAB_MODE_DERIVES_THE_STR,
        )
    )
    if surcharge_mode_str == SURCHARGE_MODE_SLAB_STR:
        regime_str, income_float = _render_surcharge_slab_inputs(
            currency
        )
        return (
            surcharge_mode_str,
            regime_str,
            income_float,
            DEFAULT_SURCHARGE_PERCENT_FLOAT,
        )
    return (
        surcharge_mode_str,
        SURCHARGE_REGIME_NEW_STR,
        0.0,
        _render_manual_surcharge_percent_float(),
    )


def _render_surcharge_slab_inputs(
    currency: Currency | None = None,
) -> tuple[str, float]:
    """Collect the regime and total income for slab mode.

    Brief:
        The slab table differs between regimes only above two
        crore, where the old regime keeps a thirty-seven percent
        band the new regime dropped.

    Arguments:
        None.

    Returns:
        Tuple[str, float]: Regime identifier and total income.

    Warning:
        Total income means income from every head, not just the
        gains this tool simulates.
    """
    regime_str = str(
        st.radio(
            "Regime",
            list(SURCHARGE_REGIMES_TUPLE),
            horizontal=True,
            help=HELP_THE_NEW_REGIME_CAPS_STR,
        )
    )
    symbol_str = resolve_display_currency(currency).symbol_str
    income_float = float(
        st.number_input(
            f"Total income for the year ({symbol_str})",
            min_value=0.0,
            value=0.0,
            step=100000.0,
        )
    )
    return regime_str, income_float


def _render_manual_surcharge_percent_float() -> float:
    """Collect a surcharge rate the taxpayer supplies directly.

    Brief:
        Preserves the original behaviour for anyone who already
        knows the rate that applies to them.

    Arguments:
        None.

    Returns:
        float: Surcharge percent before any capital gains cap.

    Warning:
        The 15% cap on gains taxed under sections 111A and 112A
        still applies on top of whatever is entered here.
    """
    return float(
        st.number_input(
            "Surcharge % on tax",
            min_value=0.0,
            max_value=40.0,
            value=DEFAULT_SURCHARGE_PERCENT_FLOAT,
            step=1.0,
            help=HELP_APPLIES_ABOVE_THE_STATUTORY_STR,
        )
    )


def _render_additional_levies(
    currency: Currency | None = None,
) -> tuple[str, str, float, float, float, bool]:
    """Collect surcharge, cess and the loss set-off switch.

    Brief:
        Cess is charged on tax plus surcharge, and booked losses
        shelter gains before the exemption applies.

    Arguments:
        currency (Optional[Currency]): Label currency.

    Returns:
        Tuple[str, str, float, float, float, bool]: Mode,
            regime, income, surcharge, cess and set-off.

    Warning:
        Surcharge on gains under sections 111A and 112A is
        capped at 15% regardless of what this returns.
    """
    with st.expander("Surcharge, cess and loss set-off"):
        (
            surcharge_mode_str,
            surcharge_regime_str,
            total_income_float,
            surcharge_percent_float,
        ) = _render_surcharge_controls(currency)
        cess_percent_float = st.number_input(
            "Health and education cess % on tax",
            help=HELP_ADDED_ON_TOP_OF_STR,
            min_value=0.0,
            max_value=20.0,
            value=DEFAULT_CESS_PERCENT_FLOAT,
            step=0.5,
        )
        allow_loss_set_off_bool = st.toggle(
            "Set booked losses off against later gains",
            value=True,
            help=HELP_SHORT_TERM_LOSSES_SHELTER_STR,
        )
    return (
        surcharge_mode_str,
        surcharge_regime_str,
        float(total_income_float),
        float(surcharge_percent_float),
        float(cess_percent_float),
        bool(allow_loss_set_off_bool),
    )


def _render_expense_model_str() -> str:
    """Collect how the expense ratio is charged to the fund.

    Brief:
        Continuous accrual matches how a real fund deducts its
        total expense ratio from the net asset value.

    Arguments:
        None.

    Returns:
        str: Selected expense model identifier.

    Warning:
        The simple model slightly understates the drag, because it
        ignores the interaction between return and expense.
    """
    return st.radio(
        "Expense ratio model",
        list(EXPENSE_MODELS_TUPLE),
        index=1,
        help=HELP_CONTINUOUS_ACCRUAL_CHARGES_THE_STR,
    )


def _render_exemption_controls(
    currency: Currency | None = None,
) -> tuple[str, float]:
    """Collect how the yearly capital gains exemption is shared.

    Brief:
        The legally correct default is one exemption per taxpayer
        across every equity holding.

    Arguments:
        None.

    Returns:
        Tuple[str, float]: Aggregation level and yearly cap.

    Warning:
        The per-fund level multiplies the shelter by the number of
        funds and therefore understates the tax due.
    """
    exemption_level_str = st.radio(
        "Exemption is tracked",
        list(EXEMPTION_LEVELS_TUPLE),
        index=0,
        help=HELP_PER_TAXPAYER_MATCHES_THE_STR,
    )
    symbol_str = resolve_display_currency(currency).symbol_str
    portfolio_exemption_amount_float = st.number_input(
        f"Yearly exemption for the whole portfolio "
        f"({symbol_str})",
        min_value=0.0,
        value=EQUITY_EXEMPTION_AMOUNT_FLOAT,
        step=10000.0,
        help=(
            "Applied once across every fund, per taxpayer per "
            "year, rather than once per fund."
        ),
        disabled=exemption_level_str
        != EXEMPTION_LEVEL_PORTFOLIO_STR,
    )
    return exemption_level_str, float(
        portfolio_exemption_amount_float
    )


def _render_global_section() -> tuple[int, date, bool]:
    """Collect horizon, start date and instalment timing.

    Brief:
        These three inputs define the simulation grid itself.

    Arguments:
        None.

    Returns:
        Tuple[int, date, bool]: Horizon in years, start date and
            the start-of-month timing flag.

    Warning:
        Changing the start date shifts every schedule with it.
    """
    st.header("Global Settings")
    horizon_years_int = st.slider(
        "Investment Horizon (years)",
        MINIMUM_HORIZON_YEARS_INT,
        MAXIMUM_HORIZON_YEARS_INT,
        DEFAULT_HORIZON_YEARS_INT,
        1,
        help=HELP_HOW_LONG_THE_MONEY_STR,
    )
    timing_label_str = st.radio(
        "SIP Timing",
        list(TIMING_OPTIONS_TUPLE),
        index=0,
        help=HELP_WHETHER_AN_INSTALMENT_EARNS_STR,
    )
    portfolio_start_date = st.date_input(
        "Portfolio Start Date",
        value=date.today(),
        help=HELP_THE_MONTH_THE_PLAN_STR,
    )
    return (
        int(horizon_years_int),
        portfolio_start_date,
        timing_label_str == TIMING_OPTIONS_TUPLE[0],
    )


def _render_stepup_section(
    currency: Currency | None = None,
) -> StepUpSettings:
    """Collect the yearly escalation rules for contributions.

    Brief:
        The global percentage is only editable in the
        modes that actually consume it.

    Arguments:
        currency (Optional[Currency]): Label currency.

    Returns:
        StepUpSettings: Escalation configuration.
    """
    st.divider()
    st.subheader("Step-up SIP")
    mode_str = st.radio(
        "Step-up mode",
        list(STEPUP_MODES_TUPLE),
        index=0,
        help=HELP_GLOBAL_LIFTS_EVERY_FUND_STR,
    )
    global_stepup_percent_float = st.number_input(
        "Global step-up % per year",
        help=HELP_HOW_MUCH_THE_INSTALMENT_STR,
        min_value=0.0,
        max_value=100.0,
        value=DEFAULT_GLOBAL_STEPUP_PERCENT_FLOAT,
        step=0.5,
        disabled=mode_str
        not in (STEPUP_MODE_GLOBAL_STR, STEPUP_MODE_BOTH_STR),
    )
    (
        interval_months_int,
        first_stepup_month_index_int,
        fixed_increment_amount_float,
    ) = _render_stepup_refinements(mode_str, currency)
    return StepUpSettings(
        mode_str=mode_str,
        global_stepup_percent_float=float(
            global_stepup_percent_float
        ),
        interval_months_int=interval_months_int,
        first_stepup_month_index_int=first_stepup_month_index_int,
        fixed_increment_amount_float=fixed_increment_amount_float,
    )


def _render_stepup_refinements(
    mode_str: str,
    currency: Currency | None = None,
) -> tuple[int, int, float]:
    """Collect how often and how the instalment escalates.

    Brief:
        Escalate every N months, delay the first increase,
        or add a flat cash amount.

    Arguments:
        mode_str (str): Selected escalation mode.
        currency (Optional[Currency]): Label currency.

    Returns:
        Tuple[int, int, float]: Interval, delay, increment.
    """
    symbol_str = resolve_display_currency(currency).symbol_str
    with st.expander("Step-up timing and fixed increments"):
        interval_months_int = st.number_input(
            "Escalate every N months",
            min_value=0,
            max_value=120,
            value=MONTHS_IN_YEAR_INT,
            step=1,
            help="12 means once a year. 0 disables escalation.",
        )
        first_stepup_month_index_int = st.number_input(
            "Delay the first increase by N months",
            min_value=0,
            max_value=240,
            value=0,
            step=1,
            help="0 keeps the usual anniversary schedule.",
        )
        fixed_increment_amount_float = st.number_input(
            f"Add a flat {symbol_str} amount each step",
            min_value=0.0,
            value=0.0,
            step=500.0,
            help=HELP_APPLIES_IN_EVERY_MODE_STR,
        )
    return (
        int(interval_months_int),
        int(first_stepup_month_index_int),
        float(fixed_increment_amount_float),
    )


def _render_inflation_section() -> float:
    """Collect the inflation rate used for the real return run.

    Brief:
        Drives the second simulation shown in today's rupees.

    Arguments:
        None.

    Returns:
        float: Annual inflation percent.

    Warning:
        Inflation never changes the nominal simulation.
    """
    st.divider()
    st.subheader("Inflation")
    return float(
        st.number_input(
            "Inflation % per year",
            help=HELP_USED_ONLY_TO_RESTATE_STR,
            min_value=-5.0,
            max_value=25.0,
            value=DEFAULT_INFLATION_PERCENT_FLOAT,
            step=0.5,
        )
    )


def _render_stagger_section() -> bool:
    """Collect whether funds may start on different dates.

    Brief:
        When disabled every fund is forced to the portfolio start.

    Arguments:
        None.

    Returns:
        bool: True when staggered start dates are allowed.

    Warning:
        Turning this off overwrites the start dates typed into the
        fund table.
    """
    st.divider()
    st.subheader("Start Dates")
    return bool(
        st.toggle(
            "Allow different SIP start dates per fund",
            value=False,
            help=HELP_LETS_EACH_FUND_BEGIN_STR,
        )
    )


def _render_rebalance_section() -> RebalanceSettings:
    """Collect the periodic rebalancing rules.

    Controls stay disabled while rebalancing is off. Rebalancing
    realises gains, and a realised gain is taxed.

    Returns:
        RebalanceSettings: Selected configuration.
    """
    st.divider()
    st.subheader("Rebalancing")
    is_enabled_bool = bool(
        st.toggle(
            "Enable periodic rebalancing",
            value=False,
            help=HELP_TRIMS_WINNERS_BACK_TO_STR,
        )
    )
    target_mode_str, interval_months_int = _render_rebalance_target(
        is_enabled_bool
    )
    method_str = st.radio(
        "Rebalance method",
        list(REBALANCE_METHODS_TUPLE),
        index=0,
        disabled=not is_enabled_bool,
        help=HELP_FULL_SELLS_BACK_TO_STR,
    )
    tax_funding_str = _render_tax_funding_str(is_enabled_bool)
    trigger_str, drift_band_percent_float = _render_rebalance_trigger(
        is_enabled_bool
    )
    use_contribution_steering_bool = _render_steering_bool()
    return RebalanceSettings(
        is_enabled_bool=is_enabled_bool,
        interval_months_int=int(interval_months_int)
        if is_enabled_bool
        else 0,
        method_str=method_str,
        target_mode_str=target_mode_str,
        tax_funding_str=tax_funding_str,
        trigger_str=trigger_str,
        drift_band_percent_float=drift_band_percent_float,
        use_contribution_steering_bool=(
            use_contribution_steering_bool
        ),
    )


def _render_steering_bool() -> bool:
    """Collect whether new money is steered to underweight funds.

    Brief:
        Cash-flow rebalancing corrects drift with fresh
        instalments, so it sells nothing and costs no tax.

    Arguments:
        None.

    Returns:
        bool: True when contribution steering is enabled.

    Warning:
        Steering alone cannot fix large drift once the corpus
        dwarfs the monthly instalment.
    """
    return bool(
        st.toggle(
            "Steer new SIP money to underweight funds",
            value=False,
            help=HELP_CASH_FLOW_REBALANCING_CORRECTS_STR,
        )
    )


def _render_tax_funding_str(is_enabled_bool: bool) -> str:
    """Collect who pays the tax that rebalancing realizes.

    Brief:
        Resident investors normally pay it from their own bank
        account, because equity redemptions carry no withholding.

    Arguments:
        is_enabled_bool (bool): Rebalancing switch state.

    Returns:
        str: Selected funding source.

    Warning:
        Choosing OUTSIDE does not make the tax disappear; it is
        still reported as a liability.
    """
    return st.radio(
        "Pay rebalancing tax from",
        list(TAX_FUNDING_SOURCES_TUPLE),
        index=0,
        disabled=not is_enabled_bool,
        help=HELP_PORTFOLIO_FUNDS_THE_TAX_STR,
    )


def _render_rebalance_trigger(
    is_enabled_bool: bool,
) -> tuple[str, float]:
    """Collect what makes a rebalance fire.

    Brief:
        Calendar dates, a drift band, or a calendar check that only
        trades when the drift band is breached.

    Arguments:
        is_enabled_bool (bool): Rebalancing switch state.

    Returns:
        Tuple[str, float]: Trigger mode and band width in points.

    Warning:
        A band of zero disables the band part of the trigger.
    """
    trigger_str = st.radio(
        "Rebalance trigger",
        list(REBALANCE_TRIGGERS_TUPLE),
        index=0,
        disabled=not is_enabled_bool,
        help=HELP_CALENDAR_TRADES_ON_EVERY_STR,
    )
    drift_band_percent_float = st.number_input(
        "Drift band (percentage points)",
        help=HELP_HOW_FAR_A_HOLDING_STR,
        min_value=0.0,
        max_value=50.0,
        value=DEFAULT_DRIFT_BAND_PERCENT_FLOAT,
        step=0.5,
        disabled=not is_enabled_bool
        or trigger_str == REBALANCE_TRIGGER_CALENDAR_STR,
    )
    return trigger_str, float(drift_band_percent_float)


def _render_rebalance_target(
    is_enabled_bool: bool,
) -> tuple[str, int]:
    """Collect the rebalancing target basis and its interval.

    Brief:
        Both controls stay disabled while rebalancing is off.

    Arguments:
        is_enabled_bool (bool): Rebalancing switch state.

    Returns:
        Tuple[str, int]: Target mode and interval in months.

    Warning:
        Short intervals realize gains far more often.
    """
    target_mode_str = st.radio(
        "Rebalance target",
        list(REBALANCE_TARGET_MODES_TUPLE),
        index=0,
        disabled=not is_enabled_bool,
        help=HELP_INITIAL_SIP_SPLIT_RESTORES_STR,
    )
    interval_months_int = st.number_input(
        "Rebalance every N months",
        help=HELP_HOW_OFTEN_THE_PLAN_STR,
        min_value=1,
        max_value=120,
        value=DEFAULT_REBALANCE_INTERVAL_MONTHS_INT,
        step=1,
        disabled=not is_enabled_bool,
    )
    return target_mode_str, int(interval_months_int)


def _render_withdrawal_section(
    portfolio_start_date: date,
    currency: Currency | None = None,
) -> WithdrawalSettings:
    """Collect the systematic withdrawal rules.

    A flat amount, a twelve month schedule, or a share of the
    corpus, each with its own yearly change.

    Arguments:
        portfolio_start_date (date): First simulated month.
        currency (Optional[Currency]): Label currency.

    Returns:
        WithdrawalSettings: Selected configuration.
    """
    st.divider()
    st.subheader("SWP (Withdrawals)")
    is_enabled_bool = _render_withdrawal_toggle_bool()
    start_date, mode_str = _render_withdrawal_basics(
        is_enabled_bool, portfolio_start_date
    )
    (
        annual_change_percent_float,
        fixed_amount_float,
    ) = _render_withdrawal_amounts(
        is_enabled_bool, mode_str, currency
    )
    portfolio_percent_float = _render_corpus_percent_float(
        is_enabled_bool and mode_str == WITHDRAWAL_MODE_PERCENT_STR
    )
    schedule_list, change_list = _render_withdrawal_schedule(
        is_enabled_bool and mode_str == WITHDRAWAL_MODE_SCHEDULE_STR
    )
    return WithdrawalSettings(
        portfolio_percent_float=portfolio_percent_float,
        is_enabled_bool=is_enabled_bool,
        start_month_index_int=max(
            0,
            count_months_between_dates_int(
                portfolio_start_date, start_date
            ),
        ),
        mode_str=mode_str,
        fixed_amount_float=fixed_amount_float,
        monthly_schedule_list=schedule_list,
        annual_change_percent_float=annual_change_percent_float,
        monthly_change_percent_list=change_list,
    )


def _render_withdrawal_toggle_bool() -> bool:
    """Whether the plan takes money out at all."""
    return bool(
        st.toggle(
            "Enable SWP",
            value=False,
            help=HELP_STARTS_A_REGULAR_WITHDRAWAL_STR,
        )
    )


def _render_withdrawal_basics(
    is_enabled_bool: bool,
    portfolio_start_date: date,
) -> tuple[date, str]:
    """Collect the withdrawal start date and the payout mode.

    Brief:
        These two inputs decide when withdrawals begin and which
        amount controls become relevant.

    Arguments:
        is_enabled_bool (bool): Withdrawal switch state.
        portfolio_start_date (date): First simulated month.

    Returns:
        Tuple[date, str]: Start date and selected mode.

    Warning:
        A start date before the portfolio start is clamped later.
    """
    start_date = st.date_input(
        "SWP Start Date",
        help=HELP_THE_MONTH_WITHDRAWALS_BEGIN_STR,
        value=portfolio_start_date,
        disabled=not is_enabled_bool,
    )
    mode_str = st.radio(
        "SWP mode",
        list(WITHDRAWAL_MODES_TUPLE),
        index=0,
        disabled=not is_enabled_bool,
        help=HELP_A_FIXED_SUM_EACH_STR,
    )
    return start_date, mode_str


def _render_withdrawal_amounts(
    is_enabled_bool: bool,
    mode_str: str,
    currency: Currency | None = None,
) -> tuple[float, float]:
    """Collect the yearly change and the flat monthly amount.

    Brief:
        The flat amount is only editable in the fixed mode.

    Arguments:
        is_enabled_bool (bool): Withdrawal switch state.
        mode_str (str): Selected withdrawal mode.
        currency (Optional[Currency]): Label currency.

    Returns:
        Tuple[float, float]: Yearly change percent and the flat
            monthly withdrawal amount.

    Warning:
        A negative yearly change shrinks the withdrawal over time.
    """
    symbol_str = resolve_display_currency(currency).symbol_str
    annual_change_percent_float = st.number_input(
        "SWP annual change % (+/-)",
        help=HELP_HOW_THE_WITHDRAWAL_CHANGES_STR,
        min_value=-50.0,
        max_value=50.0,
        value=0.0,
        step=0.5,
        disabled=not is_enabled_bool,
    )
    fixed_amount_float = st.number_input(
        f"Fixed withdrawal per month ({symbol_str})",
        min_value=0.0,
        value=DEFAULT_FIXED_WITHDRAWAL_FLOAT,
        step=1000.0,
        disabled=not (
            is_enabled_bool
            and mode_str != WITHDRAWAL_MODE_SCHEDULE_STR
        ),
    )
    return float(annual_change_percent_float), float(
        fixed_amount_float
    )


def _render_corpus_percent_float(is_enabled_bool: bool) -> float:
    """Collect the self-adjusting percentage withdrawal rate.

    Brief:
        Taking a share of the corpus rather than a fixed rupee
        amount means the plan can never fully exhaust itself.

    Arguments:
        is_enabled_bool (bool): Whether this mode is selected.

    Returns:
        float: Monthly withdrawal rate in percent of corpus.

    Warning:
        Real income falls whenever the market does.
    """
    return float(
        st.number_input(
            "Withdraw % of balance per month",
            min_value=0.0,
            max_value=100.0,
            value=0.5,
            step=0.1,
            disabled=not is_enabled_bool,
            help=HELP_SELF_ADJUSTING_WITHDRAWAL_TAKES_STR,
        )
    )


def _render_withdrawal_schedule(
    is_visible_bool: bool,
) -> tuple[list[float], list[float]]:
    """Collect the twelve month withdrawal schedule grid.

    Brief:
        Each calendar month gets its own base amount and its own
        yearly change percentage.

    Arguments:
        is_visible_bool (bool): Render the grid when True.

    Returns:
        Tuple[List[float], List[float]]: Base amounts and yearly
            change percentages, both indexed January to December.

    Warning:
        Returns twelve zeros when the grid is hidden.
    """
    if not is_visible_bool:
        return (
            [0.0] * MONTHS_IN_YEAR_INT,
            [0.0] * MONTHS_IN_YEAR_INT,
        )
    st.caption("Monthly schedule (Jan..Dec), repeats every year")
    schedule_list = _render_month_grid_list(
        key_prefix_str="withdrawal_amount",
        label_suffix_str="",
        minimum_float=0.0,
        maximum_float=None,
        step_float=1000.0,
    )
    st.caption("Optional per-month change % per year (Jan..Dec)")
    change_list = _render_month_grid_list(
        key_prefix_str="withdrawal_change",
        label_suffix_str=" %/yr",
        minimum_float=-50.0,
        maximum_float=50.0,
        step_float=0.5,
    )
    return schedule_list, change_list


def _render_month_grid_list(
    key_prefix_str: str,
    label_suffix_str: str,
    minimum_float: float,
    maximum_float,
    step_float: float,
) -> list[float]:
    """Render one twelve month grid of numeric inputs.

    Brief:
        Shared by the withdrawal amount grid and the per-month
        change grid so both stay visually identical.

    Arguments:
        key_prefix_str (str): Prefix of the widget state keys.
        label_suffix_str (str): Text appended to each month name.
        minimum_float (float): Lowest accepted value.
        maximum_float: Highest accepted value, or None.
        step_float (float): Increment of the input controls.

    Returns:
        List[float]: Twelve values indexed January to December.

    Warning:
        Widget keys must stay unique across the whole sidebar.
    """
    value_list = [0.0] * MONTHS_IN_YEAR_INT
    column_list = st.columns(SCHEDULE_COLUMN_COUNT_INT)
    for month_index_int in range(MONTHS_IN_YEAR_INT):
        with column_list[
            month_index_int % SCHEDULE_COLUMN_COUNT_INT
        ]:
            value_list[month_index_int] = float(
                st.number_input(
                    MONTH_SHORT_NAMES_TUPLE[month_index_int]
                    + label_suffix_str,
                    min_value=minimum_float,
                    max_value=maximum_float,
                    value=0.0,
                    step=step_float,
                    help=(
                        "This month's figure. The twelve repeat "
                        "every year."
                    ),
                    key=f"{key_prefix_str}_{month_index_int}",
                )
            )
    return value_list


def _render_pause_section(
    portfolio_start_date: date,
) -> PauseSettings:
    """Collect recurring and one-off pauses for both cash flows.

    Brief:
        Recurring months repeat every year while the range table
        covers explicit windows such as a career break.

    Arguments:
        portfolio_start_date (date): First simulated month.

    Returns:
        PauseSettings: Selected pause configuration.

    Warning:
        Paused instalments and withdrawals are skipped for good;
        they are never made up later.
    """
    st.divider()
    st.subheader("Gaps / Pauses (SIP & SWP)")
    sip_pause_months_list = _render_recurring_pause_list(
        "Pause SIP in these months (repeats yearly)"
    )
    withdrawal_pause_months_list = _render_recurring_pause_list(
        "Pause SWP in these months (repeats yearly)"
    )
    pause_range_dataframe = _render_pause_range_dataframe(
        portfolio_start_date
    )
    return PauseSettings(
        sip_pause_months_list=sip_pause_months_list,
        withdrawal_pause_months_list=withdrawal_pause_months_list,
        pause_ranges_list=build_pause_ranges_list(
            pause_range_dataframe
        ),
    )


def _render_recurring_pause_list(label_str: str) -> list[int]:
    """Render one multi-select of yearly repeating pause months.

    Brief:
        Months are shown by their short names but stored as their
        calendar numbers.

    Arguments:
        label_str (str): Label shown above the control.

    Returns:
        List[int]: Selected month numbers, January being one.

    Warning:
        The same months are paused in every year of the horizon.
    """
    selected_month_list = st.multiselect(
        label_str,
        options=list(range(1, MONTHS_IN_YEAR_INT + 1)),
        default=[],
        format_func=lambda month_int: MONTH_SHORT_NAMES_TUPLE[
            month_int - 1
        ],
    )
    return [int(month_int) for month_int in selected_month_list]


def _render_pause_range_dataframe(
    portfolio_start_date: date,
) -> pd.DataFrame:
    """Render the editable table of irregular pause windows.

    Brief:
        Each row names a window and the cash flow it suspends.

    Arguments:
        portfolio_start_date (date): First simulated month.

    Returns:
        pd.DataFrame: Edited pause range table.

    Warning:
        Both boundary months are included in the pause.
    """
    st.caption("Irregular pause ranges (both months inclusive).")
    return st.data_editor(
        pd.DataFrame(
            [
                {
                    "Start": portfolio_start_date,
                    "End": portfolio_start_date,
                    "Apply To": PAUSE_SCOPE_BOTH_STR,
                }
            ]
        ),
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Start": st.column_config.DateColumn(),
            "End": st.column_config.DateColumn(),
            "Apply To": st.column_config.SelectboxColumn(
                options=list(PAUSE_SCOPES_TUPLE)
            ),
        },
        key="pause_range_editor",
    )


def build_pause_ranges_list(
    pause_range_dataframe: pd.DataFrame,
) -> list[PauseRange]:
    """Convert the pause range table into typed range objects.

    Brief:
        Rows with a missing start or end date are dropped so the
        engine never has to test for blanks.

    Arguments:
        pause_range_dataframe (pd.DataFrame): Editor table.

    Returns:
        List[PauseRange]: Valid pause ranges only.

    Warning:
        Reversed ranges survive this conversion but never match a
        month, so they behave as if absent.
    """
    if pause_range_dataframe is None:
        return []
    pause_ranges_list: list[PauseRange] = []
    for _, range_row in pause_range_dataframe.iterrows():
        start_value = range_row.get("Start")
        end_value = range_row.get("End")
        if pd.isna(start_value) or pd.isna(end_value):
            continue
        pause_ranges_list.append(
            PauseRange(
                start_date=_coerce_to_date(start_value),
                end_date=_coerce_to_date(end_value),
                scope_str=str(
                    range_row.get("Apply To", PAUSE_SCOPE_BOTH_STR)
                ),
            )
        )
    return pause_ranges_list


def _coerce_to_date(cell_value) -> date:
    """Normalise a table cell into a plain date object.

    Brief:
        The data editor may return timestamps or dates depending
        on how the cell was filled.

    Arguments:
        cell_value: Raw value taken from the editor table.

    Returns:
        date: Equivalent plain date.

    Warning:
        Any time component is discarded.
    """
    if isinstance(cell_value, pd.Timestamp):
        return cell_value.date()
    return cell_value


def _render_slab_rate_section() -> float:
    """Collect the income tax slab rate for the debt preset.

    Brief:
        Debt style funds are taxed at the investor's slab rate.

    Arguments:
        None.

    Returns:
        float: Slab rate in percent.

    Warning:
        Surcharge and cess are not added on top of this rate.
    """
    st.divider()
    st.subheader("Slab rate (Debt preset)")
    return float(
        st.number_input(
            "Your slab rate %",
            help=HELP_YOUR_MARGINAL_INCOME_TAX_STR,
            min_value=0.0,
            max_value=60.0,
            value=DEFAULT_SLAB_RATE_PERCENT_FLOAT,
            step=0.5,
        )
    )
