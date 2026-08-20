"""A form dashboard that speaks your currency. No longer wired up.

This was the third of three front ends onto one engine: the classic
*shape* - fill a form, read an answer - carrying the newer
machinery, a currency of your choosing, a tax regime, and inputs
that are sliders or keyboard as you prefer.

The portal now does all of that, and its launcher is the only one
left, so nothing in the shipped application reaches this module. It
is kept because `tests/test_studio_app.py` drives it to check
behaviour that is genuinely worth checking - that a chosen regime
reaches the funds' tax rates, that a currency reaches the cards and
the chart axis, that only India charges a cess - and deleting the
module would delete those checks with it.

If that coverage is ever moved onto the portal's own screens, this
file goes with it. Until then it is tested, unreachable, and
honestly labelled as such.

Nothing here re-implements any finance. It collects inputs, hands
them to the same `PortfolioSimulator`, and renders what comes back.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

import streamlit as st

from investment_journey_simulator.app import (
    NOMINAL_SECTION_HEADING_STR,
    REAL_SECTION_HEADING_STR,
    build_runs_pair,
    render_export_section,
    render_mode_description,
    render_notes_expander,
    render_run_section,
    render_summary_lines,
    render_validation_section,
)
from investment_journey_simulator.constants import (
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXPENSE_MODEL_ACCRUED_STR,
    PRESET_DEBT_STR,
    PRESET_EQUITY_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODE_OFF_STR,
)
from investment_journey_simulator.currency import (
    DEFAULT_CURRENCY_CODE_STR,
    Currency,
    describe_money_str,
    list_currency_code_list,
    resolve_currency,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.formatting import describe_annual_rate_str
from investment_journey_simulator.fund_builder import (
    build_fund_configurations_list,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    PauseSettings,
    RebalanceSettings,
    SimulationSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.money_weighted import (
    calculate_post_tax_xirr_percent_float,
    calculate_pre_tax_xirr_percent_float,
)
from investment_journey_simulator.narrative import build_mode_description_str
from investment_journey_simulator.regimes import (
    DEFAULT_REGIME_CODE_STR,
    TaxRegime,
    describe_regime_str,
    list_regime_code_list,
    resolve_regime,
)
from investment_journey_simulator.scenarios import render_scenario_controls
from investment_journey_simulator.ui.fund_inputs import (
    render_fund_table_dataframe,
)
from investment_journey_simulator.ui.risk_view import render_risk_section
from investment_journey_simulator.ui.sidebar_controls import (
    render_sidebar_selections,
)
from investment_journey_simulator.ui.studio_view import (
    build_growth_figure,
    build_year_row_list,
    render_outcome_cards,
    render_return_cards,
)
from investment_journey_simulator.ui.timeline_view import (
    render_hero,
    render_page_style,
)
from investment_journey_simulator.ui.value_input import (
    render_input_mode_control,
    render_tunable_float,
)

PAGE_LAYOUT_STR: Literal["centered", "wide"] = "wide"
PAGE_TITLE_STR: str = "Plan Studio"
HERO_TITLE_STR: str = "Plan studio"
HERO_SUBTITLE_STR: str = (
    "Fill in a plan and read the answer - in your currency, under "
    "the tax rules you choose, with sliders or a keyboard as you "
    "prefer."
)

CURRENCY_KEY_STR: str = "studio_currency_code"
REGIME_KEY_STR: str = "studio_regime_code"
MONTHLY_KEY_STR: str = "studio_monthly_amount"
LUMPSUM_KEY_STR: str = "studio_lumpsum_amount"
HORIZON_KEY_STR: str = "studio_horizon_years"
RETURN_KEY_STR: str = "studio_return_percent"
DEBT_RETURN_KEY_STR: str = "studio_debt_return_percent"
EXPENSE_KEY_STR: str = "studio_expense_percent"
EQUITY_KEY_STR: str = "studio_equity_percent"
STEPUP_KEY_STR: str = "studio_stepup_percent"
INFLATION_KEY_STR: str = "studio_inflation_percent"
GROWTH_FIGURE_KEY_STR: str = "studio_growth_figure"

START_DATE: date = date(2026, 1, 1)
EQUITY_FUND_NAME_STR: str = "Equity"
DEBT_FUND_NAME_STR: str = "Debt"
DEFAULT_MONTHLY_FLOAT: float = 25_000.0
DEFAULT_HORIZON_YEARS_FLOAT: float = 20.0
DEFAULT_RETURN_PERCENT_FLOAT: float = 12.0
DEFAULT_DEBT_RETURN_PERCENT_FLOAT: float = 7.0
DEFAULT_EXPENSE_PERCENT_FLOAT: float = 0.5
DEFAULT_DEBT_EXPENSE_PERCENT_FLOAT: float = 0.25
DEFAULT_EQUITY_PERCENT_FLOAT: float = 100.0
SLAB_RATE_PERCENT_FLOAT: float = 30.0


def read_currency() -> Currency:
    """Read the currency every figure is displayed in.

    Brief:
        Held in session state so the cards, the chart axis and the
        yearly table cannot disagree about the denomination.

    Arguments:
        None.

    Returns:
        Currency: The chosen currency.

    Warning:
        Changes only how figures are written. No conversion is
        applied and no exchange rate exists in this program.
    """
    return resolve_currency(
        str(
            st.session_state.get(
                CURRENCY_KEY_STR, DEFAULT_CURRENCY_CODE_STR
            )
        )
    )


def read_regime() -> TaxRegime:
    """Read whose capital gains rules apply.

    Brief:
        Held in session state so the funds and the portfolio tax
        settings are always built from the same regime.

    Arguments:
        None.

    Returns:
        TaxRegime: The chosen regime.

    Warning:
        Only India is modelled beyond its headline rates.
    """
    return resolve_regime(
        str(
            st.session_state.get(
                REGIME_KEY_STR, DEFAULT_REGIME_CODE_STR
            )
        )
    )


def render_context_controls() -> tuple:
    """Collect the three choices that frame everything else.

    Brief:
        Currency, tax regime and input style sit together at the
        top because each one changes how every control below it
        behaves or reads.

    Arguments:
        None.

    Returns:
        tuple: The chosen currency and regime.

    Warning:
        Renders widgets as a side effect.
    """
    column_list = st.columns(3)
    with column_list[0]:
        _render_currency_selectbox()
    with column_list[1]:
        _render_regime_selectbox()
    with column_list[2]:
        render_input_mode_control()
    return read_currency(), read_regime()


def _render_currency_selectbox() -> None:
    """Offer every currency, labelled by code, symbol and name.

    Brief:
        A reader looks for whichever of the three they know.

    Arguments:
        None.

    Returns:
        None: A widget is written to the page.

    Warning:
        Renders a widget as a side effect.
    """
    code_list = list_currency_code_list()
    st.selectbox(
        "Currency",
        code_list,
        index=code_list.index(read_currency().code_str),
        key=CURRENCY_KEY_STR,
        format_func=lambda code_str: resolve_currency(
            code_str
        ).label_str,
        help=(
            "Sets the symbol, the digit grouping and the words "
            "for large numbers. It converts nothing."
        ),
    )


def _render_regime_selectbox() -> None:
    """Offer every regime, saying which is modelled in full.

    Brief:
        The label carries the depth, so the choice is informed
        before it is made rather than explained afterwards.

    Arguments:
        None.

    Returns:
        None: A widget is written to the page.

    Warning:
        Renders a widget as a side effect.
    """
    code_list = list_regime_code_list()
    st.selectbox(
        "Tax regime",
        code_list,
        index=code_list.index(read_regime().code_str),
        key=REGIME_KEY_STR,
        format_func=lambda code_str: resolve_regime(
            code_str
        ).label_str,
        help=(
            "India is modelled in full. Others fill in opening "
            "rates you can edit."
        ),
    )


def render_regime_notice(regime: TaxRegime) -> None:
    """State how deeply the chosen regime is actually modelled.

    Brief:
        Choosing a country fills in rates; it does not add that
        country's tax machinery. A reader has to be told which
        they are getting.

    Arguments:
        regime (TaxRegime): Regime being described.

    Returns:
        None: A caption is written to the page.

    Warning:
        Renders as markdown.
    """
    st.caption(describe_regime_str(regime))
    if not regime.is_fully_modelled_bool:
        st.caption(
            ":orange[Surcharge, cess, marginal relief and "
            "grandfathering are Indian mechanisms and are switched "
            "off for this regime.]"
        )


def render_money_controls(currency: Currency) -> tuple:
    """Collect what goes in, and for how long.

    Brief:
        Each figure echoes itself back named in the chosen
        currency's own magnitudes, so an extra zero is obvious
        while it is being typed.

    Arguments:
        currency (Currency): Currency amounts are entered in.

    Returns:
        tuple: Monthly amount, lump sum and horizon in years.

    Warning:
        Renders widgets as a side effect.
    """
    column_list = st.columns(3)
    with column_list[0]:
        monthly_float = render_tunable_float(
            f"Every month ({currency.symbol_str} a month)",
            MONTHLY_KEY_STR,
            (0.0, 1_000_000.0, 1_000.0),
            DEFAULT_MONTHLY_FLOAT,
            help_str="Invested at the start of each month.",
        )
        st.caption(describe_money_str(monthly_float, currency))
    with column_list[1]:
        lumpsum_float = render_tunable_float(
            f"Lump sum now ({currency.symbol_str}, once)",
            LUMPSUM_KEY_STR,
            (0.0, 100_000_000.0, 10_000.0),
            0.0,
            help_str="Invested once, in the very first month.",
        )
        st.caption(describe_money_str(lumpsum_float, currency))
    with column_list[2]:
        horizon_years_int = int(
            render_tunable_float(
                "How long (years)",
                HORIZON_KEY_STR,
                (1.0, 60.0, 1.0),
                DEFAULT_HORIZON_YEARS_FLOAT,
                help_str="Simulated month by month.",
            )
        )
        st.caption(f"{horizon_years_int * 12} months")
    return monthly_float, lumpsum_float, horizon_years_int


def render_growth_controls() -> tuple:
    """Collect the return, fee and escalation assumptions.

    Brief:
        The return caption names the monthly rate it compounds to,
        which is how a reader can check the convention.

    Arguments:
        None.

    Returns:
        tuple: Equity return, expense ratio and step-up percent.

    Warning:
        Every one of these is an assumption, not a forecast.
    """
    column_list = st.columns(3)
    with column_list[0]:
        return_percent_float = render_tunable_float(
            "Equity return (% a year)",
            RETURN_KEY_STR,
            (-20.0, 40.0, 0.25),
            DEFAULT_RETURN_PERCENT_FLOAT,
            help_str="Your assumption. Compounded monthly.",
        )
        st.caption(describe_annual_rate_str(return_percent_float))
    with column_list[1]:
        expense_percent_float = render_tunable_float(
            "Fund fee, TER (% a year)",
            EXPENSE_KEY_STR,
            (0.0, 3.0, 0.05),
            DEFAULT_EXPENSE_PERCENT_FLOAT,
            help_str="Accrued on the value, not on the return.",
        )
    with column_list[2]:
        stepup_percent_float = render_tunable_float(
            "Yearly step-up (% a year)",
            STEPUP_KEY_STR,
            (0.0, 50.0, 0.5),
            0.0,
            help_str="Raises the instalment once a year.",
        )
    return (
        return_percent_float,
        expense_percent_float,
        stepup_percent_float,
    )


def render_portfolio_controls() -> tuple:
    """Collect the asset split and the debt assumptions.

    Brief:
        A hundred percent equity is a single-asset plan, which the
        caption says out loud so an empty debt lane is not a
        mystery.

    Arguments:
        None.

    Returns:
        tuple: Equity share, debt return and inflation percent.

    Warning:
        Renders widgets as a side effect.
    """
    column_list = st.columns(3)
    with column_list[0]:
        equity_percent_float = render_tunable_float(
            "Equity share (% of the portfolio)",
            EQUITY_KEY_STR,
            (0.0, 100.0, 0.5),
            DEFAULT_EQUITY_PERCENT_FLOAT,
            help_str="The rest goes to the debt fund.",
        )
        st.caption(
            f"{equity_percent_float:g}% equity, "
            f"{100.0 - equity_percent_float:g}% debt"
        )
    with column_list[1]:
        debt_return_percent_float = render_tunable_float(
            "Debt return (% a year)",
            DEBT_RETURN_KEY_STR,
            (-10.0, 20.0, 0.25),
            DEFAULT_DEBT_RETURN_PERCENT_FLOAT,
            help_str="Applies to the non-equity share.",
        )
    with column_list[2]:
        inflation_percent_float = _render_inflation_float()
    return (
        equity_percent_float,
        debt_return_percent_float,
        inflation_percent_float,
    )


def _render_inflation_float() -> float:
    """Collect the rate figures are restated at.

    Brief:
        Opens at the chosen currency's own assumption, because
        six percent is sensible in Mumbai and not in Tokyo.

    Arguments:
        None.

    Returns:
        float: Annual inflation percent.

    Warning:
        Changes no unit of the plan; only what it is said to be
        worth in today's money.
    """
    return render_tunable_float(
        "Inflation (% a year)",
        INFLATION_KEY_STR,
        (0.0, 30.0, 0.25),
        read_currency().default_inflation_percent_float,
        help_str=(
            "Used only to restate the value in today's money. "
            "It changes no unit of the plan itself."
        ),
    )


def _build_side_tuple(input_tuple: tuple) -> tuple:
    """Describe the equity and debt sides of the portfolio.

    Brief:
        Splitting the form into two side descriptions keeps the
        builder below a loop rather than a wall of arguments.

    Arguments:
        input_tuple (tuple): Monthly, lump sum, equity share,
            equity return, debt return and expense ratio.

    Returns:
        tuple: Identity, weight, growth and debt flag per side.

    Warning:
        Weights are percentages, not fractions.
    """
    (
        _monthly_float,
        _lumpsum_float,
        equity_percent_float,
        return_percent_float,
        debt_return_percent_float,
        expense_percent_float,
    ) = input_tuple
    equity_float = float(equity_percent_float)
    return (
        (
            (EQUITY_FUND_NAME_STR, PRESET_EQUITY_STR),
            equity_float,
            (return_percent_float, expense_percent_float),
            False,
        ),
        (
            (DEBT_FUND_NAME_STR, PRESET_DEBT_STR),
            100.0 - equity_float,
            (
                debt_return_percent_float,
                DEFAULT_DEBT_EXPENSE_PERCENT_FLOAT,
            ),
            True,
        ),
    )


def build_fund_list(
    input_tuple: tuple,
    regime: TaxRegime,
) -> list[FundConfiguration]:
    """Build the equity and debt funds from the form.

    Brief:
        Instalments and the lump sum follow the same split, so the
        portfolio opens at the mix asked for rather than drifting
        into it.

    Arguments:
        input_tuple (tuple): Monthly, lump sum, equity share,
            equity return, debt return and expense ratio.
        regime (TaxRegime): Regime supplying the tax fields.

    Returns:
        List[FundConfiguration]: Equity first, then debt.

    Warning:
        A hundred percent equity still produces a debt fund with
        nothing routed to it, so one path serves every split.
    """
    monthly_float, lumpsum_float = input_tuple[0], input_tuple[1]
    return [
        _build_fund(
            identity_tuple,
            (
                monthly_float * weight_float / 100.0,
                lumpsum_float * weight_float / 100.0,
                weight_float,
            ),
            growth_tuple,
            _resolve_tax_tuple(regime, is_debt_bool),
        )
        for identity_tuple, weight_float, growth_tuple, is_debt_bool
        in _build_side_tuple(input_tuple)
    ]


def _resolve_tax_tuple(
    regime: TaxRegime,
    is_debt_bool: bool,
) -> tuple:
    """Decide every tax field one fund needs.

    Brief:
        Debt is taxed at the slab rate under the Indian regime,
        per section 50AA, and at the regime's own short-term rate
        elsewhere, because that section has no counterpart abroad.

    Arguments:
        regime (TaxRegime): Regime supplying the rates.
        is_debt_bool (bool): Whether this is the debt side.

    Returns:
        tuple: Short rate, long rate, exemption, threshold and
            the always-short-term flag.

    Warning:
        Only the equity side receives an annual exemption.
    """
    threshold_int = regime.long_term_threshold_months_int
    if not is_debt_bool:
        return (
            regime.short_term_percent_float,
            regime.long_term_percent_float,
            regime.annual_exemption_float,
            threshold_int,
            False,
        )
    debt_rate_float = (
        SLAB_RATE_PERCENT_FLOAT
        if regime.is_fully_modelled_bool
        else regime.short_term_percent_float
    )
    return (
        debt_rate_float,
        debt_rate_float,
        0.0,
        threshold_int,
        regime.is_fully_modelled_bool,
    )


def _build_fund(
    identity_tuple: tuple,
    amount_tuple: tuple,
    growth_tuple: tuple,
    tax_tuple: tuple,
) -> FundConfiguration:
    """Assemble one fund from already-decided values.

    Brief:
        Every decision was made by the resolvers above, so this
        only puts the pieces together.

    Arguments:
        identity_tuple (tuple): Fund name and preset identifier.
        amount_tuple (tuple): Monthly, lump sum and target share.
        growth_tuple (tuple): Return and expense percentages.
        tax_tuple (tuple): Rates, exemption, threshold and flag.

    Returns:
        FundConfiguration: Fund ready for the engine.

    Warning:
        Performs no rate logic of its own.
    """
    name_str, preset_str = identity_tuple
    monthly_float, lumpsum_float, target_float = amount_tuple
    return_float, expense_float = growth_tuple
    short_float, long_float, exemption_float, months_int, flag_bool = (
        tax_tuple
    )
    return FundConfiguration(
        name_str=name_str,
        preset_str=preset_str,
        monthly_sip_float=monthly_float,
        stepup_percent_float=0.0,
        gross_return_percent_float=return_float,
        expense_percent_float=expense_float,
        start_date=START_DATE,
        initial_investment_float=lumpsum_float,
        target_allocation_percent_float=target_float,
        short_term_tax_percent_float=short_float,
        long_term_tax_percent_float=long_float,
        long_term_threshold_months_int=months_int,
        exemption_amount_float=exemption_float,
        exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
        is_always_short_term_bool=flag_bool,
        expense_model_str=EXPENSE_MODEL_ACCRUED_STR,
    )


def build_settings(
    horizon_years_int: int,
    stepup_percent_float: float,
    regime: TaxRegime,
) -> SimulationSettings:
    """Build the portfolio settings from the form.

    Brief:
        Every optional mechanism stays off unless the form asked
        for it, so a simple plan is simulated simply.

    Arguments:
        horizon_years_int (int): Years to simulate.
        stepup_percent_float (float): Yearly escalation.
        regime (TaxRegime): Regime supplying the tax rules.

    Returns:
        SimulationSettings: Settings ready for the engine.

    Warning:
        Exit tax is priced, so the headline corpus is spendable.
    """
    return SimulationSettings(
        horizon_years_int=horizon_years_int,
        portfolio_start_date=START_DATE,
        sip_at_month_start_bool=True,
        stepup=StepUpSettings(
            mode_str=(
                STEPUP_MODE_GLOBAL_STR
                if stepup_percent_float > 0.0
                else STEPUP_MODE_OFF_STR
            ),
            global_stepup_percent_float=stepup_percent_float,
        ),
        withdrawal=WithdrawalSettings(),
        pauses=PauseSettings(),
        rebalance=RebalanceSettings(),
        tax=TaxSettings(
            apply_final_liquidation_tax_bool=True,
            cess_percent_float=regime.cess_percent_float,
            exemption_level_str=EXEMPTION_LEVEL_PORTFOLIO_STR,
            portfolio_exemption_amount_float=(
                regime.annual_exemption_float
            ),
        ),
    )


def build_outcome_dict(result, settings) -> dict:
    """Reduce a completed run to the figures the cards show.

    Brief:
        One place where the headline numbers are decided, so the
        cards and the table cannot drift apart.

    Arguments:
        result: Completed simulation result.
        settings: Settings the run used.

    Returns:
        dict: Figures keyed for the card renderers.

    Warning:
        The spendable figure is net of exit tax only because the
        settings switch that pricing on.
    """
    return {
        "invested": result.ending_invested_float,
        "corpus": result.ending_value_float,
        "exit_cost": result.total_exit_cost_float,
        "spendable": result.post_tax_ending_value_float,
        "gain": (
            result.ending_value_float
            - result.ending_invested_float
        ),
        "xirr_pre": calculate_pre_tax_xirr_percent_float(
            result, settings.sip_at_month_start_bool
        ),
        "xirr_post": calculate_post_tax_xirr_percent_float(
            result, settings.sip_at_month_start_bool
        ),
    }


def render_results(result, settings, currency: Currency) -> None:
    """Draw the cards, the growth chart and the yearly table.

    Brief:
        Cards answer "how much", the chart answers "how it got
        there", and the table lets a reader check any single year.

    Arguments:
        result: Completed simulation result.
        settings: Settings the run used.
        currency (Currency): Currency to display in.

    Returns:
        None: The results are written to the page.

    Warning:
        Assumes the result and settings describe the same run.
    """
    outcome_dict = build_outcome_dict(result, settings)
    render_outcome_cards(outcome_dict, currency)
    st.write("")
    snapshot_list = list(result.monthly_snapshots_list)
    st.plotly_chart(
        build_growth_figure(
            [
                snapshot.month_date
                for snapshot in snapshot_list
            ],
            [
                snapshot.portfolio_value_float
                for snapshot in snapshot_list
            ],
            [
                snapshot.invested_amount_float
                for snapshot in snapshot_list
            ],
            currency,
        ),
        width="stretch",
        key=GROWTH_FIGURE_KEY_STR,
    )
    render_return_cards(outcome_dict, currency)
    st.write("")
    st.markdown("#### Year by year")
    st.dataframe(
        build_year_row_list(snapshot_list, currency),
        width="stretch",
        hide_index=True,
    )


def render_full_dashboard(currency: Currency) -> None:
    """Run the classic dashboard's whole pipeline, unmodified.

    Brief:
        Every section here is the classic dashboard's *own* code,
        imported rather than copied. That is deliberate: reusing it
        is the only way to be certain the studio's deeper tab
        behaves identically to the dashboard people already trust,
        and it leaves those files frozen.

    Arguments:
        currency (Currency): Currency the studio is displaying in.

    Returns:
        None: The full dashboard is written to the page.

    Warning:
        These sections format in rupees internally, because they
        are the classic dashboard's renderers. Under any other
        currency the notice below says so rather than letting the
        symbols quietly disagree.
    """
    sidebar_selections = render_sidebar_selections(currency)
    fund_table_dataframe = render_fund_table_dataframe(
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.slab_rate_percent_float,
        sidebar_selections.is_stagger_enabled_bool,
        currency,
    )
    render_scenario_controls(
        sidebar_selections, fund_table_dataframe
    )
    fund_configurations_list = build_fund_configurations_list(
        fund_table_dataframe,
        sidebar_selections.settings.portfolio_start_date,
        sidebar_selections.expense_model_str,
    )
    nominal_run, real_run = build_runs_pair(
        fund_table_dataframe, sidebar_selections
    )
    _render_dashboard_sections(
        (nominal_run, real_run),
        sidebar_selections,
        fund_configurations_list,
        fund_table_dataframe,
    )


def _render_dashboard_sections(
    run_pair_tuple: tuple,
    sidebar_selections,
    fund_configurations_list: list,
    fund_table_dataframe,
) -> None:
    """Write every classic section in the classic order.

    Brief:
        Split out only to keep each function readable; the order
        is the dashboard's own and must not be rearranged, since
        the risk section reads the nominal run's exit value.

    Arguments:
        run_pair_tuple (tuple): Nominal and real runs.
        sidebar_selections: Collected sidebar settings.
        fund_configurations_list (list): Funds that were run.
        fund_table_dataframe: The editable fund table.

    Returns:
        None: The sections are written to the page.

    Warning:
        Renders a large amount of the page.
    """
    nominal_run, real_run = run_pair_tuple
    render_mode_description(
        build_mode_description_str(
            sidebar_selections.settings,
            sidebar_selections.inflation_percent_float,
        )
    )
    render_summary_lines(nominal_run.summary_lines_list)
    render_run_section(nominal_run, NOMINAL_SECTION_HEADING_STR)
    render_validation_section(
        nominal_run, sidebar_selections.settings
    )
    render_risk_section(
        fund_configurations_list,
        sidebar_selections.settings,
        nominal_run.result.post_tax_ending_value_float,
    )
    st.divider()
    render_summary_lines(real_run.summary_lines_list)
    render_run_section(real_run, REAL_SECTION_HEADING_STR)
    render_notes_expander()
    render_export_section(
        fund_table_dataframe, nominal_run, real_run
    )


def main() -> None:
    """Render the studio page end to end.

    Brief:
        Two tabs on one engine. **Quick plan** is the studio's own
        form, denominated in the chosen currency and taxed under
        the chosen regime. **Full dashboard** runs the classic
        dashboard's entire pipeline - every control, ledger, chart,
        validation check, risk panel and export - by importing it
        rather than copying it, so those files stay frozen.

    Arguments:
        None.

    Returns:
        None: The page is rendered.

    Warning:
        Streamlit re-executes this on every interaction.
    """
    st.set_page_config(
        page_title=PAGE_TITLE_STR, layout=PAGE_LAYOUT_STR
    )
    render_page_style()
    render_hero(HERO_TITLE_STR, HERO_SUBTITLE_STR)
    quick_tab, full_tab = st.tabs(
        ["Quick plan", "Full dashboard"]
    )
    with full_tab:
        render_full_dashboard(read_currency())
    with quick_tab:
        _render_quick_plan()


def _render_quick_plan() -> None:
    """Render the studio's own currency-aware form and answer.

    Brief:
        The lighter of the two tabs: a handful of inputs, four
        cards, a growth chart and a yearly table - every figure
        denominated in the chosen currency.

    Arguments:
        None.

    Returns:
        None: The tab is written to the page.

    Warning:
        Runs the engine on every interaction.
    """
    currency, regime = render_context_controls()
    render_regime_notice(regime)
    st.write("")
    monthly_float, lumpsum_float, horizon_years_int = (
        render_money_controls(currency)
    )
    (
        return_percent_float,
        expense_percent_float,
        stepup_percent_float,
    ) = render_growth_controls()
    (
        equity_percent_float,
        debt_return_percent_float,
        _inflation_percent_float,
    ) = render_portfolio_controls()
    settings = build_settings(
        horizon_years_int, stepup_percent_float, regime
    )
    form_tuple = (
        monthly_float,
        lumpsum_float,
        equity_percent_float,
        return_percent_float,
        debt_return_percent_float,
        expense_percent_float,
    )
    result = PortfolioSimulator(
        build_fund_list(form_tuple, regime), settings
    ).run()
    st.write("")
    render_results(result, settings, currency)
