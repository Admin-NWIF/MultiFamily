from __future__ import annotations

from multifamily_screener.reports import build_report
from multifamily_screener.scoring import calculate_deal_score
from multifamily_screener.schemas import Report

FinalReport = Report


def screen_properties(properties: list[dict]) -> list[FinalReport]:
    reports = [build_report(property_data) for property_data in properties]
    return rank_reports(reports)


def shortlist_properties(
    reports: list[FinalReport],
    top_n: int = 10,
    score_threshold: float = 45.0,
) -> list[FinalReport]:
    ranked = rank_reports(reports)
    shortlisted: list[FinalReport] = []
    for index, report in enumerate(ranked):
        if report.decision.score > score_threshold or index < top_n:
            shortlisted.append(report)
    return shortlisted


def rank_reports(reports: list[FinalReport]) -> list[FinalReport]:
    return sorted(
        reports,
        key=lambda report: (
            _ranking_score(report),
            report.metrics.irr if report.metrics.irr is not None else float("-inf"),
            report.metrics.cash_on_cash if report.metrics.cash_on_cash is not None else float("-inf"),
        ),
        reverse=True,
    )


def _ranking_score(report: FinalReport) -> float:
    return calculate_deal_score(report.metrics, report.flags, report.provenance)
