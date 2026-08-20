# Launch post - source text

One file. The LinkedIn, Reddit and README versions all draw from
here, so the numbers cannot drift between them.

Every figure below is real output of the engine and is reproduced
with its inputs in
[comparative_journeys.md](comparative_journeys.md).

---

## The opener - origin, not features

> I kept rebuilding the same spreadsheet.
>
> What if I pause for two years? What if I'd started five years
> earlier? What if I step up 10% a year instead of staying flat?
> What does the tax actually take? Every question meant another
> sheet, another set of assumptions, and no way to compare last
> week's answer with this week's.
>
> I did that for months. Then I built the thing I wanted: one place
> to model any asset, any contribution, any life event - and see
> what each decision is actually worth.

**Why lead with this.** It is checkable, and anyone who has done it
recognises it in one sentence. Nobody is moved by a feature list.

---

## The category line

> Most calculators evaluate one investment in isolation. Real lives
> are not isolated. Contributions rise, pause and restart. People
> hold several assets, withdraw for a house, relocate, change
> priorities, and chase different goals at once.
>
> This brings the whole journey into one editable, comparable plan.

---

## The differentiator - lead with this, not the features

> Plenty of tools will show you four different outcomes.
> This one tells you **why** they differ.
>
> Same person. Same income. Same assumed return. Same retirement
> age. One decision changed in each:
>
> | | Ends with |
> |---|---|
> | Never interrupted | **₹17.29 Cr** |
> | Withdrew ₹1 L/mo for nine months in year 10 | ₹16.59 Cr |
> | Paused two years | ₹16.06 Cr |
> | Never stepped up | **₹6.32 Cr** |
>
> And the gap is not left as a mystery:
>
> ```
> Never interrupted  →  Never stepped up
>   The raise that never happened   ₹10,96,53,859
>   unexplained                                ₹0
> ```
>
> That zero is not rounding luck. The split is a Shapley
> decomposition - order-independent, and exact - and the test suite
> asserts the causes sum to the whole gap.

---

## The hook - the single most shareable fact

> Three years of paused contributions at ₹25,000 a month.
>
> **₹9 lakh** you didn't invest.
> **₹1.05 crore** you don't end up with.
>
> The difference is the twenty-two years that money never got to
> work.

---

## The one that beats every "I'll start later"

> Two people. **Exactly the same money in.** Same finish date. Same
> assumed return.
>
> | | Paid in | Ends with |
> |---|---|---|
> | ₹15,000/mo from age 25 | ₹36,00,000 | **₹1,22,34,109** |
> | ₹30,000/mo from age 35 | ₹36,00,000 | **₹63,72,892** |
>
> Doubling the monthly amount does not buy back ten years.

**Why this framing.** There is no "but they invested more"
objection available, because they didn't. That is what makes it
land.

---

## The four ways in

> You don't arrive wanting a simulator. You arrive with a question:
>
> - **See where I may reach** - put in what you invest, get a number
>   and every assumption behind it.
> - **Reach a target** - name the figure; see what monthly amount,
>   what horizon or what return would get there.
> - **Compare two journeys** - change one decision, see what it was
>   worth.
> - **Plan around a life event** - a house, a career break, a move,
>   retirement. Put it on the timeline.

---

## Scope - say this before someone else does

> A row can be a mutual fund, a stock, an ETF, gold, land, a
> deposit, a business, or something you name yourself. The engine
> doesn't care what you call it - only what goes in, what comes
> out, and when.
>
> **What it does not capture:** every asset compounds at a steady
> monthly rate. That is a fair way to ask "what if gold returns
> 8%". It is not how land or a single stock behaves - those move in
> jumps, can't always be sold when you want, and carry costs no
> percentage captures. The tool says so where you add an asset.

---

## The honesty line - put this high, not in a footer

> This does not predict markets and does not try to. You supply the
> assumptions; it works out precisely what they imply.
>
> That is a different question from *what will the market do* - and
> unlike that one, it has an answer.

---

## On tax - the claim, and its limit

> Indian capital gains are modelled in depth, for a **resident
> individual**: FIFO lots, the short and long term split at the
> section 2(42A) boundary, the §112A exemption applied **per
> taxpayer per year rather than per fund**, surcharge with marginal
> relief, cess on tax plus surcharge, grandfathering arithmetic to
> 31 Jan 2018, loss set-off with eight-year carry-forward, exit
> load and STT. Every statutory figure is sourced and dated.
>
> What it is **not**: your total income tax bill, TDS for
> non-residents, IDCW plans, or a real NAV feed - the
> grandfathering fair value is the lot's own simulated value on
> that date. The boundaries are listed in full in `SOURCES.md`,
> and I would rather you read them than discover one.
>
> Everywhere else, choosing a country fills in its headline rates
> as **editable opening values** - it does not teach the program
> that country's tax code, and the screen says so where you choose
> it.

**Do not soften this.** The limit stated first is a credential. The
limit found by a commenter is a retraction.

---

## What not to say

- **Don't claim to be first.** Say what it does and let that stand.
  The genuinely distinctive part is *explaining the gap* - plus
  real Indian tax, plus any named asset you like, plus free. That
  is plenty to lead with, and it has the advantage of being
  checkable. A claim about the whole field is neither modest nor
  provable, and it is the one line a reader will want to argue
  with instead of trying the thing.
- **Never name another product.** Not to compare with, not to beat,
  not even to acknowledge. Describe the problem and what this does.
  The comparison makes itself, and naming anyone else turns your
  launch into their advertisement.
- **Don't say "realistic future number".** Say *a transparent,
  assumption-consistent estimate*. It is both more accurate and
  more defensible.
- **Don't use "corpus"** outside the India-specific material. It is
  invisible to most of the world.

---

## The NRI thread - a second post, not a paragraph

The checklist deserves its own post. It answers a different
question for a different reader, and burying it inside a product
launch wastes both.

Draw from [nri_investment.md](../../src/investment_journey_simulator/guides/nri_investment.md), which is
written as the ordered sequence: status change → NRE and NRO →
embassy or apostille attestation → KYC and FATCA everywhere →
what you may still hold → restarting the investing → tax in two
countries.

Link the simulator at the end as *"and here's what the gap in
contributions during the move actually cost me"* - which is a
demonstration rather than a pitch.

---

## Closing line

> You define the assumptions. It shows you their consequences.
> That's the whole product.
