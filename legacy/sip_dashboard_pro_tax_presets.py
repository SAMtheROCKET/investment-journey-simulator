# sip_dashboard_matlab_pro.py
# Run:
#   pip install streamlit plotly pandas
#   streamlit run sip_dashboard_matlab_pro.py

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

RUPEE = "₹"

# =========================
# Formatting: ₹ + Indian commas + compact
# =========================
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
    R = annual_percent / 100.0
    return (1.0 + R) ** (1.0 / 12.0) - 1.0

def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)

def net_return_simple(gross_return_percent: float, expense_percent: float) -> float:
    # planning approximation: net ≈ gross - expense
    return gross_return_percent - expense_percent

def real_return_from_nominal(nominal_percent: float, inflation_percent: float) -> float:
    nominal = nominal_percent / 100.0
    infl = inflation_percent / 100.0
    if (1.0 + infl) <= 0:
        return nominal_percent
    real = (1.0 + nominal) / (1.0 + infl) - 1.0
    return real * 100.0


# =========================
# SIP simulation (series + contrib series for tax lots)
# =========================
def simulate_sip_series(
    sip_monthly: float,
    annual_return_percent: float,
    years_horizon: int,
    sip_timing_start_of_month: bool,
    portfolio_start: date,
    fund_start: date,
    stepup_enabled: bool,
    stepup_percent_per_year: float,
):
    total_months = years_horizon * 12
    i = monthly_rate_from_annual(annual_return_percent)

    offset = max(0, months_between(portfolio_start, fund_start))
    balance = 0.0
    invested = 0.0

    invested_series = []
    fv_series = []
    contrib_series = []

    for m in range(total_months):
        contrib = 0.0
        if m >= offset:
            months_since_start = m - offset
            if stepup_enabled:
                year_index = months_since_start // 12
                contrib = sip_monthly * ((1.0 + stepup_percent_per_year / 100.0) ** year_index)
            else:
                contrib = sip_monthly

        contrib_series.append(contrib)
        invested += contrib

        if sip_timing_start_of_month:
            balance = (balance + contrib) * (1.0 + i)
        else:
            balance = balance * (1.0 + i) + contrib

        invested_series.append(invested)
        fv_series.append(balance)

    invested_final = invested_series[-1] if invested_series else 0.0
    fv_final = fv_series[-1] if fv_series else 0.0

    return {
        "months": total_months,
        "monthly_rate": i,
        "invested_series": invested_series,
        "fv_series": fv_series,
        "contrib_series": contrib_series,
        "invested_final": invested_final,
        "fv_final": fv_final,
        "gain_final": fv_final - invested_final,
        "offset_months": offset,
    }


# =========================
# Tax (lot-wise at final redemption)
# - Taxes apply ONLY on gains, not principal
# - Preset supports: equity (STCG/LTCG + LTCG exemption), debt post-2023 (always STCG slab)
# =========================
def compute_tax_lotwise(
    contrib_series,
    monthly_rate_i: float,
    sip_timing_start_of_month: bool,
    stcg_percent: float,
    ltcg_percent: float,
    ltcg_threshold_months: int,
    exemption_amount: float,
    exemption_scope: str,   # "LTCG_ONLY" or "TOTAL_GAINS"
    always_stcg: bool,
):
    total_months = len(contrib_series)
    stcg_gain = 0.0
    ltcg_gain = 0.0

    for t, contrib in enumerate(contrib_series):
        if contrib <= 0:
            continue

        if sip_timing_start_of_month:
            months_held = total_months - t
        else:
            months_held = total_months - t - 1
        months_held = max(0, months_held)

        fv_lot = contrib * ((1.0 + monthly_rate_i) ** months_held)
        gain_lot = fv_lot - contrib  # ✅ only gains taxed

        if always_stcg:
            stcg_gain += gain_lot
        else:
            if months_held >= ltcg_threshold_months:
                ltcg_gain += gain_lot
            else:
                stcg_gain += gain_lot

    total_gain = stcg_gain + ltcg_gain

    if exemption_scope == "LTCG_ONLY":
        taxable_stcg = max(0.0, stcg_gain)
        taxable_ltcg = max(0.0, ltcg_gain - max(0.0, exemption_amount))
    else:
        taxable_total = max(0.0, total_gain - max(0.0, exemption_amount))
        if total_gain > 0:
            taxable_stcg = taxable_total * (stcg_gain / total_gain)
            taxable_ltcg = taxable_total * (ltcg_gain / total_gain)
        else:
            taxable_stcg = 0.0
            taxable_ltcg = 0.0

    tax = taxable_stcg * (stcg_percent / 100.0) + taxable_ltcg * (ltcg_percent / 100.0)

    return {
        "tax": tax,
        "stcg_gain": stcg_gain,
        "ltcg_gain": ltcg_gain,
        "total_gain": total_gain,
        "taxable_stcg_gain": taxable_stcg,
        "taxable_ltcg_gain": taxable_ltcg,
    }


# =========================
# MATLAB-ish plotting helpers
# =========================
def matlab_grid_axes(fig, row=1, col=1):
    fig.update_xaxes(
        showgrid=True, gridwidth=1,
        showline=True, linewidth=1, mirror=True,
        ticks="outside", ticklen=6,
        minor=dict(showgrid=True, gridwidth=0.5),
        row=row, col=col,
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1,
        showline=True, linewidth=1, mirror=True,
        ticks="outside", ticklen=6,
        minor=dict(showgrid=True, gridwidth=0.5),
        row=row, col=col,
    )
    return fig

def add_matlab_style_growth_traces(fig, x_dates, invested_series, fv_series, contrib_series, row=1, col=1):
    gains_series = [fv - inv for fv, inv in zip(fv_series, invested_series)]

    # Stacked stepped area: Invested
    fig.add_trace(
        go.Scatter(
            x=x_dates,
            y=invested_series,
            name="Invested (Principal)",
            mode="lines",
            line_shape="hv",
            line=dict(width=2.5),
            fill="tozeroy",
            hovertemplate="%{x|%b %Y}<br>Invested: %{customdata}<extra></extra>",
            customdata=[fmt_rupee(v) for v in invested_series],
        ),
        row=row, col=col
    )

    # Stacked stepped area: Gains
    fig.add_trace(
        go.Scatter(
            x=x_dates,
            y=gains_series,
            name="Gains",
            mode="lines",
            line_shape="hv",
            line=dict(width=2.5),
            fill="tonexty",
            hovertemplate="%{x|%b %Y}<br>Gains: %{customdata}<extra></extra>",
            customdata=[fmt_rupee(v) for v in gains_series],
        ),
        row=row, col=col
    )

    # FV outline
    fig.add_trace(
        go.Scatter(
            x=x_dates,
            y=fv_series,
            name="Future Value (Total)",
            mode="lines",
            line_shape="hv",
            line=dict(width=2.5),
            hovertemplate="%{x|%b %Y}<br>Total FV: %{customdata}<extra></extra>",
            customdata=[fmt_rupee(v) for v in fv_series],
        ),
        row=row, col=col
    )

    # Monthly contribution impulses (thin bars on secondary axis concept, but keep same axis for simplicity)
    # This makes step-up jumps very visible.
    fig.add_trace(
        go.Bar(
            x=x_dates,
            y=contrib_series,
            name="Monthly SIP",
            opacity=0.35,
            hovertemplate="%{x|%b %Y}<br>Monthly SIP: %{customdata}<extra></extra>",
            customdata=[fmt_rupee(v) for v in contrib_series],
        ),
        row=row, col=col
    )

    fig.update_xaxes(title_text="Month", row=row, col=col)
    fig.update_yaxes(title_text=f"Amount ({RUPEE})", row=row, col=col)

    fig.update_layout(hovermode="x unified")
    matlab_grid_axes(fig, row=row, col=col)
    return fig


# =========================
# Subplot dashboard figure (MATLAB-ish growth + 3 donuts)
# =========================
def build_dashboard_figure_matlab(
    x_dates,
    portfolio_invested,
    portfolio_fv,
    portfolio_contrib,   # monthly contributions (portfolio-level)
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
        subplot_titles=("MATLAB-style Growth (Monthly Steps)", "Invested Split", "Gains Split", "Total FV Split")
    )

    # Replace top-left panel with MATLAB-ish stepped stacked area + monthly bars
    fig = add_matlab_style_growth_traces(
        fig,
        x_dates=x_dates,
        invested_series=portfolio_invested,
        fv_series=portfolio_fv,
        contrib_series=portfolio_contrib,
        row=1, col=1
    )

    def donut(labels, values, hover_text, hole=0.58):
        return go.Pie(
            labels=labels, values=values, hole=hole,
            textinfo="percent",
            hovertemplate="%{label}<br>%{customdata}<extra></extra>",
            customdata=hover_text,
            sort=False,
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
        barmode="overlay",
        height=950,
        title=title,
        title_x=0.02,
        margin=dict(t=95, l=30, r=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0.02),
        font=dict(size=14),
    )

    return fig


# =========================
# Streamlit App
# =========================
st.set_page_config(page_title="SIP Dashboard (MATLAB-ish)", layout="wide")
st.title("📊 SIP Portfolio Dashboard — MATLAB-ish Time Series + Dynamic Funds + Tax Presets")

with st.sidebar:
    st.header("Global Settings")
    years = st.slider("Investment Horizon (years)", 1, 50, 10, 1)
    sip_timing = st.radio("SIP Timing", ["Start of Month", "End of Month"], index=0)
    sip_start_of_month = (sip_timing == "Start of Month")
    portfolio_start = st.date_input("Portfolio Start Date", value=date.today())

    st.divider()
    st.subheader("Step-up SIP")
    stepup_enabled = st.toggle("Enable Step-up SIP", value=False)
    stepup_percent = st.number_input(
        "Step-up % per year", min_value=0.0, max_value=100.0, value=10.0, step=0.5,
        disabled=not stepup_enabled
    )

    st.divider()
    st.subheader("Inflation (Real section)")
    inflation_percent = st.number_input("Inflation % per year", min_value=-5.0, max_value=25.0, value=6.0, step=0.5)

    st.divider()
    st.subheader("Start Dates")
    stagger_enabled = st.toggle("Allow different SIP start dates per fund", value=False)

    st.divider()
    st.subheader("Slab rate (used by Debt preset)")
    slab_rate_percent = st.number_input("Your slab rate %", min_value=0.0, max_value=60.0, value=30.0, step=0.5)


# Defaults from your requested rule-set (equity preset)
DEFAULT_EQUITY_STCG = 20.0
DEFAULT_EQUITY_LTCG = 12.5
DEFAULT_EQUITY_LTCG_EXEMPT = 125000.0
DEFAULT_EQUITY_LTCG_MONTHS = 12
DEFAULT_EQUITY_EXEMPT_SCOPE = "LTCG_ONLY"
DEFAULT_DEBT_EXEMPT_SCOPE = "TOTAL_GAINS"


# -------------------------
# Dynamic funds table
# -------------------------
if "funds_df" not in st.session_state:
    st.session_state.funds_df = pd.DataFrame([
        {
            "MF Name": "Nifty 50 Index",
            "Fund Type Preset": "Equity-Oriented (Default)",
            "Override Preset?": False,
            "SIP / month": 1500,
            "Return % (gross)": 12.0,
            "Expense %": 0.20,
            "Fund Start": portfolio_start,
            "STCG %": DEFAULT_EQUITY_STCG,
            "LTCG %": DEFAULT_EQUITY_LTCG,
            "LTCG threshold (months)": DEFAULT_EQUITY_LTCG_MONTHS,
            "Exemption (₹)": DEFAULT_EQUITY_LTCG_EXEMPT,
            "Exemption Scope": DEFAULT_EQUITY_EXEMPT_SCOPE,
        },
        {
            "MF Name": "Debt Fund Example",
            "Fund Type Preset": "Debt (post Apr 1, 2023) - slab",
            "Override Preset?": False,
            "SIP / month": 2000,
            "Return % (gross)": 9.0,
            "Expense %": 0.40,
            "Fund Start": portfolio_start,
            "STCG %": slab_rate_percent,
            "LTCG %": 0.0,
            "LTCG threshold (months)": 9999,
            "Exemption (₹)": 0.0,
            "Exemption Scope": DEFAULT_DEBT_EXEMPT_SCOPE,
        },
    ])

st.subheader("Mutual Funds (Dynamic) — Pro + Tax Presets + MATLAB-ish Growth")
c_add, c_rm, c_hint = st.columns([1, 1, 3])

with c_add:
    if st.button("➕ Add Fund"):
        st.session_state.funds_df = pd.concat([
            st.session_state.funds_df,
            pd.DataFrame([{
                "MF Name": f"MF-{len(st.session_state.funds_df) + 1}",
                "Fund Type Preset": "Equity-Oriented (Default)",
                "Override Preset?": False,
                "SIP / month": 1000,
                "Return % (gross)": 12.0,
                "Expense %": 0.50,
                "Fund Start": portfolio_start,
                "STCG %": DEFAULT_EQUITY_STCG,
                "LTCG %": DEFAULT_EQUITY_LTCG,
                "LTCG threshold (months)": DEFAULT_EQUITY_LTCG_MONTHS,
                "Exemption (₹)": DEFAULT_EQUITY_LTCG_EXEMPT,
                "Exemption Scope": DEFAULT_EQUITY_EXEMPT_SCOPE,
            }])
        ], ignore_index=True)

with c_rm:
    if st.button("➖ Remove Last Fund") and len(st.session_state.funds_df) > 1:
        st.session_state.funds_df = st.session_state.funds_df.iloc[:-1].reset_index(drop=True)

with c_hint:
    st.caption(
        "Top-left plot is MATLAB-ish (stepped areas + dense grids + monthly impulses). "
        "Preset fills tax defaults; enable Override to edit tax fields."
    )

df = st.session_state.funds_df.copy()
if not stagger_enabled:
    df["Fund Start"] = portfolio_start

def apply_preset(row: pd.Series) -> pd.Series:
    preset = row.get("Fund Type Preset", "Equity-Oriented (Default)")
    override = bool(row.get("Override Preset?", False))
    if override:
        return row

    if preset == "Equity-Oriented (Default)":
        row["STCG %"] = DEFAULT_EQUITY_STCG
        row["LTCG %"] = DEFAULT_EQUITY_LTCG
        row["LTCG threshold (months)"] = DEFAULT_EQUITY_LTCG_MONTHS
        row["Exemption (₹)"] = DEFAULT_EQUITY_LTCG_EXEMPT
        row["Exemption Scope"] = DEFAULT_EQUITY_EXEMPT_SCOPE
    elif preset == "Debt (post Apr 1, 2023) - slab":
        row["STCG %"] = float(slab_rate_percent)
        row["LTCG %"] = 0.0
        row["LTCG threshold (months)"] = 9999
        row["Exemption (₹)"] = 0.0
        row["Exemption Scope"] = DEFAULT_DEBT_EXEMPT_SCOPE
    # Custom: leave as is
    return row

df = df.apply(apply_preset, axis=1)

edited_df = st.data_editor(
    df,
    width="stretch",
    num_rows="dynamic",
    column_config={
        "MF Name": st.column_config.TextColumn(required=True),
        "Fund Type Preset": st.column_config.SelectboxColumn(
            options=["Equity-Oriented (Default)", "Debt (post Apr 1, 2023) - slab", "Custom"],
            required=True
        ),
        "Override Preset?": st.column_config.CheckboxColumn(help="Turn ON to edit tax fields manually."),
        "SIP / month": st.column_config.NumberColumn(min_value=0, step=100),
        "Return % (gross)": st.column_config.NumberColumn(step=0.1),
        "Expense %": st.column_config.NumberColumn(min_value=0.0, step=0.05),
        "Fund Start": st.column_config.DateColumn(),
        "STCG %": st.column_config.NumberColumn(min_value=0.0, max_value=60.0, step=0.5),
        "LTCG %": st.column_config.NumberColumn(min_value=0.0, max_value=60.0, step=0.5),
        "LTCG threshold (months)": st.column_config.NumberColumn(min_value=1, max_value=120, step=1),
        "Exemption (₹)": st.column_config.NumberColumn(min_value=0, step=10000),
        "Exemption Scope": st.column_config.SelectboxColumn(options=["LTCG_ONLY", "TOTAL_GAINS"]),
    }
)
st.session_state.funds_df = edited_df


# -------------------------
# Build fund configs
# -------------------------
funds = []
for _, row in edited_df.iterrows():
    name = str(row["MF Name"]).strip() or "Unnamed MF"
    sip = float(row.get("SIP / month", 0) or 0)
    gross = float(row.get("Return % (gross)", 0) or 0)
    exp = float(row.get("Expense %", 0) or 0)

    fstart = row.get("Fund Start", portfolio_start)
    if isinstance(fstart, pd.Timestamp):
        fstart = fstart.date()
    if not isinstance(fstart, date):
        fstart = portfolio_start

    preset = row.get("Fund Type Preset", "Equity-Oriented (Default)")
    always_stcg = (preset == "Debt (post Apr 1, 2023) - slab")

    stcg = float(row.get("STCG %", 0) or 0)
    ltcg = float(row.get("LTCG %", 0) or 0)
    ltcg_months = int(row.get("LTCG threshold (months)", 12) or 12)
    exemption = float(row.get("Exemption (₹)", 0) or 0)
    exemption_scope = row.get("Exemption Scope", "LTCG_ONLY")

    net = net_return_simple(gross, exp)

    funds.append({
        "name": name,
        "sip": sip,
        "gross": gross,
        "expense": exp,
        "net": net,
        "start": fstart,
        "preset": preset,
        "always_stcg": always_stcg,
        "stcg": stcg,
        "ltcg": ltcg,
        "ltcg_months": ltcg_months,
        "exemption": exemption,
        "exemption_scope": exemption_scope,
    })


# =========================
# NOMINAL + TAX
# =========================
total_months = years * 12
x_dates = pd.date_range(start=portfolio_start, periods=total_months, freq="MS")

results_nom = []
portfolio_invested_nom = [0.0] * total_months
portfolio_fv_nom = [0.0] * total_months
portfolio_contrib_nom = [0.0] * total_months

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

    tax_info = compute_tax_lotwise(
        contrib_series=r["contrib_series"],
        monthly_rate_i=r["monthly_rate"],
        sip_timing_start_of_month=sip_start_of_month,
        stcg_percent=f["stcg"],
        ltcg_percent=f["ltcg"],
        ltcg_threshold_months=f["ltcg_months"],
        exemption_amount=f["exemption"],
        exemption_scope=f["exemption_scope"],
        always_stcg=f["always_stcg"],
    )

    r.update(f)
    r.update(tax_info)
    r["fv_after_tax"] = max(0.0, r["fv_final"] - r["tax"])
    r["gain_after_tax"] = r["fv_after_tax"] - r["invested_final"]
    results_nom.append(r)

    for idx in range(total_months):
        portfolio_invested_nom[idx] += r["invested_series"][idx]
        portfolio_fv_nom[idx] += r["fv_series"][idx]
        portfolio_contrib_nom[idx] += r["contrib_series"][idx]

portfolio_invested_final_nom = portfolio_invested_nom[-1]
portfolio_fv_final_nom = portfolio_fv_nom[-1]
portfolio_tax_nom = sum(r["tax"] for r in results_nom)
portfolio_fv_after_tax_nom = max(0.0, portfolio_fv_final_nom - portfolio_tax_nom)
portfolio_gain_nom = portfolio_fv_final_nom - portfolio_invested_final_nom

names = [r["name"] for r in results_nom]
invested_vals = [r["invested_final"] for r in results_nom]
gain_vals = [r["gain_final"] for r in results_nom]
total_vals = [r["fv_final"] for r in results_nom]

title_nom = (
    f"Nominal | FV: {fmt_rupee(portfolio_fv_final_nom)} ({inr_compact(portfolio_fv_final_nom)}) "
    f"| Tax: {fmt_rupee(portfolio_tax_nom)} ({inr_compact(portfolio_tax_nom)}) "
    f"| After-tax FV: {fmt_rupee(portfolio_fv_after_tax_nom)} ({inr_compact(portfolio_fv_after_tax_nom)})"
)

fig_nom = build_dashboard_figure_matlab(
    x_dates=x_dates,
    portfolio_invested=portfolio_invested_nom,
    portfolio_fv=portfolio_fv_nom,
    portfolio_contrib=portfolio_contrib_nom,
    names=names,
    invested_vals=invested_vals,
    gain_vals=gain_vals,
    total_vals=total_vals,
    title=title_nom
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Invested", fmt_rupee(portfolio_invested_final_nom), inr_compact(portfolio_invested_final_nom))
k2.metric("Total Gain (pre-tax)", fmt_rupee(portfolio_gain_nom), inr_compact(portfolio_gain_nom))
k3.metric("Total Tax (estimated)", fmt_rupee(portfolio_tax_nom), inr_compact(portfolio_tax_nom))
k4.metric("Total FV (after-tax)", fmt_rupee(portfolio_fv_after_tax_nom), inr_compact(portfolio_fv_after_tax_nom))

st.plotly_chart(fig_nom, width="stretch")

st.subheader("Per-Fund Summary (Nominal + Tax)")
rows = []
for r in results_nom:
    rows.append({
        "MF": r["name"],
        "Preset": r["preset"],
        "SIP / month": fmt_rupee(r["sip"]),
        "Start": r["start"].isoformat(),
        "Gross%": f"{r['gross']:.2f}",
        "Expense%": f"{r['expense']:.2f}",
        "Net% (approx)": f"{r['net']:.2f}",
        "STCG%": f"{r['stcg']:.2f}",
        "LTCG%": f"{r['ltcg']:.2f}",
        "LTCG months": r["ltcg_months"],
        "Exemption": fmt_rupee(r["exemption"]),
        "Exempt scope": r["exemption_scope"],
        "Invested": f"{fmt_rupee(r['invested_final'])} ({inr_compact(r['invested_final'])})",
        "Gain": f"{fmt_rupee(r['gain_final'])} ({inr_compact(r['gain_final'])})",
        "Tax": f"{fmt_rupee(r['tax'])} ({inr_compact(r['tax'])})",
        "After-tax FV": f"{fmt_rupee(r['fv_after_tax'])} ({inr_compact(r['fv_after_tax'])})",
    })
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# =========================
# REAL RETURNS SECTION
# =========================
st.divider()
st.header("Inflation-adjusted (Real Returns) — Separate Section")

results_real = []
portfolio_invested_real = [0.0] * total_months
portfolio_fv_real = [0.0] * total_months
portfolio_contrib_real = [0.0] * total_months

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

    tax_info = compute_tax_lotwise(
        contrib_series=r["contrib_series"],
        monthly_rate_i=r["monthly_rate"],
        sip_timing_start_of_month=sip_start_of_month,
        stcg_percent=f["stcg"],
        ltcg_percent=f["ltcg"],
        ltcg_threshold_months=f["ltcg_months"],
        exemption_amount=f["exemption"],
        exemption_scope=f["exemption_scope"],
        always_stcg=f["always_stcg"],
    )

    r.update(f)
    r["real_net"] = real_net
    r.update(tax_info)
    r["fv_after_tax"] = max(0.0, r["fv_final"] - r["tax"])
    results_real.append(r)

    for idx in range(total_months):
        portfolio_invested_real[idx] += r["invested_series"][idx]
        portfolio_fv_real[idx] += r["fv_series"][idx]
        portfolio_contrib_real[idx] += r["contrib_series"][idx]

portfolio_invested_final_real = portfolio_invested_real[-1]
portfolio_fv_final_real = portfolio_fv_real[-1]
portfolio_tax_real = sum(r["tax"] for r in results_real)
portfolio_fv_after_tax_real = max(0.0, portfolio_fv_final_real - portfolio_tax_real)

names_r = [r["name"] for r in results_real]
invested_vals_r = [r["invested_final"] for r in results_real]
gain_vals_r = [r["gain_final"] for r in results_real]
total_vals_r = [r["fv_final"] for r in results_real]

title_real = (
    f"Real (Inflation-adjusted) | Inflation: {inflation_percent:.2f}% "
    f"| FV: {fmt_rupee(portfolio_fv_final_real)} ({inr_compact(portfolio_fv_final_real)}) "
    f"| Tax: {fmt_rupee(portfolio_tax_real)} ({inr_compact(portfolio_tax_real)}) "
    f"| After-tax FV: {fmt_rupee(portfolio_fv_after_tax_real)} ({inr_compact(portfolio_fv_after_tax_real)})"
)

fig_real = build_dashboard_figure_matlab(
    x_dates=x_dates,
    portfolio_invested=portfolio_invested_real,
    portfolio_fv=portfolio_fv_real,
    portfolio_contrib=portfolio_contrib_real,
    names=names_r,
    invested_vals=invested_vals_r,
    gain_vals=gain_vals_r,
    total_vals=total_vals_r,
    title=title_real
)

a1, a2, a3 = st.columns(3)
a1.metric("Real Invested", fmt_rupee(portfolio_invested_final_real), inr_compact(portfolio_invested_final_real))
a2.metric("Real FV (pre-tax)", fmt_rupee(portfolio_fv_final_real), inr_compact(portfolio_fv_final_real))
a3.metric("Real FV (after-tax)", fmt_rupee(portfolio_fv_after_tax_real), inr_compact(portfolio_fv_after_tax_real))

st.plotly_chart(fig_real, width="stretch")

st.caption(
    "Notes: Net return uses net ≈ gross − expense (planning approximation). "
    "Equity preset uses STCG 20%, LTCG 12.5%, 12-month threshold, and ₹1.25L exemption on LTCG only. "
    "Debt preset (post Apr 1, 2023) is modeled as always STCG at slab rate. "
    "This is a simulator for planning; not a tax/financial guarantee."
)
