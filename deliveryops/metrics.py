"""KPI calculations. All functions are deterministic and expect validated data.

Definitions
- total_orders      : all rows.
- cancel_rate       : cancelled / total_orders.
- late              : delivered AND prep + delivery > promised_minutes.
- late_rate         : late / delivered orders (cancelled orders are excluded).
- avg_prep/delivery : mean minutes over delivered orders.
- avg_rating        : mean over orders that have a rating (unrated are ignored).
An empty denominator gives None, never a crash or a fake 0.
"""
import pandas as pd

KPI_COLS = ["total_orders", "late_rate", "cancel_rate",
            "avg_prep_minutes", "avg_delivery_minutes", "avg_rating"]


def _ratio(num, den):
    return None if den == 0 else float(num) / den


def add_late_flag(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["is_late"] = (out["status"] == "delivered") & (
        out["prep_minutes"] + out["delivery_minutes"] > out["promised_minutes"])
    return out


def compute_kpis(df: pd.DataFrame) -> dict:
    d = add_late_flag(df)
    delivered = d[d["status"] == "delivered"]
    rated = d["rating"].dropna()
    n_cancel = int((d["status"] == "cancelled").sum())
    return {
        "total_orders": int(len(d)),
        "delivered_orders": int(len(delivered)),
        "cancelled_orders": n_cancel,
        "late_orders": int(d["is_late"].sum()),
        "cancel_rate": _ratio(n_cancel, len(d)),
        "late_rate": _ratio(int(d["is_late"].sum()), len(delivered)),
        "avg_prep_minutes": None if delivered.empty else float(delivered["prep_minutes"].mean()),
        "avg_delivery_minutes": None if delivered.empty else float(delivered["delivery_minutes"].mean()),
        "avg_rating": None if rated.empty else float(rated.mean()),
        "rated_orders": int(len(rated)),
    }


def kpis_by_category(df: pd.DataFrame) -> pd.DataFrame:
    rows = [{"category": cat, **compute_kpis(g)} for cat, g in df.groupby("category")]
    return pd.DataFrame(rows, columns=["category", *KPI_COLS]) if rows \
        else pd.DataFrame(columns=["category", *KPI_COLS])


def kpis_over_time(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """KPIs per period (freq 'D', 'W' or 'M')."""
    if df.empty:
        return pd.DataFrame(columns=["period", *KPI_COLS])
    period = df["order_date"].dt.to_period(freq).dt.start_time
    rows = [{"period": p, **compute_kpis(g)} for p, g in df.groupby(period)]
    return pd.DataFrame(rows)[["period", *KPI_COLS]]
