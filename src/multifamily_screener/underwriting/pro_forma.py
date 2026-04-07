from __future__ import annotations

from multifamily_screener.schemas import ProFormaRow, UnderwritingAssumptions
from multifamily_screener.underwriting.debt import annual_debt_service
from multifamily_screener.underwriting.expenses import noi
from multifamily_screener.underwriting.income import effective_gross_income


def build_pro_forma(assumptions: UnderwritingAssumptions) -> list[ProFormaRow]:
    debt_service = annual_debt_service(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
    )
    rows: list[ProFormaRow] = []
    for year in range(1, assumptions.hold_years + 1):
        rent_growth_factor = (1.0 + assumptions.rent_growth_rate) ** (year - 1)
        expense_growth_factor = (1.0 + assumptions.expense_growth_rate) ** (year - 1)
        gross_potential_rent = assumptions.gross_potential_rent * rent_growth_factor
        other_income = assumptions.other_income * rent_growth_factor
        operating_expenses = assumptions.operating_expenses * expense_growth_factor
        capex_reserve = assumptions.capex_reserve * expense_growth_factor
        vacancy_loss = gross_potential_rent * assumptions.vacancy_rate
        egi = effective_gross_income(gross_potential_rent, assumptions.vacancy_rate, other_income)
        noi_before_reserves = noi(egi, operating_expenses, 0.0)
        noi_after_reserves = noi(egi, operating_expenses, capex_reserve)
        cash_flow_before_tax = noi_after_reserves - debt_service
        rows.append(
            ProFormaRow(
                year=year,
                gross_potential_rent=gross_potential_rent,
                vacancy_loss=vacancy_loss,
                other_income=other_income,
                effective_gross_income=egi,
                operating_expenses=operating_expenses,
                noi_before_reserves=noi_before_reserves,
                capex_reserve=capex_reserve,
                noi_after_reserves=noi_after_reserves,
                annual_debt_service=debt_service,
                cash_flow_before_tax=cash_flow_before_tax,
                total_cash_flow=cash_flow_before_tax,
            )
        )
    return rows
