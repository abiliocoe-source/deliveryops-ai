import numpy as np
import pandas as pd
import pytest

from deliveryops.data import REQUIRED_COLUMNS, generate_synthetic, validate
from deliveryops.export import to_csv, to_markdown_report
from deliveryops.insights import build_insights, llm_summary, numbers_are_grounded
from deliveryops.metrics import compute_kpis, kpis_by_category, kpis_over_time
from deliveryops.savings import estimate_savings


def row(**kw):
    base = dict(order_id="A1", order_date="2025-01-01", category="Pizza", status="delivered",
                prep_minutes=10.0, delivery_minutes=20.0, promised_minutes=45.0, rating=5.0)
    return {**base, **kw}


def test_synthetic_is_reproducible_and_big_enough():
    a, b = generate_synthetic(seed=1), generate_synthetic(seed=1)
    assert len(a) >= 500
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == REQUIRED_COLUMNS
    clean, rep = validate(a)
    assert rep.ok and len(clean) == len(a)


def test_missing_columns_gives_clear_error():
    _, rep = validate(pd.DataFrame({"order_id": ["1"]}))
    assert not rep.ok and "Missing required columns" in rep.errors[0]


def test_invalid_rows_are_removed_with_messages():
    df = pd.DataFrame([
        row(order_id="1"),
        row(order_id="1"),                       # duplicate
        row(order_id="2", rating=9),             # bad rating
        row(order_id="3", prep_minutes=-5),      # negative time
        row(order_id="4", order_date="not-a-date"),
        row(order_id="5", status="lost"),
        row(order_id="6", status="cancelled", prep_minutes=np.nan,
            delivery_minutes=np.nan, rating=np.nan),  # valid cancelled
    ])
    clean, rep = validate(df)
    assert rep.ok and set(clean["order_id"]) == {"1", "6"}
    assert any("duplicate" in w for w in rep.warnings)


def test_all_invalid_is_an_error():
    _, rep = validate(pd.DataFrame([row(rating=99)]))
    assert not rep.ok and rep.errors


def test_kpis_known_values():
    df, _ = validate(pd.DataFrame([
        row(order_id="1", prep_minutes=30, delivery_minutes=20),  # 50 > 45 late
        row(order_id="2"),
        row(order_id="3", status="cancelled", prep_minutes=np.nan, delivery_minutes=np.nan, rating=np.nan),
        row(order_id="4", rating=np.nan),
    ]))
    k = compute_kpis(df)
    assert k["total_orders"] == 4 and k["cancel_rate"] == 0.25
    assert k["late_rate"] == pytest.approx(1 / 3)
    assert k["avg_rating"] == 5.0 and k["rated_orders"] == 2


def test_kpis_edge_cases_empty_and_all_cancelled():
    empty = validate(generate_synthetic(600))[0].iloc[0:0]
    k = compute_kpis(empty)
    assert k["total_orders"] == 0 and k["late_rate"] is None and k["cancel_rate"] is None
    cancelled, _ = validate(pd.DataFrame([row(order_id="1", status="cancelled", prep_minutes=np.nan,
                                              delivery_minutes=np.nan, rating=np.nan)]))
    k = compute_kpis(cancelled)
    assert k["cancel_rate"] == 1.0 and k["late_rate"] is None and k["avg_prep_minutes"] is None


def test_exactly_on_promised_time_is_not_late():
    df, _ = validate(pd.DataFrame([row(prep_minutes=25, delivery_minutes=20)]))
    assert compute_kpis(df)["late_rate"] == 0.0


def test_grouping_and_time_series():
    df, _ = validate(generate_synthetic())
    cat = kpis_by_category(df)
    assert cat["total_orders"].sum() == len(df)
    ts = kpis_over_time(df, "M")
    assert ts["total_orders"].sum() == len(df)


def test_insights_cite_evidence_and_dont_claim_causality():
    df, _ = validate(generate_synthetic())
    ins = build_insights(compute_kpis(df), kpis_by_category(df), kpis_over_time(df))
    assert {"fact", "hypothesis", "recommendation"} <= {i["kind"] for i in ins}
    assert all(i["evidence"] for i in ins)
    assert all("because" not in i["text"].lower() for i in ins)
    kinds = [i["kind"] for i in ins]
    assert kinds == sorted(kinds, key=["fact", "hypothesis", "recommendation"].index)


def test_insights_empty_data():
    df = validate(generate_synthetic())[0].iloc[0:0]
    assert build_insights(compute_kpis(df), kpis_by_category(df), kpis_over_time(df)) == []


def test_llm_number_guard_and_no_key_fallback(monkeypatch):
    ins = [{"kind": "fact", "text": "Late rate is 10.0%.", "evidence": "5 of 50"}]
    assert numbers_are_grounded("Late rate 10.0% (5 of 50)", ins)
    assert not numbers_are_grounded("Late rate is 99%", ins)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm_summary(ins) is None


def test_savings_and_validation():
    r = estimate_savings(1000, 3, 0.5, 20)
    assert r["hours_saved_per_month"] == 25.0 and r["cost_saved_per_month"] == 500.0
    assert "ESTIMATE" in r["label"]
    assert estimate_savings(0, 3, 0.5, 20)["hours_saved_per_month"] == 0
    with pytest.raises(ValueError):
        estimate_savings(10, 3, 1.5, 20)


def test_export():
    df, _ = validate(generate_synthetic())
    k, c = compute_kpis(df), kpis_by_category(df)
    md = to_markdown_report(k, c, build_insights(k, c, kpis_over_time(df)), "synthetic (fictional)")
    assert "# DeliveryOps AI report" in md and "| Pizza |" in md and "synthetic" in md
    assert to_csv(df).splitlines()[0].startswith("order_id")
