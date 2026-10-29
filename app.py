"""DeliveryOps AI - Streamlit dashboard. Run: streamlit run app.py"""
import pandas as pd
import plotly.express as px
import streamlit as st

from deliveryops.data import REQUIRED_COLUMNS, generate_synthetic, validate
from deliveryops.export import to_csv, to_markdown_report
from deliveryops.insights import build_insights, llm_available, llm_summary
from deliveryops.metrics import add_late_flag, compute_kpis, kpis_by_category, kpis_over_time
from deliveryops.savings import estimate_savings

st.set_page_config(page_title="DeliveryOps AI", page_icon="🛵", layout="wide")
st.title("DeliveryOps AI")

# ---- data source -----------------------------------------------------------
with st.sidebar:
    st.header("Data")
    upload = st.file_uploader("Upload orders CSV", type="csv")
    st.caption("Required columns: " + ", ".join(REQUIRED_COLUMNS))
    st.download_button("Download fictional sample CSV", to_csv(generate_synthetic()),
                       "sample_orders.csv", "text/csv")

if upload is not None:
    try:
        raw = pd.read_csv(upload)
    except Exception as exc:  # unreadable / not a CSV
        st.error(f"Could not read the file as CSV: {exc}")
        st.stop()
    source = f"uploaded file ({upload.name})"
else:
    raw, source = generate_synthetic(), "SYNTHETIC / FICTIONAL demo data (no real orders)"

df, report = validate(raw)
for e in report.errors:
    st.error(e)
if not report.ok:
    st.info("Fix the file and upload it again, or remove it to use the demo data.")
    st.stop()
for w in report.warnings:
    st.warning(w)
st.caption(f"Source: {source} · {report.rows_valid} valid of {report.rows_in} rows")

# ---- filters -----------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    cats = sorted(df["category"].unique())
    chosen = st.multiselect("Category", cats, default=cats)
    dmin, dmax = df["order_date"].min().date(), df["order_date"].max().date()
    rng = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    freq = st.radio("Time granularity", ["D", "W", "M"], index=1, horizontal=True)

start, end = (rng[0], rng[-1]) if isinstance(rng, (tuple, list)) and rng else (dmin, dmax)
view = df[df["category"].isin(chosen) & df["order_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
if view.empty:
    st.info("No orders match the current filters. Widen the date range or pick more categories.")
    st.stop()

kpis, by_cat, ts = compute_kpis(view), kpis_by_category(view), kpis_over_time(view, freq)


def pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def num(x):
    return "n/a" if x is None else f"{x:.1f}"


tab_dash, tab_ins, tab_save = st.tabs(["Dashboard", "Insights", "Savings estimate"])

with tab_dash:
    c = st.columns(6)
    c[0].metric("Orders", kpis["total_orders"])
    c[1].metric("Late rate", pct(kpis["late_rate"]), help="late / delivered orders")
    c[2].metric("Cancel rate", pct(kpis["cancel_rate"]), help="cancelled / all orders")
    c[3].metric("Avg prep (min)", num(kpis["avg_prep_minutes"]))
    c[4].metric("Avg delivery (min)", num(kpis["avg_delivery_minutes"]))
    c[5].metric("Avg rating", num(kpis["avg_rating"]), help=f"{kpis['rated_orders']} rated orders")
    left, right = st.columns(2)
    left.plotly_chart(px.line(ts, x="period", y="late_rate", markers=True,
                              title="Late rate over time", labels={"late_rate": "late rate"}),
                      width="stretch")
    right.plotly_chart(px.bar(by_cat, x="category", y="late_rate", title="Late rate by category",
                              labels={"late_rate": "late rate"}), width="stretch")
    left.plotly_chart(px.bar(by_cat, x="category", y="cancel_rate", title="Cancel rate by category",
                             labels={"cancel_rate": "cancel rate"}), width="stretch")
    right.plotly_chart(px.line(ts, x="period", y="total_orders", markers=True,
                               title="Orders over time"), width="stretch")
    st.dataframe(by_cat.round(3), width="stretch", hide_index=True)

with tab_ins:
    insights = build_insights(kpis, by_cat, ts)
    mode = "LLM available (optional summary)" if llm_available() else "Local rule-based mode (no API key)"
    st.caption(f"Mode: {mode}. Rules only use the computed indicators; hypotheses are not causal claims.")
    if llm_available() and st.button("Generate LLM summary"):
        text = llm_summary(insights)
        st.write(text or "LLM summary unavailable or rejected (numbers not grounded). Showing rules only.")
    if not insights:
        st.info("Not enough data for insights.")
    for kind, title in [("fact", "Facts"), ("hypothesis", "Hypotheses (unconfirmed)"),
                        ("recommendation", "Recommendations (by impact / effort)")]:
        items = [i for i in insights if i["kind"] == kind]
        if items:
            st.subheader(title)
            for i in items:
                extra = f" · impact {i['impact']}/3, effort {i['effort']}/3" if "impact" in i else ""
                st.markdown(f"- {i['text']}  \n  _Evidence: {i['evidence']}{extra}_")
    st.divider()
    st.download_button("Export report (Markdown)", to_markdown_report(kpis, by_cat, insights, source),
                       "deliveryops_report.md", "text/markdown")
    st.download_button("Export filtered data (CSV)", to_csv(add_late_flag(view)),
                       "filtered_orders.csv", "text/csv")

with tab_save:
    st.caption("ESTIMATE based only on the assumptions you enter. Not a measured result.")
    a, b = st.columns(2)
    opm = a.number_input("Orders per month", 0, 1_000_000, 2000)
    mins = a.number_input("Manual minutes per order (reporting/follow-up)", 0.0, 600.0, 3.0)
    cov = b.slider("Share of that work automated", 0.0, 1.0, 0.5)
    cost = b.number_input("Hourly cost", 0.0, 10_000.0, 25.0)
    res = estimate_savings(opm, mins, cov, cost)
    st.warning(res["label"])
    m = st.columns(3)
    m[0].metric("Hours saved / month", res["hours_saved_per_month"])
    m[1].metric("Cost saved / month", res["cost_saved_per_month"])
    m[2].metric("Hours saved / year", res["hours_saved_per_year"])
