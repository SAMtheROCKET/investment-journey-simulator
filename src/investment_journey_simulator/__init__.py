"""Modular SIP portfolio simulator package.

Layout:
    constants        Shared constants and column labels.
    formatting       Rupee formatting helpers.
    time_utils       Month grid and financial year helpers.
    returns          Rate conversions, expense models, guards.
    models           Typed containers for inputs and outputs.
    taxation         Capital gains policy and exemption ledger.
    holdings         FIFO lot book of a single fund.
    schedules        Contribution, withdrawal and pause plans.
    allocation       Target weight resolution for rebalancing.
    engine           Month-by-month portfolio simulator.
    inflation        Deflation of nominal results to real rupees.
    tables           Result to DataFrame conversion.
    ledgers          Rebalance, withdrawal, annual and fund audits.
    validation       Invariants every run must satisfy.
    charts           Plotly dashboard figure.
    narrative        Summary, caution and usage text.
    fund_builder     Editor table to fund object translation.
    scenarios        Saving and loading a whole plan as JSON.
    dashboard_run    Bundling of one run with its presentation.
    rebalancing_lab  Side-by-side comparison of rebalance policies.
    exports          Workbook and printable report writers.
    ui               Streamlit input and output widgets.
    app              Application entry point.
"""

# Three different things were all called "the version" in this
# project, and two of them were wrong at once: the distribution said
# 1.0.0, this attribute said 3.0.0, and the saved-file schema said
# 3.0 while a legacy writer said 2.1. They are genuinely different
# concepts and they move for different reasons, so they are named
# separately here and only one of them lives in this file.
#
#   Product and package
#       The number below. One value, because a reader who installs
#       the package and a reader who opens the app should never be
#       comparing two different numbers. `pyproject.toml` reads it
#       from here rather than repeating it, so they cannot drift.
#
#   Scenario schema
#       `scenario_io.SCENARIO_VERSION_STR`. Stamped into every
#       saved plan and bumped only when the file format changes,
#       which is a promise to people holding old files rather than
#       a statement about the product. `scenarios.py` still writes
#       the superseded 2.1 shape, which migration reads.
#
#   Data provenance
#       Dated in `docs/SOURCES.md`, and versioned by nothing here.
#       Statutory rates change on their own calendar.
__version__: str = "4.3.1"
