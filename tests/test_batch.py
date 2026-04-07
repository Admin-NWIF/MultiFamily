from __future__ import annotations

import unittest
from pathlib import Path

from multifamily_screener.ingestion import load_property_json
from multifamily_screener.reports import build_report
from multifamily_screener.schemas import Flag
from multifamily_screener.screening.batch import rank_reports, screen_properties, shortlist_properties


class BatchScreeningTests(unittest.TestCase):
    def _base_report(self):
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_property.json"
        return build_report(load_property_json(sample_path))

    def test_ranking_sorts_correctly(self) -> None:
        first = self._base_report().model_copy(deep=True)
        second = self._base_report().model_copy(deep=True)
        third = self._base_report().model_copy(deep=True)
        first.property_id = "first"
        second.property_id = "second"
        third.property_id = "third"
        first.metrics.irr = 0.16
        first.metrics.cash_on_cash = 0.05
        second.metrics.irr = 0.18
        second.metrics.cash_on_cash = 0.04
        third.metrics.irr = 0.16
        third.metrics.cash_on_cash = 0.07
        for report in [first, second, third]:
            report.flags = []
            report.total_flags = 0

        ranked = rank_reports([first, second, third])

        self.assertEqual([report.property_id for report in ranked], ["second", "third", "first"])

    def test_shortlist_filters_correctly(self) -> None:
        good = self._base_report().model_copy(deep=True)
        negative_npv = self._base_report().model_copy(deep=True)
        low_dscr = self._base_report().model_copy(deep=True)
        low_irr = self._base_report().model_copy(deep=True)
        good.property_id = "good"
        negative_npv.property_id = "negative_npv"
        low_dscr.property_id = "low_dscr"
        low_irr.property_id = "low_irr"

        good.metrics.npv = 100_000
        good.metrics.dscr = 1.35
        good.metrics.irr = 0.15
        good.flags = []
        good.total_flags = 0
        negative_npv.metrics.npv = -1
        negative_npv.metrics.dscr = 1.35
        negative_npv.metrics.irr = 0.15
        negative_npv.flags = []
        negative_npv.total_flags = 0
        low_dscr.metrics.npv = 100_000
        low_dscr.metrics.dscr = 1.19
        low_dscr.metrics.irr = 0.15
        low_dscr.flags = []
        low_dscr.total_flags = 0
        low_irr.metrics.npv = 100_000
        low_irr.metrics.dscr = 1.35
        low_irr.metrics.irr = 0.119
        low_irr.flags = []
        low_irr.total_flags = 0

        shortlisted = shortlist_properties([negative_npv, low_dscr, low_irr, good])

        self.assertEqual([report.property_id for report in shortlisted], ["good"])

    def test_flags_affect_ranking(self) -> None:
        clean = self._base_report().model_copy(deep=True)
        flagged = self._base_report().model_copy(deep=True)
        clean.property_id = "clean"
        flagged.property_id = "flagged"
        clean.metrics.irr = 0.14
        clean.metrics.cash_on_cash = 0.05
        clean.flags = []
        clean.total_flags = 0
        flagged.metrics.irr = 0.15
        flagged.metrics.cash_on_cash = 0.10
        flagged.flags = [
            Flag(code="TEST", severity="warning", message="Synthetic flag."),
        ]
        flagged.total_flags = len(flagged.flags)

        ranked = rank_reports([flagged, clean])

        self.assertEqual([report.property_id for report in ranked], ["clean", "flagged"])

    def test_low_confidence_lowers_ranking(self) -> None:
        normal = self._base_report().model_copy(deep=True)
        low_confidence = self._base_report().model_copy(deep=True)
        normal.property_id = "normal"
        low_confidence.property_id = "low_confidence"
        normal.metrics.irr = 0.15
        low_confidence.metrics.irr = 0.15
        normal.metrics.cash_on_cash = 0.06
        low_confidence.metrics.cash_on_cash = 0.06
        normal.flags = []
        low_confidence.flags = []
        normal.total_flags = 0
        low_confidence.total_flags = 0
        low_confidence.provenance["purchase_price"].confidence = "low"

        ranked = rank_reports([low_confidence, normal])

        self.assertEqual([report.property_id for report in ranked], ["normal", "low_confidence"])

    def test_bad_data_gets_filtered_out(self) -> None:
        good = self._base_report().model_copy(deep=True)
        bad_data = self._base_report().model_copy(deep=True)
        good.property_id = "good"
        bad_data.property_id = "bad_data"
        for report in [good, bad_data]:
            report.metrics.npv = 100_000
            report.metrics.dscr = 1.35
            report.metrics.irr = 0.15
        good.flags = []
        good.total_flags = 0
        bad_data.flags = [
            Flag(code=f"TEST_{idx}", severity="warning", message="Synthetic flag.")
            for idx in range(7)
        ]
        bad_data.total_flags = len(bad_data.flags)

        shortlisted = shortlist_properties([bad_data, good])

        self.assertEqual([report.property_id for report in shortlisted], ["good"])

    def test_screen_properties_returns_ranked_reports(self) -> None:
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_batch.json"
        import json

        properties = json.loads(sample_path.read_text())
        reports = screen_properties(properties)

        self.assertEqual(len(reports), len(properties))
        self.assertTrue(all(report.metrics.binding_offer_constraint for report in reports))


if __name__ == "__main__":
    unittest.main()
