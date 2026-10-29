"""Presentation components for DeliveryOps (HTML/SVG strings + one Plotly figure).
No data logic here: everything is computed by the deliveryops package and only formatted."""
import html
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from deliveryops.metrics import add_late_flag

ASSETS = Path(__file__).resolve().parent / "assets"
FREQ_WORD = {"D": "day", "W": "week", "M": "month"}
MONO = "IBM Plex Mono, ui-monospace, Menlo, Consolas, monospace"


def inject_css() -> None:
    st.markdown(f"<style>{(ASSETS / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


def pct(x, digits=1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def num(x, digits=1) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def notice(kind: str, title: str, text: str = "") -> None:
    """kind: error | warn | ok | empty. Always carries a text title, never color alone."""
    st.markdown(f"<div class='notice {kind}'><b>{esc(title)}</b><br>{esc(text)}</div>", unsafe_allow_html=True)


def board(source: str, rows_ok: int, rows_in: int, synthetic: bool) -> None:
    tag = "<span class='tag'>FICTIONAL DATA</span>" if synthetic else ""
    st.markdown(
        f"<div class='board'><span class='name'>DELIVERY<b>OPS</b> AI</span>"
        f"<span class='meta'>{esc(source)} · {rows_ok:,} of {rows_in:,} rows valid{tag}</span></div>",
        unsafe_allow_html=True)


def state_for(value, target):
    """Traffic light for a rate where lower is better. Words + glyph, so color is never the only cue."""
    if value is None:
        return "warn", "▲ NO DATA"
    if value <= target:
        return "ok", "● ON TARGET"
    if value <= target * 1.5:
        return "warn", "▲ WATCH"
    return "bad", "■ OFF TARGET"


def spark(values, w=84, h=24) -> str:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = [(i * (w - 6) / (len(vals) - 1) + 3, h - 4 - (v - lo) / span * (h - 8)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (f"<svg class='spark' width='{w}' height='{h}' viewBox='0 0 {w} {h}' aria-hidden='true'>"
            f"<polyline points='{line}' fill='none' stroke='#16140F' stroke-width='1.5'/>"
            f"<circle cx='{pts[-1][0]:.1f}' cy='{pts[-1][1]:.1f}' r='3' fill='#F26B1D'/></svg>")


def delta(ts, col, freq, unit, scale=1, worse_when_up=True, neutral=False) -> str:
    s = ts[col].dropna()
    if len(s) < 2:
        return "<span class='delta flat'>no earlier period</span>"
    d = (s.iloc[-1] - s.iloc[-2]) * scale
    word = FREQ_WORD[freq]
    if abs(d) < 0.05:
        return f"<span class='delta flat'>= vs prev {word}</span>"
    cls = "flat" if neutral else ("worse" if (d > 0) == worse_when_up else "better")
    arrow = "▲" if d > 0 else "▼"
    return f"<span class='delta {cls}'>{arrow} {d:+.1f} {unit} vs prev {word}</span>"


def hero(kpis, ts, freq, target) -> str:
    cls, word = state_for(kpis["late_rate"], target)
    value = "n/a" if kpis["late_rate"] is None else f"{kpis['late_rate'] * 100:.1f}"
    unit = "" if kpis["late_rate"] is None else "<small>%</small>"
    return (f"<div class='hero-main'><div class='hero-label'>LATE RATE</div>"
            f"<div class='hero-num'>{value}{unit}</div>"
            f"<span class='state {cls}'>{word}</span> "
            f"<span class='hero-sub'>target ≤ {target * 100:.1f}% · {kpis['late_orders']:,} late of "
            f"{kpis['delivered_orders']:,} delivered</span><br>"
            f"{delta(ts, 'late_rate', freq, 'pp', 100)} {spark(list(ts['late_rate']), 360, 64)}</div>")


def kpi_grid(kpis, ts, freq, cancel_target) -> str:
    cls, word = state_for(kpis["cancel_rate"], cancel_target)
    def tile(label, value, unit, col, scale, du, wide=False, worse_up=True, neutral=False, extra=""):
        return (f"<div class='kpi{' wide' if wide else ''}'><div class='kpi-row'><span class='kpi-label'>{label}</span>{extra}</div>"
                f"<div class='kpi-num'>{value}<small>{unit}</small></div>"
                f"<div class='kpi-row'>{delta(ts, col, freq, du, scale, worse_up, neutral)}{spark(list(ts[col]))}</div></div>")
    return ("<div class='kpis'>"
            + tile("CANCEL RATE", num(None if kpis["cancel_rate"] is None else kpis["cancel_rate"] * 100), "%",
                   "cancel_rate", 100, "pp", wide=True, extra=f"<span class='state {cls}'>{word}</span>")
            + tile("ORDERS", f"{kpis['total_orders']:,}", "orders", "total_orders", 1, "orders", neutral=True)
            + tile("AVG RATING", num(kpis["avg_rating"], 2), "/ 5", "avg_rating", 1, "pts", worse_up=False)
            + tile("AVG PREP", num(kpis["avg_prep_minutes"]), "min", "avg_prep_minutes", 1, "min")
            + tile("AVG DELIVERY", num(kpis["avg_delivery_minutes"]), "min", "avg_delivery_minutes", 1, "min")
            + "</div>")


def late_timeline(ts, target, freq) -> go.Figure:
    t = ts.dropna(subset=["late_rate"])
    fig = go.Figure(go.Scatter(x=t["period"], y=t["late_rate"], mode="lines+markers",
                               line=dict(color="#F26B1D", width=2.5), marker=dict(size=6, color="#16140F"),
                               hovertemplate="%{x|%d %b %Y}<br>late rate %{y:.1%}<extra></extra>"))
    fig.add_hline(y=target, line=dict(color="#16140F", width=1, dash="dot"),
                  annotation_text=f"target {target * 100:.0f}%", annotation_position="top left",
                  annotation_font=dict(family=MONO, size=11, color="#16140F"))
    if len(t):
        peak = t.loc[t["late_rate"].idxmax()]
        fig.add_annotation(x=peak["period"], y=peak["late_rate"], ax=-60, ay=-20, showarrow=True,
                           arrowcolor="#16140F", font=dict(family=MONO, size=11, color="#16140F"),
                           text=f"peak {peak['late_rate'] * 100:.1f}% · {FREQ_WORD[freq]} of {peak['period']:%d %b}")
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, font=dict(family=MONO, size=11),
                      paper_bgcolor="#F2F3F0", plot_bgcolor="#FFFFFF", hovermode="x")
    fig.update_yaxes(tickformat=".0%", gridcolor="#CFCBC0", rangemode="tozero", title=None)
    fig.update_xaxes(showgrid=False, linecolor="#16140F", title=None)
    return fig


def category_table(by_cat) -> str:
    rows = by_cat.sort_values("late_rate", ascending=False, na_position="last")
    worst = rows["late_rate"].max()
    body = ""
    for i, (_, r) in enumerate(rows.iterrows()):
        lr = r["late_rate"]
        width = 0 if lr is None or lr != lr else min(100, lr * 100 / (worst or 1))
        flag = " ▲" if i == 0 and lr == worst and lr else ""
        body += (f"<tr{' class=top' if flag else ''}><td>{esc(r['category'])}{flag}</td><td>{int(r['total_orders']):,}</td>"
                 f"<td><span class='bar'><i style='width:{width:.0f}%'></i></span>{pct(lr)}</td>"
                 f"<td>{pct(r['cancel_rate'])}</td><td>{num(r['avg_prep_minutes'])}</td>"
                 f"<td>{num(r['avg_delivery_minutes'])}</td><td>{num(r['avg_rating'], 2)}</td></tr>")
    head = "".join(f"<th>{h}</th>" for h in ["CATEGORY", "ORDERS", "LATE RATE", "CANCEL RATE", "PREP (min)", "DELIVERY (min)", "RATING (/5)"])
    return f"<div class='tbl-wrap'><table class='tbl'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def coupon(view) -> str:
    d = add_late_flag(view)
    late = d[d["is_late"]].copy()
    if late.empty:
        return ("<div class='notice empty'><b>Nothing on the late spike.</b><br>"
                "No late orders in this view, so there is no coupon to print.</div>")
    late["over"] = late["prep_minutes"] + late["delivery_minutes"] - late["promised_minutes"]
    w = late.loc[late["over"].idxmax()]
    total = w["prep_minutes"] + w["delivery_minutes"]
    scale = max(total, w["promised_minutes"]) * 1.08
    pw, dw, mk = w["prep_minutes"] / scale * 100, w["delivery_minutes"] / scale * 100, w["promised_minutes"] / scale * 100
    return (f"<div class='coupon'><div class='c-head'>COUPON · MOST LATE ORDER IN VIEW</div>"
            f"<div class='c-id'>{esc(w['order_id'])} · {esc(w['category'])}</div>"
            f"<div class='note'>{w['order_date']:%d %b %Y}</div>"
            f"<div class='tl'><div class='seg prep' style='width:{pw:.1f}%'>PREP {w['prep_minutes']:.0f}</div>"
            f"<div class='seg del' style='width:{dw:.1f}%'>RIDE {w['delivery_minutes']:.0f}</div>"
            f"<div class='mark' style='left:{mk:.1f}%'><span>PROMISED {w['promised_minutes']:.0f}</span></div></div>"
            f"<div class='c-foot'>{total:.0f} min total · <b>{w['over']:.0f} min over</b> the promise</div></div>")


def insight_list(insights) -> None:
    labels = {"fact": ("FACT", "fact"), "hypothesis": ("HYPOTHESIS", "hyp"), "recommendation": ("TO DO", "rec")}
    rank = 0
    out = ""
    for i in insights:
        text, cls = labels[i["kind"]]
        prio = ""
        if i["kind"] == "recommendation":
            rank += 1
            prio = f" <span class='prio'>#{rank} · impact {i['impact']}/3 × effort {i['effort']}/3</span>"
        out += (f"<div class='insight'><span class='seal {cls}'>{text}</span>{esc(i['text'])}{prio}"
                f"<span class='ev'>evidence: {esc(i['evidence'])}</span></div>")
    st.markdown(out, unsafe_allow_html=True)
