"""Words the interface is not allowed to use.

"Corpus" is standard Indian financial English and near-invisible in
US and UK usage, where it reads as either Latin or a typo. The
program is positioned as global, so it must not appear on screen -
while remaining perfectly fine in the India guides, where it is what
a reader would actually say, and in docstrings, where the audience
is whoever maintains this.

The check walks string *literals* by AST rather than grepping, so a
docstring explaining the rule cannot trip the rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "investment_journey_simulator"
)
GUIDE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "investment_journey_simulator"
    / "guides"
)

BANNED_WORD_STR: str = "corpus"

# Modules whose strings a reader can see. The legacy single-file
# dashboards are outside every gate in this project and are not
# included; nor is anything under `exports`, whose sheet headings
# are a separate vocabulary decision.
USER_FACING_DIRECTORY_TUPLE: tuple = ("pages", "ui")
USER_FACING_MODULE_TUPLE: tuple = (
    "portal_app.py",
    "narrative.py",
    "tables.py",
    "timeline_app.py",
    "studio_app.py",
    "app.py",
)

# Internal identifiers that merely *contain* the word. These are
# dictionary keys and colour constants, never rendered, and
# renaming them would break lookups for no reader's benefit.
ALLOWED_LITERAL_TUPLE: tuple = (
    "corpus",
    "rgba",
)


def collect_user_facing_path_list() -> list[Path]:
    """Every module whose strings reach a reader."""
    path_list: list[Path] = []
    for directory_str in USER_FACING_DIRECTORY_TUPLE:
        path_list.extend(
            sorted(
                (SOURCE_DIRECTORY_PATH / directory_str).rglob(
                    "*.py"
                )
            )
        )
    for module_str in USER_FACING_MODULE_TUPLE:
        module_path = SOURCE_DIRECTORY_PATH / module_str
        if module_path.is_file():
            path_list.append(module_path)
    return path_list


def collect_docstring_id_set(tree: ast.AST) -> set:
    """Identify every docstring node, so it can be skipped."""
    docstring_id_set = set()
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.Module,
                ast.ClassDef,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue
        body_list = getattr(node, "body", [])
        if not body_list:
            continue
        first_node = body_list[0]
        if isinstance(first_node, ast.Expr) and isinstance(
            first_node.value, ast.Constant
        ):
            docstring_id_set.add(id(first_node.value))
    return docstring_id_set


def find_banned_literal_list(file_path: Path) -> list[str]:
    """Find rendered string literals using the banned word.

    Brief:
        Skips docstrings and the small set of internal identifiers
        that contain the word without ever showing it.

    Arguments:
        file_path (Path): Module to inspect.

    Returns:
        List[str]: Offending literals, trimmed for the message.

    Warning:
        A word built at runtime by concatenation would slip
        through. Nothing in this codebase does that, and the cost
        of catching it would be a far more fragile check.
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    docstring_id_set = collect_docstring_id_set(tree)
    offender_list = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if id(node) in docstring_id_set:
            continue
        if node.value.strip() in ALLOWED_LITERAL_TUPLE:
            continue
        if BANNED_WORD_STR in node.value.lower():
            offender_list.append(node.value.strip()[:70])
    return offender_list


@pytest.mark.parametrize(
    "file_path",
    collect_user_facing_path_list(),
    ids=lambda path: path.name,
)
def test_no_user_facing_string_says_corpus(file_path):
    """The word must not reach a screen.

    It is fine in a docstring and fine in the India guides. It is
    not fine in something a reader in Toronto or Berlin will see,
    because there it reads as Latin rather than as money.
    """
    offender_list = find_banned_literal_list(file_path)
    assert offender_list == [], (
        f"{file_path.name} shows the word to a reader: "
        f"{offender_list}"
    )


def test_the_check_would_actually_catch_something():
    """A guard that cannot fail is not a guard.

    Proves the AST walk sees ordinary literals, so a passing suite
    means the word is absent rather than the check being blind.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as directory_str:
        probe_path = Path(directory_str) / "probe.py"
        probe_path.write_text(
            '"""A docstring mentioning corpus is fine."""\n'
            'import streamlit as st\n'
            'st.caption("Your corpus at the end")\n',
            encoding="utf-8",
        )
        offender_list = find_banned_literal_list(probe_path)
    assert offender_list == ["Your corpus at the end"]


def test_the_guides_are_exempt_but_do_not_rely_on_it():
    """The guides may use the word; today none of them needs to.

    An earlier version of this test asserted the India guides
    *did* use it, which was simply false - they were written
    without it. Asserting a premise nobody had checked is the same
    mistake as a fixture written by hand, so this records the
    exemption without pretending anything is exercising it.

    If a guide later needs the word, it may have it: markdown
    under the packaged guides folder is outside it by design.
    """
    guide_path_list = sorted(GUIDE_DIRECTORY_PATH.glob("*.md"))
    assert guide_path_list, "the guides went missing"
    for guide_path in guide_path_list:
        assert guide_path.read_text(encoding="utf-8").strip()
