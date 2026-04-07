from __future__ import annotations

from multifamily_screener.schemas import OfferAnalysis, UnderwritingAssumptions
from multifamily_screener.underwriting.common import safe_divide
from multifamily_screener.underwriting.debt import mortgage_constant


def exit_value(noi_value: float, exit_cap_rate: float) -> float:
    return safe_divide(noi_value, exit_cap_rate) or 0.0


def suggested_max_offer(assumptions: UnderwritingAssumptions, noi_value: float) -> tuple[float, str | None]:
    analysis = analyze_suggested_offer(assumptions, noi_value)
    return analysis.suggested_max_offer, analysis.binding_constraint


def analyze_suggested_offer(assumptions: UnderwritingAssumptions, noi_value: float) -> OfferAnalysis:
    cap_offer = safe_divide(noi_value, assumptions.target_cap_rate) or 0.0
    debt_constant = mortgage_constant(assumptions.interest_rate, assumptions.amortization_years)
    supported_loan = safe_divide(noi_value, assumptions.target_dscr * debt_constant) or 0.0
    dscr_offer = safe_divide(supported_loan, assumptions.max_ltv) or 0.0
    coc_denominator = assumptions.max_ltv * debt_constant + assumptions.target_cash_on_cash * (
        1.0 - assumptions.max_ltv + assumptions.acquisition_cost_rate
    )
    coc_offer = safe_divide(noi_value, coc_denominator) or 0.0
    candidates = {
        "cap_rate": cap_offer,
        "dscr": dscr_offer,
        "cash_on_cash": coc_offer,
    }
    positive_candidates = {key: value for key, value in candidates.items() if value > 0}
    if not positive_candidates:
        return OfferAnalysis(
            suggested_max_offer=0.0,
            binding_constraint=None,
            cap_rate_offer=cap_offer,
            dscr_offer=dscr_offer,
            cash_on_cash_offer=coc_offer,
        )
    binding_constraint = min(positive_candidates, key=positive_candidates.get)
    return OfferAnalysis(
        suggested_max_offer=positive_candidates[binding_constraint],
        binding_constraint=binding_constraint,
        cap_rate_offer=cap_offer,
        dscr_offer=dscr_offer,
        cash_on_cash_offer=coc_offer,
    )
