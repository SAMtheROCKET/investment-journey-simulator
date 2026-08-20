# When to stop layering CSS and write a component

**Decision: not yet. Keep Streamlit. Revisit once the product is
functionally stable.** Recorded here so the reasoning survives.

## The ceiling this acknowledges

Most of what a reader touches on these screens is a native widget -
`st.number_input`, `st.tabs`, `st.metric`, `st.columns`,
`st.expander`, `st.dataframe` - with the Ink and Brass stylesheet
layered over it. That gets a long way, and the screenshots show how
far, but there is a real ceiling: a stylesheet can restyle a widget
and cannot change how it behaves, what it animates, or where its
parts sit relative to one another.

Two symptoms of that ceiling have already shown up in this project,
and both were fixed by working *with* the framework rather than
against it:

- Streamlit hangs a chain icon off every heading that looks like a
  disclosure and only copies a link. The fix was to hide it and
  provide a real affordance, not to replace the heading.
- The theme is not selectable from CSS, so a Python-side guess about
  which theme was running inverted the text twice. The fix was to
  derive every colour from `currentColor` and stop guessing.

Neither needed a custom component. A good deal of the remaining gap
does not either.

## What would actually be worth replacing

The parts where the interaction *is* the product, and where a native
widget is doing something close to but not quite the right thing:

| Experience | Why a component earns its cost |
|---|---|
| **Plan Pulse** | Figures should count to their new value when an input changes. A markdown block cannot animate; the number simply jumps. |
| **Journey timeline** | Drag an event to a new month, drag its edge to change a span. Today the rail is a Plotly click target and everything else is a form beneath it. |
| **Compare Journeys** | Hovering one trajectory should dim the others and pin a shared crosshair across the overlay and the waterfall together. |
| **Goal control panel** | A goal ring the reader can drag, with the three levers re-solving live against it. |

## What should stay native, permanently

Ordinary forms, the fund table, every ledger, the export controls,
the guides. These are inputs and tables. A custom component would
cost weeks and buy nothing a reader would notice, and each one is
another thing to keep accessible, keyboard-navigable and in step
with the theme.

## The judgement

Replacing four signature experiences gets most of the way to feeling
like a custom application, at a fraction of the cost of rebuilding
the product in React, and without giving up the thing Streamlit is
genuinely good at: one Python process, one plan object, and a screen
that recomputes itself when the plan changes.

**The precondition is functional stability.** A custom component
freezes an interaction into TypeScript and a build step. Doing that
while the interaction is still changing weekly buys the worst of
both: the cost of a component and the churn of a prototype.
