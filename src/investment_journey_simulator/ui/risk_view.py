"""Risk panel: the fan of outcomes behind a single projection."""

from __future__ import annotations

import random

import plotly.graph_objects as go
import streamlit as st

from investment_journey_simulator.constants import (
    DEFAULT_STOCHASTIC_TRIALS_INT,
    DEFAULT_VOLATILITY_PERCENT_FLOAT,
    MAXIMUM_STOCHASTIC_TRIALS_INT,
    PLOTLY_TEMPLATE_STR,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.formatting import (
    format_money_amount_str,
    resolve_display_currency,
)
from investment_journey_simulator.market_data import (
    MarketHistory,
    describe_coverage_str,
    load_bundled_market_history,
)
from investment_journey_simulator.models import (
    FundConfiguration,
    SimulationSettings,
)
from investment_journey_simulator.palette import (
    LOSS_COLOUR_STR,
    PORTFOLIO_VALUE_COLOUR_STR,
)
from investment_journey_simulator.stochastic import (
    PathOutcomeSummary,
    build_bootstrap_path_builder,
    build_lognormal_path_builder,
    run_stochastic_trials,
)
from investment_journey_simulator.ui.theme import (
    apply_page_figure_theme,
)

RISK_HEADING_STR: str = "Risk: the fan of outcomes"
RISK_INTRODUCTION_STR: str = (
    "We can't tell you what the market will do. Nobody can. What "
    "we can do is show you the whole fan of outcomes instead of "
    "the one that looks best on a brochure - and price the tax, "
    "fees and exit costs that the brochure forgot."
)
RISK_TOGGLE_LABEL_STR: str = "Simulate a range of market paths"
RISK_TOGGLE_HELP_STR: str = (
    "Runs the whole plan many times over random return paths. "
    "Off by default because each run is a full simulation."
)
VOLATILITY_HELP_STR: str = (
    "Roughly 15-20% for Indian equity, 2-5% for short duration debt."
)
SEED_HELP_STR: str = (
    "Same seed gives the same paths, so a result you report can be "
    "reproduced."
)
DEFAULT_SEED_INT: int = 2026
BOOTSTRAP_BLOCK_MONTHS_INT: int = 12
SOURCE_BELL_CURVE_STR: str = "Bell curve (type a volatility)"
SOURCE_REAL_HISTORY_STR: str = "Real index history (resampled)"
SOURCE_HELP_STR: str = (
    "Resampling real months keeps the shape of history - momentum, "
    "clustering, fat tails - that a bell curve smooths away."
)
NO_HISTORY_MESSAGE_STR: str = (
    "No index history is bundled with this build, so only the bell "
    "curve is available."
)
FAN_FIGURE_HEIGHT_INT: int = 360
PROVENANCE_TEMPLATE_STR: str = (
    "{trials} simulated paths from {source}, seed {seed}. Each "
    "fund draws its own independent path, so a diversified plan "
    "looks safer here than it would in a real crash, where "
    "correlations rise together."
)
BELL_CURVE_SOURCE_TEMPLATE_STR: str = (
    "a bell curve at {volatility:.0f}% volatility"
)
REAL_HISTORY_SOURCE_STR: str = "resampled real index history"
# There is deliberately no path here any more. Walking up three
# parents from this file finds the repository when run from a clone
# and finds nothing at all when run from site-packages, which is
# how an installed copy silently lost its history.
PERCENTILE_LABEL_DICT: dict[int, str] = {
    5: "Bad case (5th)",
    25: "Poor (25th)",
    50: "Middle (median)",
    75: "Good (75th)",
    95: "Great case (95th)",
}

HELP_HOW_MANY_SIMULATED_FUTURES_STR: str = (
    "How many simulated futures to generate. More paths give a "
    "steadier picture and take longer."
)


def render_risk_controls_tuple() -> tuple[bool, float, int, int]:
    """Collect the inputs the risk simulation needs.

    Brief:
        Kept beside the panel rather than in the sidebar, because
        the simulation is expensive and the reader should see the
        cost of the switch they are flipping.

    Arguments:
        None.

    Returns:
        Tuple[bool, float, int, int]: Whether to run, annual
            volatility, number of trials and the random seed.

    Warning:
        Raising the trial count multiplies the run time linearly.
    """
    is_enabled_bool = bool(
        st.toggle(
            RISK_TOGGLE_LABEL_STR,
            value=False,
            help=RISK_TOGGLE_HELP_STR,
        )
    )
    if not is_enabled_bool:
        return (
            False,
            DEFAULT_VOLATILITY_PERCENT_FLOAT,
            DEFAULT_STOCHASTIC_TRIALS_INT,
            0,
        )
    return (True, *_render_simulation_inputs_tuple())


def render_history_source_str(
    history: MarketHistory | None,
) -> str:
    """Ask whether to resample real history or a bell curve.

    Brief:
        The real-history option is offered only when a history
        actually loaded, so the interface never promises data it
        does not have.

    Arguments:
        history (Optional[MarketHistory]): Loaded history.

    Returns:
        str: Chosen source identifier.

    Warning:
        Falls back to the bell curve, and says why, when no
        history is present.
    """
    if history is None or history.month_count_int < 2:
        st.caption(NO_HISTORY_MESSAGE_STR)
        return SOURCE_BELL_CURVE_STR
    st.caption(describe_coverage_str(history))
    return str(
        st.radio(
            "Where should the returns come from?",
            [SOURCE_REAL_HISTORY_STR, SOURCE_BELL_CURVE_STR],
            horizontal=True,
            help=SOURCE_HELP_STR,
        )
    )


def _render_simulation_inputs_tuple() -> tuple[float, int, int]:
    """Collect volatility, trial count and seed side by side.

    Brief:
        Split out so the toggle handler stays within the house
        function length limit.

    Arguments:
        None.

    Returns:
        Tuple[float, int, int]: Volatility, trials and seed.

    Warning:
        The seed is exposed deliberately: a percentile band nobody
        can reproduce is not evidence.
    """
    first_column, second_column, third_column = st.columns(3)
    volatility_percent_float = float(
        first_column.number_input(
            "Annual volatility %",
            min_value=0.0,
            max_value=80.0,
            value=DEFAULT_VOLATILITY_PERCENT_FLOAT,
            step=1.0,
            help=VOLATILITY_HELP_STR,
        )
    )
    trial_count_int = int(
        second_column.number_input(
            "Number of paths",
            help=HELP_HOW_MANY_SIMULATED_FUTURES_STR,
            min_value=20,
            max_value=MAXIMUM_STOCHASTIC_TRIALS_INT,
            value=DEFAULT_STOCHASTIC_TRIALS_INT,
            step=50,
        )
    )
    seed_int = int(
        third_column.number_input(
            "Random seed",
            min_value=0,
            value=DEFAULT_SEED_INT,
            step=1,
            help=SEED_HELP_STR,
        )
    )
    return volatility_percent_float, trial_count_int, seed_int


def build_outcome_fan_figure(
    summary: PathOutcomeSummary,
    deterministic_value_float: float,
    currency: Currency | None = None,
) -> go.Figure:
    """Draw the spread of simulated outcomes as a bar range.

    Brief:
        A horizontal bar per percentile makes the asymmetry
        obvious: the downside is nearer the median than the upside
        is, because compounded outcomes are right skewed.

    Arguments:
        summary (PathOutcomeSummary): Distribution to plot.
        deterministic_value_float (float): The single answer.
        currency (Optional[Currency]): Display currency.

    Returns:
        go.Figure: Percentile bars, projection marked.

    Warning:
        Returns an empty figure when no trials were run.
    """
    figure = go.Figure()
    if not summary.percentile_dict:
        return figure
    label_list = list(PERCENTILE_LABEL_DICT.values())
    value_list = [
        summary.percentile_dict[percentile_int]
        for percentile_int in PERCENTILE_LABEL_DICT
    ]
    figure.add_trace(
        go.Bar(
            x=value_list,
            y=label_list,
            orientation="h",
            marker=dict(color=PORTFOLIO_VALUE_COLOUR_STR),
            customdata=[
                format_money_amount_str(value_float, currency)
                for value_float in value_list
            ],
            hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        )
    )
    _add_projection_marker(figure, deterministic_value_float)
    return _apply_fan_layout(figure, currency)


def _add_projection_marker(
    figure: go.Figure,
    deterministic_value_float: float,
) -> None:
    """Mark where the single-number projection sits in the fan.

    Brief:
        Drawn in the loss colour on purpose: seeing how much of the
        distribution falls to its left is the point of the chart.

    Arguments:
        figure (go.Figure): Figure being annotated.
        deterministic_value_float (float): Projection to mark.

    Returns:
        None: A vertical rule is added in place.

    Warning:
        The rule is a reference line, not an outcome.
    """
    figure.add_vline(
        x=float(deterministic_value_float),
        line_width=2,
        line_dash="dash",
        line_color=LOSS_COLOUR_STR,
        annotation_text="single-number projection",
        annotation_position="top",
    )


def _apply_fan_layout(
    figure: go.Figure,
    currency: Currency | None = None,
) -> go.Figure:
    """Style the outcome fan figure.

    Brief:
        Separated so the trace builder stays short.

    Arguments:
        figure (go.Figure): Figure being styled.

    Returns:
        go.Figure: The same figure, styled in place.

    Warning:
        No legend: every bar is already labelled on its axis.
    """
    symbol_str = resolve_display_currency(currency).symbol_str
    figure.update_layout(
        template=PLOTLY_TEMPLATE_STR,
        height=FAN_FIGURE_HEIGHT_INT,
        title="Where the plan actually landed across the paths",
        margin=dict(t=70, l=30, r=30, b=30),
        xaxis_title=f"Value ({symbol_str})",
        showlegend=False,
    )
    return figure


def _render_risk_metrics(
    summary: PathOutcomeSummary,
    deterministic_value_float: float,
    currency: Currency | None = None,
) -> None:
    """Show the headline risk numbers as metric tiles.

    Brief:
        The shortfall probability is deliberately first, because
        it is the number that changes decisions.

    Arguments:
        summary (PathOutcomeSummary): Distribution to report.
        deterministic_value_float (float): Single-number answer.

    Returns:
        None: Widgets are written to the page.

    Warning:
        These describe the simulated model, not the real market.
    """
    column_list = st.columns(4)
    column_list[0].metric(
        "Chance of missing the projection",
        f"{summary.shortfall_probability_float:.0%}",
    )
    column_list[1].metric(
        "Bad case (5th percentile)",
        format_money_amount_str(
            summary.percentile_dict[5], currency
        ),
    )
    column_list[2].metric(
        "Median outcome",
        format_money_amount_str(
            summary.percentile_dict[50], currency
        ),
    )
    column_list[3].metric(
        "Single-number projection",
        format_money_amount_str(
            deterministic_value_float, currency
        ),
    )


def render_risk_section(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    deterministic_value_float: float,
    currency: Currency | None = None,
) -> None:
    """Render the whole risk panel.

    Brief:
        Simulates the plan over many random return paths, so the
        reader sees how much of the headline is assumption.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        deterministic_value_float (float): The single answer the
            fan is compared against.
        currency (Optional[Currency]): Display currency.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Every fund draws an independent path, so a mixed portfolio
        looks safer here than in a real crash.
    """
    (
        control_tuple,
        history,
        source_str,
    ) = _render_risk_header_controls_tuple()
    if not control_tuple[0]:
        return
    summary = _run_trials(
        fund_configurations_list,
        settings,
        control_tuple[1:],
        deterministic_value_float,
        (source_str, history),
    )
    if not summary.percentile_dict:
        return
    _render_risk_results(
        summary,
        deterministic_value_float,
        control_tuple[1],
        control_tuple[3],
        source_str,
        currency,
    )


def _render_risk_header_controls_tuple() -> tuple:
    """Write the panel heading and collect its controls.

    Brief:
        The introduction sits above the switch on purpose, so the
        reader learns what the panel is for before deciding
        whether to pay for the simulation. The coverage note for
        the loaded history is printed beside the source picker, so
        the limits of the data arrive with the choice to use it.

    Arguments:
        None.

    Returns:
        tuple: Control tuple, loaded history and chosen source.

    Warning:
        Renders widgets as a side effect.
    """
    st.divider()
    st.subheader(RISK_HEADING_STR)
    st.caption(RISK_INTRODUCTION_STR)
    history = load_bundled_market_history()
    control_tuple = render_risk_controls_tuple()
    if not control_tuple[0]:
        return control_tuple, history, SOURCE_BELL_CURVE_STR
    return (
        control_tuple,
        history,
        render_history_source_str(history),
    )


def _build_path_builder(
    source_tuple: tuple,
    volatility_percent_float: float,
    total_months_int: int,
    generator: random.Random,
):
    """Choose between resampling history and a bell curve.

    Brief:
        Real history is used whenever it was both chosen and
        actually loaded; anything else falls back to the
        distribution, so the panel always produces something.

    Arguments:
        source_tuple (tuple): Chosen source and loaded history.
        volatility_percent_float (float): Bell-curve volatility.
        total_months_int (int): Months each path must cover.
        generator (random.Random): Seeded randomness.

    Returns:
        Callable: Builder mapping a fund to a return path.

    Warning:
        Resampling drives every fund from one index, so a mixed
        equity and debt plan is modelled as if it were all equity.
    """
    source_str, history = source_tuple
    if (
        source_str == SOURCE_REAL_HISTORY_STR
        and history is not None
        and history.month_count_int >= 2
    ):
        return build_bootstrap_path_builder(
            history.monthly_return_list,
            total_months_int,
            BOOTSTRAP_BLOCK_MONTHS_INT,
            generator,
        )
    return build_lognormal_path_builder(
        volatility_percent_float, total_months_int, generator
    )


def _run_trials(
    fund_configurations_list: list[FundConfiguration],
    settings: SimulationSettings,
    control_tuple: tuple[float, int, int],
    deterministic_value_float: float,
    source_tuple: tuple = (SOURCE_BELL_CURVE_STR, None),
) -> PathOutcomeSummary:
    """Simulate the plan over the requested number of paths.

    Brief:
        Split out so the section renderer stays short and the
        simulation call has one obvious place to live.

    Arguments:
        fund_configurations_list (List[FundConfiguration]): Funds.
        settings (SimulationSettings): Portfolio rules.
        control_tuple (Tuple[float, int, int]): Volatility, trial
            count and random seed.
        deterministic_value_float (float): Shortfall target.
        source_tuple (tuple): Chosen source and loaded history.

    Returns:
        PathOutcomeSummary: Distribution across the paths.

    Warning:
        Cost grows linearly with the trial count.
    """
    (
        volatility_percent_float,
        trial_count_int,
        seed_int,
    ) = control_tuple
    return run_stochastic_trials(
        fund_configurations_list,
        settings,
        _build_path_builder(
            source_tuple,
            volatility_percent_float,
            settings.total_months_int,
            random.Random(seed_int),
        ),
        trial_count_int,
        target_corpus_float=deterministic_value_float,
    )


def _render_risk_results(
    summary: PathOutcomeSummary,
    deterministic_value_float: float,
    volatility_percent_float: float,
    seed_int: int,
    source_str: str = SOURCE_BELL_CURVE_STR,
    currency: Currency | None = None,
) -> None:
    """Render the tiles, the fan chart and the provenance note.

    Brief:
        The provenance note names the source, trial count and
        seed, so the reader can reproduce or challenge the band.

    Arguments:
        summary (PathOutcomeSummary): Distribution to report.
        deterministic_value_float (float): Single-number answer.
        volatility_percent_float (float): Volatility used.
        seed_int (int): Random seed used.
        source_str (str): Where the returns came from.

    Returns:
        None: Widgets are written to the page.

    Warning:
        States the independent-path assumption in plain sight,
        because it makes a mixed portfolio look safer than it is.
    """
    _render_risk_metrics(
        summary, deterministic_value_float, currency
    )
    st.plotly_chart(
        apply_page_figure_theme(
            build_outcome_fan_figure(
                summary, deterministic_value_float, currency
            ),
        ),
        width="stretch",
        key="risk_outcome_fan",
    )
    st.caption(
        PROVENANCE_TEMPLATE_STR.format(
            trials=summary.trial_count_int,
            source=_describe_source_str(
                source_str, volatility_percent_float
            ),
            seed=seed_int,
        )
    )


def _describe_source_str(
    source_str: str,
    volatility_percent_float: float,
) -> str:
    """Name where the simulated returns came from.

    Brief:
        The provenance line has to distinguish resampled real
        months from an invented distribution, because the two
        deserve very different amounts of trust.

    Arguments:
        source_str (str): Chosen source identifier.
        volatility_percent_float (float): Bell-curve width.

    Returns:
        str: Phrase naming the source.

    Warning:
        Never claims real history when the fallback was used.
    """
    if source_str == SOURCE_REAL_HISTORY_STR:
        return REAL_HISTORY_SOURCE_STR
    return BELL_CURVE_SOURCE_TEMPLATE_STR.format(
        volatility=volatility_percent_float
    )
