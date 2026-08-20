"""The script Streamlit runs when the console command is used.

`streamlit run` needs a *file*, not a function, and the file it
runs has to be one that exists inside an installed distribution.
`streamlit_app.py` at the repository root cannot be that file - a
wheel does not carry the repository - so the packaged copy lives
here and the root launcher stays as the thing a clone runs.

Two files, one line of code each, and neither is the place to put
anything else: both exist only so `main()` has something to be
called from.
"""

from __future__ import annotations

from investment_journey_simulator.portal_app import main

main()
