"""Target weight resolution used by the rebalancing engine."""

from __future__ import annotations

from investment_journey_simulator.constants import (
    MONEY_TOLERANCE_FLOAT,
    PERCENT_TOTAL_FLOAT,
    REBALANCE_TARGET_SIP_SPLIT_STR,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    RebalanceSettings,
)


def build_equal_weight_dict(
    fund_configurations_list: list[FundConfiguration],
) -> dict[str, float]:
    """Spread the portfolio equally across every fund.

    Brief:
        Last-resort fallback when no usable weights were supplied.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.

    Returns:
        Dict[str, float]: Fund name to weight percent mapping.

    Warning:
        Returns an empty mapping when there are no funds.
    """
    if not fund_configurations_list:
        return {}
    equal_weight_float = PERCENT_TOTAL_FLOAT / len(
        fund_configurations_list
    )
    return {
        fund_configuration.name_str: equal_weight_float
        for fund_configuration in fund_configurations_list
    }


def build_contribution_weight_dict(
    fund_configurations_list: list[FundConfiguration],
) -> dict[str, float]:
    """Derive weights from the original monthly instalments.

    Brief:
        Reproduces the investor's own split so rebalancing returns
        the portfolio to the proportions they chose.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.

    Returns:
        Dict[str, float]: Fund name to weight percent mapping.

    Warning:
        Falls back to equal weights when every instalment is zero.
    """
    instalment_total_float = sum(
        max(0.0, float(fund_configuration.monthly_sip_float))
        for fund_configuration in fund_configurations_list
    )
    if instalment_total_float <= MONEY_TOLERANCE_FLOAT:
        return build_equal_weight_dict(fund_configurations_list)
    return {
        fund_configuration.name_str: (
            PERCENT_TOTAL_FLOAT
            * max(0.0, float(fund_configuration.monthly_sip_float))
            / instalment_total_float
        )
        for fund_configuration in fund_configurations_list
    }


def build_declared_weight_dict(
    fund_configurations_list: list[FundConfiguration],
) -> dict[str, float]:
    """Read the target weights typed into the fund table.

    Brief:
        Lets the investor rebalance toward a policy allocation that
        differs from the instalment split.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.

    Returns:
        Dict[str, float]: Fund name to weight percent mapping.

    Warning:
        Falls back to instalment weights when the column is blank.
    """
    declared_total_float = sum(
        max(
            0.0,
            float(fund_configuration.target_allocation_percent_float),
        )
        for fund_configuration in fund_configurations_list
    )
    if declared_total_float <= MONEY_TOLERANCE_FLOAT:
        return build_contribution_weight_dict(
            fund_configurations_list
        )
    return {
        fund_configuration.name_str: max(
            0.0,
            float(fund_configuration.target_allocation_percent_float),
        )
        for fund_configuration in fund_configurations_list
    }


def normalise_weight_dict(
    weight_percent_dict: dict[str, float],
) -> dict[str, float]:
    """Rescale weights so that they add up to one hundred.

    Brief:
        Guarantees the rebalancer always deploys the full corpus.

    Arguments:
        weight_percent_dict (Dict[str, float]): Raw weights.

    Returns:
        Dict[str, float]: Weights summing to one hundred percent.

    Warning:
        An all-zero mapping is replaced by an equal split.
    """
    weight_total_float = sum(
        max(0.0, float(weight_float))
        for weight_float in weight_percent_dict.values()
    )
    if weight_total_float <= MONEY_TOLERANCE_FLOAT:
        if not weight_percent_dict:
            return {}
        equal_weight_float = PERCENT_TOTAL_FLOAT / len(
            weight_percent_dict
        )
        return dict.fromkeys(weight_percent_dict, equal_weight_float)
    return {
        fund_name_str: (
            PERCENT_TOTAL_FLOAT
            * max(0.0, float(weight_float))
            / weight_total_float
        )
        for fund_name_str, weight_float in weight_percent_dict.items()
    }


def resolve_target_weight_dict(
    fund_configurations_list: list[FundConfiguration],
    rebalance_settings: RebalanceSettings,
) -> dict[str, float]:
    """Choose and normalise the weights the rebalancer aims at.

    Brief:
        Returns all-zero weights while rebalancing is switched off
        so that targets can never influence a passive run.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        rebalance_settings (RebalanceSettings): Rebalance rules.

    Returns:
        Dict[str, float]: Normalised fund name to weight mapping.

    Warning:
        Duplicate fund names collapse into a single weight entry.
    """
    if not rebalance_settings.needs_target_weights_bool:
        return {
            fund_configuration.name_str: 0.0
            for fund_configuration in fund_configurations_list
        }
    if (
        rebalance_settings.target_mode_str
        == REBALANCE_TARGET_SIP_SPLIT_STR
    ):
        raw_weight_dict = build_contribution_weight_dict(
            fund_configurations_list
        )
    else:
        raw_weight_dict = build_declared_weight_dict(
            fund_configurations_list
        )
    return normalise_weight_dict(raw_weight_dict)
