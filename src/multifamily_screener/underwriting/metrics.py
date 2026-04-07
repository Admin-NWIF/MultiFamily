from __future__ import annotations

from multifamily_screener.schemas import UnderwritingAssumptions, UnderwritingMetrics
from multifamily_screener.underwriting.common import safe_divide
from multifamily_screener.underwriting.dcf import equity_multiple, irr, npv
from multifamily_screener.underwriting.debt import annual_debt_service, dscr, loan_balance
from multifamily_screener.underwriting.expenses import break_even_occupancy, noi
from multifamily_screener.underwriting.income import effective_gross_income
from multifamily_screener.underwriting.offer import exit_value, suggested_max_offer


def cap_rate(noi_value: float, purchase_price: float) -> float:
    return safe_divide(noi_value, purchase_price) or 0.0


def cash_on_cash(noi_value: float, annual_debt_service_value: float, equity_invested: float) -> float | None:
    return safe_divide(noi_value - annual_debt_service_value, equity_invested)


def calculate_metrics(assumptions: UnderwritingAssumptions) -> UnderwritingMetrics:
    egi = effective_gross_income(
        assumptions.gross_potential_rent,
        assumptions.vacancy_rate,
        assumptions.other_income,
    )
    noi_value = noi(egi, assumptions.operating_expenses, assumptions.capex_reserve)
    debt_service = annual_debt_service(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
    )
    acquisition_costs = assumptions.purchase_price * assumptions.acquisition_cost_rate
    equity_invested = assumptions.purchase_price - assumptions.loan_amount + acquisition_costs
    sale_price = exit_value(noi_value, assumptions.exit_cap_rate)
    terminal_balance = loan_balance(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
        assumptions.hold_years,
    )
    net_sale_proceeds = sale_price * (1.0 - assumptions.selling_cost_rate) - terminal_balance
    annual_cash_flow = noi_value - debt_service
    cash_flows = [-equity_invested] + [annual_cash_flow] * assumptions.hold_years
    cash_flows[-1] += net_sale_proceeds

    return UnderwritingMetrics(
        effective_gross_income=egi,
        noi=noi_value,
        cap_rate=cap_rate(noi_value, assumptions.purchase_price),
        annual_debt_service=debt_service,
        dscr=dscr(noi_value, debt_service),
        cash_on_cash=cash_on_cash(noi_value, debt_service, equity_invested),
        irr=irr(cash_flows),
        npv=npv(assumptions.discount_rate, cash_flows),
        equity_multiple=equity_multiple(cash_flows, equity_invested),
        break_even_occupancy=break_even_occupancy(
            assumptions.operating_expenses,
            assumptions.capex_reserve,
            debt_service,
            assumptions.gross_potential_rent,
            assumptions.other_income,
        ),
        exit_value=sale_price,
        suggested_max_offer=suggested_max_offer(assumptions, noi_value),
        terminal_loan_balance=terminal_balance,
    )
