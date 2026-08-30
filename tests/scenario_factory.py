"""Random plans, built to collide rather than to look sensible.

A generator that only produces plausible plans tests the cases
somebody already thought about. This one deliberately overlaps its
events: withdrawals that begin inside a pause, pauses that open on
a rebalancing month, several instalment changes landing on the same
month, funds that start after the money has begun coming out.

Every plan is built from a seed, so a failure is reproducible from
the number printed in the assertion.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date

from investment_journey_simulator.models import (
    FundConfiguration,
    InstalmentOverride,
    OneOffContribution,
    OneOffWithdrawal,
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    SimulationSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)

MONTHS_IN_YEAR_INT: int = 12
START_DATE: date = date(2026, 1, 1)

PRESET_STR: str = "Equity-Oriented (Default)"
FULL_METHOD_STR: str = "Full liquidation (exact target split)"
PARTIAL_METHOD_STR: str = "Partial (sell overweight only)"
TARGET_COLUMN_STR: str = "TARGET_ALLOC_COLUMN"
SIP_SPLIT_STR: str = "INITIAL_SIP_SPLIT"


def month_date_at(month_index_int: int) -> date:
    """The calendar month one index along the grid."""
    zero_based_int = START_DATE.month - 1 + int(month_index_int)
    return date(
        START_DATE.year + zero_based_int // MONTHS_IN_YEAR_INT,
        zero_based_int % MONTHS_IN_YEAR_INT + 1,
        1,
    )


def build_fund(
    rng: random.Random,
    index_int: int,
    horizon_months_int: int,
    is_taxed_bool: bool,
) -> FundConfiguration:
    """One fund with random economics and a random start month."""
    starts_late_bool = rng.random() < 0.25
    start_month_int = (
        rng.randrange(0, max(1, horizon_months_int // 2))
        if starts_late_bool
        else 0
    )
    return FundConfiguration(
        name_str=f"Fund-{index_int}",
        preset_str=PRESET_STR,
        monthly_sip_float=rng.choice(
            [0.0, 500.0, 2500.0, 10000.0, 45000.0]
        ),
        stepup_percent_float=rng.choice([0.0, 5.0, 12.0, -8.0]),
        gross_return_percent_float=rng.choice(
            [-4.0, 0.0, 4.5, 8.0, 12.0, 16.5, 22.0]
        ),
        expense_percent_float=rng.choice([0.0, 0.35, 1.25]),
        start_date=month_date_at(start_month_int),
        target_allocation_percent_float=rng.choice(
            [0.0, 15.0, 30.0, 55.0, 70.0]
        ),
        **build_tax_field_dict(rng, is_taxed_bool),
        expense_model_str=rng.choice(
            [
                "SIMPLE_SUBTRACTION",
                "SIMPLE_SUBTRACTION",
                "CONTINUOUS_ACCRUAL",
            ]
        ),
        monthly_rate_path_list=build_rate_path_list(
            rng, horizon_months_int
        ),
        initial_investment_float=rng.choice(
            [0.0, 0.0, 100000.0, 750000.0]
        ),
    )


def build_tax_field_dict(
    rng: random.Random, is_taxed_bool: bool
) -> dict:
    """One fund's tax parameters, or none of them.

    An untaxed run needs every rate at zero so the reference
    simulator - which keeps no lot book and therefore cannot tax
    anything - can be compared against it exactly.
    """
    if not is_taxed_bool:
        return {
            "short_term_tax_percent_float": 0.0,
            "long_term_tax_percent_float": 0.0,
            "long_term_threshold_months_int": 12,
            "exemption_amount_float": 0.0,
            "exemption_scope_str": "LTCG_ONLY",
            "is_always_short_term_bool": False,
            "exit_load_percent_float": 0.0,
            "exit_load_within_months_int": 0,
        }
    return {
        "short_term_tax_percent_float": 20.0,
        "long_term_tax_percent_float": 12.5,
        "long_term_threshold_months_int": 12,
        "exemption_amount_float": 125000.0,
        "exemption_scope_str": rng.choice(
            ["LTCG_ONLY", "LTCG_ONLY", "TOTAL_GAINS"]
        ),
        "is_always_short_term_bool": rng.random() < 0.3,
        "exit_load_percent_float": rng.choice([0.0, 1.0]),
        "exit_load_within_months_int": 12,
    }


def build_rate_path_list(
    rng: random.Random, horizon_months_int: int
) -> list | None:
    """Sometimes a realised path instead of one constant rate.

    A path is what a stochastic run hands the engine, and it is the
    only way sequence-of-returns risk shows up at all: the same
    average return arrives in a different order and the answer
    changes. One rate per simulated month, because a short path is
    a caller error the engine does not defend against.
    """
    if rng.random() < 0.8:
        return None
    return [
        rng.choice([-0.03, -0.01, 0.0, 0.004, 0.009, 0.02])
        for _month_int in range(horizon_months_int)
    ]


def build_stepup(rng: random.Random) -> StepUpSettings:
    """A random escalation rule, sometimes downwards."""
    mode_str = rng.choice(
        ["OFF", "GLOBAL", "GLOBAL", "PER_FUND", "BOTH"]
    )
    return StepUpSettings(
        mode_str=mode_str,
        global_stepup_percent_float=rng.choice(
            [0.0, 5.0, 10.0, 25.0, -15.0]
        ),
        interval_months_int=rng.choice([12, 12, 6, 24]),
        first_stepup_month_index_int=rng.choice([0, 0, 18, 37]),
        fixed_increment_amount_float=rng.choice([0.0, 0.0, 500.0]),
    )


def build_pauses(
    rng: random.Random,
    horizon_months_int: int,
    withdrawal_start_int: int,
) -> PauseSettings:
    """Breaks placed where they will collide with something."""
    range_list = []
    for _index_int in range(rng.choice([0, 1, 1, 2])):
        anchor_int = rng.choice(
            [
                rng.randrange(0, max(1, horizon_months_int)),
                withdrawal_start_int,
                max(0, withdrawal_start_int - 2),
                MONTHS_IN_YEAR_INT - 1,
            ]
        )
        length_int = rng.choice([1, 3, 12, 30])
        range_list.append(
            PauseRange(
                month_date_at(min(anchor_int, horizon_months_int)),
                month_date_at(
                    min(
                        anchor_int + length_int, horizon_months_int
                    )
                ),
                rng.choice(["SIP", "SIP", "SWP", "BOTH"]),
            )
        )
    recurring_list = (
        [rng.randrange(1, 13)] if rng.random() < 0.15 else []
    )
    return PauseSettings(
        sip_pause_months_list=recurring_list,
        withdrawal_pause_months_list=(
            [rng.randrange(1, 13)] if rng.random() < 0.1 else []
        ),
        pause_ranges_list=range_list,
    )


def build_withdrawal(
    rng: random.Random,
    horizon_months_int: int,
    start_month_int: int,
) -> WithdrawalSettings:
    """A withdrawal plan, off about a third of the time."""
    if rng.random() < 0.35:
        return WithdrawalSettings(is_enabled_bool=False)
    mode_str = rng.choice(
        ["FIXED", "FIXED", "PERCENT_OF_CORPUS", "SCHEDULE_12"]
    )
    schedule_list = [
        rng.choice([0.0, 2000.0, 9000.0])
        for _index_int in range(MONTHS_IN_YEAR_INT)
    ]
    return WithdrawalSettings(
        is_enabled_bool=True,
        start_month_index_int=start_month_int,
        mode_str=mode_str,
        fixed_amount_float=rng.choice(
            [1000.0, 15000.0, 60000.0]
        ),
        monthly_schedule_list=schedule_list,
        annual_change_percent_float=rng.choice([0.0, 6.0, -10.0]),
        monthly_change_percent_list=[],
        portfolio_percent_float=rng.choice([0.25, 1.0, 3.0]),
    )


def build_rebalance(
    rng: random.Random,
    is_taxed_bool: bool,
) -> RebalanceSettings:
    """Calendar rebalancing, since that is what the oracle models."""
    if rng.random() < 0.4:
        return RebalanceSettings(
            is_enabled_bool=False,
            use_contribution_steering_bool=rng.random() < 0.3,
            target_mode_str=TARGET_COLUMN_STR,
        )
    return RebalanceSettings(
        is_enabled_bool=True,
        interval_months_int=rng.choice([3, 6, 12, 12, 24]),
        method_str=rng.choice(
            [FULL_METHOD_STR, FULL_METHOD_STR, PARTIAL_METHOD_STR]
        ),
        target_mode_str=rng.choice(
            [TARGET_COLUMN_STR, SIP_SPLIT_STR]
        ),
        tax_funding_str=(
            "PORTFOLIO" if is_taxed_bool else "OUTSIDE"
        ),
        maximum_events_int=rng.choice([0, 0, 3]),
        trigger_str=rng.choice(
            [
                "CALENDAR",
                "CALENDAR",
                "DRIFT_BAND",
                "CALENDAR_AND_BAND",
            ]
        ),
        drift_band_percent_float=rng.choice([0.0, 2.0, 5.0, 15.0]),
        use_contribution_steering_bool=rng.random() < 0.25,
        rebalance_month_index_tuple=tuple(
            rng.randrange(0, 120) for _index_int in range(2)
        )
        if rng.random() < 0.15
        else (),
    )


def build_override_list(
    rng: random.Random,
    horizon_months_int: int,
    fund_list: list,
) -> list:
    """Dated changes to the instalment, sometimes on one month."""
    override_list = []
    for _index_int in range(rng.choice([0, 0, 1, 2, 3])):
        month_int = rng.choice(
            [
                0,
                rng.randrange(0, max(1, horizon_months_int)),
                MONTHS_IN_YEAR_INT,
            ]
        )
        names_fund_bool = rng.random() < 0.3
        override_list.append(
            InstalmentOverride(
                month_int,
                rng.choice([0.0, 5000.0, 25000.0, 90000.0]),
                (
                    rng.choice(fund_list).name_str
                    if names_fund_bool
                    else ""
                ),
            )
        )
    return override_list


def build_one_off_list(
    rng: random.Random,
    horizon_months_int: int,
    fund_list: list,
) -> list:
    """Lump sums dropped in at random months."""
    one_off_list = []
    for _index_int in range(rng.choice([0, 0, 0, 1, 2])):
        one_off_list.append(
            OneOffContribution(
                rng.randrange(0, max(1, horizon_months_int)),
                rng.choice([25000.0, 200000.0]),
                (
                    rng.choice(fund_list).name_str
                    if rng.random() < 0.4
                    else ""
                ),
            )
        )
    return one_off_list


def build_one_off_withdrawal_list(
    rng: random.Random,
    horizon_months_int: int,
    fund_list: list,
) -> list:
    """Lump sums taken out at random months.

    Deliberately allowed to exceed the corpus sometimes, because a
    withdrawal larger than the money available is a real thing a
    reader can ask for and the engine has to cap it rather than go
    negative.
    """
    withdrawal_list = []
    for _index_int in range(rng.choice([0, 0, 0, 1, 2])):
        withdrawal_list.append(
            OneOffWithdrawal(
                rng.randrange(0, max(1, horizon_months_int)),
                rng.choice([50000.0, 250000.0, 5000000.0]),
                (
                    rng.choice(fund_list).name_str
                    if rng.random() < 0.3
                    else ""
                ),
            )
        )
    return withdrawal_list


def build_liquidation_month_int(
    rng: random.Random,
    horizon_months_int: int,
) -> int | None:
    """Sometimes the plan sells the lot part way through.

    Placed anywhere in the run rather than near the end, because
    the interesting case is a liquidation with years left after
    it: the instalment keeps running unless something stops it,
    and both simulators have to agree about what happens next.
    """
    if rng.random() < 0.85:
        return None
    return rng.randrange(0, max(1, horizon_months_int))


def build_scenario_tuple(
    seed_int: int,
    is_taxed_bool: bool = False,
) -> tuple:
    """One random plan: its funds and its settings.

    The seed is the whole state, so a failing scenario can be
    rebuilt from the number alone.
    """
    rng = random.Random(seed_int)
    horizon_years_int = rng.choice([1, 3, 7, 12, 25, 40])
    horizon_months_int = horizon_years_int * MONTHS_IN_YEAR_INT
    fund_list = [
        build_fund(rng, index_int, horizon_months_int, is_taxed_bool)
        for index_int in range(rng.choice([1, 2, 2, 3, 5]))
    ]
    withdrawal_start_int = rng.randrange(0, horizon_months_int)
    settings = SimulationSettings(
        horizon_years_int=horizon_years_int,
        sip_at_month_start_bool=rng.random() < 0.75,
        stepup=build_stepup(rng),
        withdrawal=build_withdrawal(
            rng, horizon_months_int, withdrawal_start_int
        ),
        pauses=build_pauses(
            rng, horizon_months_int, withdrawal_start_int
        ),
        rebalance=build_rebalance(rng, is_taxed_bool),
        tax=TaxSettings(
            apply_final_liquidation_tax_bool=is_taxed_bool,
            apply_grandfathering_bool=False,
        ),
        portfolio_start_date=START_DATE,
        one_off_contributions_list=build_one_off_list(
            rng, horizon_months_int, fund_list
        ),
        instalment_override_list=build_override_list(
            rng, horizon_months_int, fund_list
        ),
        one_off_withdrawals_list=build_one_off_withdrawal_list(
            rng, horizon_months_int, fund_list
        ),
        liquidation_month_index_int=build_liquidation_month_int(
            rng, horizon_months_int
        ),
    )
    return fund_list, settings


def describe_scenario_str(fund_list: list, settings) -> str:
    """A one-screen summary, printed when a scenario fails."""
    line_list = [
        f"horizon {settings.horizon_years_int}y, "
        f"sip_at_start={settings.sip_at_month_start_bool}",
        f"stepup {settings.stepup}",
        f"withdrawal {settings.withdrawal}",
        f"pauses {settings.pauses}",
        f"rebalance {settings.rebalance}",
        f"overrides {settings.instalment_override_list}",
        f"one-offs {settings.one_off_contributions_list}",
        f"lump withdrawals {settings.one_off_withdrawals_list}",
        f"liquidation month {settings.liquidation_month_index_int}",
    ]
    for fund in fund_list:
        line_list.append(
            f"  {fund.name_str}: sip={fund.monthly_sip_float} "
            f"ret={fund.gross_return_percent_float} "
            f"exp={fund.expense_percent_float} "
            f"target={fund.target_allocation_percent_float} "
            f"start={fund.start_date} "
            f"lump={fund.initial_investment_float}"
        )
    return chr(10).join(line_list)


def build_taxed_scenario_tuple(seed_int: int) -> tuple:
    """A taxed plan, shaped so the tax machinery is under load.

    Three things are varied that the untaxed generator leaves
    alone, because each changes which gain is taxed at which rate
    in which year:

      * the exemption level, so a run is sometimes one allowance
        per fund and sometimes one allowance for the taxpayer;
      * the surcharge and the cess, which are charged on the tax
        and then on the tax-plus-surcharge;
      * loss set-off, which is what makes the order of sales
        matter rather than only their total.

    Odd seeds get a crash-then-recovery return path. Losses have
    to be realised *before* the gains they shelter, and a fund
    with one constant rate can only ever go one way, so without
    the path the carry-forward rules would never be exercised.

    Grandfathering is off, and is covered by its own tests: the
    deemed cost of a January 2018 valuation cannot arise in a plan
    that starts in 2026.
    """
    fund_list, settings = build_scenario_tuple(
        seed_int, is_taxed_bool=True
    )
    if seed_int % 2 == 1:
        fund_list = apply_crash_then_recovery_list(
            fund_list, seed_int, int(settings.total_months_int)
        )
    settings = replace(
        settings,
        tax=TaxSettings(
            exemption_level_str=(
                "PER_TAXPAYER" if seed_int % 3 == 0 else "PER_FUND"
            ),
            portfolio_exemption_amount_float=125000.0,
            apply_final_liquidation_tax_bool=False,
            surcharge_percent_float=(
                15.0 if seed_int % 5 == 0 else 0.0
            ),
            cess_percent_float=(4.0 if seed_int % 4 == 0 else 0.0),
            allow_loss_set_off_bool=(seed_int % 2 == 0),
            apply_grandfathering_bool=False,
        ),
    )
    return fund_list, settings


def apply_crash_then_recovery_list(
    fund_list: list, seed_int: int, months_int: int
) -> list:
    """Give every fund a path that falls and then recovers.

    Losses have to be realised *before* the gains they shelter, and
    a fund with one constant rate can only ever go one way, so
    without this the carry-forward rules would never be exercised.
    """
    rng = random.Random(seed_int * 7919)
    path_list = [
        rng.choice([-0.05, -0.03, -0.02])
        if month_int < months_int // 3
        else rng.choice([0.01, 0.02, 0.03])
        for month_int in range(months_int)
    ]
    return [
        replace(
            fund_configuration,
            monthly_rate_path_list=list(path_list),
        )
        for fund_configuration in fund_list
    ]
