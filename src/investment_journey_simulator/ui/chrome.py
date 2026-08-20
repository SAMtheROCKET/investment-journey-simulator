"""The Ink and Brass surface, and the four components that carry it.

Streamlit gives you a competent default interface. Competent default
interfaces all look the same, which is the complaint this module
exists to answer: not "make it prettier" but "make it look like
somebody chose how it looks".

Four devices do nearly all of that work, and none of them is a
gradient:

    *A warm ground.*  Vellum rather than the near-white every
    generated dashboard lands on, with the sidebar dropped to a
    deep ink so the rail reads as a console and the canvas reads as
    the document.

    *Small-caps brass marks.*  One typographic device, used for
    every section in the app and every zone in the diagrams. It is
    what makes a page and a picture look like parts of one thing.

    *Hairlines, not shadows.*  Depth comes from a 1px rule and a
    change of surface. Soft shadows under every card is the single
    most reliable tell of generated design.

    *3px corners.*  Machined, not inflated.

What this module may not do
---------------------------
Nothing here may colour a number. Brass and verdigris are furniture;
the moment either is used to distinguish two values, the reader who
has learned that brass means "heading" has been lied to. Figures are
coloured by `palette.py` and by nothing else.

The CSS deliberately targets very little of Streamlit's internals -
the app background, headings, metrics, and this module's own
classes. Every extra selector into a framework's private DOM is a
thing that breaks on upgrade for the sake of a rounded corner.
"""

from __future__ import annotations

from html import escape

import streamlit as st

# Every colour below is derived from the page's OWN text colour
# rather than from a guess about which theme is running.
#
# The guess is what broke this twice. `st.context.theme` reports the
# browser's preference, and the app's theme comes from config.toml;
# when those disagree the chrome emitted one theme's tokens onto the
# other's surface. Measured, that is 1.09:1 for pale ink on the
# light page and 1.07:1 for dark ink on the dark one - not poor
# contrast but invisible text, and no amount of re-tuning the values
# fixes a polarity that is decided by a coin flip.
#
# `currentColor` is not a guess. It resolves, per element, to the
# colour that element actually inherited, which Streamlit always
# sets correctly for the surface it is drawing on. So:
#
#   text      is currentColor, faded by mixing toward transparent
#   surfaces  are a wash of currentColor over whatever is behind
#   accents   are mixed toward currentColor, which pulls them light
#             on a dark ground and dark on a light one
#
# The sidebar needs no override under this scheme; it inherits its
# own pale text and everything follows. Worst measured case across
# the light page, the dark page and the console is 3.75:1 for the
# faintest hint, which is held to the 3:1 non-text gate, and 5.16:1
# for anything a reader must actually read.
BRASS_PIGMENT_STR: str = "#A9762F"
VERDIGRIS_PIGMENT_STR: str = "#28887E"

_TOKEN_RULES_STR: str = """<style>
:root {
  --ijs-ink: currentColor;
  --ijs-ink-soft: color-mix(in srgb, currentColor 84%, transparent);
  --ijs-muted: color-mix(in srgb, currentColor 70%, transparent);
  --ijs-faint: color-mix(in srgb, currentColor 55%, transparent);
  --ijs-plate: color-mix(in srgb, currentColor 3.5%, transparent);
  --ijs-sunk: color-mix(in srgb, currentColor 6%, transparent);
  --ijs-rule: color-mix(in srgb, currentColor 14%, transparent);
  --ijs-rule-soft: color-mix(in srgb, currentColor 8%, transparent);
  --ijs-brass: color-mix(in srgb, #A9762F 72%, currentColor);
  --ijs-brass-wash: color-mix(in srgb, #A9762F 12%, transparent);
  --ijs-brass-edge: color-mix(in srgb, #A9762F 34%, transparent);
  --ijs-verd: color-mix(in srgb, #28887E 72%, currentColor);
  --ijs-verd-wash: color-mix(in srgb, #28887E 12%, transparent);
  --ijs-verd-edge: color-mix(in srgb, #28887E 34%, transparent);
}
"""

_STATIC_RULES_STR: str = """
/* Figures align in a column only with tabular numerals. */
[data-testid="stMetricValue"], .ijs-figure, .ijs-pulse-value {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}
/* Metrics become plates: hairline, flat, square-ish. */
[data-testid="stMetric"] {
  background: var(--ijs-plate);
  border: 1px solid var(--ijs-rule);
  border-radius: 3px;
  padding: 14px 16px;
}
[data-testid="stMetricLabel"] {
  text-transform: uppercase;
  letter-spacing: .09em;
  font-size: .72rem;
  font-weight: 700;
  color: var(--ijs-muted);
}
h1, h2, h3 { letter-spacing: -.015em; }
/* A brass rule marks a section without shouting. */
h2 {
  border-top: 1px solid var(--ijs-rule);
  padding-top: .7rem;
}
.ijs-kicker {
  text-transform: uppercase;
  letter-spacing: .16em;
  font-size: .68rem;
  font-weight: 800;
  color: var(--ijs-brass);
  margin: 0 0 .35rem 0;
}
.ijs-plate {
  background: var(--ijs-plate);
  border: 1px solid var(--ijs-rule);
  border-radius: 3px;
  padding: 18px 20px;
}
.ijs-pulse-value {
  font-size: 2.4rem;
  font-weight: 700;
  letter-spacing: -.03em;
  line-height: 1.05;
  color: var(--ijs-ink);
  margin: .1rem 0 .1rem 0;
}
.ijs-pulse-note { font-size: .8rem; color: var(--ijs-muted); }
.ijs-minis {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--ijs-rule-soft);
}
.ijs-mini-label {
  display: block;
  font-size: .66rem;
  text-transform: uppercase;
  letter-spacing: .1em;
  font-weight: 700;
  color: var(--ijs-faint);
}
.ijs-mini-value {
  display: block;
  margin-top: 3px;
  font-size: 1.02rem;
  font-weight: 650;
  color: var(--ijs-ink);
  font-variant-numeric: tabular-nums;
}
.ijs-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  margin: 2px 0 4px 0;
}
.ijs-chip {
  font-size: .72rem;
  font-weight: 600;
  padding: 4px 9px;
  border-radius: 2px;
  color: var(--ijs-verd);
  background: var(--ijs-verd-wash);
  border: 1px solid var(--ijs-verd-edge);
  font-variant-numeric: tabular-nums;
}
.ijs-chip-warn {
  color: var(--ijs-brass);
  background: var(--ijs-brass-wash);
  border-color: var(--ijs-brass-edge);
}
/* ---- The concept's furniture, adapted to what Streamlit allows.
   The prototypes are one hand-tuned document; these are the pieces
   of them that survive being driven by real data. ---- */
.ijs-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 9px 0 11px 0;
  border-bottom: 1px solid var(--ijs-rule);
  margin-bottom: 6px;
}
.ijs-crumb { font-size: .78rem; color: var(--ijs-muted); }
.ijs-crumb b { color: var(--ijs-ink); font-weight: 650; }
.ijs-topmeta { display: flex; gap: 6px; flex-wrap: wrap; }
.ijs-pill {
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .04em;
  padding: 4px 8px;
  border-radius: 2px;
  border: 1px solid var(--ijs-rule);
  color: var(--ijs-muted);
  background: var(--ijs-plate);
}
.ijs-pill-on {
  color: var(--ijs-brass);
  background: var(--ijs-brass-wash);
  border-color: var(--ijs-brass-edge);
}
/* The brand mark. A drawn ring rather than a logo file, so it
   cannot go missing and needs no asset pipeline. */
.ijs-brand { display: flex; gap: 11px; align-items: center; }
.ijs-mark {
  width: 38px;
  height: 38px;
  border-radius: 3px;
  background: linear-gradient(135deg, var(--ijs-brass), #6d4711);
  display: grid;
  place-items: center;
  flex: none;
}
.ijs-mark:before {
  content: "";
  width: 15px;
  height: 15px;
  border: 2px solid #fff7ea;
  border-top-color: transparent;
  border-radius: 50%;
  transform: rotate(-30deg);
}
.ijs-brand-name {
  font-size: .82rem;
  font-weight: 700;
  line-height: 1.2;
  color: var(--ijs-ink);
}
.ijs-brand-sub {
  display: block;
  margin-top: 2px;
  font-size: .62rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ijs-faint);
}
/* The plan capsule. The one thing a reader four screens deep
   should never have to go looking for. */
.ijs-capsule {
  margin: 14px 0 4px 0;
  padding: 12px 13px;
  border-radius: 3px;
  border: 1px solid var(--ijs-rule);
  background: var(--ijs-plate);
}
.ijs-capsule-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.ijs-capsule-name {
  font-size: .78rem;
  font-weight: 700;
  color: var(--ijs-ink);
}
.ijs-live {
  font-size: .58rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ijs-verd);
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.ijs-live:before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ijs-verd);
  box-shadow: 0 0 0 3px var(--ijs-verd-wash);
}
.ijs-capsule-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}
.ijs-capsule-meta span {
  font-size: .6rem;
  padding: 3px 6px;
  border-radius: 2px;
  border: 1px solid var(--ijs-rule);
  color: var(--ijs-muted);
  background: var(--ijs-plate);
}
/* Question cards: the concept's main way in. */
.ijs-quest {
  background: var(--ijs-plate);
  border: 1px solid var(--ijs-rule);
  border-radius: 3px;
  padding: 17px 17px 14px 17px;
  min-height: 168px;
  transition: transform .16s ease, border-color .16s ease;
}
.ijs-quest:hover {
  transform: translateY(-3px);
  border-color: var(--ijs-brass-edge);
}
.ijs-quest-icon {
  width: 34px;
  height: 34px;
  border-radius: 3px;
  display: grid;
  place-items: center;
  font-size: 1rem;
  background: var(--ijs-brass-wash);
  border: 1px solid var(--ijs-brass-edge);
}
.ijs-quest h4 {
  margin: 13px 0 5px 0;
  font-size: .95rem;
  font-weight: 700;
  color: var(--ijs-ink);
}
.ijs-quest p {
  margin: 0;
  font-size: .78rem;
  line-height: 1.55;
  color: var(--ijs-muted);
}
/* The goal meter, which the pulse grows when a target exists. */
.ijs-goal { margin-top: 15px; }
.ijs-goal-top {
  display: flex;
  justify-content: space-between;
  font-size: .7rem;
  color: var(--ijs-muted);
  margin-bottom: 6px;
}
.ijs-goal-top b { color: var(--ijs-ink); }
.ijs-track {
  height: 8px;
  border-radius: 2px;
  background: var(--ijs-sunk);
  border: 1px solid var(--ijs-rule);
  overflow: hidden;
}
.ijs-fill {
  height: 100%;
  background: linear-gradient(
    90deg,
    var(--ijs-brass),
    color-mix(in srgb, #A9762F 62%, transparent)
  );
}
/* Provenance: what kind of number this is. */
.ijs-prov {
  display: inline-block;
  font-size: .62rem;
  font-weight: 700;
  letter-spacing: .05em;
  padding: 4px 8px;
  border-radius: 2px;
  color: var(--ijs-verd);
  background: var(--ijs-verd-wash);
  border: 1px solid var(--ijs-verd-edge);
}
.ijs-pulse-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 2px;
}
.ijs-pulse-head .ijs-kicker { margin: 0; }
/* The flash. Fades in, holds, fades out, and takes no space when
   it is gone - a banner that stays would become furniture and stop
   being noticed, which is the opposite of what a confirmation is
   for. Motion is skipped for readers who ask for reduced motion. */
.ijs-flash {
  border: 1px solid var(--ijs-brass-edge);
  border-left: 3px solid var(--ijs-brass);
  background: var(--ijs-brass-wash);
  border-radius: 3px;
  padding: 11px 15px;
  margin: 4px 0 10px 0;
  font-size: .86rem;
  color: var(--ijs-ink);
  animation: ijs-flash-cycle 5.2s ease-in-out forwards;
}
.ijs-flash b { color: var(--ijs-brass); }
.ijs-flash-next {
  display: block;
  margin-top: 4px;
  font-size: .78rem;
  color: var(--ijs-muted);
}
@keyframes ijs-flash-cycle {
  0% { opacity: 0; transform: translateY(-4px); }
  8% { opacity: 1; transform: translateY(0); }
  82% { opacity: 1; transform: translateY(0); }
  100% {
    opacity: 0;
    transform: translateY(-2px);
    margin: 0;
    padding: 0 15px;
    height: 0;
    border-width: 0 0 0 3px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ijs-flash { animation: none; }
}
/* Streamlit hangs a chain icon off every heading. It looks like a
   disclosure and is not one - it copies a deep link - so a reader
   hunting for the hidden detail clicks it and gets nothing. Hidden
   here, and the things that genuinely expand carry the affordance
   below instead. */
[data-testid="stHeaderActionElements"] { display: none !important; }
h1 > a, h2 > a, h3 > a, h4 > a, h5 > a { display: none !important; }
/* A disclosure that looks like one: a chevron that turns, and a
   label that says what opening it will show. */
[data-testid="stExpander"] details {
  border: 1px solid var(--ijs-rule);
  border-radius: 3px;
  background: var(--ijs-plate);
}
[data-testid="stExpander"] summary {
  font-weight: 650;
  color: var(--ijs-ink);
}
[data-testid="stExpander"] summary:hover {
  color: var(--ijs-brass);
}
.ijs-more {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: .74rem;
  font-weight: 700;
  letter-spacing: .04em;
  color: var(--ijs-verd);
  background: var(--ijs-verd-wash);
  border: 1px solid var(--ijs-verd-edge);
  border-radius: 2px;
  padding: 3px 9px;
  margin: 2px 0 6px 0;
}
/* Drawn, not typed. This mark was a Unicode escape until a
   shell heredoc read its backslash-25 as an octal escape and
   left byte 0x15 in the stylesheet, so the affordance that
   says "this opens" rendered as a control character. A border
   triangle carries no character at all and cannot be mangled
   by anything that rewrites this file. */
.ijs-more:after {
  content: "";
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid currentColor;
  margin-top: 2px;
}
/* Trust strip: the quiet claim that the work is inspectable. */
.ijs-trust {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 12px 16px;
  border: 1px solid var(--ijs-rule);
  border-radius: 3px;
  background: var(--ijs-sunk);
}
.ijs-trust span { font-size: .74rem; color: var(--ijs-muted); }
/* Every analytical screen ends with one of these. A chart with no
   sentence under it has told the reader nothing they can act on. */
.ijs-insight {
  background: var(--ijs-sunk);
  border: 1px solid var(--ijs-rule);
  border-left: 3px solid var(--ijs-brass);
  border-radius: 3px;
  padding: 14px 18px;
  margin: 6px 0 2px 0;
}
.ijs-insight-title {
  text-transform: uppercase;
  letter-spacing: .14em;
  font-size: .66rem;
  font-weight: 800;
  color: var(--ijs-brass);
  margin-bottom: .35rem;
}
.ijs-insight-body {
  font-size: .92rem;
  line-height: 1.55;
  color: var(--ijs-ink);
  margin: 0;
}
</style>"""


def _stylesheet_str() -> str:
    """Build the stylesheet.

    Takes no theme, because it needs none: every colour resolves
    against the surface it lands on. That is the whole point of the
    scheme and the reason this function lost its argument.

    Returns:
        str: A `<style>` element.
    """
    return f"{_TOKEN_RULES_STR}{_STATIC_RULES_STR}"


def install_chrome() -> None:
    """Apply the surface to this page.

    Brief:
        Called on every rerun, deliberately. Streamlit rebuilds the
        document from scratch each time, so a "only inject once"
        guard would style the first paint and leave every
        subsequent one bare.

    Arguments:
        None.

    Returns:
        None: The stylesheet is injected.

    Warning:
        Must run after `st.set_page_config` and before the first
        component, or the first paint is unstyled.
    """
    st.markdown(_stylesheet_str(), unsafe_allow_html=True)


def render_kicker(label_str: str) -> None:
    """Draw the small-caps brass mark that opens a section."""
    st.markdown(
        f"<p class='ijs-kicker'>{escape(label_str)}</p>",
        unsafe_allow_html=True,
    )


def render_insight(body_str: str, title_str: str = "") -> None:
    """Say what a result means, in one sentence.

    Brief:
        The component that turns a chart into an answer. Every
        analytical screen should end with one; a reader left with
        only a graph has to do the interpreting themselves, which
        is the work they came here to have done.

    Arguments:
        body_str (str): The sentence. Plain language, no jargon.
        title_str (str): Override for the default mark.

    Returns:
        None: The card is rendered.

    Warning:
        Escapes its body, so a plan name carrying an angle bracket
        cannot inject markup into the page.
    """
    mark_str = title_str or "What this means"
    st.markdown(
        f"<div class='ijs-insight'>"
        f"<div class='ijs-insight-title'>{escape(mark_str)}</div>"
        f"<p class='ijs-insight-body'>{escape(body_str)}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_assumption_bar(chip_tuple: tuple) -> None:
    """Show every assumption behind the figures on this screen.

    Brief:
        Always visible, never in an expander. A projection whose
        assumptions are one click away is a projection most readers
        will take as a forecast.

    Arguments:
        chip_tuple (tuple): `(text, is_warning)` pairs.

    Returns:
        None: The bar is rendered.
    """
    chip_list = []
    for chip_pair in chip_tuple:
        body_str, is_warning_bool = chip_pair
        class_str = (
            "ijs-chip ijs-chip-warn"
            if is_warning_bool
            else "ijs-chip"
        )
        chip_list.append(
            f"<span class='{class_str}'>{escape(body_str)}</span>"
        )
    st.markdown(
        f"<div class='ijs-chips'>{''.join(chip_list)}</div>",
        unsafe_allow_html=True,
    )


def _goal_meter_str(goal_tuple: tuple) -> str:
    """Draw the funded-percentage track, when a goal exists.

    Brief:
        Clamped at a hundred percent for the bar while the label
        keeps saying the true figure, so a plan that overshoots
        reads as "138% funded" rather than as a bar spilling out
        of its own track.

    Arguments:
        goal_tuple (tuple): `(label, percent)` or empty.

    Returns:
        str: The meter's markup, or an empty string.
    """
    if not goal_tuple:
        return ""
    label_str, percent_float = goal_tuple
    width_float = max(0.0, min(100.0, float(percent_float)))
    return (
        "<div class='ijs-goal'><div class='ijs-goal-top'>"
        f"<span>{escape(label_str)}</span>"
        f"<b>{percent_float:.0f}% funded</b></div>"
        "<div class='ijs-track'>"
        f"<div class='ijs-fill' style='width:{width_float:.1f}%'>"
        "</div></div></div>"
    )


def _minis_str(mini_tuple: tuple) -> str:
    """Draw the pulse's row of secondary figures."""
    if not mini_tuple:
        return ""
    mini_list = [
        f"<div><span class='ijs-mini-label'>{escape(mini[0])}"
        f"</span><span class='ijs-mini-value'>{escape(mini[1])}"
        f"</span></div>"
        for mini in mini_tuple
    ]
    return f"<div class='ijs-minis'>{''.join(mini_list)}</div>"


def render_plan_pulse(
    headline_str: str,
    note_str: str,
    mini_tuple: tuple,
    label_str: str = "Plan pulse",
    provenance_str: str = "",
    goal_tuple: tuple = (),
) -> None:
    """Show where the plan stands, in one plate.

    Brief:
        The product's signature. One figure large enough to be the
        answer, the note that keeps it honest, the secondary
        numbers that stop it being read as a promise, and a
        provenance chip saying what kind of number it is.

    Arguments:
        headline_str (str): The figure, already formatted.
        note_str (str): What the figure is, and what it is not.
        mini_tuple (tuple): `(label, value)` pairs, at most four.
        label_str (str): Mark above the plate.
        provenance_str (str): What kind of figure this is, e.g.
            "deterministic · nominal". Never decorative - a reader
            has to be able to tell a projection from a simulation
            from a replay without leaving the plate.
        goal_tuple (tuple): `(label, percent)` for the meter.

    Returns:
        None: The plate is rendered.

    Warning:
        Formats nothing. Every figure arrives already run through
        `formatting.py`, so that lakh and crore grouping is decided
        in one place rather than in each screen that shows a total.
    """
    minis_str = _minis_str(mini_tuple)
    provenance_html_str = (
        f"<span class='ijs-prov'>{escape(provenance_str)}</span>"
        if provenance_str
        else ""
    )
    st.markdown(
        f"<div class='ijs-plate'><div class='ijs-pulse-head'>"
        f"<p class='ijs-kicker'>{escape(label_str)}</p>"
        f"{provenance_html_str}</div>"
        f"<div class='ijs-pulse-value'>{escape(headline_str)}</div>"
        f"<div class='ijs-pulse-note'>{escape(note_str)}</div>"
        f"{minis_str}{_goal_meter_str(goal_tuple)}</div>",
        unsafe_allow_html=True,
    )


def render_top_bar(
    screen_str: str,
    meta_tuple: tuple = (),
) -> None:
    """Draw the utility bar the concept puts above every screen.

    Brief:
        Breadcrumb on the left, plan state on the right. Its job is
        the one the prototype gave it: a reader several screens
        deep should never have to wonder which plan they are
        looking at or how deep the current view goes.

    Arguments:
        screen_str (str): Name of the current screen.
        meta_tuple (tuple): `(text, is_active)` pills for the right.

    Returns:
        None: The bar is rendered.
    """
    pill_list = [
        f"<span class='ijs-pill"
        f"{' ijs-pill-on' if is_active_bool else ''}'>"
        f"{escape(body_str)}</span>"
        for body_str, is_active_bool in meta_tuple
    ]
    st.markdown(
        "<div class='ijs-topbar'>"
        "<div class='ijs-crumb'>Investment Journey › "
        f"<b>{escape(screen_str)}</b></div>"
        f"<div class='ijs-topmeta'>{''.join(pill_list)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_brand_mark(
    name_str: str,
    tagline_str: str,
) -> None:
    """Draw the product mark at the top of the console.

    Brief:
        The mark is a drawn ring rather than an image, so it needs
        no asset pipeline and cannot arrive broken.

    Arguments:
        name_str (str): Product name.
        tagline_str (str): One short line beneath it.

    Returns:
        None: The mark is rendered.
    """
    st.markdown(
        "<div class='ijs-brand'><div class='ijs-mark'></div>"
        f"<div><div class='ijs-brand-name'>{escape(name_str)}"
        f"</div><span class='ijs-brand-sub'>"
        f"{escape(tagline_str)}</span></div></div>",
        unsafe_allow_html=True,
    )


def render_plan_capsule(
    name_str: str,
    status_str: str,
    meta_tuple: tuple,
) -> None:
    """Show which plan is loaded, always, in the console.

    Arguments:
        name_str (str): Plan name.
        status_str (str): Short state word, e.g. "saved".
        meta_tuple (tuple): Short facts about the plan.

    Returns:
        None: The capsule is rendered.
    """
    chip_list = [
        f"<span>{escape(body_str)}</span>"
        for body_str in meta_tuple
    ]
    st.markdown(
        "<div class='ijs-capsule'><div class='ijs-capsule-top'>"
        f"<span class='ijs-capsule-name'>{escape(name_str)}</span>"
        f"<span class='ijs-live'>{escape(status_str)}</span></div>"
        f"<div class='ijs-capsule-meta'>{''.join(chip_list)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_question_card(
    icon_str: str,
    question_str: str,
    body_str: str,
) -> None:
    """Draw one way in, phrased as the reader's own question.

    Brief:
        The concept leads with the question rather than the tool,
        because nobody arrives wanting a simulator; they arrive
        wanting to know whether they will have enough.

    Arguments:
        icon_str (str): Leading glyph for the tile.
        question_str (str): The question, in the reader's words.
        body_str (str): What the screen behind it does.

    Returns:
        None: The card is rendered.
    """
    st.markdown(
        f"<div class='ijs-quest'><div class='ijs-quest-icon'>"
        f"{escape(icon_str)}</div>"
        f"<h4>{escape(question_str)}</h4>"
        f"<p>{escape(body_str)}</p></div>",
        unsafe_allow_html=True,
    )


def render_trust_strip(claim_tuple: tuple) -> None:
    """State what is inspectable about the figures above it.

    Arguments:
        claim_tuple (tuple): Short claims, each already true.

    Returns:
        None: The strip is rendered.

    Warning:
        Every claim here is checked by the test suite somewhere
        else. A trust strip making a claim nothing enforces is
        worse than no strip at all.
    """
    item_list = [
        f"<span>✓ {escape(body_str)}</span>"
        for body_str in claim_tuple
    ]
    st.markdown(
        f"<div class='ijs-trust'>{''.join(item_list)}</div>",
        unsafe_allow_html=True,
    )


def render_flash(body_str: str, next_step_str: str = "") -> None:
    """Announce what just changed, then get out of the way.

    Brief:
        Shown after an action that alters what is on screen without
        moving anything the reader was looking at. A click with no
        visible consequence reads as a click that did not work.

    Arguments:
        body_str (str): What happened. `**bold**` is honoured.
        next_step_str (str): What the reader can now do.

    Returns:
        None: The flash is rendered.

    Warning:
        Escapes every part before re-adding the bold, so a plan
        name carrying an angle bracket cannot inject markup.
    """
    part_list = body_str.split("**")
    rebuilt_str = "".join(
        escape(part_str)
        if index_int % 2 == 0
        else f"<b>{escape(part_str)}</b>"
        for index_int, part_str in enumerate(part_list)
    )
    next_html_str = (
        f"<span class='ijs-flash-next'>{escape(next_step_str)}"
        "</span>"
        if next_step_str
        else ""
    )
    st.markdown(
        f"<div class='ijs-flash'>{rebuilt_str}{next_html_str}"
        "</div>",
        unsafe_allow_html=True,
    )


def render_disclosure_hint(label_str: str) -> None:
    """Mark the thing below as something worth opening.

    Brief:
        Streamlit's own heading anchor is a chain icon that copies
        a link, which reads as "there is more here" and delivers
        nothing. It is hidden by the stylesheet; this is what says
        "there is more here" and means it.

    Arguments:
        label_str (str): What opening it reveals, in a few words.

    Returns:
        None: The hint is rendered.
    """
    st.markdown(
        f"<span class='ijs-more'>{escape(label_str)}</span>",
        unsafe_allow_html=True,
    )
