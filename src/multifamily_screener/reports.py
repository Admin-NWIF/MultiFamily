from __future__ import annotations

from multifamily_screener.enrichment import enrich_assumptions, enrich_property_input
from multifamily_screener.ingestion import parse_property_json
from multifamily_screener.normalization import normalize_property
from multifamily_screener.schemas import NormalizedPropertyInput, ProvenanceStatus, Report
from multifamily_screener.scoring import collect_flags, score_deal
from multifamily_screener.underwriting import build_pro_forma, calculate_metrics


def build_report(property_input: NormalizedPropertyInput | dict) -> Report:
    parsed = parse_property_json(property_input) if isinstance(property_input, dict) else property_input
    enriched = enrich_property_input(parsed)
    assumptions = enrich_assumptions(normalize_property(enriched))
    metrics = calculate_metrics(assumptions)
    pro_forma = build_pro_forma(assumptions)
    final_year = pro_forma[-1]
    final_year.sale_proceeds = metrics.exit_value * (1.0 - assumptions.selling_cost_rate) - metrics.terminal_loan_balance
    final_year.total_cash_flow = final_year.cash_flow_before_tax + final_year.sale_proceeds
    assumed_fields = {
        field_name: provenance
        for field_name, provenance in assumptions.provenance.items()
        if provenance.status in {ProvenanceStatus.ESTIMATED, ProvenanceStatus.DEFAULTED, ProvenanceStatus.MISSING}
        or provenance.review_flag
    }
    decision = score_deal(assumptions, metrics)
    flags = collect_flags(assumptions, metrics)
    return Report(
        property_id=assumptions.property_id,
        name=assumptions.name,
        address=assumptions.address,
        metrics=metrics,
        pro_forma=pro_forma,
        assumed_fields=assumed_fields,
        decision=decision,
        flags=flags,
        provenance=assumptions.provenance,
    )
