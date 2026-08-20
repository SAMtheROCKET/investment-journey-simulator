"""Punctuation this project does not use.

The long dash, the en dash and the single-character ellipsis are all
perfectly good English, and all three are habits of generated prose
rather than of anyone typing at a keyboard. A reader who notices
them starts reading the writing instead of the argument, which is
the one thing a financial tool cannot afford.

So they are banned outright and this holds the ban. The replacement
in every case is the plain ASCII form: a hyphen, or three dots.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT_PATH: Path = Path(__file__).resolve().parent.parent

BANNED_CHARACTER_TUPLE: tuple = (
    ("\u2014", "em dash", "-"),
    ("\u2013", "en dash", "-"),
    ("\u2026", "ellipsis", "..."),
)

CHECKED_ROOT_TUPLE: tuple = (
    "src",
    "tests",
    "tools",
    "docs",
)
SKIPPED_PART_TUPLE: tuple = ("__pycache__", "legacy", "env")


def collect_checked_path_list() -> list[Path]:
    """Every file this rule applies to.

    Includes the markdown at the repository root, which is the
    first thing anybody reads and was the last thing the sweep
    reached.
    """
    path_list: list[Path] = list(PROJECT_ROOT_PATH.glob("*.md"))
    for root_str in CHECKED_ROOT_TUPLE:
        root_path = PROJECT_ROOT_PATH / root_str
        if not root_path.exists():
            continue
        for pattern_str in ("*.py", "*.md"):
            path_list.extend(
                file_path
                for file_path in root_path.rglob(pattern_str)
                if not any(
                    part_str in SKIPPED_PART_TUPLE
                    for part_str in file_path.parts
                )
            )
    return sorted(set(path_list))


CHECKED_PATH_LIST: list[Path] = collect_checked_path_list()


@pytest.mark.parametrize(
    "file_path",
    CHECKED_PATH_LIST,
    ids=lambda path: str(
        path.relative_to(PROJECT_ROOT_PATH)
    ).replace("\\", "/"),
)
def test_no_file_uses_banned_punctuation(file_path):
    """Not in copy, not in a docstring, not in a comment.

    The one exception is this file, which has to name the
    characters in order to ban them.
    """
    if file_path.name == Path(__file__).name:
        pytest.skip("this file holds the rule it enforces")
    text_str = file_path.read_text(encoding="utf-8")
    for character_str, name_str, replacement_str in (
        BANNED_CHARACTER_TUPLE
    ):
        assert character_str not in text_str, (
            f"{file_path.name} uses the {name_str}. Write "
            f"{replacement_str!r} instead."
        )


def test_the_rule_covers_the_whole_project():
    """A rule that checks nothing passes trivially."""
    assert len(CHECKED_PATH_LIST) > 100


# ------------------------------------------------------------------
# Control characters. The disclosure marker in the stylesheet was a
# Unicode escape until a shell heredoc read its backslash-25 as an
# octal escape and wrote byte 0x15 into the file. The rule still
# parsed; it simply drew a control character where the affordance
# should have been, and nothing caught it because every gate was
# looking at Python rather than at the CSS the browser receives.
# ------------------------------------------------------------------
def _control_character_list(text_str: str) -> list:
    """Every byte in a string that no source file should carry.

    Tab, newline and carriage return are ordinary; everything else
    below the printable range is a mistake, and a silent one.
    """
    return sorted(
        {
            character_str
            for character_str in text_str
            if ord(character_str) < 32
            and character_str not in "\t\n\r"
        }
    )


@pytest.mark.parametrize(
    "file_path",
    CHECKED_PATH_LIST,
    ids=lambda path: str(
        path.relative_to(PROJECT_ROOT_PATH)
    ).replace("\\", "/"),
)
def test_no_file_carries_a_control_character(file_path):
    """Not in source, not in copy, not in emitted CSS."""
    found_list = _control_character_list(
        file_path.read_text(encoding="utf-8")
    )
    assert found_list == [], (
        f"{file_path.name} carries "
        f"{[hex(ord(c)) for c in found_list]}"
    )


def test_the_emitted_stylesheet_is_clean():
    """The CSS the browser actually receives, not just its source.

    Checked separately because the stylesheet is assembled at run
    time from several constants, and a corrupted one would only
    show up once they are joined.
    """
    from investment_journey_simulator.ui.chrome import (
        _stylesheet_str,
    )

    assert _control_character_list(_stylesheet_str()) == []


# ------------------------------------------------------------------
# Documented figures. Four generations of this project's README
# lived side by side at once - 370 tests in one file, 679 in
# another, 1,201 in a third and 1,458 in a fourth - each true when
# it was written and none true together. A reader cannot tell which
# generation they are holding.
#
# This does not check the number against reality, which no static
# test can. It checks that every document quotes the SAME number,
# so the figure goes stale in one piece and one edit fixes it.
# ------------------------------------------------------------------
TEST_COUNT_PATTERN_STR: str = (
    r"([0-9],[0-9]{3}|[0-9]{3,4})\s+(?:tests|passing)"
)


def collect_quoted_count_dict() -> dict:
    """Every test-count figure quoted in the documentation."""
    import re

    quoted_dict: dict = {}
    for file_path in CHECKED_PATH_LIST:
        if file_path.suffix != ".md":
            continue
        if file_path.name == Path(__file__).name:
            continue
        # Percent-decoded first, because a shields.io badge writes
        # its comma as %2C and its space as %20. The stale count
        # that prompted this lived in a badge for exactly that
        # reason: the pattern below needs a comma and a space, and
        # an encoded URL has neither.
        from urllib.parse import unquote

        for found_str in re.findall(
            TEST_COUNT_PATTERN_STR,
            unquote(file_path.read_text(encoding="utf-8")),
        ):
            quoted_dict.setdefault(
                found_str.replace(",", ""), []
            ).append(file_path.name)
    return quoted_dict


def test_every_document_quotes_the_same_test_count():
    """One figure, or none. Never several."""
    quoted_dict = collect_quoted_count_dict()
    assert len(quoted_dict) <= 1, (
        "the documentation quotes several different test counts: "
        + "; ".join(
            f"{count_str} in {sorted(set(name_list))}"
            for count_str, name_list in sorted(quoted_dict.items())
        )
    )
