"""The one door into the Investment Journey Simulator.

Run it:

    streamlit run streamlit_app.py

That is the whole interface. There used to be four launchers - a
classic dashboard, an event rail, a studio and this - and keeping
four front ends in step with one engine cost more than it ever
returned. Three of them are still here; they are just not doors any
more. The classic dashboard runs inside Advanced Simulator and the
rail runs inside Guided Journey, and the portal calls both.

This file sits at the repository root rather than under `src/`
because `src/` holds the package and nothing else - that is the
whole point of a src layout. It also means Streamlit Community
Cloud finds the app without being told where to look.

If the package is installed - `pip install -e .` - the import below
resolves on its own. If it is not, the path line makes a clone work
straight after `git clone` with no install step, which is how most
people will first try it.
"""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_DIRECTORY_PATH: Path = (
    Path(__file__).resolve().parent / "src"
)
if str(SOURCE_DIRECTORY_PATH) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY_PATH))

from investment_journey_simulator.portal_app import (  # noqa: E402
    main,
)

main()
