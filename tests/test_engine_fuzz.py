"""Thousands of random plans, checked two ways.

A test suite made of hand-written cases can only cover the
combinations somebody thought of. The two defects that started this
work - a screen flattening every fund's return, and a portfolio
instalment handed to every fund in full - both survived a large and
carefully written suite, because nobody had written the case that
crossed them.

So this file does not write cases. It generates them: random
horizons, random funds, random step-ups, pauses, withdrawals,
rebalances, instalment changes and lump sums, deliberately placed so
they collide. Each plan is then checked in one of two ways.

**With tax off**, against `reference_simulator`, which computes the
same portfolio by a different algorithm - one number per fund rolled
forward, no lot book at all. The two must agree to floating point.
Any disagreement is a real difference of opinion between two
independent implementations.

**With tax, exit loads and the transaction tax on**, no independent
answer exists, so the plans are held to laws instead: money is
conserved, cumulative totals only ever rise and always equal the sum
of their own monthly columns, nothing goes negative, and a
withdrawal only ever falls short when the corpus is genuinely empty.

The conservation law is the strongest of them and is worth reading
twice. Setting every return to zero removes growth from the
arithmetic entirely, and what is left is an identity that has to
hold exactly:

    what is left  ==  what went in
                      - what came out
                      - what the fund house charged

That identity is what caught the exit-load defect. The charge was
computed correctly, reported correctly, and never actually taken
out of the portfolio, so the books were short by exactly the
charges - in 873 of the first 3,000 random plans. The test that was
supposed to cover this asserted only that the charge equalled one
per cent of the withdrawal, which was true whether or not anybody
ever paid it.

Seeds are fixed, so a failure here is reproducible from the number
in the message. The counts are kept modest enough to run in the
normal suite; the same generators have been run over far more
scenarios by hand.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from investment_journey_simulator.engine import PortfolioSimulator
from reference_simulator import run_reference
from scenario_factory import (
    build_scenario_tuple,
    describe_scenario_str,
)

# A rupee has two decimal places; anything smaller is noise, not
# money. Both bounds are needed because these plans range from a
# few thousand rupees to fifty trillion, and neither an absolute
# nor a relative tolerance alone covers that span.
PAISA_TOLERANCE_FLOAT: float = 0.01
RELATIVE_TOLERANCE_FLOAT: float = 1e-9

EXACT_SCENARIO_COUNT_INT: int = 600
INVARIANT_SCENARIO_COUNT_INT: int = 400
CONSERVATION_SCENARIO_COUNT_INT: int = 300


def is_close_bool(got_float: float, want_float: float) -> bool:
    """Equal to the paisa, or to nine significant figures."""
    allowed_float = max(
        PAISA_TOLERANCE_FLOAT,
        RELATIVE_TOLERANCE_FLOAT
        * max(abs(got_float), abs(want_float)),
    )
    return abs(got_float - want_float) <= allowed_float


def build_failure_message_str(
    seed_int: int,
    label_str: str,
    got_float: float,
    want_float: float,
) -> str:
    """A message that carries the whole scenario with it."""
    fund_list, settings = build_scenario_tuple(seed_int)
    return (
        f"seed {seed_int}: {label_str} "
        f"engine={got_float:,.4f} reference={want_float:,.4f} "
        f"difference={got_float - want_float:,.4f}"
        + chr(10)
        + describe_scenario_str(fund_list, settings)
    )


def build_flat_fund_list(fund_list: list) -> list:
    """The same funds with every source of growth removed.

    Clearing the rate is not enough on its own: a fund carrying an
    explicit monthly path ignores its annual rate entirely, so the
    path has to go too or "zero return" quietly is not zero.
    """
    return [
        replace(
            fund_configuration,
            gross_return_percent_float=0.0,
            expense_percent_float=0.0,
            monthly_rate_path_list=None,
            monthly_rate_override_float=None,
        )
        for fund_configuration in fund_list
    ]


def seed_range_list(
    start_int: int, count_int: int
) -> list[int]:
    """A contiguous block of seeds, as a parametrisation."""
    return list(range(start_int, start_int + count_int))


# ------------------------------------------------------------------
# Two implementations, one answer.
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "batch_start_int",
    seed_range_list(0, EXACT_SCENARIO_COUNT_INT // 20),
)
def test_the_engine_agrees_with_an_independent_simulator(
    batch_start_int,
):
    """Twenty random plans per batch, every figure compared.

    REFERENCE: G3-CROSSCHECK. The reference simulator carries one
    number per fund and rolls it forward; the engine keeps a book
    of lots and compounds each parcel from its own purchase month.
    Nothing about the two algorithms is shared, so agreement is
    evidence rather than tautology.
    """
    for offset_int in range(20):
        seed_int = batch_start_int * 20 + offset_int
        fund_list, settings = build_scenario_tuple(
            seed_int, is_taxed_bool=False
        )
        engine_result = PortfolioSimulator(fund_list, settings).run()
        reference_outcome = run_reference(fund_list, settings)
        for label_str, got_float, want_float in (
            (
                "ending value",
                engine_result.ending_value_float,
                reference_outcome.ending_value_float,
            ),
            (
                "invested",
                engine_result.ending_invested_float,
                reference_outcome.invested_float,
            ),
            (
                "withdrawn",
                engine_result.ending_withdrawn_float,
                reference_outcome.withdrawn_float,
            ),
        ):
            assert is_close_bool(got_float, want_float), (
                build_failure_message_str(
                    seed_int, label_str, got_float, want_float
                )
            )


@pytest.mark.parametrize(
    "seed_int", seed_range_list(9000, 40)
)
def test_every_fund_agrees_fund_by_fund(seed_int):
    """Portfolio totals can agree while the split is wrong.

    REFERENCE: G3-CROSSCHECK. This is the shape of the defect a
    reader originally reported, so it is checked per fund and not
    only in total.
    """
    fund_list, settings = build_scenario_tuple(
        seed_int, is_taxed_bool=False
    )
    engine_result = PortfolioSimulator(fund_list, settings).run()
    reference_outcome = run_reference(fund_list, settings)
    for fund_outcome in engine_result.fund_outcomes_list:
        want_float = reference_outcome.value_by_fund_dict[
            fund_outcome.name_str
        ]
        assert is_close_bool(
            fund_outcome.ending_value_float, want_float
        ), build_failure_message_str(
            seed_int,
            f"{fund_outcome.name_str} ending value",
            fund_outcome.ending_value_float,
            want_float,
        )


@pytest.mark.parametrize(
    "seed_int", seed_range_list(7000, 40)
)
def test_the_monthly_series_agrees_month_by_month(seed_int):
    """Not merely the last month: every month of the run.

    REFERENCE: G3-CROSSCHECK. A run can arrive at the right total
    by two compensating errors, and a month-by-month comparison is
    what rules that out.
    """
    fund_list, settings = build_scenario_tuple(
        seed_int, is_taxed_bool=False
    )
    engine_result = PortfolioSimulator(fund_list, settings).run()
    reference_outcome = run_reference(fund_list, settings)
    engine_list = [
        snapshot.portfolio_value_float
        for snapshot in engine_result.monthly_snapshots_list
    ]
    assert len(engine_list) == len(
        reference_outcome.monthly_value_list
    )
    for month_index_int, (got_float, want_float) in enumerate(
        zip(
            engine_list,
            reference_outcome.monthly_value_list,
            strict=True,
        )
    ):
        assert is_close_bool(got_float, want_float), (
            build_failure_message_str(
                seed_int,
                f"value at month {month_index_int}",
                got_float,
                want_float,
            )
        )


# ------------------------------------------------------------------
# Laws that hold when tax makes an independent answer impossible.
# ------------------------------------------------------------------
def check_totals_only_rise(engine_result) -> list:
    """Cumulative counters may never decrease."""
    broken_list = []
    for field_str in (
        "invested_amount_float",
        "withdrawn_amount_float",
        "tax_paid_float",
    ):
        value_list = [
            getattr(snapshot, field_str)
            for snapshot in engine_result.monthly_snapshots_list
        ]
        if value_list != sorted(value_list):
            broken_list.append(f"{field_str} decreases")
    return broken_list


def check_totals_match_columns(engine_result) -> list:
    """Each running total equals the sum of its own months."""
    broken_list = []
    snapshot_list = engine_result.monthly_snapshots_list
    for label_str, total_float, monthly_str in (
        (
            "invested",
            engine_result.ending_invested_float,
            "monthly_sip_float",
        ),
        (
            "withdrawn",
            engine_result.ending_withdrawn_float,
            "monthly_withdrawal_float",
        ),
        (
            "tax",
            engine_result.ending_tax_paid_float,
            "monthly_tax_float",
        ),
    ):
        column_float = sum(
            getattr(snapshot, monthly_str)
            for snapshot in snapshot_list
        )
        if not is_close_bool(total_float, column_float):
            broken_list.append(
                f"{label_str} total {total_float:,.2f} != "
                f"monthly column {column_float:,.2f}"
            )
    return broken_list


def check_month_is_coherent(snapshot, index_int, settings) -> list:
    """Everything one month has to satisfy on its own."""
    broken_list = []
    if snapshot.portfolio_value_float < -PAISA_TOLERANCE_FLOAT:
        broken_list.append(f"negative value at month {index_int}")
    fund_total_float = sum(
        state.value_float for state in snapshot.fund_states_list
    )
    if not is_close_bool(
        fund_total_float, snapshot.portfolio_value_float
    ):
        broken_list.append(
            f"portfolio != sum of funds at month {index_int}"
        )
    if snapshot.unmet_withdrawal_float > PAISA_TOLERANCE_FLOAT:
        broken_list.extend(
            check_shortfall_is_honest(snapshot, index_int, settings)
        )
    return broken_list


def names_a_fund_this_month_bool(index_int, settings) -> bool:
    """Whether a lump withdrawal this month named one fund.

    A withdrawal that names a fund may only be met from that fund,
    so it can fall short while the rest of the portfolio is still
    full. That is the engine keeping a promise, not breaking one:
    taking the shortfall from a fund the reader did not name would
    be worse than reporting it unmet.
    """
    return any(
        int(withdrawal.month_index_int) == int(index_int)
        and withdrawal.fund_name_str
        for withdrawal in settings.one_off_withdrawals_list
    )


def check_shortfall_is_honest(snapshot, index_int, settings) -> list:
    """A withdrawal may only fall short when the money is gone."""
    if names_a_fund_this_month_bool(index_int, settings):
        return []
    paid_after_float = (
        0.0
        if settings.sip_at_month_start_bool
        else snapshot.monthly_sip_float
    )
    residue_float = (
        snapshot.portfolio_value_float - paid_after_float
    )
    if residue_float <= 1.0:
        return []
    return [
        f"month {index_int} left "
        f"{snapshot.unmet_withdrawal_float:,.2f} unpaid with "
        f"{residue_float:,.2f} still held"
    ]


@pytest.mark.parametrize(
    "batch_start_int",
    seed_range_list(0, INVARIANT_SCENARIO_COUNT_INT // 20),
)
def test_the_laws_hold_with_tax_and_charges_on(batch_start_int):
    """Twenty taxed plans per batch, held to their invariants.

    REFERENCE: G4-SYNTHETIC. No closed form exists once first-in
    first-out lots, an annual exemption and exit loads are in play,
    so these are the statements that must be true regardless of
    what the arithmetic underneath produces.
    """
    for offset_int in range(20):
        seed_int = batch_start_int * 20 + offset_int
        fund_list, settings = build_scenario_tuple(
            seed_int, is_taxed_bool=True
        )
        engine_result = PortfolioSimulator(fund_list, settings).run()
        broken_list = check_totals_only_rise(engine_result)
        broken_list.extend(check_totals_match_columns(engine_result))
        for index_int, snapshot in enumerate(
            engine_result.monthly_snapshots_list
        ):
            broken_list.extend(
                check_month_is_coherent(
                    snapshot, index_int, settings
                )
            )
            if broken_list:
                break
        assert not broken_list, (
            f"seed {seed_int}: {broken_list}"
            + chr(10)
            + describe_scenario_str(fund_list, settings)
        )


@pytest.mark.parametrize(
    "seed_int",
    seed_range_list(0, CONSERVATION_SCENARIO_COUNT_INT),
)
def test_no_rupee_is_created_or_destroyed(seed_int):
    """The books balance once growth is taken out of the picture.

    REFERENCE: G1-ANALYTIC. Every return set to zero, so there is
    no growth to account for and the identity is exact:

        left == paid in - taken out - charged

    This is the check that found the exit load being reported but
    never deducted. It failed on 873 of the first 3,000 random
    plans, by exactly the charges each time.
    """
    fund_list, settings = build_scenario_tuple(
        seed_int, is_taxed_bool=True
    )
    flat_fund_list = build_flat_fund_list(fund_list)
    engine_result = PortfolioSimulator(
        flat_fund_list, settings
    ).run()
    expected_float = (
        engine_result.ending_invested_float
        - engine_result.ending_withdrawn_float
        - engine_result.charges_paid_float
    )
    assert is_close_bool(
        engine_result.ending_value_float, expected_float
    ), build_failure_message_str(
        seed_int,
        "conservation at zero return",
        engine_result.ending_value_float,
        expected_float,
    )


@pytest.mark.parametrize(
    "seed_int",
    seed_range_list(0, 120),
)
def test_a_portfolio_that_never_gained_is_never_taxed(seed_int):
    """No gain, no tax - whatever the events did.

    REFERENCE: G2-STATUTORY. Capital gains tax applies to gains.
    A plan whose funds returned nothing has none to tax, however
    many times it rebalanced, withdrew or changed its instalment.
    """
    fund_list, settings = build_scenario_tuple(
        seed_int, is_taxed_bool=True
    )
    flat_fund_list = build_flat_fund_list(fund_list)
    engine_result = PortfolioSimulator(
        flat_fund_list, settings
    ).run()
    assert engine_result.ending_tax_paid_float == pytest.approx(
        0.0, abs=PAISA_TOLERANCE_FLOAT
    ), f"seed {seed_int} taxed a portfolio that never gained"
