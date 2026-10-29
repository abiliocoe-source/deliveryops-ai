"""DeliveryOps AI - dispatch board. Run: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

import ui
from deliveryops.data import REQUIRED_COLUMNS, generate_synthetic, validate
from deliveryops.export import to_csv, to_markdown_report
from deliveryops.insights import build_insights, llm_available, llm_summary
from deliveryops.metrics import add_late_flag, compute_kpis, kpis_by_category, kpis_over_time
from deliveryops.savings import estimate_savings

st.set_page_config(page_title="Dispatch board · DeliveryOps", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"),
                   layout="wide")
ui.inject_css()

# ---- data source -----------------------------------------------------------
with st.sidebar:
    st.header("Order feed")
    upload = st.file_uploader("Orders CSV", type="csv")
    st.caption("Required columns: " + ", ".join(REQUIRED_COLUMNS))
    st.download_button("Download fictional sample CSV", to_csv(generate_synthetic()), "sample_orders.csv", "text/csv")

if upload is not None:
    try:
        raw = pd.read_csv(upload)
    except Exception as exc:  # unreadable / not a CSV
        ui.notice("error", "Feed rejected at the pass.", f"This file is not readable as CSV: {exc}")
        st.stop()
    source, synthetic = f"file {upload.name}", False
else:
    raw, source, synthetic = generate_synthetic(), "demo feed", True

df, report = validate(raw)
if not report.ok:
    for e in report.errors:
        ui.notice("error", "Feed rejected at the pass.", e)
    ui.notice("empty", "Nothing to plate yet.", "Fix the file and upload it again, or remove it to use the demo feed.")
    st.stop()

ui.board(source, report.rows_valid, report.rows_in, synthetic)
if upload is not None:
    ui.notice("ok", "Feed accepted.", f"{report.rows_valid:,} valid orders.")
for w in report.warnings:
    ui.notice("warn", "Sent back to the kitchen:", w)

# ---- filters and targets -----------------------------------------------------
with st.sidebar:
    st.header("Filters")
    cats = sorted(df["category"].unique())
    chosen = st.multiselect("Category", cats, default=cats)
    dmin, dmax = df["order_date"].min().date(), df["order_date"].max().date()
    rng = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    freq = st.radio("Time bucket", ["D", "W", "M"], index=1, horizontal=True,
                    format_func=lambda f: {"D": "Day", "W": "Week", "M": "Month"}[f])
    st.header("Service targets")
    late_target = st.number_input("Late rate target (%)", 0.0, 100.0, 10.0, 0.5) / 100
    cancel_target = st.number_input("Cancel rate target (%)", 0.0, 100.0, 5.0, 0.5) / 100
    st.caption("Traffic light: on target ≤ target, watch ≤ 1.5× target, off target above.")

start, end = (rng[0], rng[-1]) if isinstance(rng, (tuple, list)) and rng else (dmin, dmax)
view = df[df["category"].isin(chosen) & df["order_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
if view.empty:
    ui.notice("empty", "Empty rail.", "No orders match these filters. Widen the dates or add categories.")
    st.stop()

kpis, by_cat, ts = compute_kpis(view), kpis_by_category(view), kpis_over_time(view, freq)

tab_dash, tab_ins, tab_save = st.tabs(["Dashboard", "Insights", "Time saved"])

with tab_dash:
    st.markdown(f"<div class='hero'>{ui.hero(kpis, ts, freq, late_target)}{ui.kpi_grid(kpis, ts, freq, cancel_target)}</div>",
                unsafe_allow_html=True)
    st.markdown("<div class='note'>Δ compares the last bucket with the one before; a partial last bucket can look off. "
                "Sparklines show the same bucketed series.</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>LATE RATE OVER TIME</div>", unsafe_allow_html=True)
    st.plotly_chart(ui.late_timeline(ts, late_target, freq), width="stretch", config={"displayModeBar": False})
    left, right = st.columns([3, 1.2])
    with left:
        st.markdown("<div class='section-title'>BY CATEGORY</div>", unsafe_allow_html=True)
        st.markdown(ui.category_table(by_cat), unsafe_allow_html=True)
    with right:
        st.markdown("<div class='section-title'>WORST TICKET</div>", unsafe_allow_html=True)
        st.markdown(ui.coupon(view), unsafe_allow_html=True)

with tab_ins:
    insights = build_insights(kpis, by_cat, ts)
    mode = "LLM available: optional summary below" if llm_available() else "Local rules, no API key"
    st.markdown(f"<div class='note'>Mode: {mode}. Rules read only the computed indicators; a hypothesis is never a cause.</div>",
                unsafe_allow_html=True)
    if llm_available() and st.button("Write LLM summary"):
        text = llm_summary(insights)
        st.write(text or "Summary rejected: it used numbers that are not in the evidence. Showing rules only.")
    if not insights:
        ui.notice("empty", "Quiet board.", "Not enough orders in this view to say anything useful.")
    else:
        ui.insight_list(insights)
    st.divider()
    c1, c2 = st.columns(2)
    c1.download_button("Export report (Markdown)", to_markdown_report(kpis, by_cat, insights, source),
                       "deliveryops_report.md", "text/markdown")
    c2.download_button("Export filtered orders (CSV)", to_csv(add_late_flag(view)), "filtered_orders.csv", "text/csv")

with tab_save:
    st.markdown("<div class='notice warn'><b>ESTIMATE.</b><br>Built only from the assumptions below. Not a measured result.</div>",
                unsafe_allow_html=True)
    a, b = st.columns(2)
    opm = a.number_input("Orders per month", 0, 1_000_000, 2000)
    mins = a.number_input("Manual minutes per order (reports, follow-up)", 0.0, 600.0, 3.0)
    cov = b.slider("Share of that work automated", 0.0, 1.0, 0.5)
    cost = b.number_input("Hourly cost", 0.0, 10_000.0, 25.0)
    res = estimate_savings(opm, mins, cov, cost)
    st.markdown(f"<div class='kpis'><div class='kpi'><div class='kpi-label'>HOURS SAVED / MONTH</div>"
                f"<div class='kpi-num'>{res['hours_saved_per_month']:,.1f}<small>h</small></div></div>"
                f"<div class='kpi'><div class='kpi-label'>COST SAVED / MONTH</div>"
                f"<div class='kpi-num'>{res['cost_saved_per_month']:,.2f}</div></div>"
                f"<div class='kpi wide'><div class='kpi-label'>HOURS SAVED / YEAR</div>"
                f"<div class='kpi-num'>{res['hours_saved_per_year']:,.1f}<small>h</small></div></div></div>",
                unsafe_allow_html=True)
