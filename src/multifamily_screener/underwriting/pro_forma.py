from __future__ import annotations

from multifamily_screener.schemas import ProFormaRow, UnderwritingAssumptions
from multifamily_screener.underwriting.debt import annual_debt_service, loan_balance
from multifamily_screener.underwriting.expenses import noi_after_reserves, noi_before_reserves
from multifamily_screener.underwriting.income import effective_gross_income


def build_pro_forma(assumptions: UnderwritingAssumptions) -> list[ProFormaRow]:
    debt_service = annual_debt_service(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
    )
    rows: list[ProFormaRow] = []
    for year in range(1, assumptions.hold_years + 1):
        rent_growth_factor = (1.0 + assumptions.rent_growth) ** (year - 1)
        expense_growth_factor = (1.0 + assumptions.expense_growth) ** (year - 1)
        gross_potential_rent = assumptions.gross_potential_rent * rent_growth_factor
        other_income = assumptions.other_income * rent_growth_factor
        operating_expenses = assumptions.operating_expenses * expense_growth_factor
        capex_reserve = assumptions.capex_reserve * expense_growth_factor
        vacancy_loss = gross_potential_rent * assumptions.vacancy_rate
        egi = effective_gross_income(gross_potential_rent, assumptions.vacancy_rate, other_income)
        noi_before_reserves_value = noi_before_reserves(egi, operating_expenses)
        noi_after_reserves_value = noi_after_reserves(noi_before_reserves_value, capex_reserve)
        cash_flow_before_tax = noi_after_reserves_value - debt_service
        ending_loan_balance = loan_balance(
            assumptions.loan_amount,
            assumptions.interest_rate,
            assumptions.amortization_years,
            year,
        )
        rows.append(
            ProFormaRow(
                year=year,
                gross_potential_rent=gross_potential_rent,
                vacancy_loss=vacancy_loss,
                other_income=other_income,
                effective_gross_income=egi,
                operating_expenses=operating_expenses,
                noi_before_reserves=noi_before_reserves_value,
                capex_reserve=capex_reserve,
                noi_after_reserves=noi_after_reserves_value,
                annual_debt_service=debt_service,
                cash_flow_before_tax=cash_flow_before_tax,
                ending_loan_balance=ending_loan_balance,
                total_cash_flow=cash_flow_before_tax,
            )
        )
    return rows
