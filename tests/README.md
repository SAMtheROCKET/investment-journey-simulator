# Test suite and benchmark provenance

```bash
python -m pytest tests -q                       # run everything
python -m pytest tests -q --cov=investment_journey_simulator   # with coverage
```

**Current status: 2,585 passed · 4 intentionally skipped · 93%
statement coverage.**

The four skips are deliberate and self-describing: two files exempt
themselves from the rule they enforce, and two cover a documented
export-only exemption. None of them is a test that could not be
made to run. The Streamlit layer is covered too: `test_app_smoke.py`
boots the classic dashboard through Streamlit's own headless test
runner, so widget-level failures are caught by CI.

Quality gate (all green, all in CI):

```bash
python -m pytest                       # 2,585 passed, 4 skipped
ruff check src tests tools streamlit_app.py
python tools/check_house_style.py      # 0 long lines, 0 long functions
mypy                                   # 0 errors
```

### What the full count needs

That figure is the whole suite with every dependency installed. It
is not reproducible in a bare environment, and it is worth saying
which parts need what rather than leaving somebody to discover it
from a stack trace:

| Requirement | Covers | Without it |
|---|---|---|
| **Streamlit** | 13 of the 56 test files - every page, the portal shell, the rail and the input styles | those files cannot import and the run aborts at collection |
| **Kaleido** | the PDF export's chart rasterisation, in `test_presentation.py` | those tests skip. The four skips in the count above are not these: they are the deliberate exemptions described above |

`pip install -e .` pulls both, as does `pip install -r
requirements.txt`. Neither is optional for a full run, and neither
touches the finance itself: **the engine, taxation, attribution and
scenario tests need no front end at all**, so a bare environment
still exercises everything that computes a number.

| Module | Coverage |
|---|---|
| `constants`, `formatting`, `time_utils`, `returns` | 100% |
| `allocation`, `ledgers`, `validation`, `tables` | 100% |
| `goal_seek`, `stochastic`, `palette` | 100% |
| `charts`, `taxation`, `excel_report`, `rebalancing_lab`, `dashboard_run` | 99% |
| `inflation`, `fund_builder` | 98% |
| `engine`, `schedules` | 96-97% |
| `models` | 97% |
| `holdings` | 95% |
| `narrative`, `pdf_report` | 94% |
| `money_weighted` | 92% |
| `ui/sidebar_controls`, `ui/result_view` | 89-90% |
| `scenarios` | 82% (upload path needs a real file handle) |
| `app` | 76% |
| `ui/fund_inputs` | 57% (button and mode-switch paths) |

---

## Provenance taxonomy

Every test carries a `REFERENCE:` line naming the class of truth it
is checked against. This is deliberate: a number is only as
trustworthy as the thing it was compared with.

| Tag | Meaning | How strong is it? |
|---|---|---|
| **G1-ANALYTIC** | Closed-form mathematics or a standard financial function. The expected value is computed **live from the formula** inside the test, so it cannot silently drift. | Strongest. Identical to what a spreadsheet `FV()` produces. |
| **G2-STATUTORY** | Indian Income-tax Act parameters - rates, thresholds, exemption, financial-year boundary, FIFO. | Strong, but **time-sensitive**: verify against the current Act. |
| **G3-CROSSCHECK** | Values from `notebooks/testing.ipynb`, an independent earlier implementation written before this package existed. Two independent implementations agreeing is real evidence. | Strong for the features it covers. |
| **G4-SYNTHETIC** | Hand-derived scenario with the arithmetic shown in the test docstring, or a branch/guard test. | Verifies logic, not real-world fidelity. |
| **G5-PLAUSIBILITY** | Real-world magnitudes (12% equity, 6% inflation, 0.5% TER, 30% slab) used **only as inputs**, never asserted as truth. | Not evidence of anything - realism of inputs only. |

---

## What is benchmarked against ground truth

### G1 - Mathematical ground truth (exact)

| Claim | Test |
|---|---|
| Monthly rate compounds back to the annual rate | `test_returns.py::test_monthly_rate_compounds_back_to_annual` |
| Annual ↔ monthly conversions are exact inverses | `test_monthly_and_annual_conversions_are_inverses` |
| Accrual expense model equals `(1+R)^(1/12)·(1−e)^(1/12)` | `test_accrual_model_matches_its_definition` |
| Real return satisfies the Fisher relation exactly | `test_real_return_uses_the_fisher_relation` |
| SIP future value = annuity-due closed form, at real SIP sizes (₹5k-₹1L, 7-30 yrs) | `test_benchmarks.py::test_engine_matches_closed_form_for_realistic_plans` |
| End-of-month = ordinary annuity (exactly one month less) | `test_end_of_month_timing_matches_ordinary_annuity` |
| Multi-fund run = sum of independent single-fund runs (linearity) | `test_portfolio_equals_sum_of_independent_runs` |
| Identical funds produce identical outcomes (symmetry) | `test_two_equal_funds_split_exactly_in_half` |
| Zero return returns exactly the principal | `test_zero_return_returns_exactly_the_principal` |
| Deflation factor = `(1+π)^(months/12)` | `test_inflation.py::test_deflation_factor_matches_the_price_level_formula` |
| Real principal = Σ deflated instalments, **not** total ÷ final factor | `test_real_principal_deflates_each_instalment_separately` |
| Cost basis + unrealized gain = market value | `test_engine.py::test_cost_basis_plus_unrealized_equals_value` |
| Weights always sum to 100% | `test_reporting.py::test_fund_history_weights_sum_to_one_hundred` |

### G2 - Statutory ground truth (Indian tax law)

Rates as applicable to transfers **on or after 23 July 2024** under
the Finance (No. 2) Act 2024, unchanged by Budget 2025 and Budget
2026. They live in one place - `tests/reference_data.py` - so an
amendment is a one-line change.

> **Section renumbering.** The **Income-tax Act, 2025 came into
> force on 1 April 2026**. Every rate below carries over unchanged,
> but the section numbers moved: **111A → 196**, **112 → 197**,
> **112A → 198**, and "previous year / assessment year" became
> "tax year". Both numbers are given below; the 1961 numbers are
> kept in brackets because most published commentary still uses
> them.

| Provision | Modelled as | Test |
|---|---|---|
| STCG on equity, s.196 [111A] | 20% | `test_taxation.py::test_short_term_rate_matches_section_111a` |
| LTCG on equity, s.198 [112A] | 12.5% | `test_long_term_rate_matches_section_112a` |
| Holding period for listed equity | 12 months, inclusive at the boundary | `test_holding_threshold_boundary_is_inclusive` |
| Exemption, proviso to s.198 [112A] | ₹1,25,000 per **taxpayer** per year | `test_exemption_shelters_the_first_lakh_and_a_quarter`, `test_portfolio_exemption_is_shared_between_funds` |
| Exemption is annual, not per transaction | consumed once, resets next FY | `test_exemption_is_consumed_only_once_per_year`, `test_exemption_resets_in_the_next_financial_year` |
| s.196 [111A] carries no exemption | LTCG-only scope | `test_long_term_scope_does_not_shelter_short_term_gains` |
| Specified (debt) funds, s.50AA | always short term, slab rate | `test_debt_style_fund_is_never_long_term`, `test_reporting.py::test_debt_preset_uses_the_slab_rate` |
| Tax year = April-March | FY boundary at 1 April | `test_units.py::test_financial_year_boundary_is_first_of_april` |
| FIFO for units, Rule 8AA | oldest lot sold first | `test_units.py::test_fifo_consumes_the_oldest_lot_first` |
| Holding period follows the units | partial sale does not reset it | `test_partial_sale_keeps_the_original_purchase_month` |
| Tax applies to gains only | losses and zero gains untaxed | `test_zero_and_negative_gains_are_never_taxed` |
| **Grandfathering, proviso to s.198 [112A]** | deemed cost = higher of actual cost and lower of 31 Jan 2018 FMV and sale value | `test_grandfathering_uses_the_deemed_cost_of_acquisition` and 3 more |
| **Loss carry-forward limit, s.74** | 8 assessment years, then the loss lapses | `test_charges_and_scenarios.py::test_losses_expire_after_eight_assessment_years` and 2 more |
| **Surcharge slabs on total income** | nil / 10% / 15% / 25%, plus the 37% band in the old regime | `test_new_regime_surcharge_slabs_match_the_statute` and 3 more |
| Indian digit grouping | 2-2-3 convention | `test_units.py::test_indian_grouping_covers_every_digit_boundary` |

**Source check performed 2026-08-04, re-verified 2026-08-05.**

| Parameter | Value | Confirmed |
|---|---|---|
| LTCG rate, s.198 [112A] | 12.5% (was 10%) | ✅ raised by Budget 2024, effective 23 Jul 2024 |
| LTCG exemption | ₹1,25,000/yr (was ₹1,00,000) | ✅ unchanged by Budget 2025 and 2026 |
| STCG rate, s.196 [111A] | 20% (was 15%) | ✅ effective 23 Jul 2024 |
| Holding period, listed equity & EOF | 12 months | ✅ |
| Specified (debt) funds, s.50AA | always short term, slab rate, no indexation | ✅ units bought on/after 1 Apr 2023 |
| Health & education cess | 4% on tax | ✅ |
| Surcharge cap on 196/198 gains | 15% | ✅ modelled, and enforced above the slab rate |
| Surcharge slabs, new regime | 0 / 10 / 15 / 25% at 50L / 1cr / 2cr | ✅ **now modelled** (was a single flat user-entered rate) |
| Surcharge slabs, old regime | adds 37% above ₹5 crore | ✅ **now modelled** |
| STT on EOF redemption | 0.001% of redemption value | ✅ |
| Grandfathering, 31 Jan 2018 NAV | real provision | ✅ **now modelled** (see the caveat below) |
| Loss carry-forward | 8 assessment years | ✅ **now enforced** (was unlimited, which understated tax) |

> ⚠️ **One honest caveat on the newly modelled provisions.**
> **Grandfathering** needs the *actual quoted NAV* on 31 January
> 2018. The engine has no NAV feed, so it uses the lot's own
> *simulated* value on that date as the deemed fair market value.
> That is exact only to the extent the assumed return actually
> happened, and it is the best a return-assumption engine can do.
>
> There used to be a second caveat here, saying surcharge slabs
> did not apply **marginal relief**. They do: in slab mode the band
> rate is replaced by an effective rate holding the extra tax at or
> below the extra income at every threshold, computed before cess.
> The caveat outlived the limitation it described, which is the
> ordinary fate of a document that is written about code rather
> than checked against it.

> ⚠️ **Verify before relying on these.** Tax law changes every
> Budget. The suite pins today's understanding in
> `tests/reference_data.py` so that a future amendment produces a
> *visible test failure* rather than a silent wrong number.

### G3 - Independent implementation cross-check

Every expected dictionary from `notebooks/testing.ipynb` is replayed
through the full engine. The notebook was written independently,
before this package existed, so agreement is genuine evidence.

| Notebook table | Values | Test |
|---|---|---|
| Plain SIP (₹100 @ 12%, 8 horizons) | 1,276.65 ... 1,70,220.66 | `test_engine_matches_notebook_sip_values` |
| Step-up SIP (10%/yr, 8 horizons) | 1,276.65 ... 3,93,550.18 | `test_engine_matches_notebook_stepup_values` |
| Lump sum (₹100 @ 12%, 8 horizons) | 112.00 ... 1,700.01 | `test_engine_matches_notebook_lumpsum_values` |
| 3-fund table @ 15 yrs (10/12/14%) | 12,04,863.65 / 14,27,794.20 / 16,95,621.41 | `test_engine_matches_notebook_three_fund_table` |
| SIP with a 2-year gap (3 start years) | 1,01,804.57 / 1,09,224.20 / 1,15,356.12 | `test_engine_matches_notebook_paused_sip` |
| SWP from a corpus (₹25,000 @ 12%, ₹500/m) | reference loop replayed live | `test_engine_matches_reference_withdrawal_plan` |

The notebook's functions are **re-implemented verbatim** in
`tests/reference_data.py` and must stay naive - never refactor them
to call package code, or the cross-check becomes circular.

### G3b - The engine audit

`test_engine_audit.py` is the same principle applied to every
feature rather than to the notebook's six tables. Nothing in it
compares the engine to a stored figure. Each test either derives the
answer in closed form or re-computes it with a plain loop written
from the definition; where no closed form exists - rebalancing, and
the combinations - it asserts an invariant that must hold whatever
the arithmetic underneath is.

It was written after a reader noticed that the invested split and
the ending split of a three-fund plan showed identical percentages,
which is impossible when the funds assume different returns. Two
defects came out of it, both in the space *between* features, which
is how a suite this size had missed both:

| Defect | What it did | Held by |
|---|---|---|
| Quick Projection rewrote every fund's return to the first fund's, simply by being opened | flattened the split - the reported symptom | `test_apply_actions.py` |
| A portfolio instalment was given to every fund in full instead of divided between them | a two-fund plan invested **twice** what was asked for, and the error grew with the fund count | `test_a_portfolio_instalment_is_divided_not_duplicated` |

What the audit covers: the compounding convention, per-fund
attribution, step-up, step-down, contribution pauses, withdrawal
schedules and their start gap, calendar rebalancing and its
interval, the inflation adjustment, and then all of those running at
once - a pause inside a step-up, a withdrawal during a rebalancing
schedule, cumulative totals against their own monthly columns.

### G3c - The engine fuzz

`test_engine_fuzz.py` does not contain test cases. It generates
them: random horizons, funds, step-ups, pauses, withdrawals,
rebalances, instalment changes and lump sums, placed so that they
collide with each other. Each plan is then checked one of two ways.

**Tax off** - against `reference_simulator.py`, which computes the
same portfolio by a different algorithm. The engine keeps a book of
lots and compounds each parcel from its own purchase month, because
capital gains tax needs to know which units were sold. The
reference carries one number per fund and rolls it forward:

    value = value * (1 + rate) + money in - money out

No lots, no purchase dates, no first-in-first-out. A mistake in the
lot book cannot also be made there, because there is nothing there
to make it in. The two must agree to floating point.

**Tax, exit loads and transaction tax on** - no independent answer
is available, so the plans are held to laws. The strongest is
conservation with every return set to zero, which removes growth
from the arithmetic and leaves an exact identity:

    what is left == what went in - what came out - what was charged

That identity found the defect below. `test_engine_overlaps.py`
then covers by hand the collisions a random generator hits only by
luck, and states which event wins when two land in one month.

| Scenarios cross-checked | How |
|---|---|
| 29,000 untaxed plans | against `reference_simulator`, every figure, zero disagreements |
| 4,800 taxed plans | against `reference_tax`, a second lot book |
| 4,500 taxed plans | against the invariants |
| 1,800 zero-return plans | against the conservation identity |
| 3,000 untaxed and 1,000 taxed plans carrying the two money-out events | 1,186 with a lump withdrawal, 476 with a liquidation, 188 with both |
| 17 hand-built collisions | withdrawal starting inside a pause, pause opening on a rebalancing month, two instalment changes on one month, a fund joining a portfolio already paying out, a withdrawal larger than the corpus, negative returns |

The generators cover every feature the engine has, and the coverage
is measured rather than assumed - over 1,500 random plans: 80% hold
more than one fund, 79% escalate (19% *de*-escalate), 73% contain a
pause, 64% withdraw, 59% rebalance, 45% use continuous accrual, 41%
carry an explicit return path, 27% steer contributions, 21% trim
partially rather than liquidating, 16% trigger on a drift band, 61%
start at least one fund late, and 32% assume a fund that loses
money.

**Proving the fuzz can fail.** A cross-check that never fails is
worth nothing unless failure is possible, so each generator is
checked by planting a defect and confirming it is caught:

| Planted defect | Caught in |
|---|---|
| Growth off by one month | 192 of 200 plans |
| Accrual expense model swapped for simple subtraction | 112 of 400 |
| Return path shifted one month | 137 of 400 |
| Holding-period boundary made inclusive | 56 of 300 |
| Exemption never resetting each April | 42 of 300 |
| A long-term loss allowed to shelter a short-term gain | 8 of 300 |
| Carried-forward losses never expiring | 3 of 300 |

The last two are low because they need a loss realised *before* a
gain it can shelter, which is rare even in a generator that goes
looking for it. Both rules also carry their own hand-written
tests.

**What it found: the exit load was reported but never deducted.**
A charge on an investor withdrawal was computed correctly, added to
the charges column, and then left in the portfolio. The same charge
*was* deducted when a rebalance sold, and *was* subtracted from the
post-tax figure at final exit, so one charge had three behaviours.
The conservation identity failed on 873 of the first 3,000 random
plans, short by exactly the charges every time.

The test that was supposed to cover this - named
`test_exit_load_reduces_what_the_investor_receives`, with a
docstring saying the investor "receives less than the gross
redemption" - asserted only that the charge equalled one per cent
of the withdrawal. That was true whether or not anybody ever paid
it. It now compares two runs, so the money has to go somewhere.

### G3d - The tax cross-check

Tax was the last part with no independent check. `reference_simulator`
cannot supply one: it keeps no lot book, and that absence is exactly
what makes it good evidence about value. Tax needs to know which
units were sold, when they were bought and which financial year the
sale fell in.

So `reference_tax.py` is a second lot book, written from the rules
rather than from `taxation.py`. `test_engine_tax_fuzz.py` runs both
over the same random plans and requires them to agree on tax,
charges, corpus, principal and payout.

**What the disagreement was.** The first run disagreed on 97 of 400
plans - on tax alone, with every other figure matching, which is
what said the flows were right and only the classification was
wrong. The cause was the holding-period boundary. Section 2(42A)
calls an asset short term when it was held for *not more than* the
threshold, so twelve whole months is short term and only the
thirteenth earns the lower rate. The comparison is strict. **The
engine had it right and the second reading had it wrong** - every
one of the 97 was a parcel sold at exactly the boundary, which the
second book taxed at 12.5 per cent instead of 20.

It is worth recording as the shape of thing a hand-written suite
misses: not a wrong formula, but a wrong inequality on one line,
visible only when a sale lands on the exact month. This engine had
made that same mistake once before, in the other direction, and
fixed it on 5 August 2026.

Covered by the tax cross-check: first-in first-out consumption,
partial sales keeping their original purchase month, short against
long term, the annual exemption per fund and per taxpayer, the April
year boundary, exemption scope, specified debt funds that are always
short term, loss set-off and its two pools, carry-forward expiry,
surcharge and cess, exit loads and the transaction tax - all of it
while contributions, withdrawals and rebalances are running.

Not covered by it, and held by their own tests: grandfathering,
which cannot arise in a plan starting in 2026, and the automatic
surcharge bands, where the rate is derived from total income.

### What is cross-checked, and what is not

Being plain about the boundary matters more than the headline
number. Two independent implementations agreeing is strong evidence;
an invariant holding is weaker; neither is a substitute for the
other.

| Part of the engine | Held by |
|---|---|
| Compounding, both expense models, return paths | `reference_simulator`, exact |
| Contributions, step-ups, overrides, one-offs, lump sums | `reference_simulator`, exact |
| Pauses of every scope, staggered fund starts | `reference_simulator`, exact |
| Withdrawals, all three modes | `reference_simulator`, exact |
| Rebalancing: both methods, all four triggers, caps, steering | `reference_simulator`, exact |
| Capital gains tax, exemptions, set-off, charges | `reference_tax`, exact |
| Cash conservation with tax and charges live | an exact identity at zero return |
| Grandfathering, automatic surcharge bands | hand-written tests only |
| Money-weighted return, goal seek, stochastic sampling | hand-written tests only |

### G3e - Taking money out

`test_money_out.py` covers the two events added in 4.3.0: a lump
sum taken out of one month, and a full exit that closes the plan.
Both are held the same three ways as everything else - hand
arithmetic, the independent simulators, and invariants - and the
combinations get more attention than the features, because a lump
withdrawal on a rebalancing month crosses two mechanisms that were
written separately.

Two defects surfaced while it was being built, both from the
cross-check rather than from a hand-written case:

| Defect | Found by |
|---|---|
| Raising money from one *named* fund looped over every holding while being handed a mapping containing one, and raised a `KeyError` | the first cross-check run |
| A closure left nine nano-rupees behind, because selling a sum equal to the balance is not the same operation as selling everything | a 3,000-plan fuzz, on one seed |

The second is worth the sentence it costs. Nine nano-rupees on a
₹3.55 crore corpus is not money, and no chart or table would ever
show it. But "this plan holds exactly nothing" is a claim about
kind rather than size, and a later feature asking `value > 0` would
have got the wrong answer. Closing now empties the lot book instead
of raising a target amount, which cannot leave a remainder because
there is no arithmetic left to round.

One more thing that file records: the hand-computed gap a
₹2,00,000 withdrawal opens is that amount compounded for **119**
months, not 120. The sale happens at the close of its own month, so
that month's growth is already earned. The off-by-one lands within
one per cent - the size of error a test written to agree with the
code would have enshrined without anybody noticing.

### Headless application runs

`test_app_smoke.py` boots the classic dashboard end to end through
`streamlit.testing.v1.AppTest` and asserts that the page
raises nothing, renders both runs, draws all eight charts, shows
sixteen metric tiles, and gives every chart a unique element id.

That last check exists because of a real crash: Streamlit derives
an element id from the element's parameters, and the nominal and
real **weight** charts are byte identical - weights are ratios, so
deflation does not change them. Without a run-specific `key`,
Streamlit raised `StreamlitDuplicateElementId`. No headless unit
test could see it, because element ids are only registered when
widgets actually render.

The launcher files these harnesses used to read off disk were
deleted when the portal became the only way in, so
`conftest.build_launch_script_str` builds the same four lines they
contained. Nothing about what the tests exercise changed; only
where the entry point comes from.

### G4 - Synthetic, analytically validated

Branch and edge-case coverage where no external truth exists. Each
docstring shows the derivation. Examples: all four step-up modes,
step-up intervals and delays, fixed-rupee increments, every pause
scope, reversed date ranges, withdrawal caps and depletion, all
three rebalance triggers, the event cap, contribution steering,
target-weight fallbacks, `-100%` returns, blank fund names,
duplicate fund names, empty portfolios, zero horizons, gain/loss
bar colouring, drawdown sign, target lines, and the JSON scenario
round trip.

### G5 - Plausibility inputs only

12% equity / 7% debt / 6% inflation / 0.2-0.5% TER / 30% slab, and
SIP sizes of ₹1,500-₹1,00,000. These make tests *realistic*; they
are never asserted as facts about markets.

---

### Money-weighted return (XIRR)

`money_weighted.py` solves the annual rate that discounts the dated
cash flows to zero - the figure printed on a consolidated account
statement, and the only correct return measure once step-ups,
pauses, withdrawals or rebalancing make the cash flow stream
irregular. A **post-tax** XIRR is reported beside it, which no
mainstream Indian SIP calculator publishes.

| Claim | Test |
|---|---|
| Reproduces the spreadsheet vendor's own documented XIRR example (37.336%) | `test_money_weighted.py::test_solver_matches_the_documented_spreadsheet_example` |
| The solved rate is a root of the present-value function | `test_present_value_at_the_solved_rate_is_zero` |
| An untaxed plan recovers exactly the rate its funds compound at, across 2 rates × 3 horizons × both timings | `test_untaxed_plan_recovers_its_own_growth_rate` |
| A series with no sign change reports **no rate**, never a fabricated zero | `test_degenerate_series_have_no_rate` |
| The closing corpus is dated at month *close*, not month start | `test_terminal_corpus_settles_after_the_last_instalment` |

The residual error against the fund's own rate is about **1 basis
point**. That is not slack in the solver: it is the genuine
difference between the engine's idealised twelfth-of-a-year month
and the actual/365 day count XIRR uses, and a spreadsheet on the
same dated flows reproduces it.

### Goal seek

`goal_seek.py` drives the engine backwards by bisection to answer
the question users actually ask: what instalment, what return or
what horizon reaches a target corpus. Verified by round trip - the
solved input is replayed through the engine - and for the plain-SIP
case against the closed form. An unreachable goal returns **None**
rather than a search bound.

### Stochastic return paths

`stochastic.py` replaces the single constant rate with a monthly
return *path*, so `FundHoldings` compounds on a cumulative growth
index instead of one exponent. This is what finally lets the engine
express **sequence-of-returns risk**.

| Claim | Test |
|---|---|
| A zero-volatility path reproduces the deterministic run exactly | `test_stochastic.py::test_zero_volatility_reproduces_the_deterministic_run` |
| A flat path equals the annuity-due closed form | `test_a_flat_path_equals_the_closed_form` |
| **The same returns in a different order end differently** | `test_the_order_of_returns_changes_the_outcome` |
| Bootstrap emits only returns the history contained | `test_bootstrap_only_ever_emits_observed_returns` |
| Block resampling keeps consecutive months together | `test_bootstrap_preserves_runs_of_months` |
| More volatility widens the percentile band | `test_volatility_widens_the_distribution` |

The deterministic branch is untouched: with no path supplied,
`_growth_factor_float` delegates to the original function, so every
pre-existing number is bit-identical.

### Chart colour

`palette.py` separates *status* colour (gain, loss, tax, rebalance,
pause - reserved) from *identity* colour (which fund). Identity is
keyed on the fund's slot in the sorted roster of the whole plan, not
on trace order, which fixes a real defect: Plotly assigned colours
from its cycle by position, so the same fund could be a different
colour in the value chart and the weight chart.

Both palettes were validated by computation, not by eye, against
OKLCH lightness and chroma, OKLab separation under simulated
protanopia and deuteranopia, and WCAG contrast. Measured worst
cases, all pairs: **light CVD ΔE 10.3 / normal ΔE 15.8; dark CVD
ΔE 9.4 / normal ΔE 16.6**. Six fund colours in light mode and five
in dark is a **ceiling, not a preference** - exhaustive search over
a 27-colour pool found no seven-colour set clearing the same gates.

---

## What is **not** benchmarked (be honest about this)

| Not verified | Why it matters |
|---|---|
| **Actual fund returns** | Every return is a user assumption. Nothing here predicts markets, and a distribution fitted to the past is still an assumption. |
| **Correlation between funds** | Each fund draws its own independent path, so a diversified portfolio looks safer than it is: real correlations rise in a crash. |
| **Live NAV, TER or scheme data** | No AMFI/SEBI feed is wired in. TERs are typed by the user. |
| **Grandfathering FMV** | Modelled, but from the *simulated* 31 Jan 2018 value, not a real quoted NAV. |
| **Marginal relief beside the 15% cap** | Relief itself *is* modelled. What the Act does not spell out is the ordering when relief meets the cap on capital-gains surcharge; this applies relief first, then the cap. |
| **Dividend/IDCW plans** | Growth-plan assumption only. |
| **Exact same-day NAV mechanics** | The engine works on a monthly grid, not daily NAVs. |

---

## Conventions inside the tests

- Test functions use a compact docstring: a one-line title plus a
  `REFERENCE:` block naming the provenance and, for G4, the
  derivation. Full four-section docstrings are reserved for the
  package itself and for shared helpers.
- Naming (`<meaning>_<dtype>`), the 79-character limit and the
  50-line function limit apply here exactly as in `src/`.
- Fixtures default every optional feature **off**, so each test
  switches on only what it exercises and a failure points at one
  mechanism.
