from __future__ import annotations

from multifamily_screener.underwriting.common import safe_divide


def noi(effective_gross_income_value: float, operating_expenses: float, capex_reserve: float) -> float:
    return effective_gross_income_value - operating_expenses - capex_reserve


def break_even_occupancy(
    operating_expenses: float,
    capex_reserve: float,
    annual_debt_service_value: float,
    gross_potential_rent: float,
    other_income: float,
) -> float:
    required_rental_income = operating_expenses + capex_reserve + annual_debt_service_value - other_income
    return max(0.0, min(1.0, safe_divide(required_rental_income, gross_potential_rent) or 0.0))
