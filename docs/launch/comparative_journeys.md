# Comparative journeys - the worked numbers

Every figure on this page is **real output of this engine**, not an
illustration. The inputs are stated with each comparison so anyone
who doubts a number can rebuild it and check.

**Shared assumptions throughout**, unless a row says otherwise:

| | |
|---|---|
| Assumed return | 12% a year, gross |
| Expense ratio | 1.0% a year |
| Inflation (for today's-money column) | 6% a year |
| Tax | Indian equity - 12.5% long-term above 12 months, ₹1,25,000 exemption per year |

These are *assumptions*, not forecasts. Nothing here predicts a
market. The point is what these assumptions imply - which, unlike
the market, has an answer.

---

## 1. Starting early versus starting late

Both people pay in **exactly the same money**. Both finish at 45.
Neither steps up, so the totals stay transparent. The only thing
that differs is which decade it went in.

| Journey | Paid in | Ends with | In today's money |
|---|---|---|---|
| Started at 25 - ₹15,000/mo for 20 years | ₹36,00,000 | **₹1,22,34,109** | ₹38,14,653 |
| Started at 35 - ₹30,000/mo for 10 years | ₹36,00,000 | **₹63,72,892** | ₹19,87,098 |

> **Gap: ₹58,61,216.**
> Same money. Same finish date. Same assumed return.
> That figure is what the first ten years were worth - and doubling
> the monthly amount in the second ten does not buy them back.

**Why this one matters.** It isolates timing completely. There is no
"but they invested more" objection available, because they didn't.

---

## 2. One decision at a time

A thirty-year plan: ₹25,000 a month from age 25, stepping up 10% a
year. Then one thing changes in each variant.

| Journey | Paid in | Ends with | In today's money |
|---|---|---|---|
| **A. Never interrupted** | ₹4,93,48,207 | **₹17,28,60,910** | ₹3,00,96,836 |
| B. Paused two years | ₹4,81,20,515 | ₹16,06,20,654 | ₹2,79,65,683 |
| C. Withdrew ₹1 L/mo for nine months in year 10 | ₹4,93,48,207 | ₹16,59,11,835 | ₹2,88,86,931 |
| D. Never stepped up | ₹90,00,000 | ₹6,32,07,052 | ₹1,10,04,988 |

### What each decision cost, and why

**B - paused two years: −₹1,22,40,257**
> Compounding lost to the pause - ₹1,22,40,257
> *unexplained - ₹0*

Only ₹12,27,692 of instalments were skipped. The rest is what that
money would have earned in the twenty-one years that remained.

**C - withdrew in year 10: −₹69,49,075**
> Money taken out early - ₹69,49,075
> *unexplained - ₹0*

₹9 lakh came out. Nearly ₹70 lakh never arrived.

**D - never stepped up: −₹10,96,53,859**
> The raise that never happened - ₹10,96,53,859
> *unexplained - ₹0*

The largest single number on this page, and the one nobody expects.
Not stepping up costs more than pausing and withdrawing put
together, several times over - because a step-up compounds for every
year after it.

**On those zeroes.** The causes sum to the whole gap exactly. That
is not rounding luck; it is the efficiency property of the Shapley
decomposition the attribution uses, and `test_attribution.py`
asserts it rather than assuming it.

---

## 2b. Four decisions at once, which is how life arrives

Section 2 changes one thing at a time, and one thing at a time is
not what happens to anybody. It also makes the attribution look
like arithmetic: with a single cause, every method gives the same
answer, so nothing is being demonstrated.

Here is the messy version. Same person, same fund, same assumed
return, thirty years. The plan they *meant* to follow against the
one they actually followed:

| | Intended | What happened |
|---|---|---|
| Monthly instalment | ₹30,000 throughout | ₹30,000, cut to ₹18,000 from year 4 |
| Yearly step-up | 8% | 3% |
| Career break | none | 3 years off, years 8 to 10 |
| Withdrawals | none | ₹40,000 a month from year 13 |

| | Ends with |
|---|---|
| Intended | **₹14,65,17,397** |
| What happened | **₹2,55,23,470** |
| Gap | **−₹12,09,93,927** |

Four causes now, and they interact: a pause costs more when the
instalment is larger, and a withdrawal costs more when there is
more in the pot to withdraw from. So the obvious method breaks.

### The obvious method, and why it fails

Revert one decision at a time, measure each drop on its own:

```
Contributions never made        −₹6,64,01,811
The raise that never happened   −₹6,01,62,317
Money taken out early           −₹2,39,88,128
Compounding lost to the pause   −₹1,65,72,634
                                ──────────────
Sum of the parts                −₹16,71,24,890
The actual gap                  −₹12,09,93,927
                                ──────────────
Unaccounted for                   ₹4,61,30,963
```

**The parts add up to more than the whole**, by ₹4.61 crore. Every
cause measured alone claims interaction effects that belong to it
jointly with the others, so the same rupees are counted twice.

It is worse than a wrong total. Revert the causes *sequentially*
instead, and the answer depends on the order you picked. Across all
twenty-four orderings of four causes:

| Cause | Smallest answer | Largest answer | Spread |
|---|---|---|---|
| Contributions never made | −₹2,53,21,397 | −₹6,64,74,992 | **₹4,11,53,595** |
| The raise that never happened | −₹2,25,47,773 | −₹6,02,40,712 | **₹3,76,92,939** |
| Compounding lost to the pause | −₹62,37,279 | −₹1,65,81,268 | ₹1,03,43,989 |
| Money taken out early | −₹2,39,88,128 | −₹2,41,50,809 | ₹1,62,680 |

Same two journeys, same question, and the cost of the reduced
instalment lands anywhere between ₹2.5 crore and ₹6.6 crore
depending on nothing but which cause you happened to revert first.
There is no honest way to pick one of those orderings and print it.

### What this program prints instead

```
Contributions never made        −₹4,53,02,707
The raise that never happened   −₹4,08,00,147
Money taken out early           −₹2,40,69,421
Compounding lost to the pause   −₹1,08,21,652
                                ──────────────
Total                          −₹12,09,93,927
Unexplained                              ₹0
```

Each figure is that cause's **Shapley value**: its average marginal
effect across all twenty-four orderings. The interaction is not
dropped and it is not shown as a mystery line at the bottom - it is
shared out among the causes that jointly produced it, which is why
the column sums to the gap exactly.

That zero is the whole point. It is not rounding luck, and it is not
decoration: it is the efficiency property of the Shapley value, and
`test_attribution.py` asserts it to the rupee on this very scenario
rather than assuming it.

**What it costs.** Two to the power of the number of causes, in
simulations - sixteen full thirty-year runs here. That is why the
causes are capped at six.

---

## 3. The pause, on its own

The single most shareable fact here. ₹25,000 a month, thirty years,
no step-up. Then three years off in the middle.

| | |
|---|---|
| Instalments skipped | **₹9,00,000** |
| Value never accumulated | **₹1,05,43,672** |
| Ratio | **11.7×** the money skipped |

> Three years of paused contributions is ₹9 lakh you didn't invest.
> It is **₹1.05 crore** you don't end up with.
> The difference is the twenty-two years that money never got to
> work.

---

## 4. Five crore by 45

Starting point: ₹25,000 a month for 20 years reaches
**₹2,03,90,181**. The target is ₹5,00,00,000. Three levers, and the
tool takes no view on which is right:

| Lever | What it would take |
|---|---|
| **Invest more** | ₹61,304 a month instead of ₹25,000 |
| **Wait longer** | 28 years instead of 20 |
| **Earn more** | 19.3% a year instead of 12% |

**Read the third one as a warning, not an option.** A required
return is a diagnosis. Very few assets have sustained 19% over two
decades, and no fund can be chosen to guarantee it. When that number
gets large, the honest reading is that the target needs more time or
more money - not a better fund.

---

## Reproducing these

Every figure comes from the same engine the portal runs. To rebuild
them, construct the journeys described above on the **Guided
Journey** screen, save each under its name on **Compare Journeys**,
and read the attribution.

### The four panels, keystroke by keystroke

This is the picture at the top of the README, written out as things
to type. Set the asset once, then build four journeys: two pairs,
each pair differing by exactly one decision.

**The asset, and the plan, identical in all four**

| Field | Value |
|---|---|
| Plan starts | January 2027 |
| Horizon | 20 years |
| Assets | one, 100% allocation |
| Monthly instalment | ₹25,000 |
| Assumed return | 12% a year, gross |
| Expense ratio | 1.0% a year, simple |
| Long-term rate · threshold | 12.5% · 12 months |
| Short-term rate | 20% |
| Exemption | ₹1,25,000 a year, long-term gains only |

#### The pair that isolates timing

Both pay in **exactly ₹45,00,000** and both take five years off.
Only the placement of the break differs, which is the whole point:
nothing else in either plan is different.

**Pause later (5 years)**

| Month | Event | Value |
|---|---|---|
| Jan 2027 | Start investing | ₹25,000 a month |
| Jan 2037 | Pause investing | |
| Jan 2042 | Resume investing | |

Ends on **₹1,70,57,325** (₹1.71 Cr).

**Pause earlier (5 years)**

| Month | Event | Value |
|---|---|---|
| Jan 2027 | Start investing | ₹25,000 a month |
| Jan 2032 | Pause investing | |
| Jan 2037 | Resume investing | |

Ends on **₹1,47,74,125** (₹1.48 Cr), which is **₹22,83,200 less**
for the same ₹45,00,000 paid in. Attribution puts the whole gap on
one cause and leaves nothing unexplained:

```
Pause later  →  Pause earlier

  Compounding lost to the pause        ₹-22,83,200
  unexplained                                   ₹0
```

The resume months are January, so 2037 to 2041 and 2032 to 2036 are
the silent years in each: a pause window is inclusive at its start
and the resume month pays.

#### The pair that isolates the raise

Both draw **₹5,000 a month out from January 2032** and run for the
same twenty years, because a plan interrupted by living is the
ordinary case rather than the exception.

**Step up 5% + SWP**

| Month | Event | Value |
|---|---|---|
| Jan 2027 | Start investing | ₹25,000 a month |
| Jan 2027 | Step up | 5% a year |
| Jan 2032 | Start withdrawing | ₹5,000 a month |

Paid in ₹99,19,786, drew out ₹9,00,000, ends on **₹2,64,64,380**.

**Step up 10% + SWP**

| Month | Event | Value |
|---|---|---|
| Jan 2027 | Start investing | ₹25,000 a month |
| Jan 2027 | Step up | 10% a year |
| Jan 2032 | Start withdrawing | ₹5,000 a month |

Paid in ₹1,71,82,500, drew out ₹9,00,000, ends on **₹4,02,25,852**
- **₹1,37,61,472 more** for ₹72,62,714 more paid in.

#### What the picture is for

The two rows answer two different questions, and only the first is
a fair fight. The top row moves nothing but the calendar, so its
₹22,83,200 is purely what *timing* was worth. The bottom row pays
in more as well as raising faster, so its gap is a raise and its
consequences together, not a free lunch.

All four are drawn to one vertical scale, which is why
`tools/render_journey_comparison.py` fixes the axis by the largest
journey rather than letting each panel choose its own. Four
screenshots stitched together each carry whatever scale the app
chose for them, and the comparison dies. If the panels are to be
captured from the screen rather than generated, put all four on
**Compare Journeys** at once: one chart, one axis.

### What an interruption costs, and when

The same arithmetic decides every interruption, and it is worth
writing down on its own. A plain ₹25,000 plan, twenty years, 12%,
with ₹6,00,000 taken out of it:

| When the ₹6,00,000 leaves | Ends with | What it cost |
|---|---|---|
| Never | ₹2,03,90,181 | - |
| All at once, in year 16 | ₹1,93,87,901 | ₹10,02,280 |
| ₹5,000 a month, years 6 to 15 | ₹1,86,15,896 | ₹17,74,285 |
| All at once, in year 6 | ₹1,75,44,285 | ₹28,45,896 |

One amount, one plan, and a cost between ₹10 lakh and ₹28 lakh
depending on nothing but when it left. Every figure in that last
column is larger than the ₹6,00,000 itself, because what you spend
is the money and what it costs is the money plus everything it
would have earned.

Two consequences follow from the arithmetic, and neither is a
recommendation. Spreading a withdrawal into instalments costs less
than taking the same total in one go, because most of it stays
invested while the rest is drawn down. Borrowing rather than
withdrawing is the same trade running the other way: the corpus
keeps compounding and interest is paid for that, which comes out
ahead only if the borrowing rate is below the return actually
realised - and the return is an assumption, while the interest is a
contract. This document reports what the stated assumptions imply.
It is not advice, and nothing in it is a substitute for a licensed
adviser.

The tables above were generated directly against
`investment_journey_simulator.scenario_set.run_journey_outcome` and
`investment_journey_simulator.attribution.attribute_gap`.

**One caveat worth stating.** Every asset here compounds at a steady
monthly rate. Real markets do not, and the order returns arrive in
changes the answer - sometimes a great deal, near the end of a plan.
The **Historical & Risk Lab** replays the same plan over real index
history and shows that spread; these deterministic figures are the
*consequence of the stated assumptions*, which is a different and
more answerable question than what a market will do.
