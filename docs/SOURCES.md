# Sources - where every number comes from

Every statutory parameter in this program is listed below with the
source it was checked against and the calculation that verifies it.
Where **no published source exists**, the row says so plainly and
states how the value was arrived at instead. A number with no source
and no derivation would be a guess, and there are none of those here.

**Checked on 5 August 2026, for FY 2026-27 (AY 2027-28).** The
Budget presented in February 2026 changed neither regime's slabs,
the surcharge, the cess, nor the capital gains rates.

**Re-verify after each Budget.** The test suite pins today's rules,
so an amendment shows up as a *failing test* rather than a silently
wrong number.

---

## How to read this page

| Column | Meaning |
|---|---|
| **Value** | What the program uses. |
| **Where** | The constant or function that holds it. |
| **Basis** | The statutory provision it comes from. |
| **How verified** | The calculation or comparison that proves it. |

---

## Part 1 - Capital gains on equity-oriented funds

| Parameter | Value | Where | Basis | How verified |
|---|---|---|---|---|
| Short-term rate | **20%** | `constants.py:271` | s.111A, as amended by the Finance (No. 2) Act 2024 for transfers on or after 23 July 2024 | Published commentary, 4-5 Aug 2026; asserted in `test_short_term_rate_matches_section_111a` |
| Long-term rate | **12.5%** | `constants.py:272` | s.112A, same amendment | Published commentary; `test_long_term_rate_matches_section_112a` |
| Annual exemption | **₹1,25,000** | `constants.py:274` | proviso to s.112A | Published commentary; hand calculation `₹2,00,000 − ₹1,25,000 = ₹75,000 taxable at 12.5%` |
| Holding threshold | **more than 12 months** | `constants.py` fund defaults | s.2(42A) | Strict comparison; `test_holding_threshold_boundary_is_exclusive` asserts 12 months is short-term and 13 is long-term |
| Indexation | **not applied** | - | withdrawn for these gains by the 2024 amendment | Absence verified: no indexation path exists in `taxation.py` |
| Debt funds always short-term | **yes** | fund preset | s.50AA, specified mutual funds acquired on or after 1 April 2023 | `test_debt_style_fund_is_never_long_term` |

## Part 2 - Levies on top of the tax

| Parameter | Value | Where | Basis | How verified |
|---|---|---|---|---|
| Health and education cess | **4%** | `constants.py:101` | Finance Act, charged on tax **plus** surcharge | Order asserted in `test_surcharge_is_charged_before_cess`: `12,500 → +10% → ×1.04` |
| Surcharge cap on 111A/112A gains | **15%** | `constants.py:103` | first proviso to s.2(9) of the Finance Act | `test_equity_gains_surcharge_is_capped_at_fifteen_percent`: a 25% band still yields `12.5% × 1.15` |
| STT on equity redemption | **0.001%** | `constants.py:176` | Securities Transaction Tax, equity-oriented fund redemption | Published rate schedule |

## Part 3 - Surcharge slabs

| Total income | New regime | Old regime | Where |
|---|---|---|---|
| Up to ₹50 lakh | 0% | 0% | `constants.py:128` and `:134` |
| Above ₹50 lakh | 10% | 10% | same |
| Above ₹1 crore | 15% | 15% | same |
| Above ₹2 crore | 25% | 25% | same |
| Above ₹5 crore | 25% (capped) | 37% | same |

**Basis.** Finance Act rates; the new regime, default since
FY 2023-24, drops the 37% band. **Verified** against published
commentary on 4-5 Aug 2026 and asserted band by band in
`test_new_regime_surcharge_slabs_match_the_statute` and
`test_old_regime_keeps_the_thirty_seven_percent_band`.

## Part 4 - Income tax slabs *(used only for marginal relief)*

These slabs exist for one purpose: marginal relief cannot be
computed without the tax on total income and the tax at the slab
floor. **This program never reports your income tax bill.**

| New regime FY 2026-27 | Rate | | Old regime | Rate |
|---|---|---|---|---|
| Up to ₹4,00,000 | Nil | | Up to ₹2,50,000 | Nil |
| ₹4,00,001-₹8,00,000 | 5% | | ₹2,50,001-₹5,00,000 | 5% |
| ₹8,00,001-₹12,00,000 | 10% | | ₹5,00,001-₹10,00,000 | 20% |
| ₹12,00,001-₹16,00,000 | 15% | | Above ₹10,00,000 | 30% |
| ₹16,00,001-₹20,00,000 | 20% | | | |
| ₹20,00,001-₹24,00,000 | 25% | | | |
| Above ₹24,00,000 | 30% | | | |

**Where.** `constants.py`, `NEW_REGIME_INCOME_TAX_SLABS_TUPLE` and
`OLD_REGIME_INCOME_TAX_SLABS_TUPLE`.

**Verified** against published slab tables for FY 2026-27 on
5 Aug 2026, which confirm Budget 2026 left both regimes unchanged.
Cross-checked in `test_income_tax_matches_an_independent_slab_walk`
against a longhand reimplementation in `reference_data.py`.

**Deliberately not modelled, and why it is safe:** the §87A rebate
stops far below ₹50 lakh, so it can never affect relief. The higher
senior-citizen exemption under the old regime shifts the tax at the
income and at the floor by the same amount, moving relief by at most
a few hundred rupees. Deductions are not modelled because the figure
the user supplies is *total income*, already net of them.

## Part 5 - Marginal relief

**The anchor calculation.** Old regime, tax at exactly ₹50 lakh:

```
 5% × ₹2,50,000  =    ₹12,500
20% × ₹5,00,000  =   ₹1,00,000
30% × ₹40,00,000 =  ₹12,00,000
                    ----------
                    ₹13,12,500
```

Relief runs out when the extra tax equals the extra income:

```
0.10 × ₹13,12,500 ÷ 0.67 = ₹1,95,895.52
```

so the window closes at **₹51,95,896**.

**Why this is the anchor.** That figure appears in published tax
commentary independently of this program, which makes it a real
external check rather than a restatement of our own arithmetic. It
is asserted to the rupee in
`test_the_relief_window_closes_at_the_published_income`.

**Relief is computed before cess**, which is the order the Act
prescribes. At the second and higher thresholds the comparison
carries the surcharge of the band below; continuity across every
threshold is asserted in
`test_earning_one_more_rupee_never_costs_more_than_a_rupee`.

---

## Part 6 - Corrected: the 12-month holding boundary

**What the statute says.** Section 2(42A) defines a short-term
capital asset as one held for **not more than** twelve months. An
asset held for *exactly* twelve months is therefore **short-term**.

**What this program used to do.** `taxation.py` treated
`months_held >= 12` as long-term, so a holding of exactly twelve
whole months got the more favourable treatment - 12.5% instead of
20%, understating the tax by 7.5% of the gain on any lot sold
exactly a year after it was bought.

**Fixed on 5 August 2026.** The comparison is now strict (`>`), and
two tests hold it there: one asserts the classification on both
sides of the boundary, the other asserts that a lot held exactly
twelve months is actually *charged* the section 111A rate of 20%,
so the rule cannot regress into a flag nothing reads.

**Scope of the change.** Only the twelfth month moved. Eleven months
was short-term before and after; thirteen was long-term before and
after. Exactly one test in the suite depended on the old behaviour,
which is itself evidence the boundary was an oversight rather than a
deliberate convention.

---

## Part 7 - Engine conventions

These are not rates. They are **decisions about how to compute**,
and a wrong one is as damaging as a wrong rate - so each states its
basis and the test that pins it.

| Convention | What this program does | Basis | How verified |
|---|---|---|---|
| **Monthly compounding** | `(1 + annual)^(1/12) − 1` | Definition of an effective annual rate | Matches a major platform's published worked example and a bank-scheme figure **to ₹0**. See Part 8. |
| **Lot ordering** | First in, first out | **Rule 8AA** of the Income-tax Rules | `test_engine.py` lot-split tests; the ₹597.87 worked example in FEATURES §1.2 |
| **Financial year** | 1 April to 31 March | Income-tax Act | `time_utils.derive_financial_year_int`; asserted where the exemption resets |
| **Exemption scope** | Per taxpayer per year, not per fund | s.112A relief is personal, not per scheme | Two identical funds exiting together consume **one** allowance |
| **Cess order** | On tax **plus** surcharge | Finance Act charging order | `test_surcharge_is_charged_before_cess` |
| **Loss set-off order** | Losses applied **before** the exemption | Sections 74 and 74(1)(b) | Order asserted in the set-off tests; the reverse would overstate the shelter |
| **Expense accrual** | `(1+R)^(1/12) · (1−e)^(1/12)` monthly | How a fund actually deducts TER from NAV | Both models implemented; the ₹44,280 gap over 15 years on a 1% TER is a real output |
| **Rebalancing tax funding** | `PORTFOLIO` or `OUTSIDE`, chosen | Resident equity redemptions carry no TDS | Both paths tested; "ignore tax" was removed because the tax is never free |
| **Internal transfers** | Raise cost basis, never principal | Moving your own money is not a contribution | Asserted so XIRR cannot be inflated by rebalancing |
| **XIRR** | Brackets the root, then bisects, to 1e-7 | Standard money-weighted return definition | **37.336%**, matching the spreadsheet vendor's own documented example to 5 dp. Bisection is used rather than Newton because it **cannot diverge** on the irregular sign patterns a real plan produces. |

### 7.1 Loss carry-forward

**Eight years**, `constants.py` `LOSS_CARRY_FORWARD_YEARS_INT`.

**Basis.** Section 74 permits carry-forward of capital losses for
eight assessment years following the year the loss arose.

**Verified.** A loss booked in FY 2026 can shelter gains up to
FY 2034 and not beyond; the boundary is asserted on both sides. The
earlier version carried losses **forever**, which let a year-one
loss shelter a year-thirty gain and silently understated tax.

### 7.2 Grandfathering

**31 January 2018**, `GRANDFATHER_VALUATION_YEAR_INT` and
`..._MONTH_INT`.

**Basis.** The proviso to s.112A: for units acquired before
1 February 2018, cost is the higher of actual cost and the lower of
the 31 January 2018 fair market value and the sale value.

**Verified.** Hand calculation, exact to the paisa.

> ⚠️ **A limit worth stating plainly.** The FMV used is this
> program's own **simulated** value at that date, not a real quoted
> NAV. The *arithmetic* of grandfathering is right; the *input* is
> synthetic. No source can fix this - it would need real historical
> NAV data, which this package deliberately does not carry.

---

## Part 8 - The timeline's translation rules

These are **derivations, not citations.** No statute says how "I
retire" should become engine settings. Each rule below is a reading
of what a person means, and each is stated so you can disagree with
the reading rather than the arithmetic.

| Rule | The reading | Why |
|---|---|---|
| **One-off investment** compounds from its own month | A bonus received in year eight has eight fewer years to grow | Until 5 Aug 2026 every lump sum was invested in **month zero**, which silently overstated the corpus. Now dated; asserted against the closed form `(1+m)^-N` at six different months. |
| **Retire** = pause + withdraw | Stopping contributions and starting an income in the same month | Nobody thinks of retiring as two settings |
| **Pause with no resume** runs to the horizon | "I stopped and never restarted" | The window has to close somewhere, and the horizon is the only honest choice |
| **Resume with no pause** is ignored | A stray event, not an instruction | Events can be added and deleted in any order |
| **Change the amount** resets the step-up clock | "My SIP is now ₹30,000" means ₹30,000 | Not ₹30,000 × every step-up since inception |
| **Stop withdrawing** = withdrawal-scoped pause | An income that ends | Reuses a mechanism already tested, rather than adding one |
| **Second step-up ignored** | The engine models one escalation rule | Stated in the interface rather than silently dropped |
| **Two salary events in one year** | The later one wins | A financial year has one total income |
| **Rebalance event** fires in its month only | A trade you asked for by hand, not a rule with an interval | A calendar rule would fire in months you never chose |
| **Note to self** changes nothing | A marker on the story, not the money | Asserted by a test: the plan values identically with and without |
| **Relieved surcharge applied to gains** | Apportionment | Relief is a property of *total* income; charging it to the capital-gains slice is a choice, not a rule the Act states |

---

## Part 9 - Values with no published source

These are **not statutory**. Each is a modelling choice or a
plausible default, and none is asserted as truth anywhere.

| Value | What it is | How it was arrived at |
|---|---|---|
| 12% assumed return | Default equity return | A conventional planning figure, **not a forecast**. Every result is explicitly *your assumption*; nothing here predicts markets. |
| 7% debt return | Default debt return | Same - a plausible magnitude used as an input only. |
| 6% inflation | Default deflation rate | A long-run Indian CPI order of magnitude, used to restate figures in today's rupees. Tagged `G5-PLAUSIBILITY`: used as an input, never asserted. |
| 0.5% TER | Default fund fee | Typical active equity fund expense ratio; the user is expected to type their own. |
| 1% / 12 months exit load | Default early-redemption penalty | The most common structure across Indian AMCs. A fund-level input, not a rule. |
| 18% volatility | Default for the risk panel | A plausible equity volatility, used only to generate illustrative paths. |
| 0.25% debt TER | Default debt fund fee | Typical for a short-duration debt fund; a fund-level input the user overrides. |
| 30% slab rate | Debt fund taxation default | The **top** slab, chosen deliberately: it is the conservative assumption. A reader on a lower slab will find the tool overstates their debt tax, which is the safer direction to be wrong in. |
| 100% equity default | Opening portfolio split | Not a recommendation. It is the simplest starting point, and it is why a rebalance event does nothing until the split is changed. |
| ₹1,00,000 reference amount | Used only to price a rate in the interface | An amount most readers can reason about. It illustrates a percentage; it is never part of any calculation. |
| ₹25,000 default SIP, 20-year horizon | Opening plan on the timeline | So the rail is not empty on first load. Every figure is editable and none is asserted anywhere. |
| Colour palette | Chart colours | Not sourced - **derived by computation**. An OKLab/WCAG validator searched 27 candidates; six colours in light mode and five in dark is a proven ceiling, not a taste decision. |
| Gantt lane order | Contributions, step-up, withdrawals, salary, inflation, events | **Derived, not sourced.** Ordered money-in, then money-out, then context - so the lanes a reader controls sit above the ones they only observe. |
| ₹51,95,896 | Relief window close | Derived above from the slabs, *and* independently corroborated by published commentary. |

---

## Part 10 - Compounding convention

**The disagreement worth knowing about.** Given a 12% annual return,
this program uses the effective monthly rate:

```
monthly rate = (1 + 0.12)^(1/12) − 1 = 0.9489%
```

Two widely-used calculators use `0.12 ÷ 12 = 1%`, which compounds
to **12.68%** a year when you asked for 12%.

**Verified against:** a major platform's published worked example and
a bank-scheme calculator - **both matched to ₹0**. The other three
differ because their convention is mathematically incorrect, not
because our arithmetic is.

*Other products are not named anywhere in this project. The check
stands on its own: apply the formula above and compare.*

This is the one place where matching fewer published sources is the
correct outcome, and it is why the scorecard reports "2 of 5" rather
than treating it as a failure.

---

## Part 11 - The risk engine

| Element | What it is | Source, or how derived |
|---|---|---|
| **Monte Carlo draws** | Lognormal monthly returns from your mean and volatility | Standard geometric Brownian motion discretised monthly. **Derived**, not cited - and the shape is an assumption, not a fact about markets. |
| **Bootstrap** | Resamples **blocks** of months from a history you supply | Block bootstrap, chosen so serial correlation within a block survives resampling - drawing single months independently would destroy exactly the sequence risk this is meant to measure. A short NIFTY 100 history **does** ship inside the package, so this runs out of the box - but three years is 36 observations with no crash in them, and a bootstrap cannot resample a disaster its source never saw. Treat the downside tail it produces as too kind, and supply a longer series when the answer matters. |
| **Seeding** | Per-trial seed from a master seed | So a reported percentile can be reproduced exactly. Verified: the same seed gives bit-identical output. |
| **Percentile bands** | Empirical quantiles across trials | No distributional assumption beyond the draws themselves. |

> ⚠️ **The flaw this section must state.** Each fund draws an
> **independent** path. Real assets correlate, and correlations rise
> in a crash - so a mixed portfolio looks *safer here than it is*.
> This is the single largest known overstatement in the tool. It is
> listed in the scorecard as the highest-value fix outstanding.

---

## Part 11B - Asset classes other than funds

**Read this first.** The interface lets a reader name any asset -
gold, land, a deposit, a business - and offers a starting tax
treatment for each. Two of those treatments are verified in this
document. **The rest are not**, and the interface marks them.

| Treatment | Verified? | Basis |
|---|---|---|
| Equity-Oriented (Default) | **Yes** | ss.111A / 112A - Part 1 of this document |
| Debt (post Apr 1, 2023) | **Yes** | s.50AA - Part 1 of this document |
| Listed shares | **Yes** | Same sections as an equity fund, so it inherits the same verified rates |
| Gold or similar asset | **No** | 12.5% above 24 months, short-term at slab. A plausible reading of the post-2024 position for non-financial assets, *not checked against the Act* the way the rows above were |
| Property or land | **No** | As gold. Ignores indexation history, exemptions on reinvestment, and every stamp-duty or registration cost |
| Deposit or interest income | **No** | Slab throughout. Ignores the distinction between accrual and receipt |

**Why they ship unverified rather than not at all.** A reader
modelling land otherwise has to look up four numbers before seeing
a single curve. A flagged starting point is more useful than a
blank row, and less dangerous than an unflagged one.

**What would change this.** Sourcing each unverified row the way
Part 1 sources equity - by section, with a date and a published
commentary - and flipping `is_sourced_bool` in
`asset_presets.py`. `test_asset_presets.py` asserts exactly which
treatments claim to be sourced, so the flag cannot be flipped
without someone noticing.

**Beyond the rates.** Every asset compounds at a steady monthly
rate. That is a fair way to ask "what if gold returns 8%"; it is
not how land or a single share behaves, and the asset editor says
so where a reader adds one.

---

## Part 12 - Other countries' capital gains rates

**Read this first.** Choosing a country here fills in **opening
rates you can then edit**. It does *not* teach this program that
country's tax code. Exactly one regime - India - is modelled beyond
its headline rates, and a test asserts that claim never quietly
broadens.

Surcharge, cess, marginal relief and grandfathering are Indian
mechanisms. They are **switched off** for every other regime rather
than being applied where they do not exist.

| Country | Rate | Allowance | Checked |
|---|---|---|---|
| **India** | 20% short-term, 12.5% long-term above 12 months | ₹1,25,000 | ss.111A / 112A as amended by the Finance (No. 2) Act 2024, for transfers on or after 23 July 2024 |
| **Japan** | **20.315% flat**, whatever the holding period | none | 15.315% national *including the reconstruction surtax* + 5% local inhabitant tax, on listed shares |
| **United Kingdom** | 18% within the basic-rate band, **24%** above it | **£3,000** | 2026/27 annual exempt amount and rates |
| **United States** | 15% long-term (middle bracket), ordinary rates short-term | none | Long-term bracketed 0% / 15% / 20% by income |
| **Singapore** | **0%** | - | No general capital gains tax regime |
| **United Arab Emirates** | **0%** | - | No personal income or capital gains tax |

**Verified 6 August 2026** against published tax commentary.

### What each one leaves out - stated, not hidden

| Country | Not modelled |
|---|---|
| **Japan** | NISA shelters, loss carry-forward, unlisted shares |
| **United Kingdom** | The 18% basic-rate band (the higher rate is used, which is the conservative reading), ISAs, Business Asset Disposal Relief |
| **United States** | The 0% and 20% brackets, the 3.8% net investment income tax, **every state tax** |
| **Singapore** | Gains from trading *as a business*, which can be taxed as income |
| **United Arab Emirates** | Nothing material for a personal investor; corporate tax does not reach personal investment gains |

**Why the UK and US defaults lean high.** Both are progressive, and
this engine takes one rate per fund. Where a choice had to be made,
the higher bracket was chosen - a plan that overstates its tax is
safer to be wrong about than one that understates it. Both are
editable, and the interface says to edit them.

---

## Part 13 - Currencies

A currency carries more than a symbol: it decides digit grouping,
what large numbers are *called*, and whether a minor unit exists.

| Code | Symbol | Grouping | Decimals shown | Counts in |
|---|---|---|---|---|
| INR | ₹ | 12,34,567 | 0 | thousand, lakh, crore |
| USD | $ | 1,234,567 | 2 | thousand, million, billion |
| EUR | € | 1,234,567 | 2 | thousand, million, billion |
| GBP | £ | 1,234,567 | 2 | thousand, million, billion |
| JPY | ¥ (円) | 1,234,567 | **0** | thousand, million, billion |
| CNY | ¥ (元) | 1,234,567 | 2 | thousand, million, billion |
| AUD / CAD / SGD | A$ / C$ / S$ | 1,234,567 | 2 | thousand, million, billion |
| CHF | Fr | 1,234,567 | 2 | thousand, million, billion |
| AED | د.إ | 1,234,567 | 2 | thousand, million, billion |

**Codes and symbols are ISO 4217.**

**Two decisions worth stating.** Yen shows **no decimals** because
there are no sen in circulation - writing ¥1,234.56 invents a coin.
Rupees show none either, but for a different reason: paise exist,
and no figure in this program has ever displayed them, because a
thirty-year corpus quoted to the paisa is false precision.

**Magnitude names follow the currency, not the number.** Describing
a dollar figure as "12.35 lakh" would be worse than leaving it
unnamed, so the naming table is a property of the currency and a
test asserts no currency ever borrows another's words.

**Changing currency converts nothing.** There are no exchange rates
in this program. It changes how figures are *written*.

**Inflation defaults travel with the currency** - 6% for the rupee,
1% for the yen, 2-2.5% elsewhere. These are **opening assumptions of
the right order of magnitude, not forecasts and not sourced from any
single publication.** Every one is overwritable, and an inflation
event on the rail overrides it from its own month onward.

---

## Part 14 - What is deliberately absent

Stated so their absence is a decision on the record, not an
oversight a reader has to discover.

| Not modelled | Why |
|---|---|
| Live NAV, TER or scheme data | No AMFI feed. You type the numbers. |
| Correlation between funds | See Part 11. |
| Marginal relief interaction with the 15% cap | Relief is applied, then the cap. The Act does not spell out the ordering for this combination. |
| Senior-citizen exemption | Moves relief by at most a few hundred rupees; see Part 4. |
| Dividend / IDCW plans | Growth plan assumed throughout. |
| Daily NAV mechanics | Monthly grid; no T+1 settlement, no unit rounding. |
| Securities lending, TDS for non-residents | Out of scope: this models a resident individual. |
| Your total income tax bill | Slabs exist here **only** to compute marginal relief. |
| Currency conversion | No exchange rates. Changing currency changes how figures are written, nothing more. |
| Non-Indian tax machinery | Other regimes supply opening rates only; see Part 12. |

---

## Sources consulted

Statutory rates were checked against published Indian tax
commentary on 4-5 August 2026:

- Published slab tables from a major Indian tax-filing portal,
  FY 2025-26 and FY 2026-27
- Published slab tables from an insurer's tax guide, FY 2026-27
  (AY 2027-28)
- Published commentary on s.111A / s.112A as amended by the
  Finance (No. 2) Act 2024, effective 23 July 2024
- Published surcharge and marginal relief commentary carrying the
  ₹51,95,896 worked example

**A caution about secondary sources.** These are commentary, not the
bare Act. They agree with one another and with the hand calculations
above, which is why they are relied on - but for a real filing,
read the Act.
