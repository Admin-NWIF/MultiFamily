from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - exercised only without optional dependency installed.
    requests = None  # type: ignore[assignment]


class RentCastError(RuntimeError):
    pass


class RentCastClient:
    BASE_URL = "https://api.rentcast.io/v1"
    REQUEST_LIMIT = 50

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 8.0,
        override_limit: bool = False,
        usage_path: str | Path | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("RENTCAST_API_KEY")
        if not self.api_key:
            raise RentCastError("Missing RENTCAST_API_KEY environment variable.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.override_limit = override_limit
        self.usage_path = Path(usage_path) if usage_path is not None else Path.cwd() / "outputs" / "rentcast_api_usage.json"

    def fetch_property_by_address(self, address: str) -> dict[str, Any] | list[dict[str, Any]]:
        return self._get("/properties", {"address": address})

    def fetch_listing_by_address(self, address: str) -> dict[str, Any] | list[dict[str, Any]]:
        return self._get("/listings/sale", {"address": address})

    def fetch_rent_estimate_by_address(self, address: str) -> dict[str, Any]:
        return self._get("/avm/rent/long-term", {"address": address})

    def fetch_bundle_by_address(self, address: str) -> dict[str, Any]:
        property_data = self.fetch_property_by_address(address)
        listing_data = self.fetch_listing_by_address(address)
        return {
            "property": _first_record(property_data),
            "listing": _first_record(listing_data),
            "rent_estimate": None,
        }

    def _get(self, endpoint: str, params: dict[str, Any]) -> Any:
        if requests is None:
            raise RentCastError("The requests package is required for RentCast API access.")
        self._record_request_or_raise()
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers={
                    "Accept": "application/json",
                    "X-Api-Key": self.api_key,
                },
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            raise RentCastError(f"RentCast request failed for {endpoint}: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise RentCastError(f"RentCast returned invalid JSON for {endpoint}.") from exc

    def _record_request_or_raise(self) -> None:
        count = self.api_request_count()
        if count >= self.REQUEST_LIMIT and not self.override_limit:
            raise RentCastError(
                f"RentCast API request limit reached ({count}/{self.REQUEST_LIMIT}). "
                "Pass --override to continue."
            )
        self._write_api_request_count(count + 1)

    def api_request_count(self) -> int:
        try:
            payload = json.loads(self.usage_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0
        except (OSError, json.JSONDecodeError) as exc:
            raise RentCastError(f"Unable to read RentCast API usage tracker: {exc}") from exc
        try:
            return int(payload.get("rentcast_requests", 0))
        except (TypeError, ValueError) as exc:
            raise RentCastError("RentCast API usage tracker has an invalid request count.") from exc

    def _write_api_request_count(self, count: int) -> None:
        try:
            self.usage_path.parent.mkdir(parents=True, exist_ok=True)
            self.usage_path.write_text(json.dumps({"rentcast_requests": count}, indent=2), encoding="utf-8")
        except OSError as exc:
            raise RentCastError(f"Unable to write RentCast API usage tracker: {exc}") from exc


def _first_record(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload else {}
    if isinstance(payload, dict):
        for key in ("data", "properties", "listings"):
            value = payload.get(key)
            if isinstance(value, list):
                return value[0] if value else {}
        return payload
    return {}
