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
    build_pro_forma,
    dscr,
    effective_gross_income,
    exit_value,
    irr,
    loan_balance,
    noi_after_reserves,
    noi_before_reserves,
    npv,
    suggested_max_offer,
)


class UnderwritingTests(unittest.TestCase):
    def test_noi_before_reserves_and_after_reserves_are_separate(self) -> None:
        egi = effective_gross_income(100_000, 0.05, 5_000)
        self.assertAlmostEqual(egi, 100_000)
        before_reserves = noi_before_reserves(egi, 35_000)
        after_reserves = noi_after_reserves(before_reserves, 2_500)
        self.assertAlmostEqual(before_reserves, 65_000)
        self.assertAlmostEqual(after_reserves, 62_500)

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
        offer, binding_constraint = suggested_max_offer(assumptions, report.metrics.noi_before_reserves)
        self.assertGreater(offer, 0)
        self.assertLess(offer, assumptions.purchase_price)
        self.assertIn(binding_constraint, {"cap_rate", "dscr", "cash_on_cash"})

    def test_rent_growth_is_applied_year_by_year(self) -> None:
        assumptions = normalize_property(enrich_property_input(load_property_json("examples/sample_property.json")))
        rows = build_pro_forma(assumptions)
        self.assertAlmostEqual(rows[0].gross_potential_rent, assumptions.gross_potential_rent)
        self.assertAlmostEqual(rows[1].gross_potential_rent, assumptions.gross_potential_rent * 1.03)

    def test_year_2_gross_potential_rent_exceeds_year_1_in_metrics_pro_forma(self) -> None:
        report = build_report(load_property_json("examples/sample_property.json"))
        self.assertGreater(
            report.metrics.pro_forma[1]["gross_potential_rent"],
            report.metrics.pro_forma[0]["gross_potential_rent"],
        )

    def test_expense_growth_is_applied_year_by_year(self) -> None:
        assumptions = normalize_property(enrich_property_input(load_property_json("examples/sample_property.json")))
        rows = build_pro_forma(assumptions)
        self.assertAlmostEqual(rows[0].operating_expenses, assumptions.operating_expenses)
        self.assertAlmostEqual(rows[1].operating_expenses, assumptions.operating_expenses * 1.025)

    def test_year_2_operating_expenses_exceed_year_1_in_metrics_pro_forma(self) -> None:
        report = build_report(load_property_json("examples/sample_property.json"))
        self.assertGreater(
            report.metrics.pro_forma[1]["operating_expenses"],
            report.metrics.pro_forma[0]["operating_expenses"],
        )

    def test_dscr_uses_noi_before_reserves(self) -> None:
        report = build_report(load_property_json("examples/sample_property.json"))
        first_year = report.pro_forma[0]
        expected_dscr = first_year["noi_before_reserves"] / first_year["annual_debt_service"]
        after_reserve_dscr = first_year["noi_after_reserves"] / first_year["annual_debt_service"]
        self.assertAlmostEqual(report.metrics.dscr or 0.0, expected_dscr)
        self.assertGreater(report.metrics.dscr or 0.0, after_reserve_dscr)

    def test_irr_and_npv_include_final_year_sale_proceeds(self) -> None:
        property_input = load_property_json("examples/sample_property.json")
        assumptions = normalize_property(enrich_property_input(property_input))
        report = build_report(property_input)
        rows = build_pro_forma(assumptions)
        equity = assumptions.purchase_price - assumptions.loan_amount + assumptions.purchase_price * assumptions.acquisition_cost_rate
        final_sale_value = exit_value(rows[-1].noi_before_reserves, assumptions.exit_cap_rate)
        terminal_balance = loan_balance(
            assumptions.loan_amount,
            assumptions.interest_rate,
            assumptions.amortization_years,
            assumptions.hold_years,
        )
        sale_proceeds = final_sale_value * (1.0 - assumptions.selling_cost_rate) - terminal_balance
        cash_flows_with_sale = [-equity] + [row.cash_flow_before_tax for row in rows]
        cash_flows_without_sale = list(cash_flows_with_sale)
        cash_flows_with_sale[-1] += sale_proceeds
        self.assertAlmostEqual(report.pro_forma[-1]["sale_proceeds"], sale_proceeds)
        self.assertAlmostEqual(
            report.pro_forma[-1]["total_cash_flow"],
            report.pro_forma[-1]["cash_flow_before_tax"] + sale_proceeds,
        )
        self.assertAlmostEqual(report.metrics.npv, npv(assumptions.discount_rate, cash_flows_with_sale))
        self.assertGreater(report.metrics.npv, npv(assumptions.discount_rate, cash_flows_without_sale))
        self.assertAlmostEqual(report.metrics.irr or 0.0, irr(cash_flows_with_sale) or 0.0)

    def test_binding_offer_constraint_is_populated(self) -> None:
        report = build_report(load_property_json("examples/sample_property.json"))
        self.assertIn(report.metrics.binding_offer_constraint, {"cap_rate", "dscr", "cash_on_cash"})

    def test_noi_before_reserves_differs_from_after_reserves_when_capex_is_positive(self) -> None:
        report = build_report(load_property_json("examples/sample_property.json"))
        first_year = report.metrics.pro_forma[0]
        self.assertGreater(first_year["capex_reserve"], 0)
        self.assertNotEqual(first_year["noi_before_reserves"], first_year["noi_after_reserves"])

    def test_provenance_field_defaults_missing_review_flag(self) -> None:
        field = ProvenanceField()
        self.assertTrue(field.review_flag)


if __name__ == "__main__":
    unittest.main()
