from __future__ import annotations

from pydantic import BaseModel

from multifamily_screener.schemas import NormalizedPropertyInput, ProvenanceField, ProvenanceStatus, UnderwritingAssumptions


class EnrichmentDefaults(BaseModel):
    vacancy_rate: float = 0.05
    rent_growth_rate: float = 0.03
    other_income: float = 0.0
    expense_growth_rate: float = 0.03
    capex_reserve: float = 250.0
    max_ltv: float = 0.70
    interest_rate: float = 0.065
    amortization_years: int = 30
    hold_years: int = 5
    exit_cap_rate: float = 0.065
    selling_cost_rate: float = 0.02
    acquisition_cost_rate: float = 0.02
    discount_rate: float = 0.10
    target_cap_rate: float = 0.065
    target_dscr: float = 1.25
    target_cash_on_cash: float = 0.08


def enrich_property_input(
    property_input: NormalizedPropertyInput,
    defaults: EnrichmentDefaults | None = None,
) -> NormalizedPropertyInput:
    defaults = defaults or EnrichmentDefaults()
    updates: dict[str, ProvenanceField] = {}

    for field_name, default_value in defaults.model_dump().items():
        current = getattr(property_input, field_name)
        if current is None or current.value is None:
            updates[field_name] = ProvenanceField(
                value=default_value,
                status=ProvenanceStatus.DEFAULTED,
                source="enrichment_defaults",
                confidence=0.5,
                review_flag=True,
                note=f"{field_name} filled by enrichment default.",
            )

    capex = updates.get("capex_reserve")
    if capex is not None and property_input.units is not None and property_input.units.value is not None:
        capex.value = float(capex.value) * float(property_input.units.value)
        capex.note = "capex_reserve filled as default reserve per unit."

    return property_input.model_copy(update=updates)


def enrich_assumptions(assumptions: UnderwritingAssumptions) -> UnderwritingAssumptions:
    """Hook for market rent, tax, insurance, and financing enrichments."""
    return assumptions
