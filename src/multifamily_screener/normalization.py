from __future__ import annotations

from typing import Any

from multifamily_screener.schemas import (
    NormalizedPropertyInput,
    ProvenanceField,
    ProvenanceStatus,
    UnderwritingAssumptions,
)


DEFAULTS: dict[str, float | int] = {
}


NUMERIC_FIELDS = (
    "purchase_price",
    "gross_potential_rent",
    "vacancy_rate",
    "other_income",
    "operating_expenses",
    "capex_reserve",
    "max_ltv",
    "interest_rate",
    "amortization_years",
    "hold_years",
    "exit_cap_rate",
    "selling_cost_rate",
    "acquisition_cost_rate",
    "discount_rate",
    "target_cap_rate",
    "target_dscr",
    "target_cash_on_cash",
)


def normalize_property(property_input: NormalizedPropertyInput) -> UnderwritingAssumptions:
    provenance: dict[str, ProvenanceField] = {}
    values: dict[str, Any] = {
        "property_id": property_input.property_id,
        "name": property_input.name,
        "address": property_input.address,
    }

    values["units"] = int(_resolve_field("units", property_input.units, provenance))

    for field_name in NUMERIC_FIELDS:
        field = getattr(property_input, field_name, None)
        values[field_name] = float(_resolve_field(field_name, field, provenance))

    loan_amount = property_input.loan_amount
    values["loan_amount"] = 0.0 if loan_amount is None or loan_amount.value is None else float(_resolve_field("loan_amount", loan_amount, provenance))

    if values["loan_amount"] <= 0:
        values["loan_amount"] = values["purchase_price"] * values["max_ltv"]
        provenance["loan_amount"] = ProvenanceField(
            value=values["loan_amount"],
            status=ProvenanceStatus.DEFAULTED,
            source="purchase_price * max_ltv",
            confidence=min(
                provenance["purchase_price"].confidence,
                provenance["max_ltv"].confidence,
            ),
            review_flag=True,
            note="Loan amount defaulted from purchase price and max LTV.",
        )

    values["amortization_years"] = int(values["amortization_years"])
    values["hold_years"] = int(values["hold_years"])
    values["provenance"] = provenance
    return UnderwritingAssumptions.model_validate(values)


def _resolve_field(
    field_name: str,
    field: ProvenanceField | None,
    provenance: dict[str, ProvenanceField],
) -> float | int:
    default = DEFAULTS.get(field_name)
    if field is None or field.value is None:
        if default is None:
            provenance[field_name] = ProvenanceField(
                value=None,
                status=ProvenanceStatus.MISSING,
                source=None,
                confidence=0.0,
                review_flag=True,
                note=f"{field_name} is required for underwriting.",
            )
            raise ValueError(f"Missing required field: {field_name}")
        provenance[field_name] = ProvenanceField(
            value=default,
            status=ProvenanceStatus.DEFAULTED,
            source="system_default",
            confidence=0.5,
            review_flag=True,
            note=f"{field_name} defaulted to {default}.",
        )
        return default

    value = field.value
    status = field.status
    review_flag = field.review_flag or status in {
        ProvenanceStatus.ESTIMATED,
        ProvenanceStatus.DEFAULTED,
        ProvenanceStatus.MISSING,
    }
    provenance[field_name] = field.model_copy(
        update={"value": value, "review_flag": review_flag}
    )
    return value
