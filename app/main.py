from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from multifamily_screener.reports import build_report
from multifamily_screener.schemas import Report
from multifamily_screener.screening.batch import screen_properties, shortlist_properties


PROVENANCE_FIELDS = {
    "units",
    "purchase_price",
    "gross_potential_rent",
    "rent_growth",
    "vacancy_rate",
    "other_income",
    "operating_expenses",
    "expense_growth",
    "capex_reserve",
    "loan_amount",
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
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Screen a normalized multifamily property JSON file.")
    parser.add_argument("property_json", help="Path to normalized property JSON.")
    args = parser.parse_args()

    payload = load_input_payload(args.property_json)
    if isinstance(payload, list):
        reports = screen_properties(payload)
        shortlist = shortlist_properties(reports)
        print_ranked_shortlist(shortlist)
        return 0

    report = build_report(payload)
    print_summary(report)
    print("\nFull report JSON:")
    print(report.model_dump_json(indent=2))
    return 0


def load_input_payload(path: str) -> dict[str, Any] | list[dict[str, Any]]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".csv":
        return load_property_csv(input_path)

    with input_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data
    raise ValueError("Input must be a JSON object, JSON array, or CSV file.")


def load_property_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        return [_csv_row_to_property(row) for row in csv.DictReader(fp)]


def _csv_row_to_property(row: dict[str, str | None]) -> dict[str, Any]:
    property_data: dict[str, Any] = {}
    for key, raw_value in row.items():
        if raw_value is None or raw_value == "":
            continue
        if key in {"property_id", "name", "address"}:
            property_data[key] = raw_value
        elif key in PROVENANCE_FIELDS:
            property_data[key] = {
                "value": _parse_csv_value(raw_value),
                "status": "actual",
                "source": "csv",
                "confidence": 0.8,
                "review_flag": False,
                "note": "Loaded from CSV input.",
            }
    return property_data


def _parse_csv_value(value: str) -> str | int | float:
    try:
        parsed = float(value)
    except ValueError:
        return value
    if parsed.is_integer():
        return int(parsed)
    return parsed


def print_ranked_shortlist(reports: list[Report]) -> None:
    print("Ranked Shortlist:")
    if not reports:
        print("  No deals met shortlist criteria.")
        return
    for rank, report in enumerate(reports, start=1):
        metrics = report.metrics
        asking_price = report.provenance.get("purchase_price")
        asking_value = asking_price.value if asking_price is not None else None
        print(
            f"{rank}. {report.address or report.name or report.property_id} | "
            f"asking_price: {_format_currency(asking_value)} | "
            f"suggested_offer: ${metrics.suggested_max_offer:,.0f} | "
            f"score: {report.decision.score:.1f} | "
            f"irr: {_format_percent(metrics.irr)} | "
            f"dscr: {_format_ratio(metrics.dscr)} | "
            f"cash_on_cash: {_format_percent(metrics.cash_on_cash)} | "
            f"total_flags: {report.total_flags} | "
            f"data_quality_score: {report.data_quality_score:.1f} | "
            f"binding_offer_constraint: {metrics.binding_offer_constraint or 'n/a'}"
        )


def print_summary(report: Report) -> None:
    metrics = report.metrics
    print(f"{report.name or report.property_id}")
    if report.address:
        print(report.address)
    print(f"Decision: {report.decision.recommendation.upper()} ({report.decision.score}/100)")
    print(f"Total flags: {report.total_flags}")
    print(f"Data quality score: {report.data_quality_score:.1f}")
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
    print(f"  Binding offer constraint: {metrics.binding_offer_constraint or 'n/a'}")
    print("")
    print("Pro Forma:")
    for row in report.pro_forma:
        sale_note = f", sale proceeds ${row['sale_proceeds']:,.0f}" if row["sale_proceeds"] else ""
        print(
            f"  Year {row['year']}: EGI ${row['effective_gross_income']:,.0f}, "
            f"NOI before reserves ${row['noi_before_reserves']:,.0f}, "
            f"NOI after reserves ${row['noi_after_reserves']:,.0f}, "
            f"CFBT ${row['cash_flow_before_tax']:,.0f}{sale_note}"
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


def _format_currency(value: Any) -> str:
    if isinstance(value, int | float):
        return f"${value:,.0f}"
    return "n/a" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
