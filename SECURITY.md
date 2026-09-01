# Security policy

This is financial software. Three different kinds of report matter
here, and only one of them is what "security" usually means.

## Reporting

Use **GitHub's private vulnerability reporting** on this repository
(Security → Report a vulnerability). It reaches the maintainer
without the report being public first.

If that is unavailable to you, open an issue that says only that
you have something to report and asks for a private channel. Do not
put the details in a public issue.

Expect an acknowledgement within seven days.

## 1. A vulnerability

Anything that lets code run, files be read or written, or data leave
the machine, from an input a user could plausibly supply. The
scenario JSON import is the obvious surface: it is parsed from a
file a stranger may have written. Report these privately.

## 2. A number that is wrong

**Treat a wrong figure as seriously as a vulnerability**, because
someone may act on it. This does not need to be private, and a
public issue is usually better because the working is worth
reading.

What makes a report actionable:

- the **saved scenario JSON**, which reproduces the plan exactly;
- which screen you were on;
- what you expected, and how you worked it out - a spreadsheet, a
  statute, a published example, or arithmetic on paper;
- what the tool showed instead.

The engine is deterministic, so a scenario file plus a version
number reproduces any figure it has ever produced. Please use that;
it turns "the number looks wrong" into something that can be fixed
in an afternoon.

Statutory parameters are dated and sourced in
[docs/SOURCES.md](docs/SOURCES.md). If a rate changed in a Budget
and this project has not caught up, that is a defect and worth
reporting as one.

## 3. Privacy

This program does not transmit anything. It has no telemetry, no
analytics, no account, no network calls to any service of ours, and
no NAV feed. Everything you type stays in the browser session and
in whatever files you choose to save.

Two caveats worth knowing:

- a **saved scenario JSON contains your figures** - amounts, dates,
  and the plan itself. Attaching one to a public issue publishes
  them. Round them or edit them first if that matters to you;
- when it runs on a **hosted deployment**, the host sees the same
  traffic any web application generates. Run it locally if that is
  a concern: `pip install -e .` and `streamlit run
  streamlit_app.py`.

If you find anything that contradicts the paragraph above - a
request leaving the machine that should not - report it privately
under section 1.

## What this is not

Not investment advice, and not a licensed advisory service. A
report that a projection did not come true is not a defect; a
report that the arithmetic does not do what it says is.
