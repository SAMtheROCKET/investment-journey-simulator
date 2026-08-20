from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# =========================
# Formatting (₹ + Indian style)
# =========================
RUPEE = "₹"

def indian_commas(num: float) -> str:
    n = int(round(num))
    s = str(abs(n))
    if len(s) <= 3:
        out = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        out = ",".join(reversed(parts)) + "," + last3
    return ("-" if n < 0 else "") + out

def fmt_rupee(num: float) -> str:
    return f"{RUPEE}{indian_commas(num)}"

def inr_compact(num: float) -> str:
    n = float(num)
    sign = "-" if n < 0 else ""
    n = abs(n)
    crore = 10_000_000
    lakh = 100_000
    thousand = 1_000
    if n >= crore:
        return f"{sign}{RUPEE}{n/crore:.2f}Cr"
    if n >= lakh:
        return f"{sign}{RUPEE}{n/lakh:.2f}L"
    if n >= thousand:
        return f"{sign}{RUPEE}{n/thousand:.2f}K"
    return f"{sign}{RUPEE}{indian_commas(n)}"


# =========================
# Core math
# =========================
def monthly_rate_from_annual(annual_percent: float) -> float:
    """Effective monthly rate from annual effective rate (decimal). annual_percent can be negative."""
    R = annual_percent / 100.0
    return (1.0 + R) ** (1.0 / 12.0) - 1.0

def months_between(start: date, end: date) -> int:
    """Number of whole month boundaries between two dates (end >= start)."""
    return (end.year - start.year) * 12 + (end.month - start.month)

def simulate_sip_series(
    sip_monthly: float,
    annual_return_percent: float,
    years_horizon: int,
    sip_timing_start_of_month: bool,
    portfolio_start: date,
    fund_start: date,
    stepup_enabled: bool,
    stepup_percent_per_year: float,
) -> dict:
    """
    Month-by-month simulation over the full horizon.
    - Contributions begin at fund_start (if later than portfolio_start).
    - Step-up is applied yearly from fund_start (0th year uses base SIP).
    - annual_return_percent is net (already adjusted for expense).
    """
    total_months = years_horizon * 12
    i = monthly_rate_from_annual(annual_return_percent)

    offset = max(0, months_between(portfolio_start, fund_start))  # month index where SIP starts
    balance = 0.0
    invested = 0.0

    invested_series = []
    fv_series = []

    for m in range(total_months):
        # Determine contribution for this month
        contrib = 0.0
        if m >= offset:
            months_since_start = m - offset
            if stepup_enabled:
                year_index = months_since_start // 12
                contrib = sip_monthly * ((1.0 + stepup_percent_per_year / 100.0) ** year_index)
            else:
                contrib = sip_monthly

        invested += contrib

        if sip_timing_start_of_month:
            balance = (balance + contrib) * (1.0 + i)
        else:
            balance = balance * (1.0 + i) + contrib

        invested_series.append(invested)
        fv_series.append(balance)

    return {
        "months": total_months,
        "monthly_rate": i,
        "invested_series": invested_series,
        "fv_series": fv_series,
        "invested_final": invested_series[-1] if invested_series else 0.0,
        "fv_final": fv_series[-1] if fv_series else 0.0,
        "gain_final": (fv_series[-1] - invested_series[-1]) if fv_series else 0.0,
        "offset_months": offset,
    }

def net_return_simple(gross_return_percent: float, expense_percent: float) -> float:
    """
    Approximation used by many planners:
      net ≈ gross - expense
    """
    return gross_return_percent - expense_percent

def real_return_from_nominal(nominal_percent: float, inflation_percent: float) -> float:
    """
    Real annual return from nominal & inflation (Fisher approximation exact in multiplicative form):
      (1+real) = (1+nominal) / (1+inflation)
    """
    nominal = nominal_percent / 100.0
    infl = inflation_percent / 100.0
    if (1.0 + infl) <= 0:
        # pathological; but keep safe
        return nominal_percent
    real = (1.0 + nominal) / (1.0 + infl) - 1.0
    return real * 100.0


# =========================
# Plot builder (Pro-style)
# =========================
def build_subplot_figure(
    x_years,
    portfolio_invested,
    portfolio_fv,
    names,
    invested_vals,
    gain_vals,
    total_vals,
    title,
):
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "xy"}, {"type": "domain"}],
               [{"type": "domain"}, {"type": "domain"}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
        subplot_titles=(
            "Growth (Total Portfolio)",
            "Invested Split",
            "Gains Split",
            "Total FV Split",
        )
    )

    # Line traces (clean hover, professional template)
    fig.add_trace(
        go.Scatter(
            x=x_years, y=portfolio_invested,
            mode="lines",
            name="Total Invested",
            hovertemplate="Years: %{x:.2f}<br>Invested: %{customdata}<extra></extra>",
            customdata=[fmt_rupee(v) for v in portfolio_invested],
            line=dict(width=3),
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=x_years, y=portfolio_fv,
            mode="lines",
            name="Total Future Value",
            hovertemplate="Years: %{x:.2f}<br>Future Value: %{customdata}<extra></extra>",
            customdata=[fmt_rupee(v) for v in portfolio_fv],
            line=dict(width=3),
        ),
        row=1, col=1
    )

    fig.update_xaxes(title_text="Years", row=1, col=1)
    fig.update_yaxes(title_text=f"Amount ({RUPEE})", row=1, col=1)

    # Donuts with labels in hover only (cleaner look)
    def donut(labels, values, hover_text, hole=0.55):
        return go.Pie(
            labels=labels,
            values=values,
            hole=hole,
            textinfo="percent",
            hovertemplate="%{label}<br>%{customdata}<extra></extra>",
            customdata=hover_text,
            sort=False,
            direction="clockwise",
            marker=dict(line=dict(width=1)),
            showlegend=False
        )

    fig.add_trace(
        donut(names, invested_vals, [f"{fmt_rupee(v)} ({inr_compact(v)})" for v in invested_vals]),
        row=1, col=2
    )
    fig.add_trace(
        donut(names, gain_vals, [f"{fmt_rupee(v)} ({inr_compact(v)})" for v in gain_vals]),
        row=2, col=1
    )
    fig.add_trace(
        donut(names, total_vals, [f"{fmt_rupee(v)} ({inr_compact(v)})" for v in total_vals]),
        row=2, col=2
    )

    fig.update_layout(
        template="plotly_white",
        height=900,
        title=title,
        title_x=0.02,
        margin=dict(t=90, l=30, r=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.02),
        font=dict(size=14),
    )
    return fig


# =========================
# Streamlit App
# =========================
st.set_page_config(page_title="SIP Portfolio Dashboard (Pro)", layout="wide")
st.title("📊 SIP Portfolio Dashboard — Pro")

with st.sidebar:
    st.header("Global Settings")

    years = st.slider("Investment Horizon (years)", 1, 50, 10, 1)
    sip_timing = st.radio("SIP Timing", ["Start of Month", "End of Month"], index=0)
    sip_start_of_month = (sip_timing == "Start of Month")

    portfolio_start = st.date_input("Portfolio Start Date", value=date.today())

    st.divider()
    st.subheader("Step-up SIP")
    stepup_enabled = st.toggle("Enable Step-up SIP", value=False)
    stepup_percent = st.number_input("Step-up % per year", min_value=0.0, max_value=100.0, value=10.0, step=0.5, disabled=not stepup_enabled)

    st.divider()
    st.subheader("Inflation (for Real Returns section)")
    inflation_percent = st.number_input("Inflation % per year", min_value=-5.0, max_value=25.0, value=6.0, step=0.5)

    st.divider()
    st.subheader("Start Dates")
    stagger_enabled = st.toggle("Allow different SIP start dates per fund", value=False)
    st.caption("If OFF, all funds start at the Portfolio Start Date.")


# -------------------------
# Dynamic funds table (add/remove)
# -------------------------
if "funds_df" not in st.session_state:
    st.session_state.funds_df = pd.DataFrame([
        {"MF Name": "Nifty 50 Index", "SIP / month": 1500, "Return % (gross)": 12.0, "Expense %": 0.20, "Fund Start": portfolio_start},
        {"MF Name": "PPFAS Flexi Cap", "SIP / month": 2000, "Return % (gross)": 11.0, "Expense %": 0.75, "Fund Start": portfolio_start},
        {"MF Name": "Tech Fund",       "SIP / month": 3000, "Return % (gross)": 13.0, "Expense %": 0.90, "Fund Start": portfolio_start},
    ])

st.subheader("Mutual Funds (Dynamic)")
c_add, c_rm, c_hint = st.columns([1, 1, 2])

with c_add:
    if st.button("➕ Add Fund"):
        st.session_state.funds_df = pd.concat([
            st.session_state.funds_df,
            pd.DataFrame([{
                "MF Name": f"MF-{len(st.session_state.funds_df)+1}",
                "SIP / month": 1000,
                "Return % (gross)": 12.0,
                "Expense %": 0.50,
                "Fund Start": portfolio_start
            }])
        ], ignore_index=True)

with c_rm:
    if st.button("➖ Remove Last Fund") and len(st.session_state.funds_df) > 1:
        st.session_state.funds_df = st.session_state.funds_df.iloc[:-1].reset_index(drop=True)

with c_hint:
    st.caption("Edit directly in the table. Add/remove funds anytime. Expense is applied as: net = gross − expense (approx).")

df = st.session_state.funds_df.copy()

# If stagger disabled: force all fund start = portfolio start (but keep the column visible)
if not stagger_enabled:
    df["Fund Start"] = portfolio_start

edited_df = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "MF Name": st.column_config.TextColumn(required=True),
        "SIP / month": st.column_config.NumberColumn(min_value=0, step=100),
        "Return % (gross)": st.column_config.NumberColumn(step=0.1),
        "Expense %": st.column_config.NumberColumn(min_value=0.0, step=0.05, help="Annual expense ratio (%)"),
        "Fund Start": st.column_config.DateColumn(help="When SIP begins for this fund"),
    }
)

st.session_state.funds_df = edited_df

# -------------------------
# Compute nominal results
# -------------------------
funds = []
for _, row in edited_df.iterrows():
    name = str(row["MF Name"]).strip() or "Unnamed MF"
    sip = float(row["SIP / month"]) if not pd.isna(row["SIP / month"]) else 0.0
    gross = float(row["Return % (gross)"]) if not pd.isna(row["Return % (gross)"]) else 0.0
    exp = float(row["Expense %"]) if not pd.isna(row["Expense %"]) else 0.0
    fstart = row["Fund Start"]
    if isinstance(fstart, pd.Timestamp):
        fstart = fstart.date()
    if not isinstance(fstart, date):
        fstart = portfolio_start

    net = net_return_simple(gross, exp)

    funds.append({
        "name": name,
        "sip": sip,
        "gross": gross,
        "expense": exp,
        "net": net,
        "start": fstart
    })

total_months = years * 12
x_years = [(k + 1) / 12 for k in range(total_months)]

results_nom = []
portfolio_invested_nom = [0.0] * total_months
portfolio_fv_nom = [0.0] * total_months

for f in funds:
    r = simulate_sip_series(
        sip_monthly=f["sip"],
        annual_return_percent=f["net"],
        years_horizon=years,
        sip_timing_start_of_month=sip_start_of_month,
        portfolio_start=portfolio_start,
        fund_start=f["start"],
        stepup_enabled=stepup_enabled,
        stepup_percent_per_year=stepup_percent if stepup_enabled else 0.0,
    )
    r.update(f)
    results_nom.append(r)

    for idx in range(total_months):
        portfolio_invested_nom[idx] += r["invested_series"][idx]
        portfolio_fv_nom[idx] += r["fv_series"][idx]

portfolio_invested_final_nom = portfolio_invested_nom[-1]
portfolio_fv_final_nom = portfolio_fv_nom[-1]
portfolio_gain_final_nom = portfolio_fv_final_nom - portfolio_invested_final_nom

names = [r["name"] for r in results_nom]
invested_vals = [r["invested_final"] for r in results_nom]
gain_vals = [r["gain_final"] for r in results_nom]
total_vals = [r["fv_final"] for r in results_nom]

title_nom = (
    f"Nominal (Net = Gross − Expense) | "
    f"Total FV: {fmt_rupee(portfolio_fv_final_nom)} ({inr_compact(portfolio_fv_final_nom)})"
)

fig_nom = build_subplot_figure(
    x_years=x_years,
    portfolio_invested=portfolio_invested_nom,
    portfolio_fv=portfolio_fv_nom,
    names=names,
    invested_vals=invested_vals,
    gain_vals=gain_vals,
    total_vals=total_vals,
    title=title_nom
)

# =========================
# Layout: KPI Cards + Charts
# =========================
k1, k2, k3, k4 = st.columns([1.2, 1.2, 1.2, 1.4])
k1.metric("Total Invested", fmt_rupee(portfolio_invested_final_nom), inr_compact(portfolio_invested_final_nom))
k2.metric("Total Gain", fmt_rupee(portfolio_gain_final_nom), inr_compact(portfolio_gain_final_nom))
k3.metric("Total Future Value", fmt_rupee(portfolio_fv_final_nom), inr_compact(portfolio_fv_final_nom))

avg_net = sum([f["net"] for f in funds]) / max(1, len(funds))
k4.caption("Assumptions")
k4.write(f"- SIP timing: **{sip_timing}**")
k4.write(f"- Step-up: **{'ON' if stepup_enabled else 'OFF'}**" + (f" @ **{stepup_percent:.2f}%/yr**" if stepup_enabled else ""))
k4.write(f"- Avg net return (rough): **{avg_net:.2f}% p.a.**")

st.plotly_chart(fig_nom, use_container_width=True)

# =========================
# Pro summary table
# =========================
st.subheader("Portfolio Summary (Nominal)")
summary_rows = []
for r in results_nom:
    summary_rows.append({
        "MF": r["name"],
        "SIP / month": fmt_rupee(r["sip"]),
        "Start": r["start"].isoformat(),
        "Gross %": f"{r['gross']:.2f}",
        "Expense %": f"{r['expense']:.2f}",
        "Net % (approx)": f"{r['net']:.2f}",
        "Invested": f"{fmt_rupee(r['invested_final'])} ({inr_compact(r['invested_final'])})",
        "Gain": f"{fmt_rupee(r['gain_final'])} ({inr_compact(r['gain_final'])})",
        "Total FV": f"{fmt_rupee(r['fv_final'])} ({inr_compact(r['fv_final'])})",
        "Start Offset (months)": r["offset_months"],
    })

st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

# =========================
# Inflation-adjusted section (REAL RETURNS)
# =========================
st.divider()
st.header("Inflation-adjusted (Real Returns) — Separate Section")

# For the real section:
# - Keep invested amounts same
# - Apply real return = (1+nominal)/(1+inflation) - 1
results_real = []
portfolio_invested_real = [0.0] * total_months
portfolio_fv_real = [0.0] * total_months

for f in funds:
    real_net = real_return_from_nominal(f["net"], inflation_percent)
    r = simulate_sip_series(
        sip_monthly=f["sip"],
        annual_return_percent=real_net,
        years_horizon=years,
        sip_timing_start_of_month=sip_start_of_month,
        portfolio_start=portfolio_start,
        fund_start=f["start"],
        stepup_enabled=stepup_enabled,
        stepup_percent_per_year=stepup_percent if stepup_enabled else 0.0,
    )
    r.update(f)
    r["real_net"] = real_net
    results_real.append(r)

    for idx in range(total_months):
        portfolio_invested_real[idx] += r["invested_series"][idx]
        portfolio_fv_real[idx] += r["fv_series"][idx]

portfolio_invested_final_real = portfolio_invested_real[-1]
portfolio_fv_final_real = portfolio_fv_real[-1]
portfolio_gain_final_real = portfolio_fv_final_real - portfolio_invested_final_real

names_r = [r["name"] for r in results_real]
invested_vals_r = [r["invested_final"] for r in results_real]
gain_vals_r = [r["gain_final"] for r in results_real]
total_vals_r = [r["fv_final"] for r in results_real]

title_real = (
    f"Real Returns (Inflation-adjusted) | Inflation: {inflation_percent:.2f}% p.a. | "
    f"Total FV: {fmt_rupee(portfolio_fv_final_real)} ({inr_compact(portfolio_fv_final_real)})"
)

fig_real = build_subplot_figure(
    x_years=x_years,
    portfolio_invested=portfolio_invested_real,
    portfolio_fv=portfolio_fv_real,
    names=names_r,
    invested_vals=invested_vals_r,
    gain_vals=gain_vals_r,
    total_vals=total_vals_r,
    title=title_real
)

k1, k2, k3 = st.columns(3)
k1.metric("Real Total Invested", fmt_rupee(portfolio_invested_final_real), inr_compact(portfolio_invested_final_real))
k2.metric("Real Total Gain", fmt_rupee(portfolio_gain_final_real), inr_compact(portfolio_gain_final_real))
k3.metric("Real Total Future Value", fmt_rupee(portfolio_fv_final_real), inr_compact(portfolio_fv_final_real))

st.plotly_chart(fig_real, use_container_width=True)

st.subheader("Portfolio Summary (Real Returns)")
summary_real_rows = []
for r in results_real:
    summary_real_rows.append({
        "MF": r["name"],
        "SIP / month": fmt_rupee(r["sip"]),
        "Start": r["start"].isoformat(),
        "Net % (nominal approx)": f"{r['net']:.2f}",
        "Real net %": f"{r['real_net']:.2f}",
        "Invested": f"{fmt_rupee(r['invested_final'])} ({inr_compact(r['invested_final'])})",
        "Gain (real)": f"{fmt_rupee(r['gain_final'])} ({inr_compact(r['gain_final'])})",
        "Total FV (real)": f"{fmt_rupee(r['fv_final'])} ({inr_compact(r['fv_final'])})",
    })

st.dataframe(pd.DataFrame(summary_real_rows), use_container_width=True, hide_index=True)

st.caption(
    "Note: Expense ratio handling uses a common approximation: net return ≈ gross return − expense. "
    "This is a planning tool (not a guarantee)."
)
