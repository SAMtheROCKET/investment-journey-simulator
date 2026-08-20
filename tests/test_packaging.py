"""What the distribution carries, as opposed to what the repo does.

Every other test in this suite runs from the repository root, with
`src/` on the path and the whole working tree present. That is not
what a user gets. A user gets a wheel, and a wheel carries only what
it was told to carry.

The gap between those two facts hid a real defect through the
whole of the rest of this suite. The index history sat in a folder
called `data/` at
the repository root, the risk lab found it by walking up three
parents from its own file, and both of those are true from a clone
and false from `site-packages`. `load_market_history` returned None,
the interface read None as "no history configured", and an installed
copy quietly lost half of what the program does. No error, no
warning, no failing test.

So these tests ask a different question from the rest of the suite:
not "is the code right" but "does the thing we ship contain the
things it needs". They are cheap, and they are the only tests here
that would have caught it.
"""

from __future__ import annotations

import tomllib
import zipfile
from importlib import resources
from pathlib import Path

import pytest

from investment_journey_simulator.market_data import (
    HISTORY_PACKAGE_STR,
    load_bundled_market_history,
    read_bundled_history_path_list,
)

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent
PACKAGE_NAME_STR: str = "investment_journey_simulator"
MINIMUM_HISTORY_MONTHS_INT: int = 24


def read_pyproject_dict() -> dict:
    """The build configuration, parsed."""
    with (PROJECT_ROOT_PATH / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


# ------------------------------------------------------------------
# The data is where an installed copy can reach it.
# ------------------------------------------------------------------
def test_the_history_is_package_data_not_a_repository_folder():
    """Reachable through the import system, from anywhere.

    REFERENCE: G4-SYNTHETIC. `importlib.resources` answers the same
    way from a clone, an editable install, a wheel and a zip. A
    path built from `__file__` does not.
    """
    assert resources.files(HISTORY_PACKAGE_STR).is_dir()


def test_the_bundled_history_has_files_in_it():
    """A package that ships an empty data folder is no better."""
    path_list = read_bundled_history_path_list()
    assert path_list, (
        "no CSVs found as package data. The distribution was built "
        "without them, which is exactly the defect this file exists "
        "for."
    )
    assert all(
        path.suffix.lower() == ".csv" for path in path_list
    )


def test_the_bundled_history_actually_loads():
    """Present is not the same as readable."""
    history = load_bundled_market_history()
    assert history is not None
    assert len(history.month_end_close_list) >= (
        MINIMUM_HISTORY_MONTHS_INT
    )
    assert history.month_end_date_list == sorted(
        history.month_end_date_list
    )


def test_no_module_reaches_out_of_the_package_for_data():
    """The habit that caused this, banned outright.

    REFERENCE: G4-SYNTHETIC. `parents[3]` from inside the package
    lands on the repository root when run from a clone and on
    somewhere meaningless when run from site-packages. Any file
    that needs its own data must ask the import system for it.
    """
    source_path = PROJECT_ROOT_PATH / "src" / PACKAGE_NAME_STR
    offender_list = []
    for module_path in sorted(source_path.rglob("*.py")):
        text_str = module_path.read_text(encoding="utf-8")
        for depth_int in (2, 3, 4):
            if f"parents[{depth_int}]" in text_str:
                offender_list.append(
                    f"{module_path.name} uses parents[{depth_int}]"
                )
    assert offender_list == [], (
        "these modules locate files by walking up from __file__, "
        f"which breaks once installed: {offender_list}"
    )


# ------------------------------------------------------------------
# The build is configured to carry it.
# ------------------------------------------------------------------
def test_the_build_declares_the_data_files():
    """A file on disk that setuptools was never told about is not
    in the wheel.

    REFERENCE: G4-SYNTHETIC.
    """
    package_data_dict = read_pyproject_dict()["tool"]["setuptools"][
        "package-data"
    ]
    declared_list = package_data_dict[PACKAGE_NAME_STR]
    assert "data/*.csv" in declared_list
    assert "guides/*.md" in declared_list
    assert "py.typed" in declared_list


def test_every_declared_data_pattern_matches_something():
    """A pattern that matches nothing is a silent lie.

    REFERENCE: G4-SYNTHETIC. `py.typed` was declared for months
    while the file did not exist, so the wheel advertised inline
    type information it never shipped.
    """
    source_path = PROJECT_ROOT_PATH / "src" / PACKAGE_NAME_STR
    declared_list = read_pyproject_dict()["tool"]["setuptools"][
        "package-data"
    ][PACKAGE_NAME_STR]
    for pattern_str in declared_list:
        assert list(source_path.glob(pattern_str)), (
            f"pyproject declares {pattern_str!r} as package data "
            "but nothing on disk matches it"
        )


def test_the_type_marker_exists():
    """Claiming inline types without shipping the marker is worse
    than not claiming them.

    REFERENCE: G4-SYNTHETIC. PEP 561.
    """
    assert (
        PROJECT_ROOT_PATH
        / "src"
        / PACKAGE_NAME_STR
        / "py.typed"
    ).is_file()


# ------------------------------------------------------------------
# And the built artefact really contains it.
# ------------------------------------------------------------------
def find_built_wheel_path() -> Path | None:
    """The most recent wheel, if one has been built."""
    wheel_list = sorted(
        (PROJECT_ROOT_PATH / "dist").glob("*.whl"),
        key=lambda path: path.stat().st_mtime,
    )
    return wheel_list[-1] if wheel_list else None


@pytest.mark.skipif(
    find_built_wheel_path() is None,
    reason="no wheel built; run `python -m build --wheel` first",
)
def test_a_built_wheel_carries_the_data():
    """The end of the argument.

    REFERENCE: G4-SYNTHETIC. Everything above can pass while the
    wheel is still empty, because everything above reads the source
    tree. This reads the artefact.
    """
    wheel_path = find_built_wheel_path()
    assert wheel_path is not None
    with zipfile.ZipFile(wheel_path) as archive:
        name_list = archive.namelist()
    csv_list = [
        name_str
        for name_str in name_list
        if name_str.lower().endswith(".csv")
    ]
    assert csv_list, (
        f"{wheel_path.name} contains no CSV data. An install from "
        "this wheel would silently lose its index history."
    )
    assert any(
        name_str.endswith("py.typed") for name_str in name_list
    ), f"{wheel_path.name} ships no PEP 561 type marker"
    guide_list = [
        name_str
        for name_str in name_list
        if "/guides/" in name_str and name_str.endswith(".md")
    ]
    assert guide_list, (
        f"{wheel_path.name} carries no guides. The Guides screen "
        "would render three empty tabs."
    )


def test_the_guides_are_readable_as_package_data():
    """The second instance of the same defect, held.

    REFERENCE: G4-SYNTHETIC. The guides were read by walking up
    three parents from the page module, so an installed copy showed
    an apology instead of the content.
    """
    from investment_journey_simulator.pages.guides_page import (
        GUIDE_SPECIFICATION_TUPLE,
        MISSING_GUIDE_MESSAGE_STR,
        read_guide_str,
    )

    for _title_str, file_name_str, _blurb_str in (
        GUIDE_SPECIFICATION_TUPLE
    ):
        text_str = read_guide_str(file_name_str)
        assert text_str != MISSING_GUIDE_MESSAGE_STR
        assert text_str.lstrip().startswith("#")
