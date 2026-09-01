# Scenario gap table - what `TimelinePlan` can and cannot express

**Question this answers:** can `TimelinePlan` serve as the canonical
scenario form for the merged portal, or does it need replacing?

**Verdict: yes, but not on its own.** `TimelinePlan` is a complete
record of *dated events*. It is not, and should not become, a record
of *rule shapes*. Every gap found below is a rule shape. The fix is
therefore not to invent new event types - it is to carry a policy
block alongside the event list.

Audited 6 August 2026 against `timeline.py`, `models.py`,
`ui/sidebar_controls.py`, `studio_app.py`.

---

## Method

Every field of `SimulationSettings` and its nested settings objects
was traced back through `compile_settings()` (`timeline.py:675`) to
ask: can a reader place events on a rail that produce this value?

Three outcomes:

* **Reachable** - some event sets it.
* **Caller-supplied** - `compile_settings` takes it as an argument,
  so it already lives outside the timeline. Not a gap.
* **Unreachable** - hardcoded or left at default, with no event able
  to change it, while another front end exposes it.

---

## Part A - Unreachable, and another front end exposes it

These are the real gaps. Each names where the classic dashboard
offers the control that the timeline cannot reach.

### A1. Instalment timing - highest severity

| Field | Timeline | Dashboard |
|---|---|---|
| `SimulationSettings.sip_at_month_start_bool` | hardcoded `True` at `timeline.py:700` | `ui/sidebar_controls.py:127` |

This decides whether an instalment compounds for the month it is
paid in. It is the exact convention documented in
`docs/SOURCES.md`, and the reason this engine matches a major
platform's published figure to the rupee while two other
widely-used calculators diverge. A
merged portal that silently pins it to `True` on some screens and
exposes it on others will produce two different corpus figures for
the same plan and offer no explanation.

### A2. Step-up shape

`_resolve_stepup` (`timeline.py:571`) sets `mode_str`,
`global_stepup_percent_float` and `first_stepup_month_index_int`.

| Field | Status | Dashboard |
|---|---|---|
| `interval_months_int` | fixed at 12 | `sidebar_controls.py:683` |
| `fixed_increment_amount_float` | fixed at 0 | `sidebar_controls.py:699` |

A step-up of a flat ₹2,000 a year, or one every six months, cannot
be expressed on the rail at all. Also documented in the resolver:
only the **first** step-up event is honoured; a second is ignored.

### A3. Withdrawal shape

`_resolve_withdrawal` (`timeline.py:641`) always builds a **fixed**
withdrawal from the **first** exit event.

| Field | Status | Dashboard |
|---|---|---|
| `mode_str` | pinned to fixed | offers other modes |
| `portfolio_percent_float` | unreachable | `sidebar_controls.py:993` |
| `annual_change_percent_float` | unreachable | `sidebar_controls.py:1073` |
| `monthly_schedule_list` | unreachable | - |
| `monthly_change_percent_list` | unreachable | - |

"Withdraw 4% of the corpus a year" - the single most common
retirement rule there is - cannot be placed on the rail.

### A4. Rebalance shape

`_resolve_rebalance` (`timeline.py:531`) always builds a **dated**
trigger with the partial method and column targets. That is correct
and deliberate for a hand-placed rebalance. It leaves the whole
rule-driven half of the feature unreachable.

| Field | Status | Dashboard |
|---|---|---|
| `interval_months_int` (calendar trigger) | unreachable | `sidebar_controls.py:953` |
| `drift_band_percent_float` (drift trigger) | unreachable | `sidebar_controls.py:913` |
| `tax_funding_str` | unreachable | `sidebar_controls.py:798` |
| `use_contribution_steering_bool` | unreachable | `sidebar_controls.py:802` |
| `maximum_events_int` | unreachable | - |
| `method_str`, `target_mode_str` | pinned | - |

### A5. Per-fund targeting

`_collect_instalment_override_list` (`timeline.py:374`) and
`_collect_one_off_list` (`timeline.py:405`) both emit their records
with `fund_name_str` left at `""`, meaning *all funds*. The engine
and both dataclasses support naming a fund.

Consequence: on a multi-fund plan the rail cannot say "raise only
the equity SIP". Every instalment change hits the whole portfolio.

### A6. Explicit pause month lists - low severity

`PauseSettings.sip_pause_months_list` and
`withdrawal_pause_months_list` are never populated by the timeline,
which uses `pause_ranges_list` throughout. Likely redundant rather
than missing; flagged for confirmation, not for work.

---

## Part B - Caller-supplied, so not gaps

These already sit outside `TimelinePlan` and need no new machinery -
only a home on the scenario object.

| Group | Where it lives now |
|---|---|
| All of `TaxSettings` | second argument to `compile_settings`; the timeline only overlays `income_by_year_tuple` and `surcharge_mode_str` via `_apply_income_to_tax` |
| All of `FundConfiguration` - returns, expense model, TER, exit load, STT, per-fund tax, target allocation | `apply_plan_to_fund` (`timeline.py:803`) preserves every field and clears only the amounts |
| Currency, tax regime | `currency.py`, `regimes.py`; studio-only today |
| Inflation schedule | `collect_inflation_schedule_tuple` (`timeline.py:503`) - see the note below |

**One design smell worth fixing while we are here.** The inflation
schedule is a *second* compile output that callers must remember to
call separately from `compile_settings`. Two screens forgetting it
in different ways is a plausible source of divergent real-terms
figures. It should come out of the same single compile call.

---

## Part C - Consequences for the plan

### C1. `TimelinePlan` stays, and stays as-is

The events are right. All thirteen types map cleanly, ordering is
well-defined, and `compile_settings` is a genuine single translation
point. Replacing it would throw away working, tested machinery.

### C2. Do **not** add event types for the Part A gaps

Every gap in Part A is a policy, not an occurrence. "Rebalance when
drift exceeds 5%" is not something that happens on a date - it is a
standing rule. Modelling it as a dated event would corrupt the one
thing the rail is good at.

### C3. The shape this implies

```
PlanScenario
├── TimelinePlan        dated events        (exists, unchanged)
├── PlanPolicy          rule shapes         (NEW - closes Part A)
├── list[FundConfiguration]                 (exists)
├── TaxSettings                             (exists)
├── Currency + TaxRegime                    (exists, studio-only)
├── inflation schedule                      (exists, fold into compile)
└── presentation preferences                (exists, scattered)
```

`PlanPolicy` carries exactly the Part A fields: instalment timing,
step-up interval and fixed increment, withdrawal mode and its rate
fields, the rebalance trigger cluster, and a default fund target for
instalment changes. `compile_settings` takes it as a third argument
the way it already takes `tax`.

### C4. This changes task #3

Task #3 was written as "close the TimelinePlan expressiveness gaps",
assuming new event types. It should instead be **"build `PlanPolicy`
and thread it through `compile_settings`"**. Same gaps closed, but
without touching the event vocabulary - which means every existing
timeline test stays valid.

### C5. Priority within Part A

| Gap | Severity | Why |
|---|---|---|
| A1 instalment timing | **High** | two screens can disagree on the corpus with no visible cause |
| A3 withdrawal shape | **High** | percent-of-corpus is a headline retirement rule |
| A4 rebalance shape | Medium | the Rebalancing Lab page needs all of it |
| A2 step-up shape | Medium | flat-increment step-up is common |
| A5 per-fund targeting | Medium | only bites on multi-fund plans |
| A6 pause month lists | Low | probably redundant |
