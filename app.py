"""DeliveryOps AI - overview for a small delivery kitchen. Run: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

import ui
from deliveryops.data import REQUIRED_COLUMNS, generate_synthetic, validate
from deliveryops.export import to_csv, to_markdown_report
from deliveryops.insights import build_insights, llm_available, llm_summary
from deliveryops.metrics import add_late_flag, compute_kpis, kpis_by_category, kpis_over_time
from deliveryops.savings import estimate_savings

st.set_page_config(page_title="Overview · DeliveryOps", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"), layout="wide")
ui.inject_css()


def finding(ts, by_cat, target, freq) -> str:
    """The one finding, built from the computed series and table (never typed in)."""
    parts = []
    t = ts.dropna(subset=["late_rate"]).tail(12)
    if len(t):
        n = int((t["late_rate"] > target).sum())
        parts.append(f"<b>{n} of the last {len(t)} {ui.WORD[freq]}s</b> ran above the {target * 100:.0f}% late-rate target.")
    c = by_cat[by_cat["total_orders"] >= 20].dropna(subset=["late_rate"])
    if len(c) >= 2:
        top = c.sort_values("late_rate", ascending=False).iloc[0]
        parts.append(f"<b>{ui.esc(top['category'])}</b> is the slowest category, {top['late_rate'] * 100:.1f}% late.")
    return " ".join(parts) or "Not enough orders in this view to name a finding."


# ---- sidebar: product, feed ---------------------------------------------------------
brand_slot = st.sidebar.container()  # filled once we know the scope; stays at the top
with st.sidebar:
    st.subheader("Order feed")
    upload = st.file_uploader("Orders CSV", type="csv")
    st.caption("Columns: " + ", ".join(REQUIRED_COLUMNS))
    st.download_button("Download fictional sample", to_csv(generate_synthetic()), "sample_orders.csv", "text/csv")

if upload is not None:
    try:
        raw = pd.read_csv(upload)
    except Exception as exc:  # unreadable or not a CSV
        with brand_slot:
            ui.brand("Uploaded file")
        ui.note("error", "File rejected.", f"It could not be read as CSV: {exc}")
        st.stop()
    source, synthetic = upload.name, False
else:
    raw, source, synthetic = generate_synthetic(), "Demo feed", True
with brand_slot:
    ui.brand("Fictional demo kitchen" if synthetic else source)

df, report = validate(raw)
if not report.ok:
    for e in report.errors:
        ui.note("error", "File rejected.", e)
    ui.note("empty", "Nothing to show yet.", "Fix the file and upload it again, or remove it to use the demo feed.")
    st.stop()

# ---- sidebar: filters and targets -----------------------------------------------------
with st.sidebar:
    st.subheader("Filters")
    cats = sorted(df["category"].unique())
    chosen = st.multiselect("Category", cats, default=cats)
    dmin, dmax = df["order_date"].min().date(), df["order_date"].max().date()
    rng = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    freq = st.radio("Group by", ["D", "W", "M"], index=1, horizontal=True, format_func=lambda f: {"D": "Day", "W": "Week", "M": "Month"}[f])
    st.subheader("Service targets")
    late_target = st.number_input("Late rate, %", 0.0, 100.0, 10.0, 0.5) / 100
    cancel_target = st.number_input("Cancel rate, %", 0.0, 100.0, 5.0, 0.5) / 100
    st.caption("On target is at or under the target. Watch is up to 1.5 times it.")

start, end = (rng[0], rng[-1]) if isinstance(rng, (tuple, list)) and rng else (dmin, dmax)
view = df[df["category"].isin(chosen) & df["order_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
if view.empty:
    ui.note("empty", "No orders match.", "Widen the dates or add a category in the sidebar.")
    st.stop()

kpis, by_cat, ts = compute_kpis(view), kpis_by_category(view), kpis_over_time(view, freq)
insights = build_insights(kpis, by_cat, ts)

# ---- title row ------------------------------------------------------------------------
stamp = f"{source} · {report.rows_valid:,} of {report.rows_in:,} rows valid · {view['order_date'].min():%d %b %Y} to {view['order_date'].max():%d %b %Y}"
t_col, act_col = st.columns([5, 2.4])
with t_col:
    ui.title("Overview", finding(ts, by_cat, late_target, freq), stamp + (" · fictional data" if synthetic else ""))
with act_col:
    a_col, b_col = st.columns(2)
    a_col.download_button("Report (.md)", to_markdown_report(kpis, by_cat, insights, source), "deliveryops_report.md", "text/markdown", width="stretch")
    b_col.download_button("Orders (.csv)", to_csv(add_late_flag(view)), "filtered_orders.csv", "text/csv", width="stretch")
for w in report.warnings:
    ui.note("warn", "Rows removed.", w)

tab_over, tab_ins, tab_save = st.tabs(["Overview", "Insights", "Time saved"])

with tab_over:
    st.markdown(ui.kpi_strip(kpis, ts, freq, late_target, cancel_target), unsafe_allow_html=True)
    metric = st.session_state.get("metric") or "Late rate"
    target = {"Late rate": late_target, "Cancel rate": cancel_target}.get(metric)
    with st.container(border=True):
        h, c = st.columns([2, 3])
        h.markdown(f"<div class='card-h'><h3>{metric} by {ui.WORD[freq]}</h3></div>", unsafe_allow_html=True)
        c.segmented_control("Metric", list(ui.METRICS), default="Late rate", key="metric", label_visibility="collapsed")
        st.plotly_chart(ui.trend_figure(ts, metric, freq, target), width="stretch", config={"displayModeBar": False})
        st.markdown("<div class='footnote'>The last bucket can be partial, which makes it look lower.</div>", unsafe_allow_html=True)
    left, right = st.columns([2.3, 1])
    with left, st.container(border=True):
        st.markdown(f"<div class='card-h'><h3>By category</h3><span class='sub'>{len(view):,} orders in view</span></div>", unsafe_allow_html=True)
        st.markdown(ui.category_table(by_cat), unsafe_allow_html=True)
    with right:
        st.markdown(ui.coupon(view), unsafe_allow_html=True)

with tab_ins:
    mode = "LLM summary available below." if llm_available() else "Rules only, no LLM connected."
    st.markdown(f"<div class='footnote' style='margin:16px 0 8px'>{mode} A hypothesis is never presented as a cause.</div>", unsafe_allow_html=True)
    if llm_available() and st.button("Write LLM summary"):
        text = llm_summary(insights)
        st.write(text or "Summary rejected: it used numbers that are not in the evidence. Showing rules only.")
    if insights:
        ui.insights(insights)
    else:
        ui.note("empty", "Nothing to report.", "Too few orders in this view to say anything useful.")

with tab_save:
    ui.note("warn", "Estimate.", "Built only from the assumptions below. Not a measured result.")
    a, b = st.columns(2)
    opm = a.number_input("Orders per month", 0, 1_000_000, 2000)
    mins = a.number_input("Manual minutes per order (reports, follow-up)", 0.0, 600.0, 3.0)
    cov = b.slider("Share of that work automated", 0.0, 1.0, 0.5)
    cost = b.number_input("Hourly cost", 0.0, 10_000.0, 25.0)
    st.markdown(ui.savings_strip(estimate_savings(opm, mins, cov, cost)), unsafe_allow_html=True)
