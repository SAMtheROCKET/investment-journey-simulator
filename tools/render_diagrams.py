"""Regenerate the money-flow diagrams and, optionally, preview them.

Run from the repository root:

    python tools/render_diagrams.py            # write the SVGs
    python tools/render_diagrams.py --preview  # also rasterise

Rasterising shells out to Chrome, which is the only dependency-free
way to see the real result: an SVG that parses is not an SVG that
lays out, and every collision found so far was found by looking.
"""

from __future__ import annotations

import subprocess
import sys
import xml.dom.minidom as minidom
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH / "src"))

from investment_journey_simulator.diagrams.money_flow import (  # noqa: E402
    CANVAS_WIDTH_INT,
    DIAGRAM_BUILDER_DICT,
)


def load_private_builder_dict() -> dict:
    """The one drawing that names real firms, if it is present.

    It documents one person's own arrangement, so it lives under
    `_local/diagrams/` rather than in the package: the published
    tool is a simulator, not a record of anybody's banking. This
    tool still renders it when the file is there, and a clean
    public clone simply has one diagram fewer.
    """
    private_path = ROOT_PATH / "_local" / "diagrams"
    if not (private_path / "personal_flow.py").is_file():
        return {}
    sys.path.insert(0, str(private_path))
    from personal_flow import EXPORT_BUILDER_DICT  # noqa: PLC0415

    return dict(EXPORT_BUILDER_DICT)


ALL_BUILDER_DICT: dict = {
    **DIAGRAM_BUILDER_DICT,
    **load_private_builder_dict(),
}

OUTPUT_PATH = ROOT_PATH / "docs" / "diagrams"
CHROME_CANDIDATE_TUPLE = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)


def height_of(svg_str: str) -> int:
    box_str = svg_str.split("viewBox='")[1].split("'")[0]
    return int(float(box_str.split()[3]))


def main() -> None:
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    preview_bool = "--preview" in sys.argv
    browser_str = next(
        (c for c in CHROME_CANDIDATE_TUPLE if Path(c).is_file()), ""
    )
    for name_str, builder in ALL_BUILDER_DICT.items():
        for is_dark_bool in (False, True):
            svg_str = builder(is_dark_bool)
            minidom.parseString(svg_str)
            suffix_str = "dark" if is_dark_bool else "light"
            svg_path = (
                OUTPUT_PATH
                / f"money_flow_{name_str}_{suffix_str}.svg"
            )
            svg_path.write_text(svg_str, encoding="utf-8")
            print(f"wrote {svg_path.name}")
            if not (preview_bool and browser_str):
                continue
            png_path = svg_path.with_suffix(".png")
            subprocess.run(
                [
                    browser_str,
                    "--headless",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    f"--screenshot={png_path}",
                    f"--window-size={CANVAS_WIDTH_INT},"
                    f"{height_of(svg_str)}",
                    svg_path.as_uri(),
                ],
                check=False,
                capture_output=True,
            )


if __name__ == "__main__":
    main()
