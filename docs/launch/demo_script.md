# Demo GIF - shot list

The arc follows a reader's actual path, not a tour of the
navigation. Each shot has to **prove one claim** from
[post.md](post.md); if a shot proves nothing, cut it.

**Target length: 30-40 seconds.** Long enough to reach the
attribution, short enough to autoplay twice on a timeline.

**Before recording**
- Window at 1440×900. Sidebar expanded.
- Detail level on **Guided**.
- Start from a fresh session ("Start a new plan") so Home shows the
  empty state.
- Currency **INR**.

---

## Shot 1 - Home · 3s

**Proves:** you arrive with a question, not a tool preference.

Land on Home. Hold long enough to read the four route cards.

> On screen: *What do you want to know?* - See where I may reach ·
> Reach a target · Compare two journeys · Plan around a life event

Do not scroll. The four questions are the shot.

---

## Shot 2 - Quick Projection · 6s

**Proves:** a defensible number in under a minute, assumptions
disclosed.

1. Type **25000** into the monthly amount.
2. Let the three tiles land.
3. Expand **What this assumed** - hold 1.5s so the list is legible.

> Must show: **₹2,03,90,181** · paid in **₹60,00,000** · today's
> money **₹63,57,755**
> And the assumptions list: no step-up, no pauses, no withdrawals.

The expander is the point. A projection with hidden assumptions is
worse than none, and this frame is where the post's honesty line
gets proved rather than asserted.

---

## Shot 3 - Guided Journey, the timeline · 10s

**Proves:** the interface is the timeline. No form, no jargon.

1. Arrive - the plan from Quick is already on the rail. **Do not
   retype anything.** This is the "you never type it twice" claim
   and it must be visibly true.
2. Click a month around 2031. The **ring and dotted leader** appear.
3. The chooser opens: *Start something / Stop or change something /
   Record something about your life*.
4. Choose **Pause contributions**. Add it.
5. Click ~2034, add **Resume contributions**.

> Must show: the pause span on the rail, and the **cash-flow arrows**
> beneath it - up for money in, sized by amount.

This is the longest shot because it is the product. Let the click →
ring → menu → placed-event sequence read at human speed.

---

## Shot 4 - Compare Journeys · 8s

**Proves:** the differentiator. Not four curves - an explanation.

1. Save the current plan as **"Paused for three years"**.
2. Load the steady version, save as **"Never interrupted"**.
3. Both tiles appear, then the overlay, then scroll to the
   waterfall.

> Must show: the spread headline, then
> **Compounding lost to the pause** and **unexplained ₹0**.

The zero is the shot. Hold on it for a full second - it is the
claim nothing else in the category makes.

---

## Shot 5 - Goal Planner · 5s

**Proves:** the question asked backwards, and an honest answer.

1. Enter target **50000000**.
2. Three tiles land.

> Must show: ₹61,304 a month · 28 years · **19.3%** - and the
> caption *"This is not a lever you control."*

The hedge on the return figure is deliberate and worth a frame. It
is the difference between a planner and a fund advertisement.

---

## Shot 6 - the closing card · 3s

Static frame, no UI:

> **You define the assumptions.**
> **It shows you their consequences.**
>
> Any asset · any contribution · any life event
> *Not a forecast.*

---

## Numbers that must appear, exactly

Cross-check against
[comparative_journeys.md](comparative_journeys.md) before
publishing. If a frame disagrees with the post, the post is wrong
too - they come from the same engine.

| Shot | Figure |
|---|---|
| 2 | ₹2,03,90,181 · ₹60,00,000 · ₹63,57,755 |
| 4 | unexplained **₹0** |
| 5 | ₹61,304 · 28 years · 19.3% |

---

## What to leave out

- **The Advanced Simulator.** It is the most impressive screen and
  the worst opener - a wall of controls contradicts the whole
  pitch. Mention it in text; do not film it.
- **The Rebalancing Lab and Risk Lab.** Both are excellent and
  neither answers a first-time question. Save them for follow-up
  posts, where they will each carry one on their own.
- **Any screen that needs explaining before it makes sense.** If a
  frame needs a caption to be understood, it belongs in the article,
  not the GIF.

---

## Recording brief for the README

The shot list above is one continuous 30-40 second demo, made for a
post. The README needs something different: **four separate
recordings, none of which is a tour.**

### How many, and why not more

One hero and three short loops. Not twelve.

A page of autoplaying GIFs is a page that jitters. The eye has
nowhere to rest, nothing holds still long enough to be read, and a
reader who cannot find a still point leaves. Worse, motion reads as
*decoration* once there is enough of it, and the whole argument
this project makes is that its numbers are worth trusting. Twelve
moving images say "look at my interface". One well-chosen one says
"watch this answer a question you have".

The four-panel comparison is deliberately **static**. It is the
densest claim on the page and it needs to be looked at, not
watched.

| Slot | Length | Shows | Placed |
|---|---|---|---|
| **Hero** | 12-15s | Quick Projection: type ₹25,000, get an answer, add a career break, watch the number move | Directly under the badges |
| **Loop 1** | ~8s | Compare Journeys and the attribution panel | Under "What makes it different" |
| **Loop 2** | ~10s | The timeline: hover a month, add an event | Under "Build a journey by clicking" |
| **Loop 3** | ~6s | Goal Planner: type a target, read the instalment | Under "Work backwards from the goal" |

If only one is ever made, make **Loop 2**. Building a plan by
pointing at a month is the least common thing here, and it is
legible in three seconds without a caption.

### The hero has one job

It must make a stranger think *"I could use this"* inside five
seconds. Not *"this is sophisticated"* - that thought comes later,
from the numbers, and it never rescues a reader who has already
decided the tool is not for them.

So the hero is **Quick Projection**, not the Advanced Simulator, for
the reason given above: a wall of controls answers a question
nobody has asked yet. Enter an amount, get an answer, change one
thing, see the answer change. That arc is the product.

### Specification

- **1440×900**, captured at 2× and downscaled, so text stays sharp.
- **No cursor hunting.** Move deliberately; a hesitating pointer
  reads as a broken interface.
- **No audio, no captions.** If a frame needs explaining, it is the
  wrong frame.
- **Under 3 MB each.** GitHub serves the README to people on
  phones. A 12 MB hero is a blank rectangle for the first several
  seconds, which is worse than no hero.
- **Loop cleanly.** Start and end on the same view so the repeat is
  not a jump cut.
- **Light theme.** It is the default, and the one a stranger sees.

### The Advanced Simulator: a still, not a loop

It earns a place in the README, but as a **static screenshot** and
not a fifth recording.

Its whole message is density - 39 controls, 8 charts, 9 tables, 20
figures on one screen, which is the visible answer to "is this
serious?" Density is read rather than watched. A recording of
someone scrolling a control panel is motion carrying no
information: the eye never settles long enough to take the wall
in, and the loop restarts before anything has been counted. A
still can be stopped on, zoomed into, and studied.

Place it **low**, among the technical sections, near the
architecture and correctness material. By then a reader has
stopped asking "is this for me?" and started asking "is this any
good?" The Advanced screenshot answers the second question well
and damages the first, which is why it must never appear near the
top - the same reason it is not the hero.

Shot: full page, light theme, sidebar expanded, 2x and
downscaled, with a couple of charts visible below the controls so
the density reads as output rather than as knobs.

That keeps the page at four moving images and two stills. Four is
the discipline, not an accident: past it, motion stops reading as
evidence and starts reading as decoration, which is corrosive for
a project whose whole argument is that its numbers can be
trusted.

### One honest warning

Record these *after* the interface has settled. A GIF is the most
expensive documentation in the repository to keep current: a
screenshot of a renamed button is a small embarrassment, and a
15-second recording of a flow that no longer exists is a reason to
distrust everything else on the page.
