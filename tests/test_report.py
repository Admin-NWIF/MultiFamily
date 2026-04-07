from __future__ import annotations

import json
import unittest
from pathlib import Path

from multifamily_screener.ingestion import load_property_json
from multifamily_screener.reports import build_report


class ReportTests(unittest.TestCase):
    def test_build_report_from_sample(self) -> None:
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_property.json"
        report = build_report(load_property_json(sample_path))

        self.assertEqual(report.property_id, "six-unit-oakland-demo")
        self.assertGreater(report.metrics.noi_before_reserves, 0)
        self.assertGreater(report.metrics.noi_after_reserves, 0)
        self.assertEqual(len(report.pro_forma), 5)
        self.assertEqual(report.pro_forma, report.metrics.pro_forma)
        self.assertGreater(report.pro_forma[-1]["sale_proceeds"], 0)
        self.assertGreater(report.metrics.annual_debt_service, 0)
        self.assertIsNotNone(report.metrics.dscr)
        self.assertGreater(report.metrics.suggested_max_offer, 0)
        self.assertIn(report.metrics.binding_offer_constraint, {"cap_rate", "dscr", "cash_on_cash"})
        self.assertIn(report.decision.recommendation, {"pass", "review", "pursue"})
        self.assertIn("purchase_price", report.provenance)
        self.assertEqual(report.provenance["purchase_price"].value, 1_650_000)
        self.assertEqual(report.provenance["other_income"].status, "defaulted")

    def test_report_is_json_serializable(self) -> None:
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_property.json"
        report = build_report(json.loads(sample_path.read_text()))

        payload = report.model_dump(mode="json")
        self.assertGreater(payload["metrics"]["noi_before_reserves"], 0)
        self.assertIn("pro_forma", payload)
        self.assertIn("assumed_fields", payload)
        self.assertEqual(payload["provenance"]["gross_potential_rent"]["status"], "estimated")
        self.assertEqual(payload["provenance"]["vacancy_rate"]["source"], "enrichment_defaults")


if __name__ == "__main__":
    unittest.main()
