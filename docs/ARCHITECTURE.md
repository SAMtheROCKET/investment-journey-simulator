# How this thing is put together

The README says what the tool does. This says how it is built, why
the pieces sit where they do, and which decisions inside it are
arguable enough to be worth writing down.

It used to live as a second README inside the package, which meant
two documents describing one project and slowly disagreeing with
each other. One of them had to go, and it was not going to be the
one people actually read.

## The shape of the repository

```
investment-journey-simulator/
├── streamlit_app.py     the only door in
├── src/
│   └── investment_journey_simulator/   the package, and nothing else
│       ├── data/        index history, shipped as package data
│       └── guides/      the checklists the app serves, likewise
├── tests/               the suite, plus two independent simulators
├── docs/                this file and its neighbours
│   ├── design/          decisions and their reasoning
│   ├── diagrams/        generated SVGs, never hand-drawn
│   └── reports/         generated output kept for reference
├── tools/               things you run *at* the project
├── notebooks/           the earlier implementation the tests check against
├── assets/              images the documentation points at
└── legacy/              seven superseded scripts, kept honestly
```

`src/` holds the package and nothing else. That is the whole point
of a src layout: the tests import the package the same way a user
would, so a missing `__init__.py` or a file left out of the
distribution fails the suite instead of passing quietly because the
repository root happened to be on the path.

`legacy/` is the one folder that is not held to any gate. It has
seven single-file scripts in it, each a stage this project went
through before it was a package. They are kept because deleting the
history of a thing makes the thing look more inevitable than it
was.

## Anything the program reads at run time lives inside the package

Not beside it. The index history and the guide markdown are package
data, declared in `pyproject.toml` and read through
`importlib.resources`.

This is worth a section because getting it wrong is invisible.
Both used to be found by walking up three parents from the module
that wanted them, which resolves to the repository root from a
clone and to nothing at all from `site-packages`. The entire suite
passed, because every test in it ran from the repository. A `pip
install` produced a program whose Historical and Risk Lab quietly
had no history and whose Guides screen quietly had no guides.

`tests/test_packaging.py` now holds three separate lines of
defence: no module may use `parents[n]` to escape the package,
every pattern declared as package data must match a real file, and
the built wheel is opened and inspected for the files themselves.

## The layers

| Layer | Modules | Depends on |
|---|---|---|
| Foundations | `constants`, `formatting`, `time_utils`, `returns` | nothing |
| Domain model | `models` | foundations |
| Engine | `taxation`, `holdings`, `schedules`, `allocation`, `engine` | model |
| Analysis | `inflation`, `tables`, `ledgers`, `validation` | engine |
| Presentation | `charts`, `narrative`, `dashboard_run`, `rebalancing_lab` | analysis |
| Input/Output | `fund_builder`, `scenarios`, `exports/*`, `ui/*` | presentation |
| Entry point | `portal_app`, `app`, `timeline_app`, `studio_app` | everything |

**Nothing below Input/Output imports Streamlit.** That is not
tidiness for its own sake - it is what lets the engine be driven
from a script, a notebook or a test with no front end anywhere near
it, and it is why the two reference simulators in `tests/` can
exist at all.

## Correctness decisions worth knowing

Each of these could defensibly have gone the other way. They are
listed because a reader who disagrees with one should be able to
find it, rather than discover it by being surprised by a number.

| Topic | What this does | Why |
|---|---|---|
| **Inflation** | Runs once in nominal terms, then deflates each cash flow **at its own date**. | Tax applies to nominal gains. Simulating at a real rate would tax real gains, which is wrong; so is deflating a cumulative total by the final factor. |
| **Exemption** | Tracked **per taxpayer** per financial year by default. | Section 112A relief belongs to a person, not to a scheme. Per-fund tracking multiplies the shelter; it stays available as an option. |
| **Holding period** | Strictly **more than** the threshold to be long term. | Section 2(42A) defines short term as *not more than*. Twelve whole months is short term; the thirteenth earns the lower rate. |
| **Rebalancing tax** | A funding choice: sell more units, or pay from your bank account. | Resident equity redemptions carry no TDS, so paying from outside is what usually happens. Neither option makes the tax free. |
| **Expense ratio** | Continuous accrual by default: `(1+R)^(1/12)·(1−e)^(1/12)`. | A real fund accrues its fee on the net asset value. Plain subtraction drops the return×expense cross term. |
| **Exit load and STT** | Deducted at source, so they come out of the payout on a withdrawal and out of the corpus on a rebalance. | The fund house takes them before you see the money. This was wrong until August 2026: the charge was reported and never actually deducted. |
| **Capital gains tax on a withdrawal** | Accrued and reported, never deducted. | A resident settles it at filing time from their own pocket, not at redemption. |
| **Internal transfers** | Rebalancing purchases raise the cost basis but never the invested principal. | Moving your own money between funds is not a new contribution. |
| **A portfolio-level instalment** | Divided between funds by target weight. | "Invest ₹25,000 a month" is a statement about the plan, not about each fund in it. Giving every fund the whole amount made a two-fund plan invest double, which is what it did until August 2026. |
| **Loss set-off** | Short-term losses shelter any gain, long-term losses shelter long-term gains only, applied **before** the exemption. | Sections 74 and 74(1)(b). The order changes the answer. |
| **Surcharge and cess** | Cess is charged on tax **plus** surcharge. | The order the Act prescribes. |
| **Marginal relief** | In slab mode the band rate is replaced by an effective rate holding the extra tax at or below the extra income. Computed before cess. | Crossing ₹50 lakh by one rupee would otherwise add over a lakh of surcharge in a single step. |
| **Duplicate fund names** | Renamed to `Name (2)`, `Name (3)`. | Names key the holdings, the targets and the tax ledger. Duplicates would silently merge two funds into one. |
| **Impossible inputs** | Returns at or below −100% and expense ratios outside 0-100% are clamped, not rejected. | Fractional powers of a negative base are undefined, and crashing on a typo helps nobody. |
| **A one-off withdrawal naming a fund** | Comes entirely from that fund, and falls short if that fund cannot cover it. | Taking the remainder from a fund the reader did not name would be worse than reporting a shortfall they can see. |
| **Closing a plan** | Sells every lot outright rather than raising an amount equal to the balance. | The two differ by float dust. "This plan holds exactly nothing" is a claim about kind, not size, and should be true rather than nearly true. |
| **A closed plan that is started again** | Allowed. The corpus is empty, so it builds from nothing. | Retiring, spending the lot and going back to work is an ordinary life; a timeline that could not express it would be the poorer tool. |

## The order of events inside one month

This is a convention rather than a truth, which is exactly why it
is written down. Both reference simulators encode it, so changing
it breaks a test rather than quietly moving every figure.

1. opening lump sums, in month zero only
2. one-off contributions dated to this month
3. the instalment, if instalments are paid at month start
4. the standing withdrawal
5. any one-off withdrawals dated to this month
6. the rebalance
7. the instalment, if instalments are paid at month end
8. the closure, if the plan is closed in this month

Everything is valued at the close of the month. An instalment paid
at the start has therefore earned that month's growth by the time
the withdrawal is taken, and one paid at the end has not. Money
bought back by a rebalance counts as bought at month end, so it
does not earn the month it was bought in.

Two orderings inside that list are choices rather than facts. The
**standing withdrawal is met before a one-off**, because the
standing one is the arrangement already running and a lump is the
exceptional act; when the corpus cannot cover both, the exception
is what falls short. And the **closure comes last**, so a plan that
ends in June still pays June's instalment and rebalances June
before it sells. Both reference simulators encode the same order,
so changing either breaks a test rather than quietly moving every
figure.

## House conventions

- Objects where state genuinely exists - `FundHoldings`,
  `PortfolioSimulator`, `ExemptionLedger`, `PauseCalendar`,
  `ContributionPlan`, `WithdrawalPlan`, `CapitalGainsTaxPolicy` -
  and plain functions everywhere else.
- Variables named `<meaning>_<dtype>`; functions named for the
  operation and the type they return.
- Every function carries a one-line title and, where it earns one,
  a `Warning` naming the way it is most likely to be misused.
- Constants upper case, declared after the imports of the module
  that owns them; shared ones in `constants.py`.
- **Enforced by `tools/check_house_style.py`:** no line over 79
  characters, no function over 50 lines.

## What is deliberately not modelled

Actual fund returns, volatility and sequence-of-returns risk in the
deterministic mode, live NAV or expense-ratio data, and IDCW plans.
The first three are unverifiable in principle from inside a
simulator; the rest depend on data this project deliberately does
not carry.

The stochastic mode exists precisely because the deterministic one
cannot say anything useful about sequence risk - see
[FEATURES.md](FEATURES.md) §5.3.
