from __future__ import annotations

import unittest

from multifamily_screener.schemas import ProvenanceField
from multifamily_screener.enrichment import enrich_property_input
from multifamily_screener.ingestion import load_property_json
from multifamily_screener.normalization import normalize_property
from multifamily_screener.reports import build_report
from multifamily_screener.underwriting import (
    annual_debt_service,
    break_even_occupancy,
    dscr,
    effective_gross_income,
    irr,
    noi,
    npv,
    suggested_max_offer,
)


class UnderwritingTests(unittest.TestCase):
    def test_effective_gross_income_and_noi(self) -> None:
        egi = effective_gross_income(100_000, 0.05, 5_000)
        self.assertAlmostEqual(egi, 100_000)
        self.assertAlmostEqual(noi(egi, 35_000, 2_500), 62_500)

    def test_annual_debt_service_zero_interest(self) -> None:
        self.assertAlmostEqual(annual_debt_service(300_000, 0.0, 30), 10_000)

    def test_annual_debt_service_amortizing(self) -> None:
        self.assertAlmostEqual(annual_debt_service(1_000_000, 0.06, 30), 71_946.06, places=2)

    def test_break_even_occupancy_is_clamped(self) -> None:
        self.assertAlmostEqual(break_even_occupancy(20_000, 5_000, 10_000, 100_000, 0), 0.35)
        self.assertEqual(break_even_occupancy(200_000, 5_000, 10_000, 100_000, 0), 1.0)

    def test_irr_for_simple_cash_flows(self) -> None:
        self.assertAlmostEqual(irr([-100, 60, 60]) or 0.0, 0.130662, places=5)

    def test_npv_for_simple_cash_flows(self) -> None:
        self.assertAlmostEqual(npv(0.10, [-100, 60, 60]), -100 + 60 / 1.1 + 60 / 1.21)

    def test_dscr(self) -> None:
        self.assertAlmostEqual(dscr(125_000, 100_000) or 0.0, 1.25)

    def test_suggested_offer_is_positive_and_below_rich_price(self) -> None:
        property_input = load_property_json("examples/sample_property.json")
        report = build_report(property_input)
        assumptions = normalize_property(enrich_property_input(property_input))
        offer = suggested_max_offer(assumptions, report.metrics.noi)
        self.assertGreater(offer, 0)
        self.assertLess(offer, assumptions.purchase_price)

    def test_provenance_field_defaults_missing_review_flag(self) -> None:
        field = ProvenanceField()
        self.assertTrue(field.review_flag)


if __name__ == "__main__":
    unittest.main()
