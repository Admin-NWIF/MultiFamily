from __future__ import annotations

from multifamily_screener.schemas import UnderwritingAssumptions, UnderwritingMetrics
from multifamily_screener.underwriting.common import safe_divide
from multifamily_screener.underwriting.dcf import equity_multiple, irr, npv
from multifamily_screener.underwriting.debt import annual_debt_service, dscr, loan_balance
from multifamily_screener.underwriting.expenses import break_even_occupancy
from multifamily_screener.underwriting.offer import analyze_suggested_offer, exit_value
from multifamily_screener.underwriting.pro_forma import build_pro_forma


def cap_rate(noi_value: float, purchase_price: float) -> float:
    return safe_divide(noi_value, purchase_price) or 0.0


def cash_on_cash(cash_flow_before_tax: float, equity_invested: float) -> float | None:
    return safe_divide(cash_flow_before_tax, equity_invested)


def calculate_metrics(assumptions: UnderwritingAssumptions) -> UnderwritingMetrics:
    pro_forma = build_pro_forma(assumptions)
    first_year = pro_forma[0]
    final_year = pro_forma[-1]
    debt_service = annual_debt_service(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
    )
    acquisition_costs = assumptions.purchase_price * assumptions.acquisition_cost_rate
    equity_invested = assumptions.purchase_price - assumptions.loan_amount + acquisition_costs
    sale_price = exit_value(final_year.noi_before_reserves, assumptions.exit_cap_rate)
    terminal_balance = loan_balance(
        assumptions.loan_amount,
        assumptions.interest_rate,
        assumptions.amortization_years,
        assumptions.hold_years,
    )
    net_sale_proceeds = sale_price * (1.0 - assumptions.selling_cost_rate) - terminal_balance
    cash_flows = [-equity_invested] + [row.cash_flow_before_tax for row in pro_forma]
    cash_flows[-1] += net_sale_proceeds
    offer_analysis = analyze_suggested_offer(assumptions, first_year.noi_before_reserves)
    final_year.sale_proceeds = net_sale_proceeds
    final_year.total_cash_flow = final_year.cash_flow_before_tax + net_sale_proceeds
    pro_forma_payload = [row.model_dump(mode="json") for row in pro_forma]

    return UnderwritingMetrics(
        effective_gross_income=first_year.effective_gross_income,
        noi_before_reserves=first_year.noi_before_reserves,
        noi_after_reserves=first_year.noi_after_reserves,
        cash_flow_before_tax=first_year.cash_flow_before_tax,
        cap_rate=cap_rate(first_year.noi_before_reserves, assumptions.purchase_price),
        annual_debt_service=debt_service,
        dscr=dscr(first_year.noi_before_reserves, debt_service),
        cash_on_cash=cash_on_cash(first_year.cash_flow_before_tax, equity_invested),
        irr=irr(cash_flows),
        npv=npv(assumptions.discount_rate, cash_flows),
        equity_multiple=equity_multiple(cash_flows, equity_invested),
        break_even_occupancy=break_even_occupancy(
            first_year.operating_expenses,
            first_year.capex_reserve,
            debt_service,
            first_year.gross_potential_rent,
            first_year.other_income,
        ),
        exit_value=sale_price,
        suggested_max_offer=offer_analysis.suggested_max_offer,
        binding_offer_constraint=offer_analysis.binding_constraint,
        pro_forma=pro_forma_payload,
        terminal_loan_balance=terminal_balance,
    )
