from __future__ import annotations

from multifamily_screener.underwriting.common import safe_divide


def annual_debt_service(loan_amount: float, interest_rate: float, amortization_years: int) -> float:
    if loan_amount <= 0:
        return 0.0
    months = amortization_years * 12
    monthly_rate = interest_rate / 12.0
    if monthly_rate == 0:
        return loan_amount / amortization_years
    payment = loan_amount * monthly_rate / (1.0 - (1.0 + monthly_rate) ** -months)
    return payment * 12.0


def mortgage_constant(interest_rate: float, amortization_years: int) -> float:
    return annual_debt_service(1.0, interest_rate, amortization_years)


def dscr(noi_value: float, annual_debt_service_value: float) -> float | None:
    return safe_divide(noi_value, annual_debt_service_value)


def loan_balance(loan_amount: float, interest_rate: float, amortization_years: int, years_elapsed: int) -> float:
    if loan_amount <= 0:
        return 0.0
    months_elapsed = min(years_elapsed * 12, amortization_years * 12)
    total_months = amortization_years * 12
    monthly_rate = interest_rate / 12.0
    if monthly_rate == 0:
        paid_down = loan_amount * months_elapsed / total_months
        return max(0.0, loan_amount - paid_down)
    payment = loan_amount * monthly_rate / (1.0 - (1.0 + monthly_rate) ** -total_months)
    return loan_amount * (1.0 + monthly_rate) ** months_elapsed - payment * (
        ((1.0 + monthly_rate) ** months_elapsed - 1.0) / monthly_rate
    )
