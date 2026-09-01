# Validation and limitations

What has been measured, and what this tool does not do. No scores:
a self-awarded grade invites an argument about the grade, and the
evidence is stronger than any number I could put beside it.

Everything in the first half comes from running the code. Everything
in the second half is a limit, stated because a reader deciding
whether to trust a figure needs the limits more than the features.

Last measured 1 September 2026, against version 4.4.2.

---

## Measured

| | |
|---|---|
| Tests passing | **2,488**, 3 intentionally skipped |
| Statement coverage | **93%** |
| Ruff findings | **0**, over the package, tests, tooling and launcher |
| Mypy errors | **0**, over 89 source files |
| Lines over 79 characters · functions over 50 lines | **0 · 0** |
| Modules at 100% coverage | **15 of 44** |
| Random whole-plan cross-checks, untaxed | **29,000** plans, engine against an independently written simulator |
| Random whole-plan cross-checks, taxed | **4,800** plans, against a second lot book written from the statute |
| Statutory parameters verified and dated | **14 of 14**, each sourced in [SOURCES.md](SOURCES.md) |
| Hand-verified tax calculations | **5 of 5 exact**: equity LTCG, debt slab, grandfathering, lot split, marginal relief |
| Chart palette contrast gates | **5 of 5 passed, in both themes** |

### What the cross-checks actually are

Two simulators, written separately and deliberately differently.
The engine keeps a lot book; the reference carries one number per
fund and no lot book at all, so a mistake in lot accounting cannot
be repeated in both. A third implementation, written from the
statute, checks the tax. Thousands of randomly generated plans -
overlapping pauses, withdrawals, step-ups, closures and rebalances
in the same months - are run through them and compared to the
paisa.

That is what found the defects this project has had. Not the
hand-written tests, which passed throughout.

### What the tax modelling covers

FIFO lots, the short and long term split at the s.2(42A) boundary,
the annual exemption ledger, cess, surcharge with marginal relief
at every threshold, grandfathering under s.112A, loss set-off with
expiry, and debt treatment under s.50AA. Each parameter is dated
and sourced, and a test fails if the document and the code drift
apart, so a stale citation breaks the build rather than misleading
a reader.

### Historical data

A short NIFTY 100 series ships inside the package, and the replay,
the sequence-risk demonstration and the bootstrap all run on it out
of the box. It is roughly 36 monthly observations. Its worst month
is about -12%, where March 2020 was near -23%.

The machinery is complete. The data behind it is a sample, not a
record, and no conclusion about crash behaviour should be drawn
from it.

---

## Limitations

**The return is your assumption.** Nothing here forecasts a market.
Every figure this tool produces is the consequence of assumptions
you supplied, which is a different and more answerable question
than what a market will do.

**Returns are smooth unless you ask otherwise.** The deterministic
engine compounds at a steady monthly rate. Real markets do not, and
the order returns arrive in changes the answer, sometimes a great
deal near the end of a plan. The Historical and Risk Lab exists to
show that spread.

**Stochastic draws are uncorrelated.** Each fund's random path is
drawn independently, which makes diversification look safer than it
is. There is no correlated multi-asset model and no fat-tailed
distribution.

**No live data.** No NAVs, no scheme database, no expense ratios
fetched from anywhere. Every rate and cost is one you type.

**No execution.** Nothing here can buy, sell, or move money, and it
never will.

**No recommendations.** It will not tell you which fund to hold,
which platform to use, or whether a plan is wise. It computes
consequences; the decisions stay yours. It is not a substitute for
a licensed adviser.

**No portfolio optimisation.** No efficient frontier, no factor
analysis. Not attempted.

**One goal at a time.** The solver answers for a monthly amount, a
return or a horizon. There is no multi-goal prioritisation and no
funding-ratio view.

**It will not reconcile with your statement to the rupee**, because
the returns are typed by hand rather than read from your holdings.

**Tax law changes every Budget.** Today's rules are pinned by
tests, so an amendment causes a visible failure rather than a
silent wrong number. That is a tripwire, not immunity: after a
Budget, the parameters need re-checking against the Act.

**Performance is single-threaded.** A thousand stochastic trials
over thirty years is 360,000 simulated months, and it is
noticeably slow.

**Coverage is weakest on the screens**, not the arithmetic:
`risk_view` at 56% and `fund_inputs` at 57% are the thinnest
paths in the suite.

---

## What cannot be verified, in principle

No amount of engineering makes a projection accurate about your
future. What can be checked is narrower and worth stating exactly:

- the arithmetic does what it claims, and two independently written
  simulators agree with it across tens of thousands of plans;
- the tax rules are the ones in force, dated and sourced;
- the limits above are stated rather than hidden.

Those are the claims this project makes. It makes no others.
