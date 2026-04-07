from __future__ import annotations

from multifamily_screener.reports import build_report
from multifamily_screener.scoring import calculate_deal_score
from multifamily_screener.schemas import Report

FinalReport = Report


def screen_properties(properties: list[dict]) -> list[FinalReport]:
    reports = [build_report(property_data) for property_data in properties]
    return rank_reports(reports)


def shortlist_properties(reports: list[FinalReport], top_n: int = 10) -> list[FinalReport]:
    qualified = [
        report
        for report in reports
        if report.metrics.npv > 0
        and report.metrics.dscr is not None
        and report.metrics.dscr >= 1.2
        and report.metrics.irr is not None
        and report.metrics.irr >= 0.12
        and report.total_flags <= 6
    ]
    return rank_reports(qualified)[:top_n]


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
