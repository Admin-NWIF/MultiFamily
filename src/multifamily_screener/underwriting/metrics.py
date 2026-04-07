from __future__ import annotations

from multifamily_screener.schemas import UnderwritingAssumptions, UnderwritingMetrics
from multifamily_screener.underwriting.common import safe_divide
from multifamily_screener.underwriting.dcf import equity_multiple, irr, npv
from multifamily_screener.underwriting.debt import annual_debt_service, dscr, loan_balance
from multifamily_screener.underwriting.expenses import break_even_occupancy, noi_after_reserves, noi_before_reserves
from multifamily_screener.underwriting.income import effective_gross_income
from multifamily_screener.underwriting.offer import exit_value, suggested_max_offer


def cap_rate(noi_value: float, purchase_price: float) -> float:
    return safe_divide(noi_value, purchase_price) or 0.0


def cash_on_cash(cash_flow_before_tax: float, equity_invested: float) -> float | None:
    return safe_divide(cash_flow_before_tax, equity_invested)


def calculate_metrics(assumptions: UnderwritingAssumptions) -> UnderwritingMetrics:
    debt_service = annual_debt_service(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
    )
    pro_forma: list[dict] = []
    gpr = assumptions.gross_potential_rent
    operating_expenses = assumptions.operating_expenses
    capex_reserve = assumptions.capex_reserve

    for year in range(1, assumptions.hold_years + 1):
        if year > 1:
            gpr *= 1.0 + assumptions.rent_growth
            operating_expenses *= 1.0 + assumptions.expense_growth
            capex_reserve *= 1.0 + assumptions.expense_growth

        egi = effective_gross_income(gpr, assumptions.vacancy_rate, assumptions.other_income)
        noi_before_reserves_value = noi_before_reserves(egi, operating_expenses)
        noi_after_reserves_value = noi_after_reserves(noi_before_reserves_value, capex_reserve)
        cash_flow_before_tax = noi_after_reserves_value - debt_service
        ending_loan_balance = loan_balance(
            assumptions.loan_amount,
            assumptions.interest_rate,
            assumptions.amortization_years,
            year,
        )
        pro_forma.append(
            {
                "year": year,
                "gross_potential_rent": gpr,
                "effective_gross_income": egi,
                "operating_expenses": operating_expenses,
                "capex_reserve": capex_reserve,
                "noi_before_reserves": noi_before_reserves_value,
                "noi_after_reserves": noi_after_reserves_value,
                "annual_debt_service": debt_service,
                "cash_flow_before_tax": cash_flow_before_tax,
                "ending_loan_balance": ending_loan_balance,
                "sale_proceeds": 0.0,
                "total_cash_flow": cash_flow_before_tax,
            }
        )

    first_year = pro_forma[0]
    final_year = pro_forma[-1]
    acquisition_costs = assumptions.purchase_price * assumptions.acquisition_cost_rate
    equity_invested = assumptions.purchase_price - assumptions.loan_amount + acquisition_costs
    sale_price = exit_value(final_year["noi_before_reserves"], assumptions.exit_cap_rate)
    terminal_balance = final_year["ending_loan_balance"]
    net_sale_proceeds = sale_price * (1.0 - assumptions.selling_cost_rate) - terminal_balance
    cash_flows = [-equity_invested] + [row["cash_flow_before_tax"] for row in pro_forma]
    cash_flows[-1] += net_sale_proceeds
    final_year["sale_proceeds"] = net_sale_proceeds
    final_year["total_cash_flow"] = final_year["cash_flow_before_tax"] + net_sale_proceeds
    suggested_offer, binding_constraint = suggested_max_offer(assumptions, first_year["noi_before_reserves"])

    return UnderwritingMetrics(
        effective_gross_income=first_year["effective_gross_income"],
        noi_before_reserves=first_year["noi_before_reserves"],
        noi_after_reserves=first_year["noi_after_reserves"],
        cash_flow_before_tax=first_year["cash_flow_before_tax"],
        cap_rate=cap_rate(first_year["noi_before_reserves"], assumptions.purchase_price),
        annual_debt_service=debt_service,
        dscr=dscr(first_year["noi_before_reserves"], debt_service),
        cash_on_cash=cash_on_cash(first_year["cash_flow_before_tax"], equity_invested),
        irr=irr(cash_flows),
        npv=npv(assumptions.discount_rate, cash_flows),
        equity_multiple=equity_multiple(cash_flows, equity_invested),
        break_even_occupancy=break_even_occupancy(
            first_year["operating_expenses"],
            first_year["capex_reserve"],
            debt_service,
            first_year["gross_potential_rent"],
            assumptions.other_income,
        ),
        exit_value=sale_price,
        suggested_max_offer=suggested_offer,
        binding_offer_constraint=binding_constraint,
        terminal_loan_balance=terminal_balance,
        pro_forma=pro_forma,
    )
