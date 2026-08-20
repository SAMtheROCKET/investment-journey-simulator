"""Colour token tests.

These guard the two properties that a chart's readability rests on
and that a refactor can silently break: identity colours must
follow the entity rather than its drawing order, and status colours
must never be reused as identity colours.
"""

from __future__ import annotations

import pandas as pd
import pytest

from investment_journey_simulator.charts import (
    build_allocation_figure,
    build_fund_history_figure,
)
from investment_journey_simulator.palette import (
    DARK_FUND_COLOUR_TUPLE,
    FUND_DASH_PATTERN_TUPLE,
    GAIN_COLOUR_STR,
    LIGHT_FUND_COLOUR_TUPLE,
    LOSS_COLOUR_STR,
    PAUSE_COLOUR_STR,
    REBALANCE_COLOUR_STR,
    resolve_fund_colour_str,
    resolve_fund_dash_str,
)

STATUS_COLOUR_TUPLE: tuple = (
    GAIN_COLOUR_STR,
    LOSS_COLOUR_STR,
    REBALANCE_COLOUR_STR,
    PAUSE_COLOUR_STR,
)


def build_history_frame(fund_name_list: list[str]) -> pd.DataFrame:
    """Build a minimal per-fund history table.

    REFERENCE: harness only.
    """
    row_list = []
    for fund_name_str in fund_name_list:
        for month_int in (1, 2):
            row_list.append(
                {
                    "Fund": fund_name_str,
                    "Date": pd.Timestamp(2026, month_int, 1),
                    "Closing value": 1000.0 * month_int,
                    "Weight %": 100.0 / len(fund_name_list),
                }
            )
    return pd.DataFrame(row_list)


def test_status_colours_are_never_used_for_identity() -> None:
    """A fund must never be painted in a status colour.

    REFERENCE: G4-SYNTHETIC. Green means gain and red means loss
    everywhere on the page; spending either on a fund's identity
    would make the reader decode the same hue two ways.
    """
    for colour_str in STATUS_COLOUR_TUPLE:
        assert colour_str not in LIGHT_FUND_COLOUR_TUPLE
        assert colour_str not in DARK_FUND_COLOUR_TUPLE


def test_colour_does_not_depend_on_trace_order() -> None:
    """Drawing order must not decide a fund's colour.

    REFERENCE: G4-SYNTHETIC. This is the defect that motivated the
    resolver: Plotly assigns from its cycle by trace position, so
    a groupby that returned the funds in a different order painted
    them differently.
    """
    roster_list = ["Alpha", "Beta", "Gamma"]
    assert resolve_fund_colour_str(
        "Gamma", roster_list
    ) == resolve_fund_colour_str("Gamma", list(reversed(roster_list)))


def test_colour_does_not_depend_on_input_order() -> None:
    """The same roster in any order gives the same colours.

    REFERENCE: G4-SYNTHETIC. A groupby may deliver funds in any
    order, so the slot must come from a canonical sort.
    """
    forward_list = ["Alpha", "Beta", "Gamma"]
    reversed_list = ["Gamma", "Beta", "Alpha"]
    for fund_name_str in forward_list:
        assert resolve_fund_colour_str(
            fund_name_str, forward_list
        ) == resolve_fund_colour_str(fund_name_str, reversed_list)


def test_a_realistic_plan_separates_every_fund() -> None:
    """Six real funds get six distinct colour-pattern pairs.

    REFERENCE: G4-SYNTHETIC. Six is the validated ceiling in light
    mode, so a plan at the ceiling must still separate cleanly.
    """
    fund_name_list = [
        "Nifty 50 Index",
        "Nifty Next 50",
        "Flexi Cap",
        "Mid Cap",
        "Short Duration Debt",
        "Gold ETF",
    ]
    encoding_list = [
        (
            resolve_fund_colour_str(fund_name_str, fund_name_list),
            resolve_fund_dash_str(fund_name_str, fund_name_list),
        )
        for fund_name_str in fund_name_list
    ]
    assert len(set(encoding_list)) == len(fund_name_list)


def test_a_plan_past_the_ceiling_still_separates_by_pattern() -> None:
    """Wrapped colours must not produce identical encodings.

    REFERENCE: G4-SYNTHETIC. The pattern tuple is longer than the
    colour tuple precisely so that the seventh fund, which reuses
    the first colour, still differs in line style.
    """
    fund_name_list = [f"Fund-{index_int}" for index_int in range(7)]
    assert resolve_fund_colour_str(
        "Fund-0", fund_name_list
    ) == resolve_fund_colour_str("Fund-6", fund_name_list)
    assert resolve_fund_dash_str(
        "Fund-0", fund_name_list
    ) != resolve_fund_dash_str("Fund-6", fund_name_list)


def test_the_same_plan_paints_identically_in_every_figure() -> None:
    """One fund is one colour across every chart of a run.

    REFERENCE: G4-SYNTHETIC. The value chart and the weight chart
    are drawn separately, so a resolver keyed on anything local to
    one figure would let them disagree.
    """
    fund_name_list = ["Alpha", "Beta", "Gamma"]
    history_frame = build_history_frame(fund_name_list)
    value_colour_list = [
        trace.line.color
        for trace in build_fund_history_figure(history_frame).data
    ]
    weight_colour_list = [
        trace.line.color
        for trace in build_allocation_figure(history_frame).data
    ]
    assert value_colour_list == weight_colour_list


def test_an_unknown_fund_falls_back_instead_of_raising() -> None:
    """A name outside the roster must not crash a chart.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    assert (
        resolve_fund_colour_str("Missing", ["Alpha"])
        == LIGHT_FUND_COLOUR_TUPLE[0]
    )
    assert (
        resolve_fund_dash_str("Missing", ["Alpha"])
        == FUND_DASH_PATTERN_TUPLE[0]
    )


@pytest.mark.parametrize(
    "build_figure", [build_fund_history_figure, build_allocation_figure]
)
def test_every_fund_trace_carries_an_explicit_colour(
    build_figure,
) -> None:
    """No trace may be left for Plotly to colour by position.

    REFERENCE: G4-SYNTHETIC. An unset colour is exactly how the
    repaint defect arose, so the absence of one is the thing worth
    asserting.
    """
    figure = build_figure(
        build_history_frame(["Alpha", "Beta", "Gamma"])
    )
    for trace in figure.data:
        assert trace.line.color is not None
        assert trace.line.color in LIGHT_FUND_COLOUR_TUPLE


def test_an_empty_history_draws_nothing_and_does_not_raise() -> None:
    """An empty portfolio is legal and must render cleanly.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    empty_frame = pd.DataFrame(
        columns=["Fund", "Date", "Closing value", "Weight %"]
    )
    assert len(build_fund_history_figure(empty_frame).data) == 0
