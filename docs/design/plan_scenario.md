# PlanScenario - the one object every screen shares

**Status:** accepted, 6 August 2026
**Supersedes:** nothing. **Depends on:**
[scenario_gap_table.md](scenario_gap_table.md)

---

## The problem

The portal merges three front ends - the classic dashboard, the
event rail and the studio - into one site with nine screens. The
requirement that actually matters is not the navigation tree:

> Users must not re-enter their information when moving between
> projection, risk, goal and comparison views.

Today each front end owns its own inputs. The dashboard builds a
`SimulationSettings` from sidebar widgets; the rail builds one from
events via `compile_settings`; the studio builds a third from its
own form. Three input paths, three interpretations, no shared state.

## The decision

One `PlanScenario` object holds everything. Every screen reads and
writes that object and nothing else. Every run goes through one
compile function.

```
PlanScenario
├── TimelinePlan              dated events        unchanged
├── PlanPolicy                rule shapes         new
├── list[FundConfiguration]   the funds
├── TaxSettings               portfolio tax rules
├── Currency, TaxRegime       presentation + tax opening values
├── inflation schedule        (folded into compile)
└── presentation preferences  input style, dark mode, units
```

### Why the timeline is canonical rather than a fresh superset

`TimelinePlan` → `compile_settings()` → `SimulationSettings` already
exists, is tested, and is the only place in the codebase where plan
intent becomes engine input. Inventing a parallel canonical form
would mean either maintaining two translators or throwing that one
away. Neither is justified: the audit found the event vocabulary
complete.

### Why `PlanPolicy` is separate from the events

The audit's central finding. Every gap in the timeline's coverage is
a **rule shape**, not an **occurrence**:

* "Rebalance on 3 March 2031" is an event. It belongs on the rail.
* "Rebalance whenever drift exceeds 5%" is a policy. It has no date
  and never will.

Forcing policies into the event list would corrupt the rail, whose
entire value is that everything on it happened on a day. So they sit
beside it. `compile_settings` takes `PlanPolicy` as a third argument
exactly as it already takes `tax`.

The practical payoff: **the event vocabulary does not change, so
every existing timeline test stays valid and unmodified.**

## The single compile path

```python
def compile_scenario(scenario: PlanScenario) -> CompiledPlan
```

Returns the `SimulationSettings`, the fitted fund list **and** the
inflation schedule together. Today the inflation schedule is a
second output that callers must remember to fetch separately
(`collect_inflation_schedule_tuple`); two screens forgetting it in
different ways would produce divergent real-terms figures with no
visible cause. One call, one bundle, no way to forget.

**Rule:** after this lands, no screen constructs `SimulationSettings`
itself. Enforced by test, not by convention.

## Modes are projections, not input paths

Quick, Guided and Expert are three *declarations over one object*.
A projection states which fields its mode exposes; everything else
keeps whatever the scenario already holds.

```
PlanScenario  ←──  Quick     (a handful of fields)
     ↑        ←──  Guided    (plain-language subset)
     └────────←──  Expert    (everything)
```

### The rule that makes this safe

> **Lossy in display. Never lossy in data.**

A mode may decline to *show* a setting. No mode may *discard* one.

The failure this exists to prevent: someone configures eight events
and a drift-band rebalance in Expert, clicks Quick to check a
number, and Quick quietly runs without any of it - showing a corpus
figure that answers a question they did not ask.

So a mode that hides active configuration must say so:

```
14 advanced settings active, not shown on this screen  ▸
```

Expandable to the list. Never silent.

### Consequences

* Adding a field to `PlanScenario` forces an explicit decision about
  which modes expose it. A field no mode can reach is a bug, and
  task #9 tests for exactly that.
* Mode switching is free and lossless in both directions. Expert →
  Quick → Expert returns the identical object.
* Quick's defaults are **disclosed**, not hidden. "Assuming no
  step-up, no pauses, no withdrawals" is stated on screen.

## Session ownership

Exactly one `PlanScenario` lives in `st.session_state`, behind a
narrow accessor. No page keeps a local copy of any input. This - not
the navigation tree - is what delivers the no-re-entry requirement.

## What this does not do

* It does not change any finance. The engine, the tax code and the
  charts are untouched; this is a plumbing and state-ownership
  change only.
* It does not break saved scenarios. Existing v2.1 JSON files
  migrate to v3 on load (task #5), and the migration is tested
  against a fixture rather than assumed.
* It does not retire the three existing launchers. They keep working
  until the portal reaches parity.

## Open question deferred

`PauseSettings.sip_pause_months_list` and
`withdrawal_pause_months_list` appear redundant with
`pause_ranges_list` - nothing populates them from the timeline.
Confirm before deciding whether `PlanPolicy` needs to reach them.
Flagged as gap A6, low severity, no work scheduled.
