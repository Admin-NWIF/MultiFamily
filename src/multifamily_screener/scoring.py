from __future__ import annotations

from multifamily_screener.schemas import Decision, Flag, ProvenanceField, ProvenanceStatus, UnderwritingAssumptions, UnderwritingMetrics


def collect_flags(assumptions: UnderwritingAssumptions, metrics: UnderwritingMetrics) -> list[Flag]:
    flags: list[Flag] = []
    for field_name, provenance in assumptions.provenance.items():
        if provenance.status in {ProvenanceStatus.ESTIMATED, ProvenanceStatus.DEFAULTED, ProvenanceStatus.MISSING} or provenance.review_flag:
            severity = "critical" if provenance.status == ProvenanceStatus.MISSING else "warning"
            flags.append(
                Flag(
                    code="INPUT_REVIEW",
                    severity=severity,
                    field=field_name,
                    message=f"{field_name}: {provenance.status.value} input requires review",
                )
            )

    if metrics.dscr is not None and metrics.dscr < assumptions.target_dscr:
        flags.append(Flag(code="LOW_DSCR", severity="warning", message=f"DSCR {metrics.dscr:.2f} is below target {assumptions.target_dscr:.2f}"))
    if metrics.cap_rate < assumptions.target_cap_rate:
        flags.append(Flag(code="LOW_CAP_RATE", severity="warning", message=f"Cap rate {metrics.cap_rate:.2%} is below target {assumptions.target_cap_rate:.2%}"))
    if metrics.cash_on_cash is not None and metrics.cash_on_cash < assumptions.target_cash_on_cash:
        flags.append(Flag(code="LOW_CASH_ON_CASH", severity="warning", message=f"Cash-on-cash {metrics.cash_on_cash:.2%} is below target {assumptions.target_cash_on_cash:.2%}"))
    if assumptions.purchase_price > metrics.suggested_max_offer:
        flags.append(Flag(code="PRICE_ABOVE_MAX_OFFER", severity="warning", message="Purchase price exceeds suggested max offer"))
    return flags


def score_deal(assumptions: UnderwritingAssumptions, metrics: UnderwritingMetrics, flags: list[Flag]) -> Decision:
    score = calculate_deal_score(metrics, flags, assumptions.provenance)
    reasons: list[str] = []

    if metrics.irr is not None:
        reasons.append("Score includes IRR contribution")
    if metrics.cash_on_cash is not None:
        reasons.append("Score includes cash-on-cash contribution")
    if metrics.dscr is not None:
        reasons.append("Score includes DSCR contribution")
    if flags:
        reasons.append("Score penalized for review flags")
    if count_low_confidence_fields(assumptions.provenance) > 0:
        reasons.append("Score penalized for low-confidence fields")

    estimated_count = count_estimated_or_defaulted_fields(assumptions.provenance)
    if estimated_count > 5:
        reasons.append("Score downgraded for more than 5 estimated/defaulted fields")

    if metrics.dscr is not None and metrics.dscr >= assumptions.target_dscr:
        reasons.append("DSCR meets target")
    if metrics.cap_rate >= assumptions.target_cap_rate:
        reasons.append("Cap rate meets target")
    if metrics.cash_on_cash is not None and metrics.cash_on_cash >= assumptions.target_cash_on_cash:
        reasons.append("Cash-on-cash meets target")
    if assumptions.purchase_price <= metrics.suggested_max_offer:
        reasons.append("Purchase price is at or below suggested max offer")

    if score >= 75:
        recommendation = "pursue"
    elif score >= 45:
        recommendation = "review"
    else:
        recommendation = "pass"

    return Decision(recommendation=recommendation, score=score, reasons=reasons)


def calculate_deal_score(
    metrics: UnderwritingMetrics,
    flags: list[Flag],
    provenance: dict[str, ProvenanceField],
) -> float:
    irr = metrics.irr or 0.0
    cash_on_cash = metrics.cash_on_cash or 0.0
    dscr_value = metrics.dscr or 0.0
    flag_penalty = 5 * len(flags)
    low_confidence_penalty = 3 * count_low_confidence_fields(provenance)
    estimated_defaulted_penalty = 20 if count_estimated_or_defaulted_fields(provenance) > 5 else 0
    return (
        (irr * 100)
        + (cash_on_cash * 50)
        + (dscr_value * 10)
        - flag_penalty
        - low_confidence_penalty
        - estimated_defaulted_penalty
    )


def calculate_data_quality_score(flags: list[Flag], provenance: dict[str, ProvenanceField]) -> float:
    downgrade = 20 if count_estimated_or_defaulted_fields(provenance) > 5 else 0
    return max(0.0, 100.0 - (5 * len(flags)) - (3 * count_low_confidence_fields(provenance)) - downgrade)


def count_low_confidence_fields(provenance: dict[str, ProvenanceField]) -> int:
    return sum(1 for field in provenance.values() if field.confidence == "low")


def count_estimated_or_defaulted_fields(provenance: dict[str, ProvenanceField]) -> int:
    return sum(
        1
        for field in provenance.values()
        if field.status in {ProvenanceStatus.ESTIMATED, ProvenanceStatus.DEFAULTED}
    )
