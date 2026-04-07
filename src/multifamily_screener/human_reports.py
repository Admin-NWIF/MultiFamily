from __future__ import annotations

import csv
import json
import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from multifamily_screener.schemas import Flag, ProvenanceField, Report


IMPORTANT_FIELDS = [
    "gross_potential_rent",
    "operating_expenses",
    "vacancy_rate",
    "exit_cap_rate",
    "interest_rate",
    "loan_amount",
]


def write_human_reports(report: Report, output_root: str | Path = "outputs") -> Path:
    output_dir = Path(output_root) / safe_filename(report.property_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.md").write_text(render_markdown_report(report), encoding="utf-8")
    (output_dir / "summary.html").write_text(render_html_report(report), encoding="utf-8")
    (output_dir / "full_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output_dir


def write_batch_reports(
    reports: list[Report],
    shortlist: list[Report],
    output_root: str | Path = "outputs",
    timestamp: str | None = None,
) -> Path:
    root = Path(output_root)
    property_dirs = {
        report.property_id: write_human_reports(report, root)
        for report in reports
    }
    batch_id = safe_filename(timestamp or datetime.now().strftime("%Y%m%d_%H%M%S"))
    batch_dir = root / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "index.html").write_text(
        render_batch_index(shortlist, batch_dir, property_dirs),
        encoding="utf-8",
    )
    _write_shortlist_csv(batch_dir / "shortlist.csv", shortlist, batch_dir, property_dirs)
    (batch_dir / "shortlist.json").write_text(
        json.dumps([_shortlist_row(report, batch_dir, property_dirs) for report in shortlist], indent=2),
        encoding="utf-8",
    )
    return batch_dir


def render_batch_index(
    shortlist: list[Report],
    batch_dir: Path,
    property_dirs: dict[str, Path],
) -> str:
    rows = "".join(
        _batch_index_row(rank, report, batch_dir, property_dirs)
        for rank, report in enumerate(shortlist, start=1)
    ) or '<tr><td colspan="13">No deals met shortlist criteria.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Multifamily Deal Shortlist</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; margin: 32px; background: #f6f8fb; }}
    main {{ max-width: 1400px; margin: 0 auto; background: white; padding: 32px; border-radius: 16px; box-shadow: 0 10px 30px rgba(20, 35, 60, 0.08); }}
    h1 {{ margin-bottom: 4px; }}
    .subtle {{ color: #667085; margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #eaecf0; padding: 10px 8px; text-align: left; white-space: nowrap; }}
    th {{ background: #f9fafb; color: #475467; }}
    td.metric, th.metric {{ text-align: right; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .green {{ background: #dcfce7; color: #166534; }}
    .yellow {{ background: #fef9c3; color: #854d0e; }}
    .red {{ background: #fee2e2; color: #991b1b; }}
    a {{ color: #175cd3; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
<main>
  <h1>Multifamily Deal Shortlist</h1>
  <p class="subtle">Ranked local screening dashboard. Click any report link for the full deal summary.</p>
  <table>
    <tr>
      <th>Rank</th>
      <th>Property name</th>
      <th>Address</th>
      <th class="metric">Asking price</th>
      <th class="metric">Suggested offer</th>
      <th class="metric">Discount %</th>
      <th class="metric">IRR</th>
      <th class="metric">DSCR</th>
      <th class="metric">Cash-on-cash</th>
      <th class="metric">Score</th>
      <th class="metric">Flags</th>
      <th class="metric">Data quality score</th>
      <th>Link to full report</th>
    </tr>
    {rows}
  </table>
</main>
</body>
</html>
"""


def render_markdown_report(report: Report) -> str:
    metrics = report.metrics
    lines = [
        f"# {report.name or report.property_id}",
        "",
        f"**Address:** {report.address or 'n/a'}",
        f"**Recommendation:** {report.decision.recommendation.upper()}",
        f"**Score:** {report.decision.score:.1f}",
        f"**Data quality score:** {report.data_quality_score:.1f}",
        f"**Total flags:** {report.total_flags}",
        "",
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Asking price | {_format_currency(_asking_price(report))} |",
        f"| Suggested max offer | {_format_currency(metrics.suggested_max_offer)} |",
        f"| Binding offer constraint | {metrics.binding_offer_constraint or 'n/a'} |",
        f"| IRR | {_format_percent(metrics.irr)} |",
        f"| NPV | {_format_currency(metrics.npv)} |",
        f"| DSCR | {_format_ratio(metrics.dscr)} |",
        f"| Cash-on-cash | {_format_percent(metrics.cash_on_cash)} |",
        f"| Cap rate | {_format_percent(metrics.cap_rate)} |",
        f"| Equity multiple | {_format_multiple(metrics.equity_multiple)} |",
        f"| Break-even occupancy | {_format_percent(metrics.break_even_occupancy)} |",
        "",
        "## Decision Summary",
        "",
    ]
    lines.extend(f"- {reason}" for reason in report.decision.reasons[:5])
    lines.extend(["", "## Key Risks / Assumptions To Verify", ""])
    risks = _top_assumptions_to_verify(report)
    lines.extend(_markdown_risk_line(field, provenance) for field, provenance in risks)
    if not risks:
        lines.append("- No priority assumed/defaulted fields flagged.")
    lines.extend(
        [
            "",
            "## Pro Forma",
            "",
            "| Year | EGI | NOI Before Reserves | NOI After Reserves | Cash Flow Before Tax | Sale Proceeds | Total Cash Flow |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report.pro_forma:
        lines.append(
            f"| {row['year']} | {_format_currency(row['effective_gross_income'])} | "
            f"{_format_currency(row['noi_before_reserves'])} | {_format_currency(row['noi_after_reserves'])} | "
            f"{_format_currency(row['cash_flow_before_tax'])} | {_format_currency(row.get('sale_proceeds', 0))} | "
            f"{_format_currency(row.get('total_cash_flow', row['cash_flow_before_tax']))} |"
        )
    lines.extend(
        [
            "",
            "## Flags",
            "",
            "| Severity | Code | Field | Message |",
            "| --- | --- | --- | --- |",
        ]
    )
    for flag in report.flags:
        lines.append(f"| {flag.severity} | {flag.code} | {flag.field or ''} | {flag.message} |")
    if not report.flags:
        lines.append("| none | none |  | No flags. |")
    lines.append("")
    return "\n".join(lines)


def _batch_index_row(
    rank: int,
    report: Report,
    batch_dir: Path,
    property_dirs: dict[str, Path],
) -> str:
    row = _shortlist_row(report, batch_dir, property_dirs)
    report_class = _deal_strength_class(report)
    return (
        f'<tr class="{report_class}">'
        f"<td>{rank}</td>"
        f"<td>{html.escape(str(row['property_name']))}</td>"
        f"<td>{html.escape(str(row['address']))}</td>"
        f"<td class=\"metric\">{html.escape(str(row['asking_price']))}</td>"
        f"<td class=\"metric\">{html.escape(str(row['suggested_offer']))}</td>"
        f"<td class=\"metric\"><span class=\"badge {report_class}\">{html.escape(str(row['discount_pct']))}</span></td>"
        f"<td class=\"metric\"><span class=\"badge {_metric_strength_class(report.metrics.irr, 0.15, 0.12)}\">{html.escape(str(row['irr']))}</span></td>"
        f"<td class=\"metric\"><span class=\"badge {_metric_strength_class(report.metrics.dscr, 1.3, 1.2)}\">{html.escape(str(row['dscr']))}</span></td>"
        f"<td class=\"metric\"><span class=\"badge {_metric_strength_class(report.metrics.cash_on_cash, 0.10, 0.08)}\">{html.escape(str(row['cash_on_cash']))}</span></td>"
        f"<td class=\"metric\">{html.escape(str(row['score']))}</td>"
        f"<td class=\"metric\"><span class=\"badge {_flag_count_class(report.total_flags)}\">{html.escape(str(row['flags']))}</span></td>"
        f"<td class=\"metric\">{html.escape(str(row['data_quality_score']))}</td>"
        f"<td><a href=\"{html.escape(str(row['report_link']))}\">Open report</a></td>"
        "</tr>"
    )


def _write_shortlist_csv(
    path: Path,
    shortlist: list[Report],
    batch_dir: Path,
    property_dirs: dict[str, Path],
) -> None:
    rows = [_shortlist_row(report, batch_dir, property_dirs) for report in shortlist]
    fieldnames = [
        "property_id",
        "property_name",
        "address",
        "asking_price",
        "suggested_offer",
        "discount_pct",
        "irr",
        "dscr",
        "cash_on_cash",
        "score",
        "flags",
        "data_quality_score",
        "binding_offer_constraint",
        "report_link",
    ]
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _shortlist_row(
    report: Report,
    batch_dir: Path,
    property_dirs: dict[str, Path],
) -> dict[str, Any]:
    metrics = report.metrics
    asking_price = _asking_price(report)
    discount_pct = _discount_pct(asking_price, metrics.suggested_max_offer)
    report_path = property_dirs[report.property_id] / "summary.html"
    return {
        "property_id": report.property_id,
        "property_name": report.name or report.property_id,
        "address": report.address or "",
        "asking_price": _format_currency(asking_price),
        "suggested_offer": _format_currency(metrics.suggested_max_offer),
        "discount_pct": _format_percent(discount_pct),
        "irr": _format_percent(metrics.irr),
        "dscr": _format_ratio(metrics.dscr),
        "cash_on_cash": _format_percent(metrics.cash_on_cash),
        "score": f"{report.decision.score:.1f}",
        "flags": report.total_flags,
        "data_quality_score": f"{report.data_quality_score:.1f}",
        "binding_offer_constraint": metrics.binding_offer_constraint or "",
        "report_link": str(Path("..") / report_path.relative_to(batch_dir.parent)),
    }


def render_html_report(report: Report) -> str:
    metrics = report.metrics
    reason_items = "".join(f"<li>{html.escape(reason)}</li>" for reason in report.decision.reasons[:5])
    risk_items = "".join(
        f"<li><strong>{html.escape(field)}</strong>: {html.escape(str(provenance.status.value))} "
        f"from {html.escape(provenance.source or 'unknown')} - {html.escape(provenance.note or '')}</li>"
        for field, provenance in _top_assumptions_to_verify(report)
    ) or "<li>No priority assumed/defaulted fields flagged.</li>"
    pro_forma_rows = "".join(
        "<tr>"
        f"<td>{row['year']}</td>"
        f"<td>{_format_currency(row['effective_gross_income'])}</td>"
        f"<td>{_format_currency(row['noi_before_reserves'])}</td>"
        f"<td>{_format_currency(row['noi_after_reserves'])}</td>"
        f"<td>{_format_currency(row['cash_flow_before_tax'])}</td>"
        f"<td>{_format_currency(row.get('sale_proceeds', 0))}</td>"
        f"<td>{_format_currency(row.get('total_cash_flow', row['cash_flow_before_tax']))}</td>"
        "</tr>"
        for row in report.pro_forma
    )
    flag_rows = "".join(_flag_row(flag) for flag in report.flags) or (
        '<tr><td><span class="badge green">none</span></td><td>none</td><td></td><td>No flags.</td></tr>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(report.name or report.property_id)} Deal Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; margin: 32px; background: #f6f8fb; }}
    main {{ max-width: 1100px; margin: 0 auto; background: white; padding: 32px; border-radius: 16px; box-shadow: 0 10px 30px rgba(20, 35, 60, 0.08); }}
    h1, h2 {{ margin-bottom: 8px; }}
    .subtle {{ color: #667085; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .green {{ background: #dcfce7; color: #166534; }}
    .yellow {{ background: #fef9c3; color: #854d0e; }}
    .red {{ background: #fee2e2; color: #991b1b; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; background: #fcfcfd; }}
    .label {{ color: #667085; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0 28px; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #eaecf0; padding: 10px 8px; text-align: left; }}
    th {{ background: #f9fafb; color: #475467; }}
    td:not(:first-child), th:not(:first-child) {{ text-align: right; }}
    .flags td:nth-child(2), .flags td:nth-child(3), .flags td:nth-child(4), .flags th:nth-child(2), .flags th:nth-child(3), .flags th:nth-child(4) {{ text-align: left; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(report.name or report.property_id)}</h1>
  <p class="subtle">{html.escape(report.address or 'n/a')}</p>
  <p><span class="badge {_recommendation_class(report.decision.recommendation)}">{html.escape(report.decision.recommendation)}</span></p>
  <div class="cards">
    {_metric_card("Score", f"{report.decision.score:.1f}", _score_class(report.decision.score))}
    {_metric_card("Data Quality", f"{report.data_quality_score:.1f}", _score_class(report.data_quality_score))}
    {_metric_card("Total Flags", str(report.total_flags), "green" if report.total_flags <= 3 else "yellow" if report.total_flags <= 6 else "red")}
    {_metric_card("DSCR", _format_ratio(metrics.dscr), "green" if metrics.dscr and metrics.dscr >= 1.25 else "yellow" if metrics.dscr and metrics.dscr >= 1.1 else "red")}
  </div>

  <h2>Key Metrics</h2>
  <table>
    <tr><th>Asking Price</th><td>{_format_currency(_asking_price(report))}</td></tr>
    <tr><th>Suggested Max Offer</th><td>{_format_currency(metrics.suggested_max_offer)}</td></tr>
    <tr><th>Binding Offer Constraint</th><td>{html.escape(metrics.binding_offer_constraint or 'n/a')}</td></tr>
    <tr><th>IRR</th><td><span class="badge {'green' if metrics.irr and metrics.irr >= 0.12 else 'red'}">{_format_percent(metrics.irr)}</span></td></tr>
    <tr><th>NPV</th><td><span class="badge {'green' if metrics.npv > 0 else 'red'}">{_format_currency(metrics.npv)}</span></td></tr>
    <tr><th>DSCR</th><td>{_format_ratio(metrics.dscr)}</td></tr>
    <tr><th>Cash-on-Cash</th><td>{_format_percent(metrics.cash_on_cash)}</td></tr>
    <tr><th>Cap Rate</th><td>{_format_percent(metrics.cap_rate)}</td></tr>
    <tr><th>Equity Multiple</th><td>{_format_multiple(metrics.equity_multiple)}</td></tr>
    <tr><th>Break-even Occupancy</th><td>{_format_percent(metrics.break_even_occupancy)}</td></tr>
  </table>

  <h2>Decision Summary</h2>
  <ul>{reason_items}</ul>

  <h2>Key Risks / Assumptions To Verify</h2>
  <ul>{risk_items}</ul>

  <h2>Pro Forma</h2>
  <table>
    <tr><th>Year</th><th>EGI</th><th>NOI Before Reserves</th><th>NOI After Reserves</th><th>Cash Flow Before Tax</th><th>Sale Proceeds</th><th>Total Cash Flow</th></tr>
    {pro_forma_rows}
  </table>

  <h2>Flags</h2>
  <table class="flags">
    <tr><th>Severity</th><th>Code</th><th>Field</th><th>Message</th></tr>
    {flag_rows}
  </table>
</main>
</body>
</html>
"""


def _top_assumptions_to_verify(report: Report) -> list[tuple[str, ProvenanceField]]:
    fields: list[tuple[str, ProvenanceField]] = []
    for field_name in IMPORTANT_FIELDS:
        provenance = report.assumed_fields.get(field_name)
        if provenance is not None:
            fields.append((field_name, provenance))
    return fields[:5]


def _markdown_risk_line(field: str, provenance: ProvenanceField) -> str:
    return f"- **{field}**: {provenance.status.value} from {provenance.source or 'unknown'}; {provenance.note or ''}"


def _flag_row(flag: Flag) -> str:
    return (
        "<tr>"
        f"<td><span class=\"badge {_severity_class(flag.severity)}\">{html.escape(flag.severity)}</span></td>"
        f"<td>{html.escape(flag.code)}</td>"
        f"<td>{html.escape(flag.field or '')}</td>"
        f"<td>{html.escape(flag.message)}</td>"
        "</tr>"
    )


def _metric_card(label: str, value: str, class_name: str) -> str:
    return f'<div class="card"><div class="label">{html.escape(label)}</div><div class="value"><span class="badge {class_name}">{html.escape(value)}</span></div></div>'


def _asking_price(report: Report) -> Any:
    field = report.provenance.get("purchase_price")
    return None if field is None else field.value


def _discount_pct(asking_price: Any, suggested_offer: float) -> float | None:
    if not isinstance(asking_price, int | float) or asking_price == 0:
        return None
    return (asking_price - suggested_offer) / asking_price


def _format_currency(value: Any) -> str:
    if isinstance(value, int | float):
        return f"${value:,.0f}"
    return "n/a" if value is None else str(value)


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _format_multiple(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}x"


def _recommendation_class(recommendation: str) -> str:
    if recommendation == "pursue":
        return "green"
    if recommendation == "review":
        return "yellow"
    return "red"


def _score_class(score: float) -> str:
    if score >= 75:
        return "green"
    if score >= 45:
        return "yellow"
    return "red"


def _severity_class(severity: str) -> str:
    if severity == "critical":
        return "red"
    if severity == "warning":
        return "yellow"
    return "green"


def _metric_strength_class(value: float | None, strong_threshold: float, moderate_threshold: float) -> str:
    if value is None:
        return "red"
    if value > strong_threshold:
        return "green"
    if value >= moderate_threshold:
        return "yellow"
    return "red"


def _flag_count_class(total_flags: int) -> str:
    if total_flags <= 3:
        return "green"
    if total_flags <= 6:
        return "yellow"
    return "red"


def _deal_strength_class(report: Report) -> str:
    metrics = report.metrics
    if report.total_flags > 6:
        return "red"
    if (
        metrics.irr is not None
        and metrics.irr > 0.15
        and metrics.dscr is not None
        and metrics.dscr > 1.3
        and metrics.cash_on_cash is not None
        and metrics.cash_on_cash > 0.10
    ):
        return "green"
    if (
        metrics.irr is not None
        and metrics.irr >= 0.12
        and metrics.dscr is not None
        and metrics.dscr >= 1.2
        and metrics.cash_on_cash is not None
        and metrics.cash_on_cash >= 0.08
    ):
        return "yellow"
    return "red"


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned or "property"
