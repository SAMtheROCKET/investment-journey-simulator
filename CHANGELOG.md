# Changelog

Notable changes, newest first. Version numbers follow the package
version in `src/investment_journey_simulator/__init__.py`, which is
the single source the distribution reads from.

Three version numbers exist in this project and they are not the
same thing. The **product version** below tracks what the tool does.
The **scenario schema version** inside a saved JSON file tracks what
that file's shape is, and only changes when an old file would
otherwise stop loading. The **Python API** is not versioned at all,
because nothing outside this repository imports it.

## 4.4.0 - 31 August 2026

Every gap on a timeline was one month too long.

### Fixed

- **A resume month did not pay.** A pause paired with a resume
  compiled to a window ending *on* the resume, and both ends of a
  window are inclusive - so the month the reader said "start
  again" was the last silent one. Every gap ran a month longer
  than it was drawn, and every plan carrying one was an instalment
  short. On a thirty-year plan with a five-year break that is
  about a fifth of a per cent: small enough to read as rounding,
  and not rounding.
- **A stop to withdrawals swallowed the next start.** "Stop
  withdrawing" ran to the end of the horizon whatever followed it,
  so a later "start withdrawing" was placed on the rail, drawn on
  the chart, and silently never paid out. A stop now ends where
  the next start begins.
- **The rail and the Gantt drew gaps a month short.** Both read a
  window's inclusive last month as an exclusive bar end. Correct
  while the compiler was also wrong; visible the moment it was
  fixed.
- **Migrated plans keep exactly the months they were saved with.**
  The migration placed a resume on a legacy window's last month to
  match the old compiler. Both halves were wrong together and
  right in combination: an old file round tripped, and a resume a
  reader placed by hand cost them an instalment.

### Changed

- Fixtures that meant "three years off" now say so under the
  corrected convention, so the figures they back are unchanged.
  Where a document quotes a pause cost, that cost still stands.

### Added

- Boundary tests that count the paying months rather than asking
  whether a pause happened at all. An off-by-one passes every test
  of the second kind, which is how this survived.

## 4.3.1 - 31 August 2026

A plan saved twice under two names, and the reason it happened.

### Fixed

- **The Compare page would save the same plan under a second name
  and draw it twice.** Two identical curves, a spread of zero and
  an attribution with nothing in it reads as an answer rather than
  as the mistake it is, so saving a journey that duplicates one
  already held is now refused, naming the journey it matches and
  saying what to change. A set that already holds duplicates -
  built before this, or restored from a file - says so where it
  draws them.
- **The Guided page had no way to change what a plan invests each
  month.** The field labelled "How much every month" belongs to
  the *add an event* composer, so typing into it changed nothing
  until the event was placed. There is now an **Invest each
  month** control beside the rail that edits the plan directly,
  and the composer says out loud that nothing there takes effect
  until *Add to timeline* is pressed.

Neither the engine nor the comparison was at fault. Each screen
was correct on its own; what was missing was any way to notice
that an edit had not landed, and any objection to comparing a plan
with itself.

### Added

- `tests/test_journey_round_trip.py`. Every other page test drives
  one screen, which is exactly why this survived: the failure only
  exists in the gap between two. It saves a journey, edits on the
  timeline, saves again, and asserts the two differ.

## 4.3.0 - 31 August 2026

Two ways of taking money out that the timeline could not express.

### Added

- **One-off withdrawal.** A single amount taken out of a single
  month - a car, a deposit, a medical bill - and the mirror of the
  one-off investment that has always been there. It sells units, so
  it realises a gain and is taxed; the exit load and transaction
  tax come off what reaches you; and it can be capped by a corpus
  too small to meet it. Naming a fund takes it all from that fund,
  and falls short rather than quietly taking the remainder from a
  fund you did not name.
- **Withdraw everything and close.** Sells every holding in one
  month, realising the whole gain at once, and stops both the
  instalment and any standing withdrawal. The corpus is then zero
  for the rest of the horizon, and the chart draws those years flat
  rather than stopping short.
- **A closed plan can be started again.** Place *Start investing*
  after a close and a new phase opens from nothing. Retiring,
  spending it and going back to work is an ordinary life, and a
  timeline that could not express it would be the poorer tool.
- Both events are refused where they make no sense: nothing may
  follow a close except a restart, and nothing may be taken out of
  a plan that was never funded. Being funded is an existence
  question rather than a state one - money does not un-exist - so
  a plan funded once by a lump sum may be drawn on years later.

### Fixed

- **A closure now empties the lot book rather than selling a sum
  equal to the balance.** The two differ by float dust, and "this
  plan holds exactly nothing" is a claim about kind rather than
  size. Found by the cross-check, at nine nano-rupees on a ₹3.55
  crore corpus.
- **Raising money from one named fund no longer reads the other
  funds.** The shared pro-rata helper looped over every holding
  while being handed a mapping containing one, which raised a
  `KeyError` the moment a fund was named. Also found by the
  cross-check, on its first run.
- The plan summary said "Nothing sold, so no tax in this figure"
  even when the plan sold something. It now says which of the two
  is true, and names the month a plan closes.

### Changed

- `SimulationSettings.closure_month_index_int` is
  `liquidation_month_index_int`, because that is what the engine
  does with it. Stopping the flows is a separate, composable
  statement that the timeline compiler adds; the field alone
  liquidates and nothing more, and a name implying otherwise was a
  trap waiting for whoever set it by hand.

### Verified

- 3,000 untaxed and 1,000 taxed random plans cross-checked against
  the two independently written simulators, agreeing to floating
  point. Of those, 1,186 carried a lump withdrawal, 476 a
  liquidation, and 188 both at once.
- `tests/test_money_out.py` holds the arithmetic by hand: the gap a
  ₹2,00,000 withdrawal opens is that amount compounded for the
  months that remained *after* it - 119 of them, not 120, because
  the sale happens at the close of its own month.

## 4.2.0 - 20 August 2026

A release-blocking packaging defect, and its twin.

### Fixed

- **The bundled index history was not in the wheel.** It sat in a
  `data/` folder beside the repository and was located by walking
  up three parents from the module that wanted it. That is the
  repository root from a clone and nothing at all from
  `site-packages`, so `pip install` produced a program whose
  Historical and Risk Lab had no history - and the interface read
  the resulting `None` as "no history configured" rather than
  "the history is missing". No error, no warning.
- **The guides were not in the wheel either**, for exactly the same
  reason, found by the first test written for the first defect. An
  installed copy rendered three empty tabs and an apology.
- **`py.typed` was declared as package data but did not exist**, so
  the distribution advertised inline type information it never
  shipped.

Both the history and the guides are now package data, read through
`importlib.resources`. The same call answers identically from a
clone, an editable install, a built wheel, the console command and
a hosted deployment; all five were verified from a working
directory outside the repository, so no relative path could rescue
a failure.

### Added

- `tests/test_packaging.py`. The defect was invisible to the whole
  suite as it then stood, because every test in it ran from the
  repository root, so these ask a different question: not "is the
  code right" but "does the thing we ship contain what it needs". Three lines of defence
  - no module may use `parents[n]` to escape the package, every
  declared package-data pattern must match a real file, and the
  built wheel is opened and inspected.

### Changed

- `data/` and `docs/guides/` moved inside the package. The CSVs
  were renamed to `nifty100_2023_2024.csv` and so on; the previous
  names carried spaces and dashes.
- `load_market_history` now requires an explicit directory. Callers
  wanting the shipped history use `load_bundled_market_history`,
  which cannot be resolved against the working directory by
  accident.

## 4.1.0 - 20 August 2026

The repository was restructured for publication and the engine was
put through two rounds of independent cross-checking. Three real
defects came out of it, all of which had survived a suite of
seventeen hundred tests.

### Fixed

- **A portfolio-level instalment was given to every fund in full**
  instead of being divided between them. A two-fund plan therefore
  invested twice what the reader asked for, a three-fund plan three
  times, and every figure downstream inherited it. It is now split
  by target weight.
- **Opening the Quick Projection screen rewrote every fund's
  expected return to the first fund's.** Equity 14 / debt 6 / gold
  10 became 14 / 14 / 14 simply by looking at the screen, which is
  why the invested split and the ending split showed identical
  percentages. The read now returns the average and the write
  shifts every fund by the delta, so the spread survives.
- **The exit load and the transaction tax were reported but never
  deducted** on an investor withdrawal. The same charges *were*
  deducted when a rebalance sold, and *were* subtracted from the
  post-tax figure at final exit, so one charge had three
  behaviours. The fund house deducts them at source, so they now
  come out of the payout: sell ₹1,00,000 of units inside the load
  window and ₹99,000 arrives.

### Added

- `tests/reference_simulator.py`, a second simulator that computes
  the same portfolio by a different algorithm - one number per fund
  rolled forward, no lot book at all - so a mistake in the lot book
  cannot be repeated in it.
- `tests/reference_tax.py`, a second lot book written from the
  statute, because tax needs to know which units were sold and the
  first reference deliberately cannot say.
- `tests/test_engine_fuzz.py`, `test_engine_tax_fuzz.py`,
  `test_engine_overlaps.py` and `test_engine_audit.py`: 29,000
  untaxed and 4,800 taxed random plans cross-checked, plus the
  event collisions a random generator hits only by luck.
- A conservation identity that holds exactly once every return is
  set to zero: what is left equals what went in, minus what came
  out, minus what was charged. That is what caught the exit load.

### Changed

- `streamlit run streamlit_app.py` replaces
  `streamlit run src/run_portal.py`. `src/` now holds the package
  and nothing else, which is what a src layout is for.
- `pip install -e .` provides an `investment-journey` command.
- `jupyter/` became `notebooks/`, `historic_data/` became `data/`,
  the generated report moved to `docs/reports/`, and the loose
  images moved to `assets/`.
- The package's own README was folded into `docs/ARCHITECTURE.md`.
  Two documents describing one project had begun to disagree.
- Notebook outputs were stripped: 50 MB of embedded chart images
  became 72 KB of source.

## 4.0.0 - 19 August 2026

The portal became the only way in, and the interface was rebuilt
around it.

### Changed

- One launcher replaced four. The classic dashboard, the event rail
  and the studio are still here and still run - inside Advanced
  Simulator and Guided Journey - but they are no longer separate
  doors.
- The interface was rebuilt on the Ink and Brass design language:
  a vellum canvas, a deep-ink console, brass section marks,
  hairlines rather than shadows.
- Every colour in an injected stylesheet is now derived from
  `currentColor`. Four separate invisible-text bugs had one cause
  between them: a stylesheet that fixed a colour for a surface it
  turned out not to be on.
- Timeline events are validated by a state machine, so a plan
  cannot pause a SIP that never started.

## 3.x and earlier

Kept in `legacy/` rather than in this file. Seven single-file
scripts, each a stage this project went through before it was a
package - a calculator, then a dashboard, then a dashboard with
tax, then one with presets. They are outside every gate and would
not pass one, and they are kept because deleting the history of a
thing makes it look more inevitable than it was.
