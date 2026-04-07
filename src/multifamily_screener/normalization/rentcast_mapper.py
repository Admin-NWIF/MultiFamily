from __future__ import annotations

from typing import Any

from multifamily_screener.ingestion.rentcast_client import RentCastClient
from multifamily_screener.schemas import ProvenanceStatus


DEFAULT_ASSUMPTIONS = {
    "vacancy_rate": 0.05,
    "max_ltv": 0.70,
    "interest_rate": 0.065,
    "amortization_years": 30,
    "hold_years": 5,
    "exit_cap_rate": 0.065,
    "discount_rate": 0.10,
    "target_cap_rate": 0.065,
    "target_dscr": 1.25,
    "target_cash_on_cash": 0.08,
    "rent_growth": 0.03,
    "expense_growth": 0.025,
}


def normalized_property_from_rentcast_address(
    address: str,
    client: RentCastClient | None = None,
) -> dict[str, Any]:
    rentcast_client = client or RentCastClient()
    bundle = rentcast_client.fetch_bundle_by_address(address)
    if not _has_actual_rent(bundle.get("property"), bundle.get("listing")):
        bundle["rent_estimate"] = rentcast_client.fetch_rent_estimate_by_address(address)
    return map_rentcast_to_normalized_property(bundle, fallback_address=address)


def map_rentcast_to_normalized_property(
    payload: dict[str, Any],
    *,
    fallback_address: str | None = None,
) -> dict[str, Any]:
    property_data = _first_record(payload.get("property") or payload.get("property_data") or payload)
    listing_data = _first_record(payload.get("listing") or payload.get("listing_data") or {})
    rent_estimate = payload.get("rent_estimate") or {}
    address = _address(property_data, listing_data, fallback_address)
    property_id = str(
        _first_value(property_data, ["id", "propertyId", "formattedAddress"])
        or _first_value(listing_data, ["id", "listingId"])
        or (address.lower().replace(" ", "-").replace(",", "") if address else "rentcast-property")
    )
    units = _to_number(_first_value(property_data, ["units", "unitCount", "numberOfUnits"]))
    purchase_price = _to_number(_first_value(listing_data, ["price", "listPrice", "salePrice", "askingPrice"]))
    monthly_rent = _to_number(
        _first_value(property_data, ["rent", "monthlyRent", "lastRent"])
        or _first_value(listing_data, ["rent", "monthlyRent", "lastRent"])
    )
    gross_potential_rent: float | None = None

    output: dict[str, Any] = {
        "property_id": property_id,
        "name": _first_value(listing_data, ["title"]) or _first_value(property_data, ["propertyType"]) or address,
        "address": address,
    }
    if units is not None:
        output["units"] = _provenance(units, ProvenanceStatus.ACTUAL, "rentcast.property", "RentCast unit count.")
    if purchase_price is not None:
        output["purchase_price"] = _provenance(purchase_price, ProvenanceStatus.ACTUAL, "rentcast.listing", "RentCast listing price.")
    if monthly_rent is not None:
        gross_potential_rent = monthly_rent * 12
        output["gross_potential_rent"] = _provenance(gross_potential_rent, ProvenanceStatus.ACTUAL, "rentcast.property", "Annualized actual rent from RentCast.")
    elif rent_estimate:
        estimated_rent = _to_number(_first_value(rent_estimate, ["rent", "rentEstimate", "price", "monthlyRent"]))
        if estimated_rent is not None:
            gross_potential_rent = estimated_rent * 12 * (units or 1)
            output["gross_potential_rent"] = _provenance(
                gross_potential_rent,
                ProvenanceStatus.ESTIMATED,
                "rentcast.rent_estimate",
                "Annualized RentCast rent estimate.",
                confidence=0.65,
                review_flag=True,
            )

    operating_expenses = _to_number(_first_value(property_data, ["operatingExpenses", "annualExpenses"]))
    if operating_expenses is not None:
        output["operating_expenses"] = _provenance(operating_expenses, ProvenanceStatus.ACTUAL, "rentcast.property", "Operating expenses from RentCast.")
    capex_reserve = _to_number(_first_value(property_data, ["capexReserve", "capitalReserve"]))
    if capex_reserve is not None:
        output["capex_reserve"] = _provenance(capex_reserve, ProvenanceStatus.ACTUAL, "rentcast.property", "Capex reserve from RentCast.")

    for field_name, value in DEFAULT_ASSUMPTIONS.items():
        output[field_name] = _provenance(
            value,
            ProvenanceStatus.DEFAULTED,
            "rentcast_mapper_defaults",
            f"{field_name} defaulted for RentCast normalization.",
            confidence=0.5,
            review_flag=True,
        )
    return output


def _has_actual_rent(property_data: Any, listing_data: Any) -> bool:
    property_record = _first_record(property_data or {})
    listing_record = _first_record(listing_data or {})
    return _first_value(property_record, ["rent", "monthlyRent", "lastRent"]) is not None or _first_value(
        listing_record,
        ["rent", "monthlyRent", "lastRent"],
    ) is not None


def _provenance(
    value: Any,
    status: ProvenanceStatus,
    source: str,
    note: str,
    *,
    confidence: float | str = 0.8,
    review_flag: bool | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "status": status.value,
        "source": source,
        "confidence": confidence,
        "review_flag": review_flag if review_flag is not None else status != ProvenanceStatus.ACTUAL,
        "note": note,
    }


def _address(property_data: dict[str, Any], listing_data: dict[str, Any], fallback_address: str | None) -> str | None:
    return _first_value(property_data, ["formattedAddress", "address"]) or _first_value(
        listing_data,
        ["formattedAddress", "address"],
    ) or fallback_address


def _first_value(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


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


def _to_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
