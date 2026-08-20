"""Immutable constants shared by every simulator module."""

from __future__ import annotations

# ------------------------------------------------------------------
# Currency and number formatting
# ------------------------------------------------------------------
RUPEE_SYMBOL_STR: str = "₹"
CRORE_UNIT_INT: int = 10_000_000
LAKH_UNIT_INT: int = 100_000
THOUSAND_UNIT_INT: int = 1_000

# ------------------------------------------------------------------
# Calendar
# ------------------------------------------------------------------
MONTHS_IN_YEAR_INT: int = 12
DAYS_IN_YEAR_FLOAT: float = 365.0

# ------------------------------------------------------------------
# Tax year
#
# When a tax year starts is a jurisdiction's choice, not a fact about
# the world. India runs April to March, Australia July to June, and
# much of the rest - the United States, Japan, Germany - simply uses
# the calendar year. The simulator works on a month grid anchored to
# the first of each month, so a tax year is identified by the month
# it opens in and labelled by the calendar year that month falls in.
#
# The United Kingdom's 6 April start is the one convention this
# cannot express exactly. Month four is the closest available answer
# and misplaces only gains realised in the first five days of April.
#
# FINANCIAL_YEAR_START_MONTH_INT is retained as the default because
# every existing caller assumes it; it is now India's answer rather
# than the only answer.
# ------------------------------------------------------------------
TAX_YEAR_START_MONTH_CALENDAR_INT: int = 1
TAX_YEAR_START_MONTH_INDIA_INT: int = 4
TAX_YEAR_START_MONTH_AUSTRALIA_INT: int = 7
FINANCIAL_YEAR_START_MONTH_INT: int = TAX_YEAR_START_MONTH_INDIA_INT
MONTH_SHORT_NAMES_TUPLE: tuple = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# ------------------------------------------------------------------
# Numerical tolerances
# ------------------------------------------------------------------
MONEY_TOLERANCE_FLOAT: float = 1e-9
RATIO_TOLERANCE_FLOAT: float = 1e-6
PERCENT_TOTAL_FLOAT: float = 100.0

# ------------------------------------------------------------------
# Money-weighted return solver
# ------------------------------------------------------------------
XIRR_BRACKET_MINIMUM_FLOAT: float = -0.9999
XIRR_BRACKET_MAXIMUM_FLOAT: float = 100.0
XIRR_CONVERGENCE_TOLERANCE_FLOAT: float = 1e-7
XIRR_MAXIMUM_ITERATIONS_INT: int = 200

# ------------------------------------------------------------------
# Goal-seek solver
# ------------------------------------------------------------------
GOAL_SEEK_MAXIMUM_ITERATIONS_INT: int = 80
GOAL_SEEK_TOLERANCE_FLOAT: float = 0.01
GOAL_SEEK_MAXIMUM_SIP_FLOAT: float = 100_000_000.0
GOAL_SEEK_MAXIMUM_RETURN_PERCENT_FLOAT: float = 100.0
GOAL_SEEK_MAXIMUM_YEARS_INT: int = 60

# ------------------------------------------------------------------
# Risk panel defaults
# ------------------------------------------------------------------
DEFAULT_VOLATILITY_PERCENT_FLOAT: float = 18.0
DEFAULT_STOCHASTIC_TRIALS_INT: int = 200
MAXIMUM_STOCHASTIC_TRIALS_INT: int = 2000

# ------------------------------------------------------------------
# Step-up modes
# ------------------------------------------------------------------
STEPUP_MODE_OFF_STR: str = "OFF"
STEPUP_MODE_GLOBAL_STR: str = "GLOBAL"
STEPUP_MODE_PER_FUND_STR: str = "PER_FUND"
STEPUP_MODE_BOTH_STR: str = "BOTH"
STEPUP_MODES_TUPLE: tuple = (
    STEPUP_MODE_OFF_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODE_PER_FUND_STR,
    STEPUP_MODE_BOTH_STR,
)

# ------------------------------------------------------------------
# Systematic withdrawal plan modes
# ------------------------------------------------------------------
WITHDRAWAL_MODE_FIXED_STR: str = "FIXED"
WITHDRAWAL_MODE_SCHEDULE_STR: str = "SCHEDULE_12"
WITHDRAWAL_MODE_PERCENT_STR: str = "PERCENT_OF_CORPUS"
WITHDRAWAL_MODES_TUPLE: tuple = (
    WITHDRAWAL_MODE_FIXED_STR,
    WITHDRAWAL_MODE_SCHEDULE_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
)

# ------------------------------------------------------------------
# Expense ratio models
# ------------------------------------------------------------------
EXPENSE_MODEL_SIMPLE_STR: str = "SIMPLE_SUBTRACTION"
EXPENSE_MODEL_ACCRUED_STR: str = "CONTINUOUS_ACCRUAL"
EXPENSE_MODELS_TUPLE: tuple = (
    EXPENSE_MODEL_SIMPLE_STR,
    EXPENSE_MODEL_ACCRUED_STR,
)

# ------------------------------------------------------------------
# Numerical guards
# ------------------------------------------------------------------
MINIMUM_ANNUAL_RETURN_PERCENT_FLOAT: float = -99.99
MINIMUM_EXPENSE_PERCENT_FLOAT: float = 0.0
MAXIMUM_EXPENSE_PERCENT_FLOAT: float = 99.99

# ------------------------------------------------------------------
# Statutory levies and charges
# ------------------------------------------------------------------
DEFAULT_CESS_PERCENT_FLOAT: float = 4.0
DEFAULT_SURCHARGE_PERCENT_FLOAT: float = 0.0
MAXIMUM_CAPITAL_GAINS_SURCHARGE_PERCENT_FLOAT: float = 15.0

# ------------------------------------------------------------------
# Surcharge on income tax
#
# Each entry is (income floor in rupees, surcharge percent). The
# applicable rate is the last entry whose floor the total income
# reaches. The new regime, default since FY 2023-24, drops the old
# 37% band and caps the surcharge at 25%.
#
# Surcharge on gains taxed under sections 111A and 112A is capped
# separately at 15% by MAXIMUM_CAPITAL_GAINS_SURCHARGE_PERCENT_FLOAT.
# ------------------------------------------------------------------
SURCHARGE_MODE_MANUAL_STR: str = "MANUAL"
SURCHARGE_MODE_SLAB_STR: str = "SLAB"
SURCHARGE_MODES_TUPLE: tuple = (
    SURCHARGE_MODE_MANUAL_STR,
    SURCHARGE_MODE_SLAB_STR,
)
SURCHARGE_REGIME_NEW_STR: str = "NEW"
SURCHARGE_REGIME_OLD_STR: str = "OLD"
SURCHARGE_REGIMES_TUPLE: tuple = (
    SURCHARGE_REGIME_NEW_STR,
    SURCHARGE_REGIME_OLD_STR,
)
NEW_REGIME_SURCHARGE_SLABS_TUPLE: tuple = (
    (0.0, 0.0),
    (5_000_000.0, 10.0),
    (10_000_000.0, 15.0),
    (20_000_000.0, 25.0),
)
OLD_REGIME_SURCHARGE_SLABS_TUPLE: tuple = (
    (0.0, 0.0),
    (5_000_000.0, 10.0),
    (10_000_000.0, 15.0),
    (20_000_000.0, 25.0),
    (50_000_000.0, 37.0),
)
# ------------------------------------------------------------------
# Income tax slabs
#
# Present only to support marginal relief on the surcharge, which
# cannot be computed without the tax on total income and the tax at
# the slab floor. Each entry is (income floor in rupees, marginal
# rate percent); the rate applies to the income above that floor.
#
# Relief only ever bites just above a surcharge threshold, and the
# lowest of those is fifty lakh. The section 87A rebate stops far
# below that and so can never change the answer. The higher basic
# exemption for senior citizens under the old regime shifts the tax
# at the income and at the floor by the same amount, so it moves the
# relief by at most a few hundred rupees; it is not modelled.
#
# Rates below are for FY 2026-27, checked against published
# commentary on 2026-08-05. Budget 2026 changed neither regime's
# slabs. Re-verify after each Budget.
# ------------------------------------------------------------------
NEW_REGIME_INCOME_TAX_SLABS_TUPLE: tuple = (
    (0.0, 0.0),
    (400_000.0, 5.0),
    (800_000.0, 10.0),
    (1_200_000.0, 15.0),
    (1_600_000.0, 20.0),
    (2_000_000.0, 25.0),
    (2_400_000.0, 30.0),
)
OLD_REGIME_INCOME_TAX_SLABS_TUPLE: tuple = (
    (0.0, 0.0),
    (250_000.0, 5.0),
    (500_000.0, 20.0),
    (1_000_000.0, 30.0),
)

EQUITY_REDEMPTION_STT_PERCENT_FLOAT: float = 0.001
DEFAULT_EXIT_LOAD_PERCENT_FLOAT: float = 1.0
DEFAULT_EXIT_LOAD_MONTHS_INT: int = 12
LOSS_BUCKET_SHORT_TERM_STR: str = "SHORT_TERM"
LOSS_BUCKET_LONG_TERM_STR: str = "LONG_TERM"
LOSS_CARRY_FORWARD_YEARS_INT: int = 8

# ------------------------------------------------------------------
# Grandfathering under the proviso to section 112A
#
# Gains on equity units acquired before 1 February 2018 are computed
# against a deemed cost: the higher of the actual cost and the lower
# of the 31 January 2018 fair market value and the sale value. The
# valuation month below is the month whose CLOSE is 31 January 2018.
# ------------------------------------------------------------------
GRANDFATHER_VALUATION_YEAR_INT: int = 2018
GRANDFATHER_VALUATION_MONTH_INT: int = 1

# ------------------------------------------------------------------
# Tax funding source
# ------------------------------------------------------------------
TAX_FUNDING_PORTFOLIO_STR: str = "PORTFOLIO"
TAX_FUNDING_OUTSIDE_STR: str = "OUTSIDE"
TAX_FUNDING_SOURCES_TUPLE: tuple = (
    TAX_FUNDING_PORTFOLIO_STR,
    TAX_FUNDING_OUTSIDE_STR,
)

# ------------------------------------------------------------------
# Exemption aggregation
# ------------------------------------------------------------------
EXEMPTION_LEVEL_PORTFOLIO_STR: str = "PER_TAXPAYER"
EXEMPTION_LEVEL_FUND_STR: str = "PER_FUND"
EXEMPTION_LEVELS_TUPLE: tuple = (
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    EXEMPTION_LEVEL_FUND_STR,
)
PORTFOLIO_LEDGER_KEY_STR: str = "__PORTFOLIO__"

# ------------------------------------------------------------------
# Rebalancing
# ------------------------------------------------------------------
REBALANCE_TRIGGER_CALENDAR_STR: str = "CALENDAR"
REBALANCE_TRIGGER_BAND_STR: str = "DRIFT_BAND"
REBALANCE_TRIGGER_BOTH_STR: str = "CALENDAR_AND_BAND"

# A rebalance the user placed on a specific month, rather than one
# a rule produced. Named months always fire, whatever trigger mode
# is configured, because the user asked for them by hand.
REBALANCE_TRIGGER_DATED_STR: str = "DATED"
REBALANCE_TRIGGERS_TUPLE: tuple = (
    REBALANCE_TRIGGER_CALENDAR_STR,
    REBALANCE_TRIGGER_BAND_STR,
    REBALANCE_TRIGGER_BOTH_STR,
)
DEFAULT_DRIFT_BAND_PERCENT_FLOAT: float = 5.0
REBALANCE_METHOD_FULL_STR: str = "Full liquidation (exact target split)"
REBALANCE_METHOD_PARTIAL_STR: str = "Partial (sell overweight only)"
REBALANCE_METHODS_TUPLE: tuple = (
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_METHOD_PARTIAL_STR,
)
REBALANCE_TARGET_SIP_SPLIT_STR: str = "INITIAL_SIP_SPLIT"
REBALANCE_TARGET_COLUMN_STR: str = "TARGET_ALLOC_COLUMN"
REBALANCE_TARGET_MODES_TUPLE: tuple = (
    REBALANCE_TARGET_SIP_SPLIT_STR,
    REBALANCE_TARGET_COLUMN_STR,
)

# ------------------------------------------------------------------
# Pause scopes
# ------------------------------------------------------------------
PAUSE_SCOPE_SIP_STR: str = "SIP"
PAUSE_SCOPE_WITHDRAWAL_STR: str = "SWP"
PAUSE_SCOPE_BOTH_STR: str = "BOTH"
PAUSE_SCOPES_TUPLE: tuple = (
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
    PAUSE_SCOPE_BOTH_STR,
)

# ------------------------------------------------------------------
# Taxation
# ------------------------------------------------------------------
EXEMPTION_SCOPE_LONG_TERM_STR: str = "LTCG_ONLY"
EXEMPTION_SCOPE_TOTAL_GAINS_STR: str = "TOTAL_GAINS"
EXEMPTION_SCOPES_TUPLE: tuple = (
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXEMPTION_SCOPE_TOTAL_GAINS_STR,
)

PRESET_EQUITY_STR: str = "Equity-Oriented (Default)"
PRESET_DEBT_STR: str = "Debt (post Apr 1, 2023) - slab"
PRESET_CUSTOM_STR: str = "Custom"
PRESET_NAMES_TUPLE: tuple = (
    PRESET_EQUITY_STR,
    PRESET_DEBT_STR,
    PRESET_CUSTOM_STR,
)

EQUITY_SHORT_TERM_PERCENT_FLOAT: float = 20.0
EQUITY_LONG_TERM_PERCENT_FLOAT: float = 12.5
EQUITY_LONG_TERM_MONTHS_INT: int = 12
EQUITY_EXEMPTION_AMOUNT_FLOAT: float = 125_000.0
EQUITY_EXEMPTION_SCOPE_STR: str = EXEMPTION_SCOPE_LONG_TERM_STR

DEBT_LONG_TERM_PERCENT_FLOAT: float = 0.0
DEBT_LONG_TERM_MONTHS_INT: int = 9_999
DEBT_EXEMPTION_AMOUNT_FLOAT: float = 0.0
DEBT_EXEMPTION_SCOPE_STR: str = EXEMPTION_SCOPE_TOTAL_GAINS_STR

# ------------------------------------------------------------------
# Asset editor column labels
# ------------------------------------------------------------------
COLUMN_FUND_NAME_STR: str = "Asset name"
COLUMN_PRESET_STR: str = "Tax treatment"
COLUMN_OVERRIDE_PRESET_STR: str = "Override Preset?"
COLUMN_MONTHLY_SIP_STR: str = "SIP / month"
COLUMN_FUND_STEPUP_STR: str = "Asset step-up %"
COLUMN_GROSS_RETURN_STR: str = "Return % (gross)"
COLUMN_EXPENSE_STR: str = "Expense %"
COLUMN_FUND_START_STR: str = "Starts"
COLUMN_TARGET_ALLOCATION_STR: str = "Target Allocation %"
COLUMN_SHORT_TERM_TAX_STR: str = "STCG %"
COLUMN_LONG_TERM_TAX_STR: str = "LTCG %"
COLUMN_LONG_TERM_MONTHS_STR: str = "LTCG threshold (months)"
# These two are dataframe *keys*, not just captions: the fund editor
# writes them and the fund builder reads them back. Naming a currency
# in a key would mean a saved scenario stopped loading the moment the
# reader switched currency, so they stay neutral and the amount's
# currency is carried by the surrounding controls instead.
COLUMN_EXEMPTION_AMOUNT_STR: str = "Exemption (amount)"
COLUMN_EXEMPTION_SCOPE_STR: str = "Exemption Scope"
COLUMN_ALLOCATION_PERCENT_STR: str = "Allocation %"
COLUMN_INITIAL_INVESTMENT_STR: str = "Lump sum now"
COLUMN_EXIT_LOAD_STR: str = "Exit load %"
COLUMN_EXIT_LOAD_MONTHS_STR: str = "Exit load within (months)"
COLUMN_TRANSACTION_TAX_STR: str = "STT % on sale"

# ------------------------------------------------------------------
# Per-asset summary column labels
# ------------------------------------------------------------------
SUMMARY_FUND_NAME_STR: str = "Asset"
SUMMARY_PRESET_STR: str = "Tax treatment"
SUMMARY_START_STR: str = "Start"
SUMMARY_NET_RETURN_STR: str = "Net return % (used)"
SUMMARY_INVESTED_STR: str = "Invested (principal)"
SUMMARY_WITHDRAWN_STR: str = "Withdrawn (gross)"
SUMMARY_ENDING_VALUE_STR: str = "Ending Value"
SUMMARY_WEALTH_STR: str = "Wealth Generated (End+Withdraw)"
SUMMARY_GAIN_STR: str = "Gain (Wealth-Invested)"
SUMMARY_TAX_PAID_STR: str = "Tax Paid (realized)"
SUMMARY_SHORT_TERM_GAIN_STR: str = "STCG realized (gross gain)"
SUMMARY_LONG_TERM_GAIN_STR: str = "LTCG realized (gross gain)"
SUMMARY_REALIZED_LOSS_STR: str = "Loss realized"
SUMMARY_UNREALIZED_GAIN_STR: str = "Unrealized gain (untaxed)"
SUMMARY_CHARGES_STR: str = "Exit load + STT paid"
SUMMARY_EXIT_COST_STR: str = "Cost to exit today"
SUMMARY_MONEY_COLUMNS_TUPLE: tuple = (
    SUMMARY_REALIZED_LOSS_STR,
    SUMMARY_UNREALIZED_GAIN_STR,
    SUMMARY_CHARGES_STR,
    SUMMARY_EXIT_COST_STR,
    SUMMARY_INVESTED_STR,
    SUMMARY_WITHDRAWN_STR,
    SUMMARY_ENDING_VALUE_STR,
    SUMMARY_WEALTH_STR,
    SUMMARY_GAIN_STR,
    SUMMARY_TAX_PAID_STR,
    SUMMARY_SHORT_TERM_GAIN_STR,
    SUMMARY_LONG_TERM_GAIN_STR,
)

# ------------------------------------------------------------------
# Monthly series column labels
# ------------------------------------------------------------------
SERIES_MONTH_STR: str = "Month"
SERIES_PORTFOLIO_VALUE_STR: str = "Portfolio_Value"
SERIES_INVESTED_STR: str = "Portfolio_Invested"
SERIES_WITHDRAWN_STR: str = "Portfolio_Withdrawn"
SERIES_TAX_PAID_STR: str = "Portfolio_TaxPaid"
SERIES_MONTHLY_SIP_STR: str = "Monthly_SIP"
SERIES_MONTHLY_WITHDRAWAL_STR: str = "Monthly_SWP_Sold"
SERIES_REQUESTED_WITHDRAWAL_STR: str = "Monthly_SWP_Requested"
SERIES_UNMET_WITHDRAWAL_STR: str = "Monthly_SWP_Unmet"
SERIES_MONTHLY_TAX_STR: str = "Monthly_Tax"
SERIES_MONTHLY_CHARGES_STR: str = "Monthly_Charges"
SERIES_DRAWDOWN_STR: str = "Drawdown_Percent"

# ------------------------------------------------------------------
# Presentation defaults
# ------------------------------------------------------------------
DASHBOARD_TITLE_STR: str = "SIP Portfolio Dashboard"
DASHBOARD_HEIGHT_INT: int = 950
DONUT_HOLE_RATIO_FLOAT: float = 0.58
PLOTLY_TEMPLATE_STR: str = "plotly_white"
EXCEL_FILE_NAME_STR: str = "sip_dashboard_export.xlsx"
PDF_FILE_NAME_STR: str = "sip_dashboard_export.pdf"
EXCEL_MIME_TYPE_STR: str = (
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet"
)
PDF_MIME_TYPE_STR: str = "application/pdf"
