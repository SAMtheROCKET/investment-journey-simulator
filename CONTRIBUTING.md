# Contributing

This is a personal project that happens to be public, so there is
no roadmap to sign up to and no issue triage rota. If something is
wrong, say so - that is the contribution I actually want.

## The one thing worth knowing first

**A number in this tool is a claim about somebody's money.** Every
figure it prints is either checked against a closed form, checked
against a second implementation, or held to an invariant, and each
test names which of those it is. If you change the engine, the
change has to arrive with the same.

That is not process for its own sake. Three defects found in August
2026 had all survived a large and carefully written suite: a portfolio
instalment that doubled the money invested, a screen that flattened
every fund's return by being opened, and an exit load that was
reported without ever being deducted. None of them were caught by a
test that compared the engine to itself. They were caught by
comparing it to something written separately.

## Setting up

```bash
git clone https://github.com/sambitd0/investment-journey-simulator
cd investment-journey-simulator
python -m venv env
env/Scripts/activate          # Windows; use source env/bin/activate elsewhere
pip install -e ".[dev]"
streamlit run streamlit_app.py
```

## Before you open a pull request

All four have to pass. There is no `|| true` anywhere in the
workflow, and a badge that says green while a gate is off is worse
than no badge.

```bash
python -m pytest                  # 2,508 passed, 4 skipped
ruff check src tests tools streamlit_app.py
mypy
python tools/check_house_style.py # 0 long lines, 0 long functions
```

## House rules the checker enforces

- No line over 79 characters.
- No function over 50 lines.

Both are unusual and both are deliberate. A 79-character limit means
two files sit side by side on a laptop; a 50-line limit means a
function fits on a screen while you are deciding whether it is
right. When a function grows past it, the fix is almost always that
it was doing two things.

## House rules the checker cannot enforce

- Variables are named `<meaning>_<dtype>`: `monthly_sip_float`,
  `month_index_int`, `fund_name_str`. Verbose, and it means the type
  of a variable is legible at its use site rather than at its
  declaration.
- Functions are named for the operation and the type they return.
- Every function gets a one-line title, and a `Warning` section when
  there is a genuine way to misuse it. A warning that says "call
  this correctly" is noise; one that says "call this twice and the
  exemption is consumed twice" is worth the line.
- **No em dashes, and no en dashes.** `tests/test_house_typography.py`
  fails the build on them. They are the clearest single tell of
  generated prose, and this project is written, not generated.

## Writing a test

Say what class of truth the test rests on, in a `REFERENCE:` line:

| Tag | Means |
|---|---|
| `G1-ANALYTIC` | Closed-form maths, computed live inside the test |
| `G2-STATUTORY` | A rate or rule from the Income-tax Act, with the section named |
| `G3-CROSSCHECK` | Compared against an independent implementation |
| `G4-SYNTHETIC` | Hand-derived, with the arithmetic shown in the docstring |
| `G5-PLAUSIBILITY` | Realistic magnitudes used as inputs only, never asserted |

If you find yourself writing a test that records what the code
currently produces, stop. That catches drift and cannot catch a
figure that was wrong the day it was written, which is exactly how
all three of August's defects survived.

## If you are reporting a wrong number

The most useful report names the scenario. The fuzz tests are
seeded, so if you can get it to fail there, the seed alone
reproduces it:

```bash
python -m pytest tests/test_engine_fuzz.py -q
```

Otherwise: what you entered, what it showed, and what you expected
instead. A screenshot of two figures that cannot both be true is a
perfectly good bug report - that is how the donut-percentage defect
was found.

## Tax law

Every statutory number lives in `tests/reference_data.py` and is
cited in `docs/SOURCES.md`, so an amendment is a one-line change and
a stale citation fails the build. Rates are as applicable to
transfers on or after 23 July 2024. **Re-verify after every Budget.**
If you update one, update its source line in the same commit.
