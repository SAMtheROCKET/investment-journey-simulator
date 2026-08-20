"""Calendar helpers for month grids and tax years."""

from __future__ import annotations

from datetime import date

from investment_journey_simulator.constants import (
    FINANCIAL_YEAR_START_MONTH_INT,
    MONTHS_IN_YEAR_INT,
)


def count_months_between_dates_int(
    start_date: date,
    end_date: date,
) -> int:
    """Count whole calendar months from one date to another.

    Brief:
        Day of month is ignored because the simulator works on a
        month grid where every period starts on the first day.

    Arguments:
        start_date (date): Earlier reference date.
        end_date (date): Later reference date.

    Returns:
        int: Month difference, negative when the order is reversed.

    Warning:
        The result is not clamped; callers that need a non-negative
        offset must clamp it themselves.
    """
    year_gap_int = end_date.year - start_date.year
    month_gap_int = end_date.month - start_date.month
    return year_gap_int * MONTHS_IN_YEAR_INT + month_gap_int


def derive_financial_year_int(
    reference_date: date,
    start_month_int: int = FINANCIAL_YEAR_START_MONTH_INT,
) -> int:
    """Derive the tax year label of a date in one jurisdiction.

    Brief:
        A tax year is labelled by the calendar year it opens in, so
        an April-start year covering April 2025 to March 2026 is
        2025. A start month of one gives the calendar year back
        unchanged, which is what most of the world uses.

    Arguments:
        reference_date (date): Date whose tax year is needed.
        start_month_int (int): Month the tax year opens in, one for
            January through twelve for December. Defaults to April,
            which is India's.

    Returns:
        int: Calendar year in which that tax year started.

    Warning:
        Resolution is a whole month. The United Kingdom's 6 April
        start cannot be expressed exactly; month four misplaces
        gains realised in the first five days of April.
    """
    clamped_start_month_int = min(
        MONTHS_IN_YEAR_INT, max(1, int(start_month_int))
    )
    if reference_date.month >= clamped_start_month_int:
        return reference_date.year
    return reference_date.year - 1


def build_month_start_dates_list(
    start_date: date,
    total_months_int: int,
) -> list[date]:
    """Build consecutive month-start dates for a simulation grid.

    Brief:
        Produces one date per simulated month, always anchored to
        the first day so that month arithmetic stays exact.

    Arguments:
        start_date (date): First month of the simulation.
        total_months_int (int): Number of months to generate.

    Returns:
        List[date]: Month-start dates in chronological order.

    Warning:
        A non-positive month count yields an empty list rather than
        raising an error.
    """
    month_dates_list: list[date] = []
    for offset_int in range(max(0, int(total_months_int))):
        zero_based_month_int = start_date.month - 1 + offset_int
        year_int = start_date.year + zero_based_month_int // (
            MONTHS_IN_YEAR_INT
        )
        month_int = zero_based_month_int % MONTHS_IN_YEAR_INT + 1
        month_dates_list.append(date(year_int, month_int, 1))
    return month_dates_list


def is_month_within_range_bool(
    candidate_date: date,
    range_start_date: date,
    range_end_date: date,
) -> bool:
    """Check whether a month falls inside an inclusive range.

    Brief:
        Comparison uses year and month only, so a range typed as
        mid-month still covers the whole boundary months.

    Arguments:
        candidate_date (date): Month being tested.
        range_start_date (date): Inclusive first month of the range.
        range_end_date (date): Inclusive last month of the range.

    Returns:
        bool: True when the candidate month lies in the range.

    Warning:
        A reversed range (end before start) never matches anything.
    """
    candidate_key_tuple = (candidate_date.year, candidate_date.month)
    start_key_tuple = (range_start_date.year, range_start_date.month)
    end_key_tuple = (range_end_date.year, range_end_date.month)
    return start_key_tuple <= candidate_key_tuple <= end_key_tuple
