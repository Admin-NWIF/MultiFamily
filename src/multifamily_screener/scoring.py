from __future__ import annotations

from multifamily_screener.schemas import Decision, Flag, ProvenanceStatus, UnderwritingAssumptions, UnderwritingMetrics


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


def score_deal(assumptions: UnderwritingAssumptions, metrics: UnderwritingMetrics) -> Decision:
    score = 0
    reasons: list[str] = []

    if metrics.dscr is not None and metrics.dscr >= assumptions.target_dscr:
        score += 30
        reasons.append("DSCR meets target")
    if metrics.cap_rate >= assumptions.target_cap_rate:
        score += 25
        reasons.append("Cap rate meets target")
    if metrics.cash_on_cash is not None and metrics.cash_on_cash >= assumptions.target_cash_on_cash:
        score += 25
        reasons.append("Cash-on-cash meets target")
    if assumptions.purchase_price <= metrics.suggested_max_offer:
        score += 20
        reasons.append("Purchase price is at or below suggested max offer")

    estimated_count = sum(
        1
        for provenance in assumptions.provenance.values()
        if provenance.status in {ProvenanceStatus.ESTIMATED, ProvenanceStatus.DEFAULTED, ProvenanceStatus.MISSING}
    )
    if estimated_count >= 4:
        score = max(0, score - 10)
        reasons.append("Multiple estimated/defaulted inputs reduce confidence")

    if score >= 75:
        recommendation = "pursue"
    elif score >= 45:
        recommendation = "review"
    else:
        recommendation = "pass"

    return Decision(recommendation=recommendation, score=score, reasons=reasons)
