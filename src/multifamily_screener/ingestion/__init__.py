from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from multifamily_screener.schemas import NormalizedPropertyInput


def load_property_json(path: str | Path) -> NormalizedPropertyInput:
    with Path(path).open("r", encoding="utf-8") as fp:
        return parse_property_json(json.load(fp))


def parse_property_json(data: dict[str, Any]) -> NormalizedPropertyInput:
    return NormalizedPropertyInput.model_validate(data)
