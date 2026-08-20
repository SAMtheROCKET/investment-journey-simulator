"""Return-rate conversions used by the growth engine."""

from __future__ import annotations

from investment_journey_simulator.constants import (
    EXPENSE_MODEL_ACCRUED_STR,
    MAXIMUM_EXPENSE_PERCENT_FLOAT,
    MINIMUM_ANNUAL_RETURN_PERCENT_FLOAT,
    MINIMUM_EXPENSE_PERCENT_FLOAT,
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
)


def clamp_annual_return_percent_float(
    annual_return_percent_float: float,
) -> float:
    """Keep an annual return inside a mathematically valid range.

    Brief:
        A return of minus one hundred percent or worse destroys the
        whole corpus and makes fractional powers undefined, so it
        is clamped just above that boundary.

    Arguments:
        annual_return_percent_float (float): Requested return.

    Returns:
        float: Return guaranteed to be above minus one hundred.

    Warning:
        Clamping is silent; validate user input separately if the
        exact value matters.
    """
    return max(
        MINIMUM_ANNUAL_RETURN_PERCENT_FLOAT,
        float(annual_return_percent_float),
    )


def clamp_expense_percent_float(
    expense_percent_float: float,
) -> float:
    """Keep an expense ratio inside a valid range.

    Brief:
        Negative expenses would create money and a ratio of one
        hundred percent would wipe the fund out in a year.

    Arguments:
        expense_percent_float (float): Requested expense ratio.

    Returns:
        float: Expense ratio between zero and just under hundred.

    Warning:
        Clamping is silent; validate user input separately.
    """
    return min(
        MAXIMUM_EXPENSE_PERCENT_FLOAT,
        max(
            MINIMUM_EXPENSE_PERCENT_FLOAT,
            float(expense_percent_float),
        ),
    )


def convert_annual_to_monthly_rate_float(
    annual_return_percent_float: float,
) -> float:
    """Convert an annual return percentage to a monthly rate.

    Brief:
        Uses effective compounding, so twelve monthly steps exactly
        reproduce the stated annual return.

    Arguments:
        annual_return_percent_float (float): Annual return in
            percent, for example 12.0 for twelve percent.

    Returns:
        float: Effective monthly rate as a decimal fraction.

    Warning:
        Returns at or below minus one hundred percent are clamped
        instead of raising a domain error.
    """
    annual_rate_float = clamp_annual_return_percent_float(
        annual_return_percent_float
    ) / PERCENT_TOTAL_FLOAT
    monthly_exponent_float = 1.0 / MONTHS_IN_YEAR_INT
    return (1.0 + annual_rate_float) ** monthly_exponent_float - 1.0


def calculate_net_return_percent_float(
    gross_return_percent_float: float,
    expense_percent_float: float,
) -> float:
    """Reduce a gross return by the fund expense ratio.

    Brief:
        Planning approximation where the net return is the gross
        return minus the total expense ratio.

    Arguments:
        gross_return_percent_float (float): Gross annual return.
        expense_percent_float (float): Annual expense ratio percent.

    Returns:
        float: Net annual return percent used for compounding.

    Warning:
        Real funds accrue expenses on the net asset value, so this
        subtraction slightly misstates the drag; use the accrual
        model for a closer figure.
    """
    return clamp_annual_return_percent_float(
        gross_return_percent_float
    ) - clamp_expense_percent_float(expense_percent_float)


def calculate_monthly_rate_after_expense_float(
    gross_return_percent_float: float,
    expense_percent_float: float,
    expense_model_str: str,
) -> float:
    """Derive the monthly rate a fund actually compounds at.

    Brief:
        The accrual model charges the expense ratio continuously on
        the net asset value, which is how a real fund works, while
        the simple model just subtracts it from the gross return.

    Arguments:
        gross_return_percent_float (float): Gross annual return.
        expense_percent_float (float): Annual expense ratio percent.
        expense_model_str (str): Expense model identifier.

    Returns:
        float: Effective monthly rate as a decimal fraction.

    Warning:
        The two models differ by roughly the product of the return
        and the expense ratio, which compounds over long horizons.
    """
    if expense_model_str != EXPENSE_MODEL_ACCRUED_STR:
        return convert_annual_to_monthly_rate_float(
            calculate_net_return_percent_float(
                gross_return_percent_float, expense_percent_float
            )
        )
    gross_monthly_factor_float = (
        1.0
        + convert_annual_to_monthly_rate_float(
            gross_return_percent_float
        )
    )
    expense_rate_float = clamp_expense_percent_float(
        expense_percent_float
    ) / PERCENT_TOTAL_FLOAT
    expense_monthly_factor_float = (1.0 - expense_rate_float) ** (
        1.0 / MONTHS_IN_YEAR_INT
    )
    return (
        gross_monthly_factor_float * expense_monthly_factor_float
        - 1.0
    )


def convert_monthly_to_annual_percent_float(
    monthly_rate_float: float,
) -> float:
    """Annualise an effective monthly rate.

    Brief:
        Inverse of the annual to monthly conversion, used to report
        the rate a fund really compounds at after expenses.

    Arguments:
        monthly_rate_float (float): Effective monthly rate.

    Returns:
        float: Equivalent annual return in percent.

    Warning:
        Monthly rates at or below minus one hundred percent are
        clamped to keep the power well defined.
    """
    safe_monthly_rate_float = max(-0.9999, float(monthly_rate_float))
    annual_rate_float = (
        1.0 + safe_monthly_rate_float
    ) ** MONTHS_IN_YEAR_INT - 1.0
    return annual_rate_float * PERCENT_TOTAL_FLOAT


def convert_nominal_to_real_percent_float(
    nominal_return_percent_float: float,
    inflation_percent_float: float,
) -> float:
    """Deflate a nominal return into an inflation-adjusted return.

    Brief:
        Applies the Fisher relation so that the real series shows
        today's purchasing power instead of future rupees.

    Arguments:
        nominal_return_percent_float (float): Nominal annual return.
        inflation_percent_float (float): Annual inflation percent.

    Returns:
        float: Real annual return percent.

    Warning:
        Inflation at or below minus one hundred percent is rejected
        and the nominal return is returned unchanged.
    """
    nominal_rate_float = float(nominal_return_percent_float) / (
        PERCENT_TOTAL_FLOAT
    )
    inflation_rate_float = float(inflation_percent_float) / (
        PERCENT_TOTAL_FLOAT
    )
    if (1.0 + inflation_rate_float) <= 0.0:
        return float(nominal_return_percent_float)
    real_rate_float = (
        (1.0 + nominal_rate_float) / (1.0 + inflation_rate_float) - 1.0
    )
    return real_rate_float * PERCENT_TOTAL_FLOAT


def calculate_growth_factor_float(
    monthly_rate_float: float,
    months_held_int: int,
) -> float:
    """Compute the compounding factor for a holding period.

    Brief:
        Returns the multiplier that converts an invested principal
        into its value after the given number of months.

    Arguments:
        monthly_rate_float (float): Effective monthly rate.
        months_held_int (int): Months the money stayed invested.

    Returns:
        float: Growth multiplier, never below one month of zero
            growth (a factor of exactly one).

    Warning:
        Negative holding periods are treated as zero months, which
        keeps same-month purchases and sales value neutral.
    """
    if int(months_held_int) <= 0:
        return 1.0
    return (1.0 + float(monthly_rate_float)) ** int(months_held_int)


def apply_annual_growth_factor_float(
    base_amount_float: float,
    annual_change_percent_float: float,
    elapsed_years_int: int,
) -> float:
    """Escalate an amount by a yearly percentage change.

    Brief:
        Shared by step-up contributions and by withdrawal schedules
        that grow or shrink once every completed year.

    Arguments:
        base_amount_float (float): Starting amount before growth.
        annual_change_percent_float (float): Yearly change percent.
        elapsed_years_int (int): Completed years since the start.

    Returns:
        float: Escalated amount, never negative.

    Warning:
        Growth is applied in whole-year steps, not continuously.
    """
    change_rate_float = float(annual_change_percent_float) / (
        PERCENT_TOTAL_FLOAT
    )
    growth_factor_float = (1.0 + change_rate_float) ** max(
        0, int(elapsed_years_int)
    )
    return max(0.0, float(base_amount_float) * growth_factor_float)
