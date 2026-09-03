# Investment Journey Simulator

**Decisions compound too.**

Investment Journey Simulator is an open-source Python investment planning
simulator with a Streamlit interface.

It models how contributions, lump sums, pauses, withdrawals, timing,
rebalancing, goals, taxes and uncertain return paths can change a long-term
investment journey - and helps explain why two journeys finish differently.

**[Project website](https://samtherocket.github.io/investment-journey-simulator/)** |
**[Try it online](https://investment-journey.streamlit.app)** |
**[Source code](https://github.com/SAMtheROCKET/investment-journey-simulator)** |
**[Documentation](https://github.com/SAMtheROCKET/investment-journey-simulator/tree/main/docs)**

![Four investment journeys compared on one shared scale](https://raw.githubusercontent.com/SAMtheROCKET/investment-journey-simulator/main/assets/journey_comparison.png)

## Install

```bash
pip install investment-journey-simulator
```

## Launch

```bash
investment-journey
```

This starts the Streamlit application locally and opens the simulator in your
browser.

## What it can model

### Investment journeys

- SIPs and recurring contributions
- lump-sum investments
- contribution step-ups
- pauses, resumes and restarts
- one-off and recurring withdrawals
- full exits and later restarts
- multi-fund portfolios

### Portfolio decisions

- target allocations and portfolio drift
- portfolio rebalancing
- multiple rebalancing policies
- fees and expense-ratio effects

### Goals and returns

- goal planning and goal seek
- XIRR and post-tax XIRR
- nominal and inflation-adjusted values
- drawdowns
- contribution-versus-growth analysis

### Risk and history

- historical replay
- rolling backtests
- sequence-of-returns risk
- Monte Carlo and stochastic simulation
- block-bootstrap paths

### Compare journeys

- side-by-side scenario comparison
- timing-effect analysis
- Shapley-based attribution when several decisions change together

### Outputs and audit

- interactive charts
- PDF reports
- Excel exports
- JSON scenarios and results
- visible assumptions
- validation and audit information

## Global core, regional depth

The core contribution, portfolio, rebalancing, risk and scenario engine does
not assume a particular country or currency.

Additional tax depth is available for the supported Indian
resident-individual scope, including lot-level capital-gains treatment and
related statutory rules.

## Validation

The published validation record includes:

- **2,488 tests passing**
- **93% statement coverage**
- Ruff clean
- mypy clean
- approximately **29,000 untaxed** randomized independent cross-checks
- approximately **4,800 taxed** randomized independent cross-checks

See the detailed evidence and limitations:

**[Validation and limitations](https://github.com/SAMtheROCKET/investment-journey-simulator/blob/main/docs/VALIDATION_AND_LIMITATIONS.md)**

Statutory parameters and modelling conventions:

**[Sources and conventions](https://github.com/SAMtheROCKET/investment-journey-simulator/blob/main/docs/SOURCES.md)**

## Important

Investment Journey Simulator is a simulation and educational tool.

Future returns are assumptions, not forecasts or guarantees. Historical data
is used for replay, backtesting, sequence-risk analysis, stochastic simulation
and validation - not to claim that past returns predict future returns.

Tax and regulatory treatment can change and may depend on individual
circumstances.

This software is not financial, investment, tax or legal advice.

---

**You define the assumptions. It shows you their consequences.**