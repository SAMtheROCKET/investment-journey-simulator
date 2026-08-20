import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

RUPEE = "₹"

# -----------------------------
# Indian money formatting
# -----------------------------
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
    lakh  = 100_000
    thousand = 1_000
    if n >= crore:
        return f"{sign}{RUPEE}{n/crore:.2f}Cr"
    if n >= lakh:
        return f"{sign}{RUPEE}{n/lakh:.2f}L"
    if n >= thousand:
        return f"{sign}{RUPEE}{n/thousand:.2f}K"
    return f"{sign}{RUPEE}{indian_commas(n)}"

# -----------------------------
# SIP simulation (month-by-month)
# -----------------------------
def monthly_rate_from_annual(R_percent: float) -> float:
    R = R_percent / 100.0
    return (1 + R) ** (1/12) - 1

def simulate_sip(P: float, R_percent: float, horizon_years: float, annuity_due: bool = True):
    i = monthly_rate_from_annual(R_percent)
    m = int(round(12 * horizon_years))
    balance = 0.0
    invested = 0.0
    invested_series, fv_series = [], []

    for _month in range(1, m + 1):
        contrib = P
        invested += contrib

        # annuity_due=True => invest at start of month then earn return
        if annuity_due:
            balance = (balance + contrib) * (1 + i)
        else:
            balance = balance * (1 + i) + contrib

        invested_series.append(invested)
        fv_series.append(balance)

    invested_final = invested_series[-1] if invested_series else 0.0
    fv_final = fv_series[-1] if fv_series else 0.0
    gain_final = fv_final - invested_final

    return {
        "months": m,
        "monthly_rate": i,
        "invested_series": invested_series,
        "fv_series": fv_series,
        "invested_final": invested_final,
        "fv_final": fv_final,
        "gain_final": gain_final,
    }

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="SIP Portfolio Dashboard", layout="wide")
st.title("📊 SIP Portfolio Dashboard (3 Mutual Funds)")

with st.sidebar:
    st.header("Portfolio Inputs")
    years = st.slider("Years", min_value=1, max_value=40, value=10, step=1)
    timing = st.radio("SIP Timing", ["Start of Month", "End of Month"], index=0)
    annuity_due = True if timing == "Start of Month" else False

    st.divider()
    st.subheader("Mutual Fund 1")
    mf1_name = st.text_input("Name (MF-1)", value="MF-1")
    mf1_sip = st.number_input("SIP / month (MF-1)", min_value=0, value=1500, step=100)
    mf1_r = st.number_input("Annual return % (MF-1)", value=12.0, step=0.1, format="%.2f")

    st.divider()
    st.subheader("Mutual Fund 2")
    mf2_name = st.text_input("Name (MF-2)", value="MF-2")
    mf2_sip = st.number_input("SIP / month (MF-2)", min_value=0, value=2000, step=100)
    mf2_r = st.number_input("Annual return % (MF-2)", value=11.0, step=0.1, format="%.2f")

    st.divider()
    st.subheader("Mutual Fund 3")
    mf3_name = st.text_input("Name (MF-3)", value="MF-3")
    mf3_sip = st.number_input("SIP / month (MF-3)", min_value=0, value=3000, step=100)
    mf3_r = st.number_input("Annual return % (MF-3)", value=13.0, step=0.1, format="%.2f")

mfs = [
    {"name": mf1_name.strip() or "MF-1", "sip": float(mf1_sip), "r": float(mf1_r)},
    {"name": mf2_name.strip() or "MF-2", "sip": float(mf2_sip), "r": float(mf2_r)},
    {"name": mf3_name.strip() or "MF-3", "sip": float(mf3_sip), "r": float(mf3_r)},
]

# -----------------------------
# Compute results
# -----------------------------
results = []
months_total = int(round(12 * years))

for mf in mfs:
    res = simulate_sip(mf["sip"], mf["r"], years, annuity_due)
    res["name"] = mf["name"]
    res["sip"] = mf["sip"]
    res["r"] = mf["r"]
    results.append(res)

portfolio_invested = [0.0] * months_total
portfolio_fv = [0.0] * months_total

for r in results:
    for idx in range(months_total):
        portfolio_invested[idx] += r["invested_series"][idx]
        portfolio_fv[idx] += r["fv_series"][idx]

portfolio_invested_final = portfolio_invested[-1]
portfolio_fv_final = portfolio_fv[-1]
portfolio_gain_final = portfolio_fv_final - portfolio_invested_final

x_years = [(k + 1) / 12 for k in range(months_total)]

names = [r["name"] for r in results]
invested_vals = [r["invested_final"] for r in results]
gain_vals = [r["gain_final"] for r in results]
total_vals = [r["fv_final"] for r in results]

# -----------------------------
# Subplot figure
# -----------------------------
fig = make_subplots(
    rows=2, cols=2,
    specs=[[{"type": "xy"}, {"type": "domain"}],
           [{"type": "domain"}, {"type": "domain"}]],
    subplot_titles=(
        f"Portfolio Growth — Total: {fmt_rupee(portfolio_fv_final)} ({inr_compact(portfolio_fv_final)})",
        f"Invested Split — {fmt_rupee(portfolio_invested_final)}",
        f"Gains Split — {fmt_rupee(portfolio_gain_final)}",
        f"Total FV Split — {fmt_rupee(portfolio_fv_final)}",
    )
)

fig.add_trace(
    go.Scatter(
        x=x_years, y=portfolio_invested, mode="lines", name="Total Invested",
        customdata=[fmt_rupee(v) for v in portfolio_invested],
        hovertemplate="Years: %{x:.2f}<br>Total Invested: %{customdata}<extra></extra>",
    ),
    row=1, col=1
)
fig.add_trace(
    go.Scatter(
        x=x_years, y=portfolio_fv, mode="lines", name="Total Future Value",
        customdata=[fmt_rupee(v) for v in portfolio_fv],
        hovertemplate="Years: %{x:.2f}<br>Total Future Value: %{customdata}<extra></extra>",
    ),
    row=1, col=1
)
fig.update_xaxes(title_text="Years", row=1, col=1)
fig.update_yaxes(title_text=f"Amount ({RUPEE})", row=1, col=1)

fig.add_trace(
    go.Pie(
        labels=names, values=invested_vals, hole=0.42,
        text=[f"{fmt_rupee(v)} ({inr_compact(v)})" for v in invested_vals],
        textinfo="label+percent",
        hovertemplate="%{label}<br>%{text}<extra></extra>",
        showlegend=False
    ),
    row=1, col=2
)

fig.add_trace(
    go.Pie(
        labels=names, values=gain_vals, hole=0.42,
        text=[f"{fmt_rupee(v)} ({inr_compact(v)})" for v in gain_vals],
        textinfo="label+percent",
        hovertemplate="%{label}<br>%{text}<extra></extra>",
        showlegend=False
    ),
    row=2, col=1
)

fig.add_trace(
    go.Pie(
        labels=names, values=total_vals, hole=0.42,
        text=[f"{fmt_rupee(v)} ({inr_compact(v)})" for v in total_vals],
        textinfo="label+percent",
        hovertemplate="%{label}<br>%{text}<extra></extra>",
        showlegend=False
    ),
    row=2, col=2
)

fig.update_layout(
    height=850,
    title=f"3-MF SIP Portfolio Dashboard — {years} years — SIP timing: {timing}",
    margin=dict(t=90, l=40, r=40, b=40),
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Portfolio Summary
# -----------------------------
st.subheader("Portfolio Summary")

c1, c2, c3 = st.columns(3)
c1.metric("Total Invested", f"{fmt_rupee(portfolio_invested_final)}", inr_compact(portfolio_invested_final))
c2.metric("Total Gain", f"{fmt_rupee(portfolio_gain_final)}", inr_compact(portfolio_gain_final))
c3.metric("Total Future Value", f"{fmt_rupee(portfolio_fv_final)}", inr_compact(portfolio_fv_final))

st.subheader("Breakdown by Mutual Fund")

table_rows = []
for r in results:
    table_rows.append({
        "MF": r["name"],
        "SIP / month": f"{fmt_rupee(r['sip'])}",
        "Return p.a.": f"{r['r']:.2f}%",
        "Invested": f"{fmt_rupee(r['invested_final'])} ({inr_compact(r['invested_final'])})",
        "Gain": f"{fmt_rupee(r['gain_final'])} ({inr_compact(r['gain_final'])})",
        "Total FV": f"{fmt_rupee(r['fv_final'])} ({inr_compact(r['fv_final'])})",
    })

st.table(table_rows)
