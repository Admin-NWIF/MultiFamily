from __future__ import annotations

import argparse

from multifamily_screener.ingestion import load_property_json
from multifamily_screener.reports import build_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Underwrite a normalized multifamily property JSON file.")
    parser.add_argument("property_json", help="Path to normalized property JSON.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation for report output.")
    args = parser.parse_args()

    property_input = load_property_json(args.property_json)
    report = build_report(property_input)
    print(report.model_dump_json(indent=args.indent))
    return 0
