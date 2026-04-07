from __future__ import annotations

from multifamily_screener.enrichment import enrich_assumptions, enrich_property_input
from multifamily_screener.ingestion import parse_property_json
from multifamily_screener.normalization import normalize_property
from multifamily_screener.schemas import NormalizedPropertyInput, ProvenanceStatus, Report
from multifamily_screener.scoring import calculate_data_quality_score, collect_flags, count_low_confidence_fields, score_deal
from multifamily_screener.underwriting import calculate_metrics


def build_report(property_input: NormalizedPropertyInput | dict) -> Report:
    parsed = parse_property_json(property_input) if isinstance(property_input, dict) else property_input
    enriched = enrich_property_input(parsed)
    assumptions = enrich_assumptions(normalize_property(enriched))
    metrics = calculate_metrics(assumptions)
    assumed_fields = {
        field_name: provenance
        for field_name, provenance in assumptions.provenance.items()
        if provenance.status in {ProvenanceStatus.ESTIMATED, ProvenanceStatus.DEFAULTED, ProvenanceStatus.MISSING}
        or provenance.review_flag
    }
    flags = collect_flags(assumptions, metrics)
    decision = score_deal(assumptions, metrics, flags)
    return Report(
        property_id=assumptions.property_id,
        name=assumptions.name,
        address=assumptions.address,
        metrics=metrics,
        pro_forma=metrics.pro_forma,
        assumed_fields=assumed_fields,
        decision=decision,
        flags=flags,
        provenance=assumptions.provenance,
        data_quality_score=calculate_data_quality_score(flags, assumptions.provenance),
        total_flags=len(flags),
        low_confidence_fields=count_low_confidence_fields(assumptions.provenance),
    )
