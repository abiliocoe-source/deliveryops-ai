"""Export helpers: CSV of filtered data and a Markdown report."""
import pandas as pd


def _fmt(v, kind):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    return f"{v * 100:.1f}%" if kind == "pct" else f"{v:.1f}" if kind == "num" else str(v)


def to_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)


def to_markdown_report(kpis: dict, by_category: pd.DataFrame, insights: list[dict],
                       source_label: str) -> str:
    lines = ["# DeliveryOps AI report", "", f"Data source: {source_label}", "", "## KPIs", "",
             f"- Total orders: {kpis['total_orders']}",
             f"- Late rate: {_fmt(kpis['late_rate'], 'pct')}",
             f"- Cancellation rate: {_fmt(kpis['cancel_rate'], 'pct')}",
             f"- Avg prep (min): {_fmt(kpis['avg_prep_minutes'], 'num')}",
             f"- Avg delivery (min): {_fmt(kpis['avg_delivery_minutes'], 'num')}",
             f"- Avg rating: {_fmt(kpis['avg_rating'], 'num')}", "", "## By category", "",
             "| Category | Orders | Late rate | Cancel rate |", "|---|---|---|---|"]
    for _, r in by_category.iterrows():
        lines.append(f"| {r['category']} | {int(r['total_orders'])} | "
                     f"{_fmt(r['late_rate'], 'pct')} | {_fmt(r['cancel_rate'], 'pct')} |")
    lines += ["", "## Insights", ""]
    for kind in ("fact", "hypothesis", "recommendation"):
        items = [i for i in insights if i["kind"] == kind]
        if items:
            lines.append(f"### {kind.capitalize()}s")
            lines += [f"- {i['text']} _(evidence: {i['evidence']})_" for i in items]
            lines.append("")
    return "\n".join(lines)
