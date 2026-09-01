"""No other product is named anywhere in this project.

Naming a rival turns your own launch into their advertisement, and
naming a source you benchmarked against invites an argument about
them rather than about the arithmetic. Neither is worth the words.

Every claim that used to rest on a name has been rewritten to rest
on something checkable instead: the compounding convention is stated
in `docs/SOURCES.md` and anyone can apply it to any calculator they
like. That is a stronger claim than "we match X", because it does
not require the reader to trust either of us.

This check covers the documents *and* the code, because a caption is
as public as a README.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent

# Products, platforms and tools that must not appear. The list is
# lowercase; matching is case-insensitive.
#
# Add to it whenever a name creeps in. Never remove an entry to make
# a failing test pass - rewrite the sentence so it does not need the
# name, the way every entry here already was.
BANNED_NAME_TUPLE: tuple = (
    "projectionlab",
    "boldin",
    "newretirement",
    "cfiresim",
    "firecalc",
    "portfolio visualizer",
    "groww",
    "zerodha",
    "cleartax",
    "et money",
    "etmoney",
    "kuvera",
    "scripbox",
    "indmoney",
    "paytm money",
    "axis max life",
)

# Directories that are not ours to police: the virtual environment,
# tool caches, build output, and `_local/` - the working folder
# that is never published and holds, among other things, the one
# drawing that names real firms.
SKIPPED_PART_TUPLE: tuple = (
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "reports",
    "legacy",
    "_local",
    "build",
    "dist",
)


def is_checked_bool(file_path: Path) -> bool:
    """Whether this file is ours to keep clean."""
    return not any(
        part_str in SKIPPED_PART_TUPLE
        for part_str in file_path.parts
    )


def collect_checked_path_list() -> list[Path]:
    """Every document and module this rule applies to."""
    path_list: list[Path] = []
    for pattern_str in ("*.md", "*.py"):
        path_list.extend(
            file_path
            for file_path in PROJECT_ROOT_PATH.rglob(pattern_str)
            if is_checked_bool(file_path)
        )
    return sorted(path_list)


def find_banned_name_list(file_path: Path) -> list[str]:
    """Names of other products found in one file."""
    try:
        text_str = file_path.read_text(encoding="utf-8").lower()
    except UnicodeDecodeError:
        return []
    return [
        name_str
        for name_str in BANNED_NAME_TUPLE
        if name_str in text_str
    ]


# There are no exemptions, and the test below proves it.
#
# There was one, for a drawing that documented one person's own
# arrangement and named the firms in it. It has been moved out of
# the published tree entirely rather than carved out of the rule:
# the tool is a simulator, and whose bank anybody uses is not part
# of it. A rule with no exceptions is also a rule nobody has to
# check the boundaries of.


def is_exempt_bool(file_path: Path) -> bool:
    """Nothing is exempt. Kept so the sweep reads as a sweep."""
    return False


CHECKED_PATH_LIST: list[Path] = collect_checked_path_list()


def test_there_is_something_to_check():
    """A sweep over an empty list would pass for the wrong reason."""
    assert len(CHECKED_PATH_LIST) > 50


@pytest.mark.parametrize(
    "file_path",
    CHECKED_PATH_LIST,
    ids=lambda path: str(
        path.relative_to(PROJECT_ROOT_PATH)
    ).replace("\\", "/"),
)
def test_no_file_names_another_product(file_path):
    """Not in a caption, not in a README, not in a comment.

    The one exception is this file, which has to hold the list in
    order to enforce it.
    """
    if file_path.name == Path(__file__).name:
        pytest.skip("this file holds the list it enforces")
    if is_exempt_bool(file_path):
        pytest.skip("the documented export-only exemption")
    found_list = find_banned_name_list(file_path)
    assert found_list == [], (
        f"{file_path.name} names another product: {found_list}. "
        "Rewrite the sentence so the claim stands without it."
    )


def test_the_compounding_claim_survives_without_a_name():
    """The claim it replaced must still be checkable.

    Removing a benchmark name is only safe if the reader can still
    verify the underlying point. The convention is stated as a
    formula, which anyone can apply to any calculator.
    """
    sources_str = (
        PROJECT_ROOT_PATH / "docs" / "SOURCES.md"
    ).read_text(encoding="utf-8")
    assert "(1 + annual)^(1/12) − 1" in sources_str
    assert "12.68%" in sources_str


def test_no_file_claims_an_exemption():
    """The carve-out is gone and must not come back.

    The drawing that needed one now lives outside the published
    tree. If a future exemption is wanted, this fails first and the
    reasoning has to be written down before the rule bends.
    """
    for file_path in CHECKED_PATH_LIST:
        assert not is_exempt_bool(file_path)
    assert not (
        PROJECT_ROOT_PATH
        / "src"
        / "investment_journey_simulator"
        / "diagrams"
        / "personal_flow.py"
    ).exists(), "the provider-named diagram is back in the package"


def test_the_application_diagrams_name_nobody():
    """The screens stay clean, exemption or no exemption."""
    from investment_journey_simulator.diagrams.money_flow import (
        DIAGRAM_BUILDER_DICT,
    )

    for name_str, builder in DIAGRAM_BUILDER_DICT.items():
        lowered_str = builder(False).lower()
        for banned_str in BANNED_NAME_TUPLE:
            assert banned_str not in lowered_str, (
                f"the {name_str} diagram names {banned_str}"
            )
