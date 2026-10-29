"""Presentation components for DeliveryOps. Only formats numbers computed by the deliveryops package."""
import html
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from deliveryops.metrics import add_late_flag

ASSETS = Path(__file__).resolve().parent / "assets"
WORD = {"D": "day", "W": "week", "M": "month"}
ACCENT, INK, MUTED, GRID = "#E2561A", "#14181A", "#5B6468", "#E3E7E9"
SANS = "IBM Plex Sans, system-ui, sans-serif"


def esc(x) -> str:
    return html.escape(str(x))


def inject_css() -> None:
    st.markdown(f"<style>{(ASSETS / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def pct(x, d=1) -> str:
    return "n/a" if x is None else f"{x * 100:.{d}f}"


def num(x, d=1) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def note(kind: str, title: str, text: str = "") -> None:
    """Inside the block that needs it. kind: error | warn | ok | empty."""
    st.markdown(f"<div class='note {kind}'><b>{esc(title)}</b> {esc(text)}</div>", unsafe_allow_html=True)


def brand(scope: str) -> None:
    """Product mark and scope at the top of the sidebar. The mark is a torn ticket, drawn for this product."""
    mark = ("<svg width='28' height='32' viewBox='0 0 28 32' aria-hidden='true'><path d='M2 1h24v26l-4 4-4-4-4 4-4-4-4 4-4-4z' "
            "fill='#fff' stroke='#14181A' stroke-width='1.5'/><rect x='7' y='7' width='14' height='3' fill='#14181A'/>"
            "<rect x='7' y='13' width='10' height='3' fill='#E2561A'/><rect x='7' y='19' width='6' height='2' fill='#CDD2D5'/></svg>")
    st.markdown(f"<div class='brand'>{mark}<div><div class='n'>DeliveryOps</div><div class='s'>{esc(scope)}</div></div></div>",
                        unsafe_allow_html=True)


def title(h1: str, finding_html: str, stamp: str) -> None:
    st.markdown(f"<div class='title'><h1>{esc(h1)}</h1><p class='finding'>{finding_html}</p>"
                f"<div class='stamp'>{esc(stamp)}</div></div>", unsafe_allow_html=True)


def last_value(ts, col):
    s = ts[col].dropna()
    return None if s.empty else float(s.iloc[-1])


def state_pill(value, target, freq="W") -> str:
    """Words, not just colour. Lower is better for both rates. `value` is the last bucket."""
    when = f" last {WORD[freq]}"
    if value is None:
        return "<span class='pill neu'>No data</span>"
    if value <= target:
        return f"<span class='pill pos'>On target{when}</span>"
    if value <= target * 1.5:
        return f"<span class='pill warn'>Watch{when}</span>"
    return f"<span class='pill neg'>Off target{when}</span>"


def last_line(ts, col, freq, scale=100.0, unit="%", worse_when_up=True) -> str:
    """'Last week 14.0%, 0.0 pp vs prior week': the last bucket, then its change, in words."""
    v = last_value(ts, col)
    if v is None:
        return "<span class='d'>no data</span>"
    s = ts[col].dropna()
    base = f"Last {WORD[freq]} <b>{v * scale:.1f}{unit}</b>"
    if len(s) < 2:
        return f"<span class='d'>{base}, no earlier period</span>"
    d = (s.iloc[-1] - s.iloc[-2]) * scale
    if abs(d) < 0.05:
        return f"<span class='d'>{base}, 0.0 pp vs prior {WORD[freq]}</span>"
    cls = "bad" if (d > 0) == worse_when_up else "good"
    return f"<span class='d'>{base}, <span class='{cls}'>{d:+.1f} pp</span> vs prior {WORD[freq]}</span>"


def delta(ts, col, freq, unit, scale=1.0, worse_when_up=True, neutral=False) -> str:
    """Change of the last bucket against the one before, named in words. Zero or undefined stays grey."""
    s = ts[col].dropna()
    if len(s) < 2:
        return "<span class='d'>no earlier period</span>"
    d = (s.iloc[-1] - s.iloc[-2]) * scale
    base = f"vs prior {WORD[freq]}"
    if abs(d) < 0.05:
        return f"<span class='d'>0.0 {unit} {base}</span>"
    cls = "" if neutral else ("bad" if (d > 0) == worse_when_up else "good")
    return f"<span class='d'><span class='{cls}'>{d:+.1f} {unit}</span> {base}</span>"


def kpi_strip(kpis, ts, freq, late_target, cancel_target) -> str:
    def cell(label, value, unit, dhtml, lead=False, pill=""):
        st_ = f"<div class='st'>{pill}</div>" if pill else ""
        return (f"<div class='kpi{' lead' if lead else ''}'><div class='l'>{label}</div>"
                f"<div class='v'>{value}<small>{unit}</small></div>{st_}{dhtml}</div>")
    return ("<div class='kpis'>"
            + cell("Late rate", pct(kpis["late_rate"]), "% in view", last_line(ts, "late_rate", freq),
                   lead=True, pill=state_pill(last_value(ts, "late_rate"), late_target, freq))
            + cell("Cancel rate", pct(kpis["cancel_rate"]), "% in view", last_line(ts, "cancel_rate", freq),
                   pill=state_pill(last_value(ts, "cancel_rate"), cancel_target, freq))
            + cell("Orders", f"{kpis['total_orders']:,}", "", delta(ts, "total_orders", freq, "orders", neutral=True))
            + cell("Prep time", num(kpis["avg_prep_minutes"]), "min", delta(ts, "avg_prep_minutes", freq, "min"))
            + cell("Delivery time", num(kpis["avg_delivery_minutes"]), "min", delta(ts, "avg_delivery_minutes", freq, "min"))
            + cell("Rating", num(kpis["avg_rating"], 2), "/ 5", delta(ts, "avg_rating", freq, "pts", worse_when_up=False))
            + "</div>")


METRICS = {  # label -> (column, unit, scale for display)
    "Late rate": ("late_rate", "%", 100), "Cancel rate": ("cancel_rate", "%", 100),
    "Prep time": ("avg_prep_minutes", " min", 1), "Delivery time": ("avg_delivery_minutes", " min", 1),
}


def trend_figure(ts, metric, freq, target=None) -> go.Figure:
    col, unit, scale = METRICS[metric]
    t = ts.dropna(subset=[col])
    y = t[col] * scale
    fig = go.Figure(go.Scatter(x=t["period"], y=y, mode="lines", line=dict(color=ACCENT, width=2),
                               hovertemplate="%{x|%d %b %Y}: %{y:.1f}" + unit + "<extra></extra>"))
    if target is not None:
        fig.add_hline(y=target * scale, line=dict(color=MUTED, width=1, dash="dash"), annotation_text=f"target {target * scale:.0f}{unit}",
                      annotation_position="bottom left", annotation_font=dict(family=SANS, size=13, color=MUTED))
    if len(t):
        i = y.idxmax()
        fig.add_annotation(x=t.loc[i, "period"], y=y.loc[i], text=f"highest: {y.loc[i]:.1f}{unit}, {WORD[freq]} of {t.loc[i, 'period']:%d %b}",
                           showarrow=True, ax=0, ay=-26, xanchor="right", arrowcolor=INK, arrowwidth=1, arrowhead=0,
                           font=dict(family=SANS, size=12, color=INK))
    fig.update_layout(height=300, margin=dict(l=0, r=8, t=8, b=0), showlegend=False, hovermode="x", font=dict(family=SANS, size=13, color=MUTED),
                      paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, range=[0, max(float(y.max()) * 1.2, (target or 0) * scale * 1.2) if len(t) else 1], nticks=5, ticksuffix=unit.strip() if unit == "%" else "", title=None, zeroline=False, showline=False)
    fig.update_xaxes(showgrid=False, linecolor=GRID, nticks=7, tickformat="%d %b", title=None)
    return fig


def category_table(by_cat) -> str:
    rows = by_cat.sort_values("late_rate", ascending=False, na_position="last")
    body = ""
    for i, (_, r) in enumerate(rows.iterrows()):
        hint = "<span class='hint'>slowest</span>" if i == 0 and r["late_rate"] == r["late_rate"] else ""
        body += (f"<tr{' class=top' if i == 0 else ''}><td>{esc(r['category'])}{hint}</td><td class='fig'>{int(r['total_orders']):,}</td>"
                 f"<td class='fig'>{pct(r['late_rate'])}%</td><td class='fig'>{pct(r['cancel_rate'])}%</td>"
                 f"<td class='fig'>{num(r['avg_prep_minutes'])}</td><td class='fig'>{num(r['avg_delivery_minutes'])}</td>"
                 f"<td class='fig'>{num(r['avg_rating'], 2)}</td></tr>")
    head = "".join(f"<th>{h}</th>" for h in ["Category", "Orders", "Late %", "Cancelled %", "Prep, min", "Delivery, min", "Rating, /5"])
    return f"<div class='tbl-wrap'><table class='tbl'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _torn(teeth=14, depth=7) -> str:
    pts = ["0 0", "100% 0"]
    step = 100 / teeth
    for k in range(teeth, -1, -1):
        x = k * step
        pts.append(f"{x:.2f}% calc(100% - {depth if k % 2 else 0}px)")
    return "polygon(" + ",".join(pts) + ")"


def coupon(view) -> str:
    d = add_late_flag(view)
    late = d[d["is_late"]].copy()
    if late.empty:
        return "<div class='note empty'><b>Nothing late.</b> No late orders in this view, so there is no ticket to print.</div>"
    late["over"] = late["prep_minutes"] + late["delivery_minutes"] - late["promised_minutes"]
    w = late.loc[late["over"].idxmax()]
    total = w["prep_minutes"] + w["delivery_minutes"]
    scale = max(total, w["promised_minutes"]) * 1.04
    pw, rw, mk = w["prep_minutes"] / scale * 100, w["delivery_minutes"] / scale * 100, w["promised_minutes"] / scale * 100
    return (f"<div class='coupon' style='clip-path:{_torn()}'><div class='h'><b>Most late order in view</b><span class='id fig'>{esc(w['order_id'])}</span></div>"
            f"<div class='m'>{esc(w['category'])} · {w['order_date']:%d %b %Y}</div>"
            f"<div class='cbar'><div class='p' style='width:{pw:.1f}%'></div><div class='r' style='width:{rw:.1f}%'></div>"
            f"<div class='tick' style='left:{mk:.1f}%'><span>promised {w['promised_minutes']:.0f}</span></div></div>"
            f"<div class='cover'><i style='left:{mk:.1f}%;width:{max(pw + rw - mk, 0):.1f}%'></i></div>"
            f"<div class='cleg'><span>Prep {w['prep_minutes']:.0f} min</span><span>Ride {w['delivery_minutes']:.0f} min</span></div>"
            f"<div class='cfoot'>{total:.0f} min in all, <b>{w['over']:.0f} min over</b> the promise</div></div>")


def insights(items) -> None:
    pill = {"fact": ("neu", "Fact"), "hypothesis": ("warn", "Hypothesis"), "recommendation": ("pos", "To do")}
    rank, out = 0, ""
    for i in items:
        cls, label = pill[i["kind"]]
        pr = ""
        if i["kind"] == "recommendation":
            rank += 1
            pr = f"<span class='pr'>priority {rank} · impact {i['impact']} of 3, effort {i['effort']} of 3</span>"
        out += (f"<div class='irow'><div><span class='pill {cls}'>{label}</span></div><div><span class='t'>{esc(i['text'])}</span>{pr}"
                f"<span class='ev'>Evidence: {esc(i['evidence'])}</span></div></div>")
    st.markdown(out, unsafe_allow_html=True)


def savings_strip(res) -> str:
    return (f"<div class='kpis three'>"
            f"<div class='kpi'><div class='l'>Hours saved per month</div><div class='v'>{res['hours_saved_per_month']:,.1f}<small>h</small></div></div>"
            f"<div class='kpi'><div class='l'>Cost saved per month</div><div class='v'>{res['cost_saved_per_month']:,.2f}</div></div>"
            f"<div class='kpi'><div class='l'>Hours saved per year</div><div class='v'>{res['hours_saved_per_year']:,.1f}<small>h</small></div></div></div>")
