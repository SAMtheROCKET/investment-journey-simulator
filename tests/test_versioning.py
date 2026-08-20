"""The three numbers this project calls a version.

They were all called "the version" and two were wrong at once: the
distribution said 1.0.0, the package attribute said 3.0.0, and the
saved-file schema said 3.0 while a superseded writer said 2.1. A
reader could not tell which number described what.

They are genuinely different concepts moving for different reasons:

    product and package   what you installed and what you are using
    scenario schema       what shape a saved plan is written in
    data provenance       when a statutory rate was last checked

These hold the first two apart and hold the first two together.
"""

from __future__ import annotations

import re
from pathlib import Path

import investment_journey_simulator
from investment_journey_simulator.scenario_io import (
    SCENARIO_VERSION_STR,
)
from investment_journey_simulator.scenarios import (
    SCENARIO_VERSION_STR as LEGACY_SCENARIO_VERSION_STR,
)

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent
PYPROJECT_PATH: Path = PROJECT_ROOT_PATH / "pyproject.toml"

SEMANTIC_PATTERN_STR: str = r"^\d+\.\d+\.\d+$"
SCHEMA_PATTERN_STR: str = r"^\d+\.\d+$"


def read_pyproject_str() -> str:
    """The packaging metadata, as written."""
    return PYPROJECT_PATH.read_text(encoding="utf-8")


def test_the_product_version_is_semantic():
    """One number for the product and the package alike."""
    assert re.match(
        SEMANTIC_PATTERN_STR, investment_journey_simulator.__version__
    )


def test_the_distribution_reads_the_package_version():
    """The two cannot drift, because there is only one of them.

    Checked by asserting the wiring rather than by comparing
    against installed metadata, which would only be right in an
    environment that had been reinstalled since the last bump.
    """
    pyproject_str = read_pyproject_str()
    assert 'dynamic = ["version"]' in pyproject_str
    assert (
        'version = { attr = '
        '"investment_journey_simulator.__version__" }'
    ) in pyproject_str


def test_the_distribution_states_no_version_of_its_own():
    """A literal here is how the two came to disagree."""
    for line_str in read_pyproject_str().split("\n"):
        stripped_str = line_str.strip()
        if stripped_str.startswith("version =") and (
            "attr" not in stripped_str
        ):
            raise AssertionError(
                f"pyproject declares its own version: {line_str!r}"
            )


def test_the_schema_version_is_not_the_product_version():
    """They move for different reasons and must stay apart.

    Bumping the product must not imply a file-format change, and a
    file-format change must not wait for a product release.
    """
    assert re.match(SCHEMA_PATTERN_STR, SCENARIO_VERSION_STR)
    assert (
        investment_journey_simulator.__version__
        != SCENARIO_VERSION_STR
    )


def test_the_legacy_writer_keeps_its_own_number():
    """Migration reads 2.1 files, so 2.1 has to stay named."""
    assert LEGACY_SCENARIO_VERSION_STR != SCENARIO_VERSION_STR
    assert LEGACY_SCENARIO_VERSION_STR.startswith("2")


def test_the_package_explains_the_difference():
    """A reader must be able to find out which is which.

    The distinction is only useful if it is written down where
    somebody changing a version number will read it.
    """
    source_str = (
        Path(investment_journey_simulator.__file__)
    ).read_text(encoding="utf-8")
    assert "Scenario schema" in source_str
    assert "Product and package" in source_str
