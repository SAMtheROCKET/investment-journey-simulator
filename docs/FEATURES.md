# What this program does - in plain terms

Every feature below is explained the same way:

> **What it means** → **A real example** → **When you'd use it** → **Why it exists**

All the rupee figures on this page are **real outputs of this code**,
not illustrations. Unless a section says otherwise the baseline plan
is: **₹10,000 a month, 12% a year, 15 years, no costs** → **₹47,59,314**.

Status as of 20 August 2026: **2,508 passing · 4 intentionally
skipped · 93% coverage · ruff, mypy and house style all clean.** Every statutory number is sourced in
[SOURCES.md](SOURCES.md).

---

## Part 1 - The core engine

### 1.1 Monthly compounding on the correct convention

**What it means.** If you type "12% a year", the program works out
what that means for one month and applies it twelve times. It uses
`(1 + 12%)^(1/12) − 1 = 0.9489%` a month - *not* `12 ÷ 12 = 1%`.

**Example.** ₹1,000/month for 12 months at 12%:

| | |
|---|---|
| This program | **₹12,766** |
| A major platform's published worked example | **₹12,766** ✅ |
| Using the wrong `12÷12` shortcut | ₹12,809 |

**When you'd use it.** Always. It's the foundation everything else
sits on.

**Why it exists - and why it matters.** Compounding 1% a month for a
year gives **12.68%**, not the 12% you asked for. Some calculators
make this error and it compounds:

| Plan | This program | A widely-used calculator | Gap |
|---|---|---|---|
| ₹5,000/m, 12%, 40 yrs | ₹4.90 crore | ₹5.94 crore | **−17.6%** |

That platform's own documentation states the rule this program
follows: *"A common mistake is to simply divide the annual return by
12...for an annual return of 12%, the effective monthly return comes to
about 0.95%, not 1%."* We match its figures, and a bank scheme's,
**to the rupee**. Where we differ from two other widely-used
calculators, the difference is their convention, not our
arithmetic.

### 1.2 FIFO lot book

**What it means.** Every monthly instalment is remembered as its own
parcel ("lot") with its own purchase date. When you sell, the oldest
parcel goes first - exactly as Indian tax law requires (Rule 8AA).

**Example.** On a 15-year plan the last 13 instalments have been held
twelve months or less. At exit they are **short-term** (20%), while
everything older is **long-term** (12.5%). On the baseline plan that
lot-level split adds **₹597.87** of tax that a naive "one big gain"
calculation misses - ₹3,85,308.69 actual against ₹3,84,710.82 naive.

**When you'd use it.** Any time tax is switched on.

**Why it exists.** Treating your whole portfolio as a single blob gets
the tax wrong. Real tax is computed parcel by parcel.

### 1.3 Expense ratio (TER), two models

**What it means.** The fee the fund house charges you every year.

**Example.** Baseline plan with a **1% TER**:

| Model | Result | Cost of the fee |
|---|---|---|
| No fee | ₹47,59,314 | - |
| Simple subtraction (12% − 1% = 11%) | ₹43,70,720 | ₹3,88,594 |
| Continuous accrual (how funds really work) | ₹43,26,440 | **₹4,32,874** |

**When you'd use it.** Comparing a direct plan (~0.2%) against a
regular plan (~1.5%), or an index fund against an active fund.

**Why two models exist.** Subtracting the fee from the return is the
quick approximation everyone uses. Real funds deduct it daily from
the NAV, which costs you **₹44,280 more** over 15 years on a 1% fee.
Having both lets you see the size of that shortcut.

### 1.4 Multi-fund portfolios

**What it means.** Model several funds at once, each with its own
amount, return, fee, tax treatment and start date.

**Example.** ₹15,000 into a Nifty index fund + ₹5,000 into a debt
fund, 15 years → **₹85,27,389** total, and you can see which fund
carried it.

**When you'd use it.** Any realistic plan. Almost nobody holds one
fund.

**Why it exists.** Every mainstream calculator models exactly one
fund. You cannot see equity/debt mix, drift or rebalancing with one.

---

## Part 2 - Real-life plan shapes

### 2.1 Step-up SIP

**What it means.** Increase your instalment every year, because your
salary grows.

**Example.** Baseline plan with a **10% yearly step-up**:

| | Invested | Final value |
|---|---|---|
| Flat ₹10,000/m | ₹18,00,000 | ₹47,59,314 |
| 10% step-up | ₹38,12,698 | **₹82,74,718 (+74%)** |

**When you'd use it.** You're salaried and expect raises.

**Why it exists.** A flat SIP quietly assumes you never get a raise
in 15 years. Four modes are supported (off, global, per-fund, both),
plus fixed-rupee increments and custom intervals.

### 2.2 Pauses and breaks

**What it means.** Stop contributing for a stretch - a job loss, a
house purchase, a sabbatical.

**Example.** Baseline plan with a **2-year break in 2029-30**:
₹39,18,717 instead of ₹47,59,314. **The break costs ₹8,40,597.**

**When you'd use it.** Stress-testing: *"what if I have to stop for
two years?"*

**Why it exists.** Life happens, and the cost of a pause is much
larger than the instalments you skipped - because those instalments
lose their compounding runway too. Skipped: ₹2,40,000. Cost:
₹8,40,597.

### 2.3 Systematic withdrawal (SWP) and depletion

**What it means.** Take a monthly income out of your portfolio, and find
out whether it lasts.

**Example.** ₹1 crore invested and earning 10%, over 25 years:

| Monthly withdrawal | Outcome |
|---|---|
| ₹60,000 | Survives; **₹3.43 crore left** |
| ₹1,00,000 | **Runs out in October 2042**; ₹98.98 lakh of withdrawals unpaid |

**When you'd use it.** Retirement planning. This is the single most
consequential number in personal finance.

**Why it exists.** "How much can I safely withdraw?" has no formula
once tax and sequence are involved. The program names the **exact
month** the money runs out.

### 2.4 Rebalancing

**What it means.** Periodically sell what's grown too big and buy
what's lagged, to return to your target mix.

**Example.** 60% equity (14%) / 40% debt (7%), 15 years:

| | Final value | Final mix | Tax paid | Trades |
|---|---|---|---|---|
| No rebalancing | ₹87,80,709 | 64% / 36% | ₹0 | 0 |
| Annual rebalancing | ₹87,86,850 | **60% / 40%** | ₹51,801 | 15 |

**When you'd use it.** Deciding whether rebalancing is worth its tax
bill.

**Why it exists.** Rebalancing has an obvious cost (tax + charges)
and a non-obvious benefit (risk control). Three triggers are
supported: calendar, drift band, or both.

> ⚠️ **Read this honestly.** In a *deterministic* run rebalancing
> looks like it barely pays. That's because a fixed-return world has
> no volatility to harvest - so the model shows only the cost, never
> the benefit. **Use the stochastic mode (§5.3) to judge
> rebalancing.** This is a limitation of constant-return maths, not
> a finding about rebalancing.

---

## Part 3 - Tax, done properly

This is where the program is genuinely ahead of the market. Mainstream
Indian SIP calculators **skip tax entirely**.

### 3.1 Capital gains - the basics

**What it means.** Equity held **more than** 12 months is long-term
(12.5%); 12 months or less is short-term (20%); debt funds bought
after 1 April 2023 are always short-term at your slab rate.

> **The boundary is strict.** Section 2(42A) defines a short-term
> asset as one held for *not more than* twelve months, so a lot sold
> exactly a year after it was bought is **short-term**. This program
> got that wrong until 5 August 2026 - it treated exactly twelve
> months as long-term, understating the tax by 7.5% of the gain on
> those lots. Fixed, and now asserted on both sides of the boundary.

**Example.** Baseline plan, exit tax with a 4% cess and no
exemption: gain ₹29,59,313.99 → tax **₹3,85,308.69**, computed lot by
lot. Applying the ₹1,25,000 exemption instead gives **₹3,69,058.69**.

**Why it exists.** A projection that ignores tax overstates what you
can actually spend by lakhs.

### 3.2 The ₹1,25,000 exemption - per taxpayer, not per fund

**What it means.** You get **one** ₹1.25 lakh long-term exemption a
year, across all your equity funds - not one per fund.

**Example.** Two identical equity funds exiting together:

| Setting | Exit tax |
|---|---|
| Per-fund (two allowances) | ₹7,09,548 |
| **Per taxpayer (one allowance - the law)** | **₹7,25,173** |

The gap is **₹15,625**, which is exactly ₹1,25,000 × 12.5%.

**When you'd use it.** Always leave it on "per taxpayer". The
per-fund setting exists only to show you what the wrong assumption
costs.

**Why it exists.** *This was a real bug found on 5 Aug 2026.* Each
fund's exit estimate used its own private copy of the allowance
ledger, so a two-fund plan claimed ₹1.25 lakh twice and understated
your tax. Now fixed, with a regression test.

### 3.3 Grandfathering (31 January 2018)

**What it means.** For units bought **before 1 February 2018**, you
don't pay tax on the gain that accrued before that date. The cost is
deemed to be the *higher of* what you actually paid and the *lower
of* the 31 Jan 2018 value and your sale price.

**Example.** ₹1,00,000 invested Jan 2015 at 12%, sold after 11 years
for ₹3,47,855. Value on 31 Jan 2018 was ₹1,41,826:

| | Tax |
|---|---|
| Without grandfathering | ₹30,982 |
| **With grandfathering** | **₹25,754** |

**When you'd use it.** Only if you hold pre-2018 units. Post-2018
plans are completely unaffected (tested).

**Why it exists.** It's the law, and it saves real money on old
holdings.

> ⚠️ **Caveat.** Real grandfathering uses the *actual quoted NAV* on
> 31 Jan 2018. This program has no NAV feed, so it uses your plan's
> *simulated* value on that date. That's exact only to the extent
> your assumed return actually happened.

### 3.4 Loss set-off and the 8-year expiry

**What it means.** A loss you book shelters a later gain from tax.
But it only lasts **8 assessment years**, then it lapses.

**Example.** A loss booked in FY 2026 can shelter gains up to
FY 2034. In FY 2035 it is worthless.

**When you'd use it.** Long horizons, or tax-loss harvesting.

**Why it exists.** The earlier version carried losses **forever**,
which let a loss from year 1 shelter a gain in year 30 - silently
understating your tax. Now capped, oldest loss spent first (the
loss closest to expiry, which wastes the least shelter).

### 3.5 Surcharge slabs

**What it means.** High earners pay a surcharge *on top of* their
tax, scaled to total income.

| Total income | New regime | Old regime |
|---|---|---|
| Up to ₹50 lakh | 0% | 0% |
| ₹50 lakh - ₹1 crore | 10% | 10% |
| ₹1 crore - ₹2 crore | 15% | 15% |
| Above ₹2 crore | **25% (capped)** | 25% |
| Above ₹5 crore | 25% | **37%** |

**Example.** On ₹3 crore income the slab is 25% - but surcharge on
equity gains is **capped at 15%** by law, so equity gains are taxed
at 12.5% × 1.15, not × 1.25.

**When you'd use it.** Income above ₹50 lakh.

**Why it exists.** Previously you typed one flat rate and had to know
it yourself. Now you enter your income and the correct rate is
derived.

### 3.5a Marginal relief on the surcharge

**What it means.** Earning one rupee more must never cost more than
one rupee. Without relief, crossing ₹50 lakh by ₹1 would add over a
lakh of surcharge in a single step. The law softens each boundary:
the surcharge is reduced until the extra tax no longer exceeds the
extra income.

**Example (old regime).** Tax at exactly ₹50 lakh is ₹13,12,500 and
the surcharge is nil. Just above, the 10% band applies - so relief
holds the surcharge down until

```
0.10 × 13,12,500 ÷ 0.67 = ₹1,95,896
```

of extra income has been earned. The window closes at **₹51,95,896**,
the figure published in tax commentary - and the test suite asserts
exactly that number.

**How it shows up here.** The band rate is replaced by an *effective*
rate: 0% at the boundary, rising smoothly to the full 10% by the top
of the window. Every threshold gets this - ₹50 lakh, ₹1 crore, ₹2
crore, and ₹5 crore on the old regime - and at the higher ones the
comparison correctly carries the surcharge of the band below.

**When it applies.** Only in slab mode. A manually typed rate is used
exactly as typed, because no income is known to compute relief from.

> ⚠️ **Caveat.** Relief is a property of *total* income. Charging the
> relieved rate to the capital gains slice is an apportionment, not a
> rule the Act states. Deductions, the §87A rebate and the senior
> citizen exemption are not modelled - the first two cannot matter at
> these incomes, the third moves the answer by a few hundred rupees.

### 3.6 Exit load and STT

**What it means.** Exit load is the fund house's early-redemption
penalty (typically 1% within 12 months). STT is a 0.001% government
levy on every equity fund redemption.

**Example.** A 15-year plan exiting fully pays **₹1,815** - mostly
exit load on the last year's instalments.

**Where it comes out.** The fund house deducts both at source, so
they are netted out of what reaches you: sell ₹1,00,000 of units
inside the load window and ₹99,000 arrives. The units still leave
the portfolio at their full value, so the corpus is the same either
way - it is the payout that is smaller. Capital gains tax is
different: it is reported but never deducted here, because a
resident settles it at filing time out of their own pocket rather
than at redemption.

**Why it exists.** Small, but real, and rarely shown.

---

## Part 4 - Understanding your results

### 4.1 Inflation-adjusted (real) values

**What it means.** ₹47.6 lakh in 15 years does not buy what ₹47.6
lakh buys today.

**Example.** Baseline plan at 6% inflation: **₹47,59,314 in 2041 =
₹19,85,895 in today's money.**

**When you'd use it.** Always look at this before feeling good about
a projection.

**Why it exists - and one subtlety.** The program deflates **each
instalment separately** by its own date, not the total by the final
factor. The shortcut would misstate your real invested principal.

### 4.2 XIRR and post-tax XIRR

**What it means.** The true annual return on your actual dated cash
flows - the number printed on your CAS or broker statement.

**Example.** ₹15,000/m, 12% gross, 0.20% TER, 15 years:

| | |
|---|---|
| Gross value | ₹70,18,074 |
| Tax + charges on exit | ₹6,00,498 |
| Spendable | ₹64,17,576 |
| XIRR before tax | 11.79% |
| **XIRR after tax** | **10.74%** |

**When you'd use it.** To reconcile this tool against your real
portfolio, and to see what tax actually costs you in return terms -
here, **1.05 percentage points a year, forever.**

**Why it exists.** Once step-ups, pauses or withdrawals are on, the
"12%" you typed is an input assumption, not your realised return.
XIRR is the only correct measure. **Post-tax XIRR is published by
essentially no Indian retail calculator.**

*Verification:* reproduces the spreadsheet vendor's own documented
XIRR example (**37.336%**) to five decimals.

### 4.3 Goal seek - the question backwards

**What it means.** Instead of "what will I get?", ask "what do I
need?".

**Example.** Target ₹2 crore in 15 years at 12%:

| Question | Answer |
|---|---|
| What SIP reaches ₹2cr? | **₹42,023/month** |
| What SIP leaves ₹2cr *after tax*? | **₹46,835/month** |
| How long at ₹10,000/m? | **27 years** |
| What return would I need at ₹10,000/m in 15 years? | +16.3 points → **28.3%** |

**When you'd use it.** Every actual planning conversation.

**Why it exists.** Nobody wakes up asking "what is ₹10,000 a month
worth?" They ask "what do I need for my child's education?" That last
row is also a useful reality check: 28.3% is not a plan, it's a
diagnosis that the goal needs more money or more time.

### 4.4 Validation panel

**What it means.** Seven internal accounting checks that must always
hold - wealth identity, principal excludes internal transfers, tax
attribution, exact rebalance targets, no rebalancing when disabled,
withdrawal feasibility, no negative values.

**Why it exists.** So you can confirm the engine's own books balance
before trusting any number on the page.

---

## Part 5 - Risk (the part that changes conclusions)

### 5.1 Drawdown chart

**What it means.** How far your portfolio fell below its previous
peak, month by month.

### 5.2 Return paths

**What it means.** Instead of the same return every month, the
program can simulate a *path* - good years and bad years in a
realistic order. Two methods:

- **Lognormal** - draw each month from a bell curve around your
  expected return and volatility.
- **Block bootstrap** - resample *chunks* of real history, keeping
  crashes clustered the way they really occur.

### 5.3 Sequence-of-returns risk - why this matters most

**What it means.** Two plans with *identical* average returns can end
very differently, depending on **when** the bad years land.

**Example.** Baseline plan, 300 simulated paths at 18% volatility
(realistic for Indian equity):

| Outcome | Spendable value |
|---|---|
| Bad case (5th percentile) | **₹32,26,418** |
| Middle (50th) | ₹65,21,380 |
| Good case (95th) | ₹1,35,97,451 |
| **Chance of missing the "guaranteed" deterministic figure** | **48%** |

**When you'd use it.** Before trusting *any* single-number
projection, and always when judging rebalancing.

**Why it exists - this is the headline.** The deterministic answer,
₹64.2 lakh, is usually presented as *the* answer. It is
actually close to a **coin flip**, and the bad case is **half** of
it. That is the single most important thing this program can tell you
and no mainstream Indian calculator can.

*Verification:* a zero-volatility path reproduces the deterministic
answer exactly, and a test proves the same returns in a different
order produce a different result.

---

## Part 5B - Backtesting against real market data

This is the only part of the program that is **not a projection**.
It replays a plan over returns the NIFTY 100 actually delivered.

### 5B.1 What actually happened

**What it means.** Instead of assuming 12%, the engine is driven by
the real month-end index levels bundled inside the package.

**Example.** ₹10,000/month into the NIFTY 100, **Aug 2023 → Aug 2026**
(the real 36 months):

| | |
|---|---|
| Invested | ₹3,60,000 |
| Value | ₹3,86,326 |
| **XIRR the investor earned** | **4.63%** |
| The index's own CAGR over the same window | **10.23%** |
| What a 12% assumption would have predicted | ₹4,29,543 (**+10.1% too high**) |

**Why the SIP earned less than half the index.** The index rose
**+40% in the first 13 months**, then fell **−4.4% over the next 23**.
A SIP holds its smallest balance early and its largest balance late,
so most of the money experienced the weak stretch and only a little
caught the surge. **That is sequence-of-returns risk, measured - not
simulated.**

**Verification.** The engine's replay matches an independent
unit-buying calculation (buy units at each month-end close, value at
the final close, no engine code involved) to **₹0.00**.

### 5B.2 Rolling backtest - how much did the start date matter?

**What it means.** Run the *same* plan starting in every possible
month, and compare. The only difference between the windows is when
you began.

**Example.** Same ₹10,000/month plan, every viable start month:

| Horizon | Windows | Best start | Median | Worst start | **Spread** |
|---|---|---|---|---|---|
| 1 year | 25 | +38.64% (Aug 2023) | +2.94% | −19.09% (Mar 2025) | **57.7 pts** |
| 2 years | 13 | +9.83% (Oct 2023) | +3.77% | −8.50% (Mar 2024) | **18.3 pts** |

**When you'd use it.** Before concluding your fund was good or bad.
Much of what looks like skill or failure over a short window is
just the start date.

**Why it exists.** A single backtest tells you what happened once.
The spread tells you how much of that was luck.

### 5B.3 Real history feeding the risk simulation

The Risk panel now offers **"Real index history (resampled)"** as
well as the bell curve. Choosing it block-bootstraps the actual
monthly returns, so simulated paths inherit real momentum and
clustering instead of a smooth bell curve.

> ⚠️ **The honest limits of this data, shown in the app itself.**
> The bundled history is **36 monthly observations**, which is thin
> for resampling. Its worst month is **−11.7%**; March 2020 was near
> **−23%**. **A bootstrap cannot resample a disaster its source never
> saw**, so the downside it shows is kinder than history allows. The
> app prints this warning next to the source picker rather than
> letting you assume otherwise.

---

## Part 5C - The timeline interface

The **Guided Journey** screen of the portal.
The classic dashboard is untouched.

**What it means.** Instead of filling in a form, you describe your
plan as *events on a horizontal timeline*: start investing, get a
raise, pause for a wedding, buy a car, retire.

**Thirteen event types**, each explaining itself on hover, offered
in five groups: *money in* (start investing, change the amount,
yearly step-up, one-off investment), *money out* (start withdrawing,
stop withdrawing, retire), *breaks* (pause, resume), *portfolio*
(rebalance back to target), and *the world around the plan* (salary
starts or changes, inflation changes, note to self).

### 5C.1 The rail - planning by clicking, not by filling in

The page opens on **Plan**: a plain panel carrying one horizontal
rail and nothing else. No value curve, no rupee axis - only time.

**Choosing an event.** The event types sit above the rail as chips.
**Hover any chip and it explains what that event does** before you
commit to it. Click one to arm it.

**Placing an event.** With a chip armed, **click the rail** at the
month it happens. The event lands there as a dot. Placement snaps to
a month because that is the grid the engine simulates, so a click
can never land somewhere the simulation does not have.

**Many events, one month.** Several things can happen in the same
month of a life - a raise, a bonus and a step-up all in one January
- so dots **stack upward** rather than hiding one another.

**Events that last.** A pause is not a moment, it is a window. Those
are drawn as **bars beneath the rail**, running from the pause to
the resume that closes it - or to the horizon, if none does.

**Reading an event.** Hover a dot for its type, date, amount and
what it does. Clicking a dot inspects it rather than stacking a new
event on top of it.

### 5C.2 The live Gantt - what is running, and when

**Generated as you type.** Beneath the rail, a second chart redraws
itself on every keystroke - no button, no refresh. It answers the
question the rail cannot: *what is in force right now?* A plan has
several things running at once.

| Lane | Shows |
|---|---|
| Contributions | Each stretch of one instalment amount, **broken wherever a pause interrupts it** |
| Yearly step-up | From the month escalation starts to the horizon |
| Withdrawals | From the month income starts until it stops |
| Salary | One band per income period |
| Inflation | One band per rate |
| One-off events | Lump sums, rebalances and notes as points |

**The visual grammar is three states.** **Solid** means money is
moving. **Hatched** means that activity is paused - *drawn* rather
than left blank, because a gap you cannot see is a gap you cannot
reason about. **Faint** is context: salary and inflation shape the
answer without being actions you take.

**Why it can be trusted.** Every bar is read from the **compiled
settings**, not from the raw events. The chart shows what the engine
was actually told - so if a lone pause compiles to a window running
to the horizon, the bar runs to the horizon too. A bar and the
value curve can never tell different stories.

Empty lanes are omitted, so the chart grows with the plan rather
than showing rows of nothing.

### 5C.3 Units on every blank, and what the numbers mean

**Every input says what it is measured in** - `₹ a month`,
`₹, one time`, `₹ a year`, `% a year`, `years` - because a rupee
figure means nothing until you know whether it repeats.

**And every input echoes itself back:**

| You type | It says |
|---|---|
| `200000` in a lump sum | ₹2,00,000 - 2.00 lakh |
| `12` as a return | 12.00% a year (0.9489% a month, compounded) - ₹3,000 on ₹25,000 in the first year |
| `20` as a horizon | 240 months - 20.0 years |
| `0.5` as a fee | 0.50% a year on the value - about ₹500 a year for every ₹1,00,000 held |
| `6` as inflation | in ten years ₹1,00,000 buys what ₹55,839 buys today |

**Why this is not decoration.** An extra zero is the easiest mistake
to make and the hardest to spot in a wall of digits. Naming the
magnitude makes it obvious immediately. And quoting the *monthly*
rate a return compounds to is how you can check this tool is using
the right convention - 12% a year is **0.9489% a month**, not 1%.
That single line is the difference documented in §1.1, put where you
are actually typing the number.

### 5C.3a Choose it, or type it - always both

**No control on this page is a slider.** A slider's step size makes
some perfectly reasonable value impossible to express: at a 5% step
you simply cannot say *62.5% equity*. Every number is a box you can
type into, and a test asserts the page contains no sliders at all.

**Quick picks sit above each box** - ₹5,000 / ₹25,000 / ₹1 lakh for
an instalment, 5 / 10 / 15 / 20% for a step-up, 0 / 40 / 60 / 80 /
100% for the equity share. They are **shortcuts, never limits**: a
chip fills the box and then gets out of the way, so `33,333`,
`7.25%` and `62.5%` all type in perfectly well afterwards. A test
clicks a chip, then types a different figure, and asserts the typed
one wins.

**The event menu is searchable** - start typing and the list of
thirteen filters down.

**The clicked month is a field.** A click that lands a month out is
corrected by typing, not by hunting for the right pixel again.

**A note now has words.** *Note to self* existed with no way at all
to type its text; it has one now, and the text shows on the rail and
in the journey report.

### 5C.4 Generate - the same journey, answered

Switch to **Result** and the plan is compiled and run through the
same engine the classic dashboard uses. You get the value curve,
the four cards, both XIRRs - and then the part a settings table can
never show:

**Your journey, decision by decision.** One row per event, in
calendar order, reporting what the portfolio was actually worth when
each decision was taken: what it was worth that month, what you had paid in by
then, the gain, the tax paid so far, and the whole thing restated in
today's purchasing power. The story and the numbers are read from
the same simulated months, so they cannot drift apart.

**How it looks.** Dark gradient surface, translucent cards, light
large type. The value curve *is* the timeline; the principal sits
beneath it as a quiet band, so the gap between them is the gain and
needs no separate series. Events are shaped **and** coloured markers
- a triangle for a step-up, a square for a pause, a star for
retirement - so the chart reads without relying on hue. Drag the
range slider to zoom, or click 5Y / 10Y / All.

**Output.** Four cards - invested, value before tax, tax and
charges, and **yours to spend** - then gain and both XIRRs.

**Why it exists.** Nobody thinks about money as a form. They think
in events. This is the same engine wearing a different interface.

**The claim that makes two interfaces safe.** `timeline.py` is a
*translation layer*, not a second implementation: it compiles events
into the settings the existing engine already understands. A test
proves both front ends value the same plan identically, including
the pause translation - so they can never disagree.

---

## Part 6 - Presentation and output

### 6.1 Accessible chart colours

**What it means.** Colours are checked by computation, not taste.
**Status colours are reserved** (green = gain, red = loss, purple =
rebalancing, amber = tax) and never reused to identify a fund.

**Measured worst cases across all pairs:**

| Mode | Colour-blind separation | Normal-vision separation | Contrast |
|---|---|---|---|
| Light | ΔE 10.3 | ΔE 15.8 | all ≥ 3:1 |
| Dark | ΔE 9.4 | ΔE 16.6 | all ≥ 3:1 |

**Why the limit is six colours.** Exhaustive search over 27 candidate
colours found **no seven-colour set** that passes the same tests. Six
in light mode, five in dark, is a mathematical ceiling - not a style
choice. Every fund also gets a **dash pattern**, so the chart still
reads in black and white or for a colour-blind reader.

**A real bug this fixed.** Plotly assigned colours by *trace order*,
so the same fund could be a different colour in the value chart and
the weight chart. Colour now follows the fund.

### 6.2 Exports and scenarios

Excel workbook, PDF report, and JSON save/load of a whole scenario.

---

## Part 7 - Honest limits

| Not modelled | Why it matters |
|---|---|
| **Actual returns** | Every return is *your assumption*. Nothing here predicts markets. |
| **Correlation between funds** | Each fund draws an independent path, so a mixed portfolio looks safer than it is - real correlations rise in a crash. |
| **Live NAV / TER / scheme data** | No AMFI feed. You type the numbers. |
| **Grandfathering FMV** | Uses the simulated 31 Jan 2018 value, not a real quoted NAV. |
| **Income tax on your salary** | Slabs are used *only* to compute marginal relief. This tool never tells you your total tax bill - only the tax on the plan. |
| **Dividend / IDCW plans** | Growth plan assumed. |
| **Daily NAV mechanics** | Monthly grid, no T+1 settlement or unit rounding. |

---

## Verification summary

| Checked against | Result |
|---|---|
| A major platform's published worked example | **exact to ₹0** |
| A bank-scheme calculator (₹500/m, 20 yrs) | **exact to ₹0** |
| Standard compound interest (lump sum) | **exact to ₹0.00** |
| Spreadsheet XIRR documented example | **37.336%, matches to 5 dp** |
| Equity LTCG hand calculation | **exact to the paisa** |
| Debt slab-rate hand calculation | **exact to ₹0.00** |
| Grandfathering hand calculation | **exact to the paisa** |
| Marginal relief window close (₹51,95,896) | **exact to the rupee** |
| Dated lump sum vs. opening lump sum | **ratio exact to (1.12)^-8** |
| Statutory rates for FY 2026-27 | **all verified 4-5 Aug 2026** |
| Independent notebook cross-check | **all dictionaries reproduce** |
