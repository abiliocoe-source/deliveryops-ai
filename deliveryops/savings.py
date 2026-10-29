"""Time-savings calculator. Output is an ESTIMATE based only on user assumptions."""


def estimate_savings(orders_per_month: int, minutes_per_order_manual: float,
                     automation_coverage: float, hourly_cost: float) -> dict:
    """automation_coverage in [0, 1] = share of the manual work that gets automated."""
    if orders_per_month < 0 or minutes_per_order_manual < 0 or hourly_cost < 0:
        raise ValueError("Inputs must not be negative.")
    if not 0 <= automation_coverage <= 1:
        raise ValueError("automation_coverage must be between 0 and 1.")
    hours = orders_per_month * minutes_per_order_manual * automation_coverage / 60
    return {
        "label": "ESTIMATE - depends entirely on the assumptions entered",
        "hours_saved_per_month": round(hours, 2),
        "cost_saved_per_month": round(hours * hourly_cost, 2),
        "hours_saved_per_year": round(hours * 12, 2),
    }
