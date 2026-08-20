"""Enforce the project's line and function length limits.

Run:
    python tools/check_house_style.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAXIMUM_LINE_LENGTH_INT: int = 79
MAXIMUM_FUNCTION_LINES_INT: int = 50
MAXIMUM_MAIN_LINES_INT: int = 100
MAIN_FUNCTION_NAME_STR: str = "main"
SOURCE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "investment_journey_simulator"
)
# Everything held to the house rules that is not inside the package
# or the suite: the launcher at the repository root, and the two
# scripts under tools/ - including this one, which has no business
# exempting itself.
EXTRA_FILE_PATH_LIST: list[Path] = [
    Path(__file__).resolve().parent.parent / "streamlit_app.py",
    Path(__file__).resolve().parent / "build_rebalancing_report.py",
    Path(__file__).resolve().parent / "render_diagrams.py",
    Path(__file__).resolve(),
]
TESTS_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent.parent / "tests"
)


def collect_python_file_list() -> list[Path]:
    """Gather every file the house style applies to.

    Brief:
        The package, its launchers, the test suite and this
        checker itself all follow the same rules.

    Arguments:
        None.

    Returns:
        List[Path]: Files to inspect, in a stable order.

    Warning:
        The legacy single-file dashboards are excluded on purpose.
    """
    file_list = sorted(SOURCE_DIRECTORY_PATH.rglob("*.py"))
    file_list.extend(sorted(TESTS_DIRECTORY_PATH.rglob("*.py")))
    file_list.extend(EXTRA_FILE_PATH_LIST)
    return [file_path for file_path in file_list if file_path.exists()]


def find_long_lines_list(
    file_path: Path,
) -> list[tuple[str, int, int]]:
    """Report lines longer than the limit in one file.

    Brief:
        Long lines break side-by-side review and printing.

    Arguments:
        file_path (Path): File being inspected.

    Returns:
        List[Tuple[str, int, int]]: File name, line and length.

    Warning:
        Counts characters, not display width.
    """
    violation_list = []
    for line_number_int, line_str in enumerate(
        file_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if len(line_str) > MAXIMUM_LINE_LENGTH_INT:
            violation_list.append(
                (file_path.name, line_number_int, len(line_str))
            )
    return violation_list


def find_long_functions_list(
    file_path: Path,
) -> list[tuple[str, str, int]]:
    """Report functions longer than the limit in one file.

    Brief:
        A function that does not fit on a screen usually does more
        than one thing.

    Arguments:
        file_path (Path): File being inspected.

    Returns:
        List[Tuple[str, str, int]]: File, function and length.

    Warning:
        The entry point may run to a hundred lines.
    """
    violation_list = []
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        length_int = node.end_lineno - node.lineno + 1
        limit_int = (
            MAXIMUM_MAIN_LINES_INT
            if node.name == MAIN_FUNCTION_NAME_STR
            else MAXIMUM_FUNCTION_LINES_INT
        )
        if length_int > limit_int:
            violation_list.append(
                (file_path.name, node.name, length_int)
            )
    return violation_list


def main() -> int:
    """Check every file and report violations.

    Brief:
        Prints a compact report and returns a non-zero exit code
        when anything breaks the house style.

    Arguments:
        None.

    Returns:
        int: Zero when clean, one when violations were found.

    Warning:
        Intended to run in continuous integration.
    """
    long_line_list: list[tuple[str, int, int]] = []
    long_function_list: list[tuple[str, str, int]] = []
    file_list = collect_python_file_list()
    for file_path in file_list:
        long_line_list.extend(find_long_lines_list(file_path))
        long_function_list.extend(
            find_long_functions_list(file_path)
        )
    print(f"files checked: {len(file_list)}")
    print(f"lines over {MAXIMUM_LINE_LENGTH_INT}: "
          f"{len(long_line_list)}")
    for violation_tuple in long_line_list:
        print("   ", violation_tuple)
    print(f"functions over limit: {len(long_function_list)}")
    for violation_tuple in long_function_list:
        print("   ", violation_tuple)
    return 1 if (long_line_list or long_function_list) else 0


if __name__ == "__main__":
    sys.exit(main())
