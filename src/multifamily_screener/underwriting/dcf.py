from __future__ import annotations

from multifamily_screener.underwriting.common import safe_divide


def npv(discount_rate: float, cash_flows: list[float]) -> float:
    return sum(cash_flow / ((1.0 + discount_rate) ** idx) for idx, cash_flow in enumerate(cash_flows))


def irr(cash_flows: list[float], *, tolerance: float = 1e-7, max_iterations: int = 200) -> float | None:
    if not any(cash_flow > 0 for cash_flow in cash_flows) or not any(cash_flow < 0 for cash_flow in cash_flows):
        return None

    low, high = -0.9999, 10.0
    low_npv = npv(low, cash_flows)
    high_npv = npv(high, cash_flows)
    if low_npv * high_npv > 0:
        return None

    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        mid_npv = npv(mid, cash_flows)
        if abs(mid_npv) < tolerance:
            return mid
        if low_npv * mid_npv <= 0:
            high = mid
            high_npv = mid_npv
        else:
            low = mid
            low_npv = mid_npv
    return (low + high) / 2.0


def equity_multiple(cash_flows: list[float], equity_invested: float) -> float | None:
    positive_cash_flows = sum(cash_flow for cash_flow in cash_flows[1:] if cash_flow > 0)
    return safe_divide(positive_cash_flows, equity_invested)
