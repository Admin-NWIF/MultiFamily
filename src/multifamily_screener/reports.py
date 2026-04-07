from __future__ import annotations

from multifamily_screener.enrichment import enrich_assumptions, enrich_property_input
from multifamily_screener.ingestion import parse_property_json
from multifamily_screener.normalization import normalize_property
from multifamily_screener.schemas import NormalizedPropertyInput, Report
from multifamily_screener.scoring import collect_flags, score_deal
from multifamily_screener.underwriting import calculate_metrics


def build_report(property_input: NormalizedPropertyInput | dict) -> Report:
    parsed = parse_property_json(property_input) if isinstance(property_input, dict) else property_input
    enriched = enrich_property_input(parsed)
    assumptions = enrich_assumptions(normalize_property(enriched))
    metrics = calculate_metrics(assumptions)
    decision = score_deal(assumptions, metrics)
    flags = collect_flags(assumptions, metrics)
    return Report(
        property_id=assumptions.property_id,
        name=assumptions.name,
        address=assumptions.address,
        metrics=metrics,
        decision=decision,
        flags=flags,
        provenance=assumptions.provenance,
    )
