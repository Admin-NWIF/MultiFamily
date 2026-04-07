from __future__ import annotations


def effective_gross_income(gross_potential_rent: float, vacancy_rate: float, other_income: float) -> float:
    return gross_potential_rent * (1.0 - vacancy_rate) + other_income
