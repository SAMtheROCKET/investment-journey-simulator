# Scorecard - how good is this, and against what?

**A single "% complete" number would be meaningless**, because the
answer depends entirely on what you compare against. A tool can be
100% of a retail SIP calculator and 40% of an institutional planning
platform at the same time. So this page does two things:

1. **Measured facts** - numbers that come from running the code. No
   opinion in them.
2. **Judged ratings** - my assessment, each with the benchmark it is
   judged against stated explicitly, so you can disagree with the
   benchmark rather than the number.

Assessed 5 August 2026.

---

## Part A - Measured (no judgement involved)

| Metric | Value | How it was measured |
|---|---|---|
| Tests passing | **2,549 passing**, 4 intentionally skipped | `pytest` |
| Statement coverage | **93%** | `pytest --cov` |
| Lint findings | **0** | `ruff check src tests tools streamlit_app.py` |
| Lines over 79 chars | **0** | `tools/check_house_style.py` |
| Functions over 50 lines | **0** | same |
| Type errors | **0** | `mypy` (49 source files) |
| Modules at 100% coverage | **15 / 44** | coverage report |
| Statutory parameters verified current | **14 / 14** | checked against published commentary, 4-5 Aug 2026; the two income tax slab tables added for marginal relief confirmed unchanged by Budget 2026 |
| Published calculator figures matched exactly | **2 / 5** | the other 3 use a different, mathematically incorrect convention |
| Hand-verified tax calculations | **5 / 5 exact** | equity LTCG, debt slab, grandfathering, lot-split, marginal relief window. Every parameter is sourced in [SOURCES.md](SOURCES.md) |
| Chart palette gates passed | **5 / 5, both modes** | ported OKLab/WCAG validator |

**What the gates cover.** The lint, type and style numbers are for the
package, its tests, the launchers and the tooling - the code that is
actually maintained. The superseded single-file scripts in `src/`
(`sip_calc*.py`, `sip_dashboard_*.py`) are kept for reference only and
are outside every gate; they would not pass one.

**On "2 out of 5 calculators matched":** this is not a 40% score. We
match India's largest investment platform and a bank-scheme figure to
the rupee. Two of the others use `annual ÷ 12`, which compounds to
12.68% when you asked for 12%. Their number is wrong; ours is right.
Scoring this as a failure would reward copying an error.

Competitors are deliberately not named anywhere in this project. The
claim above is checkable without naming them: run the convention in
Part 10 of SOURCES.md against any calculator you like.

---

## Part B - Judged ratings

Each row states its benchmark. **100% means "nothing material left to
add for that benchmark"** - not perfection in the abstract.

### B1. Against a mainstream Indian SIP calculator
*(the mainstream platform and AMC calculators)*

| Aspect | Rating | Reason |
|---|---|---|
| Core compounding correctness | **100%** | Matches the correct convention exactly; verified against published examples. |
| Tax modelling | **100%** | They model none at all. We model FIFO lots, STCG/LTCG split, exemption ledger, cess, surcharge slabs with marginal relief, grandfathering, loss set-off with expiry. |
| Costs (TER, exit load, STT) | **100%** | They model none. |
| Inflation adjustment | **100%** | Mostly absent there; per-instalment deflation here. |
| Plan shapes (step-up, pause, SWP) | **100%** | Step-up only, if that. |
| Multi-fund + rebalancing | **100%** | Single fund only there. |
| Return reporting (XIRR) | **100%** | Absent there. Post-tax XIRR absent essentially everywhere. |
| Risk / volatility | **100%** | Absent there; we now have paths and percentile bands. |
| Live data & execution | **0%** | They are brokerages. We will never have NAVs or place a trade. |
| **Overall vs this benchmark** | **~90%** | Comprehensively ahead on modelling; permanently behind on data and execution - which is not a fixable gap, it is a different product. |

### B2. Against a serious planning platform
*(institutional portfolio analytics and advisor software)*

| Aspect | Rating | Reason |
|---|---|---|
| Indian tax fidelity | **98%** | Better than anything I found. Marginal relief at every threshold; the s.2(42A) holding boundary corrected to strict. Missing only a real quoted 2018 NAV. |
| Deterministic engine quality | **95%** | Lot-level, auditable, self-validating. |
| Monte Carlo / bootstrap | **65%** | Both exist and are tested, and both run on the bundled history. Missing: correlated multi-asset draws, fat-tailed distributions, and a history long enough to contain a real crash. |
| Historical backtesting | **20-30%** | A short NIFTY 100 history *does* ship, and the replay, the sequence-risk demonstration and the bootstrap all run on it out of the box. It is deliberately not counted as production-grade coverage: roughly 36 monthly observations, no major crash cycle, no debt series and no long-run multi-asset dataset. The machinery is complete; the data behind it is a sample, not a record. |
| Portfolio optimisation | **0%** | No efficient frontier, no factor analysis. Not attempted. |
| Goal-based planning | **70%** | Goal seek solves SIP, return and horizon. No multi-goal prioritisation or funding-ratio view. |
| Reporting | **80%** | Excel, PDF, JSON, validation panel. No client-ready branded output. |
| **Overall vs this benchmark** | **~60%** | Class-leading tax engine wrapped around a good-but-young risk engine. |

### B3. Engineering quality

| Aspect | Rating | Reason |
|---|---|---|
| Test coverage & depth | **95%** | 2,549 passing, 93% coverage, provenance tagged G1-G5. Weakest: UI paths - `risk_view` 56%, `fund_inputs` 57%. |
| Correctness evidence | **90%** | Multiple independent cross-checks, including a test that the timeline and classic front ends value the same plan identically. Cannot reach 100% because returns are unverifiable in principle. |
| Code consistency | **100%** | Zero findings on three separate gates. |
| Documentation honesty | **98%** | Limits stated prominently, including ones that make the tool look worse. Every parameter and convention is sourced in `docs/SOURCES.md`, and **tests assert the document still matches the code** - a stale citation fails the build. |
| Reproducibility | **90%** | Seeded random paths; stable chart colours. |
| Performance | **75%** | Fine for one run. 1,000 stochastic trials × 30 years = 360,000 simulated months, single-threaded, and it is noticeably slow. |
| **Overall** | **~92%** | |

### B4. Fitness for actual use

| Aspect | Rating | Reason |
|---|---|---|
| Answers "what will I have?" | **95%** | With tax, costs and inflation - properly. |
| Answers "what do I need?" | **90%** | Goal seek, including a post-tax target. |
| Answers "how likely is it?" | **80%** | Percentile bands and shortfall probability. Held back by independent (uncorrelated) fund draws. |
| Answers "which fund should I buy?" | **0%** | No scheme data, no recommendations. Out of scope by design. |
| Reconciles with my real portfolio | **75%** | XIRR is comparable to a CAS. But you type returns by hand, so it will never match rupee-for-rupee. |
| Trustworthy for a real decision | **85%** | Arithmetic is verified; conclusions still rest on assumptions you supply. |

---

## Part C - The honest single number

If forced to give one:

> **For an Indian retail investor who wants to understand the
> after-tax, after-cost, risk-aware truth about a SIP plan:
> roughly 90%.**
>
> **As a general-purpose investment planning platform: roughly 60%.**

**The 10% missing from the first number** is: live scheme data,
correlated multi-asset risk, and a shipped historical return series.

**The 40% missing from the second** is mostly deliberate: no
optimisation, no recommendations, no execution. Those are different
products.

---

## Part D - What would move the numbers most

| Change | Effort | What it lifts |
|---|---|---|
| Extend the shipped history: a full crash cycle, and a debt series | Low | Backtesting 20-30% → 80%. The three years that ship make the bootstrap *usable*; they cannot make it *representative*, because its worst month is about −12% where March 2020 was near −23% |
| Correlated multi-asset draws | Medium | Monte Carlo 65% → 85%; removes the "diversification looks too safe" flaw |
| AMFI NAV/TER import *(deferred by you)* | Medium | Reconciliation 75% → 90% |
| Parallelise stochastic trials | Low | Performance 75% → 90% |
| Multi-goal planning | High | Goal planning 70% → 90% |

---

## What "100%" honestly cannot mean here

No amount of engineering makes this tool 100% accurate about your
future, because:

- **the return is your assumption**, and no model knows the future;
- **tax law changes every Budget** - the suite pins today's rules so
  an amendment causes a *visible test failure*, not a silent wrong
  number;
- **a distribution fitted to the past is still an assumption.**

What *can* be 100% is that the arithmetic does exactly what it claims,
that the tax rules are today's real ones, and that the limits are
stated rather than hidden. On those, this program is there.
