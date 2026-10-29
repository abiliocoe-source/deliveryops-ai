"""Synthetic dataset generation and CSV validation."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "order_id", "order_date", "category", "status",
    "prep_minutes", "delivery_minutes", "promised_minutes", "rating",
]
VALID_STATUS = {"delivered", "cancelled"}
CATEGORIES = ["Pizza", "Burger", "Japanese", "Healthy", "Dessert"]
# (extra prep minutes, cancel probability) per category - fictional parameters
_CAT_PARAMS = {"Pizza": (8, 0.05), "Burger": (3, 0.04), "Japanese": (6, 0.08),
               "Healthy": (0, 0.03), "Dessert": (-2, 0.02)}


def generate_synthetic(n: int = 1200, seed: int = 42) -> pd.DataFrame:
    """FICTIONAL orders. Same seed -> same data. Service gets slower over time on purpose."""
    rng = np.random.default_rng(seed)
    days = 180
    offsets = rng.integers(0, days, n)
    dates = pd.Timestamp("2025-01-01") + pd.to_timedelta(offsets, unit="D")
    cats = rng.choice(CATEGORIES, n, p=[0.28, 0.27, 0.17, 0.16, 0.12])
    extra = np.array([_CAT_PARAMS[c][0] for c in cats])
    p_cancel = np.array([_CAT_PARAMS[c][1] for c in cats])
    cancelled = rng.random(n) < p_cancel
    drift = offsets / days * 6
    prep = np.clip(rng.normal(18 + extra + drift / 2, 4), 5, None).round(1)
    delivery = np.clip(rng.normal(22 + drift, 6), 8, None).round(1)
    rating = np.clip(np.round(5 - (prep + delivery - 35) / 12 + rng.normal(0, 0.8, n)), 1, 5)
    unrated = rng.random(n) < 0.15  # not everyone rates
    df = pd.DataFrame({
        "order_id": [f"F{i:05d}" for i in range(1, n + 1)],  # F = fictional
        "order_date": dates.strftime("%Y-%m-%d"),
        "category": cats,
        "status": np.where(cancelled, "cancelled", "delivered"),
        "prep_minutes": prep,
        "delivery_minutes": delivery,
        "promised_minutes": np.full(n, 60.0),
        "rating": np.where(unrated, np.nan, rating),
    })
    df.loc[cancelled, ["prep_minutes", "delivery_minutes", "rating"]] = np.nan
    return df.sort_values("order_date", kind="stable").reset_index(drop=True)


@dataclass
class ValidationReport:
    ok: bool
    errors: list = field(default_factory=list)    # fatal: cannot proceed
    warnings: list = field(default_factory=list)  # rows dropped, etc.
    rows_in: int = 0
    rows_valid: int = 0


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """Check columns, types, nulls and invalid rows. Returns (clean_df, report)."""
    rep = ValidationReport(ok=False, rows_in=len(df))
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        rep.errors.append(f"Missing required columns: {', '.join(missing)}")
        return df.iloc[0:0], rep
    if df.empty:
        rep.errors.append("The file has no rows.")
        return df, rep

    d = df[REQUIRED_COLUMNS].copy()
    d["order_date"] = pd.to_datetime(d["order_date"], errors="coerce")
    for c in ["prep_minutes", "delivery_minutes", "promised_minutes", "rating"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["status"] = d["status"].astype(str).str.strip().str.lower()
    d["category"] = d["category"].astype(str).str.strip()
    d["order_id"] = d["order_id"].astype(str).str.strip()

    delivered = d["status"] == "delivered"
    checks = {
        "invalid or empty order_date": d["order_date"].isna(),
        "empty order_id": d["order_id"].isin(["", "nan", "None"]),
        "duplicate order_id": d["order_id"].duplicated(keep="first"),
        "empty category": d["category"].isin(["", "nan", "None"]),
        "status not in {delivered, cancelled}": ~d["status"].isin(VALID_STATUS),
        "delivered order without prep/delivery time":
            delivered & (d["prep_minutes"].isna() | d["delivery_minutes"].isna()),
        "zero or negative time":
            (d["prep_minutes"] <= 0) | (d["delivery_minutes"] <= 0) | (d["promised_minutes"] <= 0),
        "missing promised_minutes": d["promised_minutes"].isna(),
        "rating outside 1-5": d["rating"].notna() & ~d["rating"].between(1, 5),
    }
    bad = pd.Series(False, index=d.index)
    for msg, mask in checks.items():
        if mask.any():
            rep.warnings.append(f"{int(mask.sum())} row(s) with {msg}")
        bad |= mask
    clean = d[~bad].reset_index(drop=True)
    rep.rows_valid = len(clean)
    if clean.empty:
        rep.errors.append("No valid rows left after validation.")
        return clean, rep
    if bad.any():
        rep.warnings.append(f"{int(bad.sum())} invalid row(s) were removed.")
    rep.ok = True
    return clean, rep
