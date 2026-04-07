# multifamily-screener

A Python 3.11+ underwriting engine for normalized multifamily property JSON.

## Features

- Pydantic schemas for inputs, provenance, metrics, decisions, and reports
- Modular ingestion, normalization, enrichment, underwriting, scoring, and reporting
- Field-level provenance tracking for important inputs
- Computes NOI, cap rate, annual debt service, DSCR, cash-on-cash, IRR, NPV, equity multiple, break-even occupancy, exit value, and suggested max offer
- Includes tests and a sample input in `examples/`

## Usage

```bash
pip install -e .
python -m app.main examples/sample_property.json
multifamily-screener examples/sample_property.json
PYTHONPATH=src python -m unittest discover -s tests
```
