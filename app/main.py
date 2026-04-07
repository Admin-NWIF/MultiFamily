from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from multifamily_screener.ingestion import load_property_json
from multifamily_screener.reports import build_report
from multifamily_screener.schemas import Report


def main() -> int:
    parser = argparse.ArgumentParser(description="Screen a normalized multifamily property JSON file.")
    parser.add_argument("property_json", help="Path to normalized property JSON.")
    args = parser.parse_args()

    report = build_report(load_property_json(args.property_json))
    print_summary(report)
    print("\nFull report JSON:")
    print(report.model_dump_json(indent=2))
    return 0


def print_summary(report: Report) -> None:
    metrics = report.metrics
    print(f"{report.name or report.property_id}")
    if report.address:
        print(report.address)
    print(f"Decision: {report.decision.recommendation.upper()} ({report.decision.score}/100)")
    print("")
    print("Metrics:")
    print(f"  NOI before reserves: ${metrics.noi_before_reserves:,.0f}")
    print(f"  NOI after reserves: ${metrics.noi_after_reserves:,.0f}")
    print(f"  Cash flow before tax: ${metrics.cash_flow_before_tax:,.0f}")
    print(f"  Cap rate: {metrics.cap_rate:.2%}")
    print(f"  Annual debt service: ${metrics.annual_debt_service:,.0f}")
    print(f"  DSCR: {_format_ratio(metrics.dscr)}")
    print(f"  Cash-on-cash: {_format_percent(metrics.cash_on_cash)}")
    print(f"  IRR: {_format_percent(metrics.irr)}")
    print(f"  NPV: ${metrics.npv:,.0f}")
    print(f"  Equity multiple: {_format_ratio(metrics.equity_multiple)}x")
    print(f"  Break-even occupancy: {metrics.break_even_occupancy:.2%}")
    print(f"  Exit value: ${metrics.exit_value:,.0f}")
    print(f"  Suggested max offer: ${metrics.suggested_max_offer:,.0f}")
    print(f"  Binding offer constraint: {metrics.suggested_max_offer_binding_constraint}")
    print("")
    print("Pro Forma:")
    for row in report.pro_forma:
        sale_note = f", sale proceeds ${row.sale_proceeds:,.0f}" if row.sale_proceeds else ""
        print(
            f"  Year {row.year}: EGI ${row.effective_gross_income:,.0f}, "
            f"NOI before reserves ${row.noi_before_reserves:,.0f}, "
            f"NOI after reserves ${row.noi_after_reserves:,.0f}, "
            f"CFBT ${row.cash_flow_before_tax:,.0f}{sale_note}"
        )
    print("")
    print("Assumed/defaulted fields:")
    if not report.assumed_fields:
        print("  None")
    for field_name, provenance in report.assumed_fields.items():
        print(f"  - {field_name}: {provenance.status.value} from {provenance.source or 'unknown'}")
    print("")
    print("Flags:")
    if not report.flags:
        print("  None")
    for flag in report.flags:
        field = f" [{flag.field}]" if flag.field else ""
        print(f"  - {flag.severity.upper()}{field}: {flag.message}")


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
