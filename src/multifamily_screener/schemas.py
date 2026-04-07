from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProvenanceStatus(StrEnum):
    ACTUAL = "actual"
    ESTIMATED = "estimated"
    DEFAULTED = "defaulted"
    MISSING = "missing"


class ProvenanceField(BaseModel):
    model_config = ConfigDict(validate_default=True)

    value: Any = None
    status: ProvenanceStatus = ProvenanceStatus.MISSING
    source: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    review_flag: bool = False
    note: str | None = None

    @model_validator(mode="after")
    def flag_missing_values(self) -> ProvenanceField:
        if self.status == ProvenanceStatus.MISSING:
            self.review_flag = True
        return self


class NormalizedPropertyInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    property_id: str
    name: str | None = None
    address: str | None = None
    units: ProvenanceField | None = None
    purchase_price: ProvenanceField | None = None
    gross_potential_rent: ProvenanceField | None = None
    vacancy_rate: ProvenanceField | None = None
    other_income: ProvenanceField | None = None
    operating_expenses: ProvenanceField | None = None
    capex_reserve: ProvenanceField | None = None
    loan_amount: ProvenanceField | None = None
    max_ltv: ProvenanceField | None = None
    interest_rate: ProvenanceField | None = None
    amortization_years: ProvenanceField | None = None
    hold_years: ProvenanceField | None = None
    exit_cap_rate: ProvenanceField | None = None
    selling_cost_rate: ProvenanceField | None = None
    acquisition_cost_rate: ProvenanceField | None = None
    discount_rate: ProvenanceField | None = None
    target_cap_rate: ProvenanceField | None = None
    target_dscr: ProvenanceField | None = None
    target_cash_on_cash: ProvenanceField | None = None


class UnderwritingAssumptions(BaseModel):
    property_id: str
    name: str | None = None
    address: str | None = None
    units: int
    purchase_price: float
    gross_potential_rent: float
    vacancy_rate: float
    other_income: float
    operating_expenses: float
    capex_reserve: float
    loan_amount: float
    max_ltv: float
    interest_rate: float
    amortization_years: int
    hold_years: int
    exit_cap_rate: float
    selling_cost_rate: float
    acquisition_cost_rate: float
    discount_rate: float
    target_cap_rate: float
    target_dscr: float
    target_cash_on_cash: float
    provenance: dict[str, ProvenanceField]


class UnderwritingMetrics(BaseModel):
    effective_gross_income: float
    noi: float
    cap_rate: float
    annual_debt_service: float
    dscr: float | None
    cash_on_cash: float | None
    irr: float | None
    npv: float
    equity_multiple: float | None
    break_even_occupancy: float
    exit_value: float
    suggested_max_offer: float
    terminal_loan_balance: float


class Decision(BaseModel):
    recommendation: Literal["pass", "review", "pursue"]
    score: int
    reasons: list[str]


class Flag(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    message: str
    field: str | None = None


class Report(BaseModel):
    property_id: str
    name: str | None = None
    address: str | None = None
    metrics: UnderwritingMetrics
    decision: Decision
    flags: list[Flag]
    provenance: dict[str, ProvenanceField]
