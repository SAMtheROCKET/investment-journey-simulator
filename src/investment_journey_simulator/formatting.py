"""Money and duration formatting for the dashboard.

Every amount on screen passes through here, and every helper below
takes the currency that amount is denominated in. The default is
the rupee - that is what this program was built for and what every
caller assumed before currencies became configurable - but that
default is now the only Indian thing about these functions.

Digit grouping and magnitude names live in `currency.py`, which
owns how a currency writes its numbers. This module owns what the
dashboard *says* about an amount: the compact form for a tile, the
spelled-out form that makes a stray zero obvious, and the sentence
that turns a percentage into money.
"""

from __future__ import annotations

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
)
from investment_journey_simulator.currency import (
    GROUPING_INDIAN_STR,
    Currency,
    describe_money_str,
    format_money_str,
    group_digits_str,
    resolve_currency,
)


def resolve_display_currency(
    currency: Currency | None = None,
) -> Currency:
    """Settle which currency an amount should be shown in.

    Brief:
        One place decides the fallback, so a caller that has no
        currency to hand behaves the same as every other.

    Arguments:
        currency (Optional[Currency]): Currency to display in.

    Returns:
        Currency: The one given, or the rupee.

    Warning:
        The fallback is a display default only. It never implies
        the amount was computed under Indian rules.
    """
    if currency is not None:
        return currency
    return resolve_currency()


def group_digits_indian_style_str(amount_float: float) -> str:
    """Group an amount using Indian digit separators.

    Brief:
        Converts 1234567 into "12,34,567" by keeping the last
        three digits together and pairing every digit before them.

    Arguments:
        amount_float (float): Amount to group.

    Returns:
        str: Digit string with commas and an optional minus sign.

    Warning:
        Rounded to whole units, so paise are lost. Only meaningful
        for a currency that groups this way; prefer
        format_money_amount_str, which asks the currency.
    """
    return group_digits_str(amount_float, GROUPING_INDIAN_STR, 0)


def format_money_amount_str(
    amount_float: float,
    currency: Currency | None = None,
) -> str:
    """Render an amount with its symbol and grouping.

    Brief:
        The default display format of every summary tile, now
        asking the currency how it writes numbers rather than
        assuming rupees.

    Arguments:
        amount_float (float): Amount to render.
        currency (Optional[Currency]): Currency it is in.

    Returns:
        str: For example "₹12,34,567" or "$1,234,567.00".

    Warning:
        Display only; never parse this string back.
    """
    return format_money_str(
        amount_float, resolve_display_currency(currency)
    )


def format_compact_money_str(
    amount_float: float,
    currency: Currency | None = None,
) -> str:
    """Shorten an amount using its own currency's suffixes.

    Brief:
        A headline tile has no room for thirteen digits, and the
        suffix has to belong to the currency: "L" means lakh and
        says nothing true about a dollar figure.

    Arguments:
        amount_float (float): Amount to render.
        currency (Optional[Currency]): Currency it is in.

    Returns:
        str: For example "₹1.24Cr" or "$1.24M".

    Warning:
        Rounding to two decimals hides differences below one
        percent of the displayed unit. The minus sign leads the
        symbol, so a negative reads "-₹500" and not "₹-500".
    """
    display_currency = resolve_display_currency(currency)
    signed_float = float(amount_float)
    sign_str = "-" if signed_float < 0 else ""
    absolute_float = abs(signed_float)
    for unit_float, suffix_str in display_currency.compact_tuple:
        if absolute_float >= unit_float:
            scaled_float = absolute_float / unit_float
            return (
                f"{sign_str}{display_currency.symbol_str}"
                f"{scaled_float:.2f}{suffix_str}"
            )
    return sign_str + format_money_str(
        absolute_float, display_currency
    )


def describe_amount_str(
    amount_float: float,
    currency: Currency | None = None,
) -> str:
    """Say what a figure actually is, in words and digits.

    Brief:
        A number typed into a box is easy to misread by a factor
        of ten. Echoing it back grouped *and* named in the
        magnitudes its own currency counts in - lakh and crore for
        rupees, million elsewhere - makes an extra zero obvious.

    Arguments:
        amount_float (float): Amount to describe.
        currency (Optional[Currency]): Currency it is in.

    Returns:
        str: For example "₹2,00,000 - 2.00 lakh".

    Warning:
        Display only. Amounts below the smallest named magnitude
        are given plainly, because naming them adds nothing.
    """
    return describe_money_str(
        amount_float, resolve_display_currency(currency)
    )


def describe_months_str(months_int: int) -> str:
    """State a duration in both months and years.

    Brief:
        Plans are typed in years and simulated in months, and the
        reader should never have to convert between the two in
        their head.

    Arguments:
        months_int (int): Duration in whole months.

    Returns:
        str: For example "240 months - 20 years".

    Warning:
        Years are rounded to one decimal; the months are exact.
    """
    month_count_int = max(0, int(months_int))
    if month_count_int < MONTHS_IN_YEAR_INT:
        return f"{month_count_int} months"
    year_count_float = month_count_int / MONTHS_IN_YEAR_INT
    return (
        f"{month_count_int} months - {year_count_float:.1f} years"
    )


def describe_annual_rate_str(
    percent_float: float,
    principal_float: float = 0.0,
    currency: Currency | None = None,
) -> str:
    """Explain an annual percentage in money the reader can feel.

    Brief:
        "12% a year" means little on its own. Stating the monthly
        rate it compounds to, and what it is worth on a principal,
        turns a rate into something checkable.

    Arguments:
        percent_float (float): Annual rate in percent.
        principal_float (float): Optional amount to apply it to.
        currency (Optional[Currency]): Currency of that amount.

    Returns:
        str: Description of the rate, and its first-year effect.

    Warning:
        Uses the effective monthly rate the engine uses, not the
        annual figure divided by twelve.
    """
    rate_float = float(percent_float) / PERCENT_TOTAL_FLOAT
    monthly_percent_float = (
        (1.0 + rate_float) ** (1.0 / MONTHS_IN_YEAR_INT) - 1.0
    ) * PERCENT_TOTAL_FLOAT
    description_str = (
        f"{percent_float:.2f}% a year "
        f"({monthly_percent_float:.4f}% a month, compounded)"
    )
    if principal_float <= 0.0:
        return description_str
    growth_float = float(principal_float) * rate_float
    return (
        f"{description_str} - "
        f"{format_money_amount_str(growth_float, currency)} on "
        f"{format_money_amount_str(principal_float, currency)} "
        "in the first year"
    )
