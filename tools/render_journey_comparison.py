"""Draw the four journeys on one shared axis.

Run:
    python tools/render_journey_comparison.py

Writes assets/journey_comparison.svg and .png.

WHAT THE FOUR ARE

Two controlled pairs, one per row, twenty years each.

The top row is the same money, moved. Both people pay fifteen
years of instalments and take a five-year break; the only
difference is whether the break falls in years eleven to fifteen
or years six to ten. Identical rupees in, and the finishing
figures are ₹22.83 lakh apart.

The bottom row is the same shape of life at two rates of raise,
each drawing ₹5,000 a month out from year six, because most
people's plans are interrupted by living rather than by stopping.

WHY THE AXIS IS SHARED

Let each panel scale its own vertical axis and every one of them
becomes the same healthy rising line, and the reader concludes the
four outcomes are much of a muchness. Which is the opposite of
true. So all four share one scale, fixed by the largest journey,
and the short ones are *drawn* short.

That is the entire point of the figure and the reason it is
generated rather than screenshotted: four screenshots each carry
whatever axis the app chose for them, and the comparison dies.

Every number comes from the engine. Nothing here is illustrative.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_PATH / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH / "src"))

import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from investment_journey_simulator.constants import (  # noqa: E402
    EXEMPTION_SCOPE_LONG_TERM_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    PRESET_EQUITY_STR,
)
from investment_journey_simulator.design_tokens import (  # noqa: E402
    FONT_STACK_STR,
    PANEL_ACCENT_STR,
    PANEL_FAINT_STR,
    PANEL_GRID_STR,
    PANEL_INK_STR,
    PANEL_MUTED_STR,
    PANEL_SURFACE_STR,
    PANEL_WARN_STR,
)
from investment_journey_simulator.engine import (  # noqa: E402
    PortfolioSimulator,
)
from investment_journey_simulator.models import (  # noqa: E402
    FundConfiguration,
)
from investment_journey_simulator.plan_scenario import (  # noqa: E402
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.timeline import (  # noqa: E402
    EVENT_PAUSE_STR,
    EVENT_RESUME_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
)

MONTHLY_AMOUNT_FLOAT: float = 25000.0
WITHDRAWAL_AMOUNT_FLOAT: float = 5000.0
PLAN_START_DATE: date = date(2027, 1, 1)
HORIZON_YEARS_INT: int = 20
RETURN_PERCENT_FLOAT: float = 12.0
EXPENSE_PERCENT_FLOAT: float = 1.0
CRORE_FLOAT: float = 10_000_000.0
LAKH_FLOAT: float = 100_000.0

OUTPUT_DIRECTORY_PATH: Path = PROJECT_ROOT_PATH / "assets"
OUTPUT_STEM_STR: str = "journey_comparison"
FIGURE_WIDTH_INT: int = 1200
FIGURE_HEIGHT_INT: int = 760


def build_asset() -> FundConfiguration:
    """The single equity asset every worked figure uses."""
    return FundConfiguration(
        name_str="Equity fund",
        preset_str=PRESET_EQUITY_STR,
        monthly_sip_float=0.0,
        stepup_percent_float=0.0,
        gross_return_percent_float=RETURN_PERCENT_FLOAT,
        expense_percent_float=EXPENSE_PERCENT_FLOAT,
        start_date=PLAN_START_DATE,
        target_allocation_percent_float=100.0,
        short_term_tax_percent_float=20.0,
        long_term_tax_percent_float=12.5,
        long_term_threshold_months_int=12,
        exemption_amount_float=125000.0,
        exemption_scope_str=EXEMPTION_SCOPE_LONG_TERM_STR,
        is_always_short_term_bool=False,
        expense_model_str=EXPENSE_MODEL_SIMPLE_STR,
    )


def build_journey(name_str: str, event_list: list) -> PlanScenario:
    """One named thirty-year journey."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=HORIZON_YEARS_INT,
            event_list=event_list,
        ),
        fund_list=[build_asset()],
        name_str=name_str,
    )


def build_start_event() -> TimelineEvent:
    """Twenty-five thousand a month, from the first month."""
    return TimelineEvent(
        EVENT_START_SIP_STR,
        PLAN_START_DATE,
        MONTHLY_AMOUNT_FLOAT,
    )


def build_break_event_list(break_start_year_int: int) -> list:
    """Fifteen paying years with a five-year break inside them."""
    return [
        build_start_event(),
        TimelineEvent(
            EVENT_PAUSE_STR, date(break_start_year_int, 1, 1)
        ),
        TimelineEvent(
            EVENT_RESUME_STR, date(break_start_year_int + 5, 1, 1)
        ),
    ]


def build_raise_event_list(raise_percent_float: float) -> list:
    """A rising instalment, with ₹5,000 a month drawn from year 6."""
    return [
        build_start_event(),
        TimelineEvent(
            EVENT_STEPUP_STR,
            PLAN_START_DATE,
            percent_float=raise_percent_float,
        ),
        TimelineEvent(
            EVENT_WITHDRAW_STR,
            date(2032, 1, 1),
            WITHDRAWAL_AMOUNT_FLOAT,
        ),
    ]


def build_journey_specification_list() -> list:
    """The four journeys, in the order they are drawn.

    Each row is a controlled pair: the left panel is the reference
    and the right one differs by exactly one decision, so the
    figure beside it is what that decision was worth.
    """
    return [
        (
            "Pause later (5 years)",
            "₹25,000 a month, nothing paid in years 11 to 15",
            build_journey("Pause later", build_break_event_list(2037)),
        ),
        (
            "Pause earlier (5 years)",
            "The same money, the same break, in years 6 to 10",
            build_journey(
                "Pause earlier", build_break_event_list(2032)
            ),
        ),
        (
            "Step up 5% + SWP",
            "Rising 5% a year, ₹5,000 a month out from year 6",
            build_journey("Step up 5%", build_raise_event_list(5.0)),
        ),
        (
            "Step up 10% + SWP",
            "The same plan, rising 10% a year instead",
            build_journey(
                "Step up 10%", build_raise_event_list(10.0)
            ),
        ),
    ]


def format_money_str(amount_float: float) -> str:
    """Indian magnitudes, because that is who reads this."""
    if abs(amount_float) >= CRORE_FLOAT:
        return f"₹{amount_float / CRORE_FLOAT:,.2f} Cr"
    return f"₹{amount_float / LAKH_FLOAT:,.2f} L"


def read_trajectory_tuple(scenario: PlanScenario) -> tuple:
    """The month-by-month value of one journey, and its close."""
    compiled = compile_scenario(scenario)
    result = PortfolioSimulator(
        compiled.fund_list, compiled.settings
    ).run()
    value_list = [
        snapshot.portfolio_value_float
        for snapshot in result.monthly_snapshots_list
    ]
    year_list = [
        index_int / 12.0 for index_int in range(len(value_list))
    ]
    return year_list, value_list, result.ending_value_float


def build_fill_colour_str(colour_str: str) -> str:
    """The same colour, faint enough to sit under a line.

    Written out because the six-digit hex the tokens use has no
    alpha channel, and an area chart filled at full opacity is a
    block, not a chart.
    """
    red_int = int(colour_str[1:3], 16)
    green_int = int(colour_str[3:5], 16)
    blue_int = int(colour_str[5:7], 16)
    return f"rgba({red_int}, {green_int}, {blue_int}, 0.16)"


def add_panel(
    figure: go.Figure,
    row_int: int,
    column_int: int,
    year_list: list,
    value_list: list,
    colour_str: str,
) -> None:
    """Draw one trajectory into its panel."""
    figure.add_trace(
        go.Scatter(
            x=year_list,
            y=[value_float / CRORE_FLOAT for value_float in value_list],
            mode="lines",
            line=dict(color=colour_str, width=2.6),
            fill="tozeroy",
            fillcolor=build_fill_colour_str(colour_str),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=row_int,
        col=column_int,
    )


def shade_break_window(
    figure: go.Figure,
    row_int: int,
    column_int: int,
    break_start_year_int: int,
) -> None:
    """Mark the five years in which nothing was paid in.

    The two panels of the top row hold the same break, drawn in
    two different places. Saying so in words underneath is weaker
    than showing where it sits: the whole comparison is *when*.
    """
    figure.add_vrect(
        x0=break_start_year_int,
        x1=break_start_year_int + 5,
        row=row_int,
        col=column_int,
        fillcolor=PANEL_FAINT_STR,
        opacity=0.14,
        line_width=0,
        layer="below",
        annotation_text="5 years off",
        annotation_position="bottom left",
        annotation_font=dict(
            family=FONT_STACK_STR, size=11, color=PANEL_FAINT_STR
        ),
    )


def build_annotation_dict(
    title_str: str,
    subtitle_str: str,
    final_float: float,
    delta_float: float,
) -> list:
    """The four lines of text that sit inside one panel.

    The last line is what this panel's one changed decision was
    worth against the panel to its left, which is why the left
    panel of each row says so rather than showing a zero.
    """
    money_str = format_money_str(final_float)
    if delta_float == 0.0:
        delta_str = "The reference for this row"
    elif delta_float < 0.0:
        delta_str = f"−{format_money_str(abs(delta_float))}"
    else:
        delta_str = f"+{format_money_str(delta_float)}"
    return [title_str, subtitle_str, money_str, delta_str]


def render_figure() -> go.Figure:
    """Build the whole four-panel figure."""
    specification_list = build_journey_specification_list()
    trajectory_list = [
        read_trajectory_tuple(scenario)
        for _title, _subtitle, scenario in specification_list
    ]
    # Each row compares against its own left-hand panel, because
    # the four are two pairs rather than four variants of one plan.
    reference_list = [
        trajectory_list[index_int - index_int % 2][2]
        for index_int in range(len(trajectory_list))
    ]
    ceiling_float = (
        max(
            max(value_list)
            for _years, value_list, _final in trajectory_list
        )
        / CRORE_FLOAT
    )
    figure = make_subplots(
        rows=2,
        cols=2,
        shared_yaxes=True,
        shared_xaxes=True,
        horizontal_spacing=0.06,
        vertical_spacing=0.13,
    )
    # The better outcome of each pair in the accent, the poorer one
    # in the warning colour, so the rows read the same way round
    # even though the change is in a different panel each time.
    colour_tuple = (
        PANEL_ACCENT_STR,
        PANEL_WARN_STR,
        PANEL_WARN_STR,
        PANEL_ACCENT_STR,
    )
    for index_int, (specification, trajectory) in enumerate(
        zip(specification_list, trajectory_list, strict=True)
    ):
        row_int = index_int // 2 + 1
        column_int = index_int % 2 + 1
        year_list, value_list, final_float = trajectory
        add_panel(
            figure,
            row_int,
            column_int,
            year_list,
            value_list,
            colour_tuple[index_int],
        )
        if index_int < 2:
            shade_break_window(
                figure, row_int, column_int, 10 - index_int * 5
            )
        annotate_panel(
            figure,
            row_int,
            column_int,
            build_annotation_dict(
                specification[0],
                specification[1],
                final_float,
                final_float - reference_list[index_int],
            ),
            colour_tuple[index_int],
        )
    style_figure(figure, ceiling_float)
    return figure


def annotate_panel(
    figure: go.Figure,
    row_int: int,
    column_int: int,
    line_list: list,
    colour_str: str,
) -> None:
    """Write the title, the outcome and the shortfall in a panel."""
    title_str, subtitle_str, money_str, delta_str = line_list
    figure.add_annotation(
        row=row_int,
        col=column_int,
        x=0.04,
        y=0.96,
        xref="x domain",
        yref="y domain",
        xanchor="left",
        yanchor="top",
        align="left",
        showarrow=False,
        text=(
            f"<b>{title_str}</b><br>"
            f"<span style='font-size:12px;color:{PANEL_FAINT_STR}'>"
            f"{subtitle_str}</span><br><br>"
            f"<span style='font-size:26px;color:{colour_str}'>"
            f"<b>{money_str}</b></span><br>"
            f"<span style='font-size:14px;color:{PANEL_FAINT_STR}'>"
            f"{delta_str}</span>"
        ),
        font=dict(family=FONT_STACK_STR, size=14, color=PANEL_INK_STR),
    )


def style_figure(figure: go.Figure, ceiling_float: float) -> None:
    """One scale, one grid, one typeface across all four panels."""
    figure.update_yaxes(
        range=[0, ceiling_float * 1.02],
        gridcolor=PANEL_GRID_STR,
        zeroline=False,
        tickfont=dict(
            family=FONT_STACK_STR, size=11, color=PANEL_FAINT_STR
        ),
        ticksuffix=" Cr",
        showline=False,
    )
    figure.update_xaxes(
        gridcolor=PANEL_GRID_STR,
        zeroline=False,
        tickfont=dict(
            family=FONT_STACK_STR, size=11, color=PANEL_FAINT_STR
        ),
        ticksuffix=" yr",
        showline=False,
    )
    figure.update_layout(
        paper_bgcolor=PANEL_SURFACE_STR,
        plot_bgcolor=PANEL_SURFACE_STR,
        width=FIGURE_WIDTH_INT,
        height=FIGURE_HEIGHT_INT,
        margin=dict(t=86, l=64, r=32, b=56),
        font=dict(family=FONT_STACK_STR, color=PANEL_INK_STR),
        title=dict(
            text=(
                "<b>Twenty years each. One decision changed "
                "across every row</b><br>"
                "<span style='font-size:13px;"
                f"color:{PANEL_MUTED_STR}'>"
                "Top row: the same ₹45,00,000 paid in, and the "
                "same five years off, moved five years earlier. "
                "All four panels share one vertical scale.</span>"
            ),
            x=0.5,
            xanchor="center",
            font=dict(size=18, color=PANEL_INK_STR),
        ),
    )


def main() -> None:
    """Write the figure to assets/ in both formats."""
    OUTPUT_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    figure = render_figure()
    svg_path = OUTPUT_DIRECTORY_PATH / f"{OUTPUT_STEM_STR}.svg"
    png_path = OUTPUT_DIRECTORY_PATH / f"{OUTPUT_STEM_STR}.png"
    figure.write_image(str(svg_path))
    figure.write_image(str(png_path), scale=2)
    print(f"Wrote {svg_path}")
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()
