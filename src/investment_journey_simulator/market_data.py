"""Loading real index history and calibrating a model from it.

Reads the daily index CSVs that ship *inside this package* and
turns them into the monthly return series the engine and the
bootstrap consume. Nothing here simulates anything: every number
this module produces is something the market actually did.

The files are package data, not repository files, and they are
found through `importlib.resources` rather than by walking up from
`__file__`. That distinction is the whole reason this note exists.
A wheel does not carry the repository, so an installed copy looking
for a folder called `data/` beside its own source finds nothing -
and `load_market_history` returned None, which the risk lab read as
"no history configured" rather than "the history is missing". The
program lost half of what it does and said nothing. Resource lookup
gives the same answer from a clone, an installed wheel, a zip and a
hosted deployment, which is the only way that guarantee holds.

**Read the coverage warning before trusting a bootstrap built from
this.** The bundled history is short. Three years of monthly returns
is 36 observations, and a block bootstrap drawing 12-month blocks
from 36 months has very few genuinely distinct blocks to draw from.
More importantly the window contains no severe crash: its worst
month is about -12%, where March 2020 was near -23% and October 2008
worse still. A bootstrap cannot resample a disaster that never
appears in its source, so the downside tail it produces is too
kind. `describe_coverage_str` exists so the interface can say this
out loud rather than let a reader assume otherwise.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    PERCENT_TOTAL_FLOAT,
)

CSV_DATE_FORMAT_STR: str = "%d-%b-%Y"
CSV_DATE_COLUMN_STR: str = "Date"
CSV_CLOSE_COLUMN_STR: str = "Close"
HISTORY_PACKAGE_STR: str = "investment_journey_simulator.data"
SEVERE_CRASH_MONTH_THRESHOLD_FLOAT: float = -0.20
THIN_HISTORY_MONTH_COUNT_INT: int = 120


@dataclass(frozen=True)
class MarketHistory:
    """A real index history reduced to monthly observations."""

    source_name_str: str
    month_end_date_list: list[date]
    month_end_close_list: list[float]

    @property
    def monthly_return_list(self) -> list[float]:
        """Month-on-month returns as decimal fractions.

        Brief:
            One fewer entry than there are observations, because a
            return needs two month ends to exist.

        Arguments:
            None.

        Returns:
            List[float]: Monthly returns in chronological order.

        Warning:
            Returns an empty list for a history of one month.
        """
        return [
            later_float / earlier_float - 1.0
            for earlier_float, later_float in zip(
                self.month_end_close_list,
                self.month_end_close_list[1:],
                strict=False,
            )
        ]

    @property
    def month_count_int(self) -> int:
        """Number of monthly returns available.

        Brief:
            The figure that decides whether a bootstrap built from
            this history is thin.

        Arguments:
            None.

        Returns:
            int: Count of monthly returns.

        Warning:
            Fewer than about ten years is thin for resampling.
        """
        return len(self.monthly_return_list)


def _read_close_rows_list(
    csv_path: Path,
) -> list[tuple[date, float]]:
    """Read one daily index CSV into dated closing levels.

    Brief:
        The exchange files carry a byte-order mark, pad their
        header names with spaces and list newest first, so all
        three are normalised here rather than at every call site.

    Arguments:
        csv_path (Path): CSV file to read.

    Returns:
        List[Tuple[date, float]]: Dated closing levels, unsorted.

    Warning:
        Rows whose date or close cannot be parsed are skipped, so
        a malformed file yields a short series rather than raising.
    """
    row_list: list[tuple[date, float]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        for raw_row_dict in csv.DictReader(file):
            clean_row_dict = {
                str(key_str).strip(): str(value_str).strip()
                for key_str, value_str in raw_row_dict.items()
                if key_str is not None
            }
            try:
                observation_date = datetime.strptime(
                    clean_row_dict[CSV_DATE_COLUMN_STR],
                    CSV_DATE_FORMAT_STR,
                ).date()
                close_float = float(
                    clean_row_dict[CSV_CLOSE_COLUMN_STR].replace(
                        ",", ""
                    )
                )
            except (KeyError, ValueError):
                continue
            row_list.append((observation_date, close_float))
    return row_list


def read_bundled_history_path_list() -> list[Path]:
    """Locate the index CSVs that ship inside this package.

    Brief:
        Asks the import system where the package's own data lives,
        rather than guessing from the file layout on disk.

    Arguments:
        None.

    Returns:
        List[Path]: Every bundled CSV, in a stable order. Empty
            when the distribution was built without its data.

    Warning:
        An empty list means the *packaging* is broken, not that the
        user did anything wrong. Callers should say so rather than
        quietly carry on without history.
    """
    try:
        data_directory = resources.files(HISTORY_PACKAGE_STR)
    except (ModuleNotFoundError, TypeError):
        return []
    path_list: list[Path] = []
    for entry in sorted(
        data_directory.iterdir(), key=lambda item: item.name
    ):
        if entry.name.lower().endswith(".csv"):
            with resources.as_file(entry) as file_path:
                path_list.append(Path(file_path))
    return path_list


def load_bundled_market_history(
    source_name_str: str = "NIFTY 100",
) -> MarketHistory | None:
    """Load the history that ships with this package.

    Brief:
        The path every screen should use. Works identically from a
        clone, an editable install, a built wheel and a hosted
        deployment, because none of them are asked where the file
        is.

    Arguments:
        source_name_str (str): Index name, for labelling only.

    Returns:
        Optional[MarketHistory]: Monthly history, or None when the
            distribution carries no data at all.

    Warning:
        Prefer this to `load_market_history` with a hand-built
        path. A relative path is resolved against the working
        directory, so the same call succeeds from the repository
        root and fails from anywhere else.
    """
    return build_history_from_paths(
        read_bundled_history_path_list(), source_name_str
    )


def load_market_history(
    directory_path: Path | str,
    source_name_str: str = "NIFTY 100",
) -> MarketHistory | None:
    """Load every CSV in a directory into one monthly history.

    Brief:
        Files may overlap at their edges, so rows are deduplicated
        by date before the last observation of each calendar month
        is taken as that month's close.

    Arguments:
        directory_path (Union[Path, str]): Folder of daily CSVs.
        source_name_str (str): Index name, for labelling only.

    Returns:
        Optional[MarketHistory]: Monthly history, or None when the
            folder is missing or holds no readable rows.

    Warning:
        Uses the last *trading* day of each month, which is what a
        real month-end valuation uses too.
    """
    directory = Path(directory_path)
    if not directory.is_dir():
        return None
    return build_history_from_paths(
        sorted(directory.glob("*.csv")), source_name_str
    )


def build_history_from_paths(
    csv_path_list: list[Path],
    source_name_str: str = "NIFTY 100",
) -> MarketHistory | None:
    """Reduce a set of daily CSVs to one monthly history.

    Brief:
        Shared by the bundled loader and the directory loader, so
        both reduce their files the same way.

    Arguments:
        csv_path_list (List[Path]): Daily files, any order.
        source_name_str (str): Index name, for labelling only.

    Returns:
        Optional[MarketHistory]: Monthly history, or None when no
            file held a readable row.

    Warning:
        Files may overlap at their edges, so rows are deduplicated
        by date before the last observation of each calendar month
        is taken as that month's close.
    """
    dated_row_list: list[tuple[date, float]] = []
    for csv_path in csv_path_list:
        dated_row_list.extend(_read_close_rows_list(csv_path))
    if not dated_row_list:
        return None
    month_close_dict: dict[tuple[int, int], tuple[date, float]] = {}
    for observation_date, close_float in sorted(set(dated_row_list)):
        month_close_dict[
            (observation_date.year, observation_date.month)
        ] = (observation_date, close_float)
    ordered_month_list = sorted(month_close_dict)
    return MarketHistory(
        source_name_str=source_name_str,
        month_end_date_list=[
            month_close_dict[month_key][0]
            for month_key in ordered_month_list
        ],
        month_end_close_list=[
            month_close_dict[month_key][1]
            for month_key in ordered_month_list
        ],
    )


def calculate_annualised_return_percent_float(
    history: MarketHistory,
) -> float:
    """Compound annual growth rate of the loaded history.

    Brief:
        Measured end to end on the month-end closes, so it is the
        rate the index actually delivered over the window.

    Arguments:
        history (MarketHistory): Loaded monthly history.

    Returns:
        float: Annualised return in percent, zero when too short.

    Warning:
        A three-year window is a sample, not an expectation. Do
        not feed it forward as a forecast without saying so.
    """
    if history.month_count_int <= 0:
        return 0.0
    total_growth_float = (
        history.month_end_close_list[-1]
        / history.month_end_close_list[0]
    )
    elapsed_years_float = (
        history.month_count_int / MONTHS_IN_YEAR_INT
    )
    return (
        total_growth_float ** (1.0 / elapsed_years_float) - 1.0
    ) * PERCENT_TOTAL_FLOAT


def calculate_annualised_volatility_percent_float(
    history: MarketHistory,
) -> float:
    """Annualised standard deviation of the monthly returns.

    Brief:
        Scales the monthly standard deviation by the square root
        of twelve, the standard convention.

    Arguments:
        history (MarketHistory): Loaded monthly history.

    Returns:
        float: Annualised volatility in percent.

    Warning:
        A calm window understates volatility. This is a property
        of the sample, not of the market.
    """
    return_list = history.monthly_return_list
    if len(return_list) < 2:
        return 0.0
    return (
        statistics.pstdev(return_list)
        * (MONTHS_IN_YEAR_INT**0.5)
        * PERCENT_TOTAL_FLOAT
    )


def describe_coverage_str(history: MarketHistory) -> str:
    """State plainly what this history can and cannot support.

    Brief:
        Written to be shown to the reader, not logged. A bootstrap
        is only as honest as its source, so the source's limits
        travel with every number derived from it.

    Arguments:
        history (MarketHistory): Loaded monthly history.

    Returns:
        str: One paragraph naming the window, its length and the
            worst month it contains.

    Warning:
        Says nothing about what the market will do next, because
        the history cannot know.
    """
    return_list = history.monthly_return_list
    if not return_list:
        return "No usable history was loaded."
    worst_month_float = min(return_list)
    caution_str = ""
    if history.month_count_int < THIN_HISTORY_MONTH_COUNT_INT:
        caution_str = (
            f" That is only {history.month_count_int} monthly "
            "observations, which is thin for resampling."
        )
    if worst_month_float > SEVERE_CRASH_MONTH_THRESHOLD_FLOAT:
        caution_str += (
            " The window contains no severe crash - its worst "
            f"month is {worst_month_float * 100:.1f}%, where March "
            "2020 was near -23%. A bootstrap cannot resample a "
            "disaster its source never saw, so the downside shown "
            "here is kinder than history allows."
        )
    return (
        f"{history.source_name_str}, "
        f"{history.month_end_date_list[0]:%b %Y} to "
        f"{history.month_end_date_list[-1]:%b %Y}: "
        f"{calculate_annualised_return_percent_float(history):.2f}% "
        "a year at "
        f"{calculate_annualised_volatility_percent_float(history):.2f}"
        "% volatility." + caution_str
    )
