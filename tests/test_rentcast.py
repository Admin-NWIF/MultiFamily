from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multifamily_screener.ingestion.rentcast_client import RentCastClient, RentCastError
from multifamily_screener.normalization.rentcast_mapper import (
    map_rentcast_to_normalized_property,
    normalized_property_from_rentcast_address,
)
from multifamily_screener.reports import build_report


class FakeResponse:
    def __init__(self, payload: dict | list, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict | list:
        return self.payload


class RentCastTests(unittest.TestCase):
    def test_client_fetches_property_with_mocked_http_response(self) -> None:
        calls = []

        def fake_get(url: str, headers: dict, params: dict, timeout: float) -> FakeResponse:
            calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "params": params,
                    "timeout": timeout,
                }
            )
            return FakeResponse({"id": "rc_1", "formattedAddress": "2140 Oak St, Oakland, CA"})

        with patch("multifamily_screener.ingestion.rentcast_client.requests") as requests_mock:
            requests_mock.get.side_effect = fake_get
            client = RentCastClient(api_key="test-key", base_url="https://example.test", timeout=3)
            payload = client.fetch_property_by_address("2140 Oak St, Oakland, CA")

        self.assertEqual(payload["id"], "rc_1")
        self.assertEqual(calls[0]["url"], "https://example.test/properties")
        self.assertEqual(calls[0]["headers"]["X-Api-Key"], "test-key")
        self.assertEqual(calls[0]["params"], {"address": "2140 Oak St, Oakland, CA"})
        self.assertEqual(calls[0]["timeout"], 3)

    def test_client_tracks_api_request_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / "rentcast_api_usage.json"

            with patch("multifamily_screener.ingestion.rentcast_client.requests") as requests_mock:
                requests_mock.get.return_value = FakeResponse({"id": "rc_1"})
                client = RentCastClient(api_key="test-key", base_url="https://example.test", usage_path=usage_path)
                client.fetch_property_by_address("2140 Oak St, Oakland, CA")
                client.fetch_listing_by_address("2140 Oak St, Oakland, CA")

            self.assertEqual(json.loads(usage_path.read_text())["rentcast_requests"], 2)

    def test_client_stops_at_api_request_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / "rentcast_api_usage.json"
            usage_path.write_text(json.dumps({"rentcast_requests": 50}), encoding="utf-8")

            with patch("multifamily_screener.ingestion.rentcast_client.requests") as requests_mock:
                client = RentCastClient(api_key="test-key", base_url="https://example.test", usage_path=usage_path)
                with self.assertRaisesRegex(RentCastError, "request limit reached"):
                    client.fetch_property_by_address("2140 Oak St, Oakland, CA")

            requests_mock.get.assert_not_called()
            self.assertEqual(json.loads(usage_path.read_text())["rentcast_requests"], 50)

    def test_client_override_allows_requests_after_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            usage_path = Path(tmpdir) / "rentcast_api_usage.json"
            usage_path.write_text(json.dumps({"rentcast_requests": 50}), encoding="utf-8")

            with patch("multifamily_screener.ingestion.rentcast_client.requests") as requests_mock:
                requests_mock.get.return_value = FakeResponse({"id": "rc_1"})
                client = RentCastClient(
                    api_key="test-key",
                    base_url="https://example.test",
                    override_limit=True,
                    usage_path=usage_path,
                )
                client.fetch_property_by_address("2140 Oak St, Oakland, CA")

            requests_mock.get.assert_called_once()
            self.assertEqual(json.loads(usage_path.read_text())["rentcast_requests"], 51)

    def test_mapper_uses_rent_estimate_when_actual_rent_is_missing(self) -> None:
        normalized = map_rentcast_to_normalized_property(
            {
                "property": {
                    "id": "rc_2",
                    "formattedAddress": "2140 Oak St, Oakland, CA",
                    "units": 6,
                    "propertyType": "Apartment",
                    "operatingExpenses": 76_000,
                },
                "listing": {"price": 1_650_000},
                "rent_estimate": {"rent": 2_850},
            }
        )

        self.assertEqual(normalized["property_id"], "rc_2")
        self.assertEqual(normalized["address"], "2140 Oak St, Oakland, CA")
        self.assertEqual(normalized["units"]["value"], 6.0)
        self.assertEqual(normalized["purchase_price"]["value"], 1_650_000.0)
        self.assertEqual(normalized["gross_potential_rent"]["value"], 2_850 * 12 * 6)
        self.assertEqual(normalized["gross_potential_rent"]["status"], "estimated")
        self.assertTrue(normalized["gross_potential_rent"]["review_flag"])
        self.assertEqual(normalized["operating_expenses"]["value"], 76_000.0)
        self.assertEqual(normalized["rent_growth"]["value"], 0.03)
        self.assertEqual(normalized["expense_growth"]["value"], 0.025)

    def test_pipeline_from_mocked_rentcast_input_to_final_report(self) -> None:
        class FakeRentCastClient:
            def fetch_bundle_by_address(self, address: str) -> dict:
                return {
                    "property": {
                        "id": "rc_pipeline",
                        "formattedAddress": address,
                        "units": 6,
                        "propertyType": "Apartment",
                    },
                    "listing": {"price": 1_650_000},
                    "rent_estimate": None,
                }

            def fetch_rent_estimate_by_address(self, address: str) -> dict:
                return {"rent": 2_850}

        normalized = normalized_property_from_rentcast_address(
            "2140 Oak St, Oakland, CA",
            FakeRentCastClient(),
        )
        report = build_report(normalized)

        self.assertEqual(report.property_id, "rc_pipeline")
        self.assertEqual(report.address, "2140 Oak St, Oakland, CA")
        self.assertGreater(report.metrics.noi_before_reserves, 0)
        self.assertGreater(report.metrics.suggested_max_offer, 0)
        self.assertEqual(report.provenance["gross_potential_rent"].status, "estimated")
        self.assertEqual(report.provenance["operating_expenses"].status, "defaulted")
        self.assertGreater(report.total_flags, 0)


if __name__ == "__main__":
    unittest.main()
