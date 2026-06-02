"""
GMP ALCOA+ Review Report Generator
====================================
Reads findings_USP001.json produced by checker.py and renders a
self-contained professional HTML review report suitable for clinical
biologics batch disposition review.

Author : Judith Lavric | GMP Documentation Specialist
Website: judithlavric.com
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

FINDINGS_FILE    = OUTPUT_DIR / "findings_USP001.json"
BATCH_RECORD_CSV = BASE_DIR   / "batch_record_USP_001.csv"
HTML_REPORT      = OUTPUT_DIR / "ALCOA_Review_Report_USP001.html"


# ---------------------------------------------------------------------------
# CSS (embedded – no external dependencies)
# ---------------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', Arial, sans-serif;
  font-size: 13px;
  background: #f4f6f9;
  color: #1a1a2e;
}

/* ── Header ──────────────────────────────────────────────── */
.header {
  background: linear-gradient(135deg, #0d1b2a 0%, #1b2838 60%, #16213e 100%);
  color: #fff;
  padding: 28px 40px 22px;
  border-bottom: 4px solid #e63946;
}
.header-top { display: flex; justify-content: space-between; align-items: flex-start; }
.header h1 { font-size: 22px; letter-spacing: 0.5px; margin-bottom: 4px; }
.header .subtitle { font-size: 12px; color: #a8b2c1; letter-spacing: 1px; text-transform: uppercase; }
.header-meta { text-align: right; font-size: 11px; color: #a8b2c1; line-height: 1.8; }
.header-meta strong { color: #e0e6ef; }
.divider { height: 1px; background: rgba(255,255,255,0.12); margin: 14px 0 10px; }
.header-fields { display: flex; gap: 40px; font-size: 11px; color: #cdd5e0; }
.header-fields span strong { color: #fff; }

/* ── Result banner ──────────────────────────────────────── */
.result-banner {
  display: flex; align-items: center; justify-content: center;
  padding: 16px 40px; gap: 16px;
  font-weight: 700; font-size: 15px; letter-spacing: 1px;
  text-transform: uppercase;
}
.result-banner.FAIL       { background: #e63946; color: #fff; }
.result-banner.REVIEW     { background: #f4a261; color: #1a1a2e; }
.result-banner.PASS       { background: #2a9d8f; color: #fff; }
.result-icon { font-size: 22px; }

/* ── Stats row ──────────────────────────────────────────── */
.stats-row {
  display: flex; gap: 1px; background: #dde3ed;
  border-bottom: 1px solid #ccd3de;
}
.stat-card {
  flex: 1; background: #fff; padding: 14px 20px;
  text-align: center;
}
.stat-card .val { font-size: 28px; font-weight: 700; }
.stat-card .lbl { font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; color: #6b7a8d; margin-top: 2px; }
.stat-card.critical .val { color: #e63946; }
.stat-card.major    .val { color: #f4a261; }
.stat-card.minor    .val { color: #e9c46a; }
.stat-card.total    .val { color: #1b2838; }
.stat-card.steps    .val { color: #2a9d8f; }

/* ── Section wrappers ───────────────────────────────────── */
.section { padding: 24px 40px; }
.section-title {
  font-size: 12px; font-weight: 700; letter-spacing: 1.2px;
  text-transform: uppercase; color: #6b7a8d;
  border-bottom: 2px solid #e0e6ef; padding-bottom: 6px; margin-bottom: 16px;
}

/* ── ALCOA+ principle grid ──────────────────────────────── */
.principle-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
}
.principle-card {
  border-radius: 6px; padding: 14px 16px; border-left: 5px solid transparent;
  background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.principle-card.PASS { border-left-color: #2a9d8f; }
.principle-card.WARN { border-left-color: #f4a261; }
.principle-card.FAIL { border-left-color: #e63946; }
.principle-name { font-weight: 700; font-size: 13px; margin-bottom: 6px; }
.principle-card.PASS .principle-name { color: #1e7a6e; }
.principle-card.WARN .principle-name { color: #c47a2a; }
.principle-card.FAIL .principle-name { color: #b02530; }
.principle-counts { display: flex; gap: 8px; font-size: 11px; }
.pill {
  padding: 2px 8px; border-radius: 20px; font-weight: 600;
  background: #f0f2f5; color: #6b7a8d;
}
.pill.crit { background: #fde8ea; color: #c0392b; }
.pill.maj  { background: #fef3e7; color: #b5610a; }
.pill.min  { background: #fefae3; color: #9a7d0a; }
.principle-status-badge {
  float: right; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
  padding: 2px 8px; border-radius: 3px; text-transform: uppercase;
}
.principle-card.PASS .principle-status-badge { background: #d4f4f0; color: #1e7a6e; }
.principle-card.WARN .principle-status-badge { background: #fef3e7; color: #b5610a; }
.principle-card.FAIL .principle-status-badge { background: #fde8ea; color: #b02530; }

/* ── Findings table ─────────────────────────────────────── */
.findings-table-wrap { overflow-x: auto; }
table.findings-table {
  width: 100%; border-collapse: collapse; font-size: 12px; background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-radius: 6px; overflow: hidden;
}
table.findings-table thead tr { background: #1b2838; color: #fff; }
table.findings-table th {
  padding: 10px 12px; text-align: left; font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600;
}
table.findings-table td { padding: 9px 12px; border-bottom: 1px solid #edf0f5; vertical-align: top; }
table.findings-table tbody tr:hover { background: #f8f9fb; }

/* Severity badges */
.badge {
  display: inline-block; padding: 2px 9px; border-radius: 3px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
}
.badge.CRITICAL { background: #e63946; color: #fff; }
.badge.MAJOR    { background: #f4a261; color: #fff; }
.badge.MINOR    { background: #e9c46a; color: #1a1a2e; }

/* Principle tag */
.ptag {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  font-size: 10px; font-weight: 600; background: #e8edf4; color: #1b2838;
}

/* ── Batch record annotated table ───────────────────────── */
table.br-table {
  width: 100%; border-collapse: collapse; font-size: 11px; background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
table.br-table thead tr { background: #2c3e50; color: #fff; }
table.br-table th {
  padding: 8px 10px; text-align: left; font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.6px;
}
table.br-table td { padding: 7px 10px; border-bottom: 1px solid #edf0f5; }
table.br-table tr.row-critical { background: #fde8ea; }
table.br-table tr.row-major    { background: #fff4e6; }
table.br-table tr.row-minor    { background: #fffbe6; }
table.br-table tr.row-critical td:first-child { border-left: 4px solid #e63946; }
table.br-table tr.row-major    td:first-child { border-left: 4px solid #f4a261; }
table.br-table tr.row-minor    td:first-child { border-left: 4px solid #e9c46a; }

/* ── Footer ─────────────────────────────────────────────── */
.footer {
  background: #1b2838; color: #6b8094; font-size: 11px;
  padding: 18px 40px; display: flex; justify-content: space-between;
  align-items: center; margin-top: 30px;
}
.footer a { color: #89a7c0; text-decoration: none; }
.footer a:hover { color: #fff; }
.footer-right { text-align: right; line-height: 1.8; }

/* ── Observation text ───────────────────────────────────── */
.obs-text { line-height: 1.55; color: #2c3e50; }
.ref-text  { font-size: 10px; color: #8896a5; font-style: italic; margin-top: 3px; }
"""


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def status_icon(result: str) -> str:
    return {"FAIL": "✗", "REVIEW REQUIRED": "⚠", "PASS": "✓"}.get(result, "?")


def result_class(result: str) -> str:
    return {"FAIL": "FAIL", "REVIEW REQUIRED": "REVIEW", "PASS": "PASS"}.get(result, "FAIL")


def render_principle_grid(summary: dict) -> str:
    html = '<div class="principle-grid">\n'
    icons = {
        "Attributable":     "A",
        "Legible":          "L",
        "Contemporaneous":  "C",
        "Original":         "O",
        "Accurate":         "A",
        "Complete":         "C",
        "Consistent":       "C",
        "Enduring":         "E",
        "Available":        "A",
    }
    descriptions = {
        "Attributable":    "Entries traceable to a specific individual",
        "Legible":         "Data is readable and unambiguous",
        "Contemporaneous": "Recorded at the time of execution",
        "Original":        "First capture; no overwriting",
        "Accurate":        "Values within approved specification",
        "Complete":        "All required fields populated",
        "Consistent":      "Internal cross-step data coherence",
        "Enduring":        "Permanent, tamper-evident medium",
        "Available":       "Referenced documents exist and are current",
    }
    for principle, data in summary.items():
        status = data["status"]
        crit_html = f'<span class="pill crit">{data["critical"]} Critical</span>' if data["critical"] else ""
        maj_html  = f'<span class="pill maj">{data["major"]} Major</span>'    if data["major"]    else ""
        min_html  = f'<span class="pill min">{data["minor"]} Minor</span>'    if data["minor"]    else ""
        no_findings = '<span class="pill">No findings</span>' if data["total"] == 0 else ""
        html += f"""
  <div class="principle-card {status}">
    <div class="principle-name">
      {principle}
      <span class="principle-status-badge">{status}</span>
    </div>
    <div style="font-size:10px;color:#8896a5;margin-bottom:8px;">{descriptions.get(principle,'')}</div>
    <div class="principle-counts">{crit_html}{maj_html}{min_html}{no_findings}</div>
  </div>"""
    html += "\n</div>\n"
    return html


def render_findings_table(findings: list[dict]) -> str:
    if not findings:
        return "<p style='color:#2a9d8f;padding:12px;'>No findings identified. Batch record is compliant.</p>"

    rows = ""
    for i, f in enumerate(findings, 1):
        rows += f"""
    <tr>
      <td style="color:#8896a5;font-size:11px;">{i}</td>
      <td><code style="font-size:11px;background:#f0f2f5;padding:2px 6px;border-radius:3px;">{f['step_id']}</code></td>
      <td><span class="ptag">{f['principle']}</span></td>
      <td><span class="badge {f['severity']}">{f['severity']}</span></td>
      <td>
        <div class="obs-text">{f['observation']}</div>
        <div class="ref-text">Ref: {f['regulatory_reference']}</div>
      </td>
    </tr>"""

    return f"""
<div class="findings-table-wrap">
<table class="findings-table">
  <thead>
    <tr>
      <th>#</th><th>Step ID</th><th>Principle</th><th>Severity</th><th>Observation &amp; Regulatory Reference</th>
    </tr>
  </thead>
  <tbody>{rows}
  </tbody>
</table>
</div>"""


def render_batch_record_table(df: pd.DataFrame, findings: list[dict]) -> str:
    # Build a map: step_id → worst severity
    sev_rank = {"CRITICAL": 3, "MAJOR": 2, "MINOR": 1}
    step_sev: dict[str, str] = {}
    for f in findings:
        for sid in f["step_id"].split("/"):
            sid = sid.strip()
            prev = step_sev.get(sid, "")
            if not prev or sev_rank.get(f["severity"], 0) > sev_rank.get(prev, 0):
                step_sev[sid] = f["severity"]

    cols_show = [
        "step_id", "step_name", "performed_by", "checked_by",
        "timestamp", "actual_value", "unit", "pass_fail", "comments"
    ]
    header_labels = [
        "Step ID", "Step Name", "Performed By", "Checked By",
        "Timestamp", "Actual Value", "Unit", "P/F", "Comments"
    ]

    header_html = "".join(f"<th>{lbl}</th>" for lbl in header_labels)
    rows = ""
    for _, row in df.iterrows():
        sid = str(row.get("step_id", "")).strip()
        sev = step_sev.get(sid, "")
        row_class = f"row-{sev.lower()}" if sev else ""
        cells = ""
        for col in cols_show:
            val = str(row.get(col, "")).strip()
            # Truncate long step names for table readability
            if col == "step_name" and len(val) > 45:
                val = val[:42] + "…"
            if col == "comments" and len(val) > 60:
                val = val[:57] + "…"
            cells += f"<td>{val}</td>"
        rows += f'<tr class="{row_class}">{cells}</tr>\n'

    legend = """
<div style="display:flex;gap:16px;margin-bottom:10px;font-size:11px;align-items:center;">
  <span style="display:inline-block;width:12px;height:12px;background:#e63946;border-radius:2px;"></span> Critical finding
  <span style="display:inline-block;width:12px;height:12px;background:#f4a261;border-radius:2px;"></span> Major finding
  <span style="display:inline-block;width:12px;height:12px;background:#e9c46a;border-radius:2px;"></span> Minor finding
</div>"""

    return f"""{legend}
<div style="overflow-x:auto;">
<table class="br-table">
  <thead><tr>{header_html}</tr></thead>
  <tbody>
{rows}  </tbody>
</table>
</div>"""


# ---------------------------------------------------------------------------
# Full report assembly
# ---------------------------------------------------------------------------

def generate_report(payload: dict, df: pd.DataFrame) -> str:
    result      = payload["overall_result"]
    res_class   = result_class(result)
    icon        = status_icon(result)
    summary     = payload["principle_summary"]
    findings    = payload["findings"]
    now_str     = datetime.now().strftime("%Y-%m-%d %H:%M")

    principle_grid  = render_principle_grid(summary)
    findings_table  = render_findings_table(findings)
    br_table        = render_batch_record_table(df, findings)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ALCOA+ Review Report – {payload['batch_id']}</title>
  <style>
{CSS}
  </style>
</head>
<body>

<!-- ── HEADER ─────────────────────────────────────────── -->
<div class="header">
  <div class="header-top">
    <div>
      <div class="subtitle">GMP Batch Record Review — ALCOA+ Compliance Assessment</div>
      <h1>ALCOA+ Review Report &nbsp;|&nbsp; {payload['batch_id']}</h1>
    </div>
    <div class="header-meta">
      <div><strong>Reviewer:</strong> {payload['reviewer']}</div>
      <div><strong>Review Date:</strong> {payload['review_date']}</div>
      <div><strong>Report Generated:</strong> {now_str}</div>
      <div><strong>Document Status:</strong> DRAFT — For Review</div>
    </div>
  </div>
  <div class="divider"></div>
  <div class="header-fields">
    <span><strong>Product:</strong> {payload['product_name']}</span>
    <span><strong>Batch ID:</strong> {payload['batch_id']}</span>
    <span><strong>Site:</strong> {payload['manufacturing_site']}</span>
    <span><strong>Protocol:</strong> PRO-USP-2024-001 REV-04</span>
    <span><strong>Phase:</strong> Phase II Clinical</span>
  </div>
</div>

<!-- ── RESULT BANNER ──────────────────────────────────── -->
<div class="result-banner {res_class}">
  <span class="result-icon">{icon}</span>
  <span>Overall Review Result: {result}</span>
</div>

<!-- ── STATS ROW ──────────────────────────────────────── -->
<div class="stats-row">
  <div class="stat-card steps">
    <div class="val">{payload['total_steps']}</div>
    <div class="lbl">Total Steps</div>
  </div>
  <div class="stat-card total">
    <div class="val">{payload['total_findings']}</div>
    <div class="lbl">Total Findings</div>
  </div>
  <div class="stat-card critical">
    <div class="val">{payload['critical_count']}</div>
    <div class="lbl">Critical</div>
  </div>
  <div class="stat-card major">
    <div class="val">{payload['major_count']}</div>
    <div class="lbl">Major</div>
  </div>
  <div class="stat-card minor">
    <div class="val">{payload['minor_count']}</div>
    <div class="lbl">Minor</div>
  </div>
</div>

<!-- ── ALCOA+ PRINCIPLE SUMMARY ───────────────────────── -->
<div class="section">
  <div class="section-title">ALCOA+ Principle Assessment Summary</div>
  {principle_grid}
</div>

<!-- ── FINDINGS TABLE ─────────────────────────────────── -->
<div class="section" style="background:#fff;margin:0 0 2px;">
  <div class="section-title">Detailed Findings</div>
  <p style="font-size:11px;color:#8896a5;margin-bottom:14px;">
    All findings are classified per EU GMP Chapter 4, ICH Q7, and FDA Data Integrity Guidance (2018).
    Critical findings require immediate corrective action prior to batch disposition.
    Major findings require documented justification or corrective action within 30 days.
  </p>
  {findings_table}
</div>

<!-- ── ANNOTATED BATCH RECORD ─────────────────────────── -->
<div class="section">
  <div class="section-title">Annotated Batch Record — USP-001</div>
  <p style="font-size:11px;color:#8896a5;margin-bottom:14px;">
    Rows are highlighted according to the most severe finding identified for that step.
    Steps without highlighting are compliant with ALCOA+ requirements as reviewed.
  </p>
  {br_table}
</div>

<!-- ── REVIEWER DECLARATION ───────────────────────────── -->
<div class="section" style="background:#f8f9fb;border-top:1px solid #e0e6ef;border-bottom:1px solid #e0e6ef;">
  <div class="section-title">Reviewer Declaration</div>
  <p style="line-height:1.7;font-size:12px;color:#2c3e50;">
    I, <strong>{payload['reviewer']}</strong>, GMP Documentation Specialist, have reviewed the executed
    batch record for Batch <strong>{payload['batch_id']}</strong> against the ALCOA+ principles
    in accordance with EU GMP Chapter 4, ICH Q7, and applicable site SOPs.
    This review is based on the data presented in the executed batch record and
    does not constitute a formal Quality Unit batch release decision.
    All identified findings must be addressed through the site's deviation and CAPA management system
    prior to clinical batch disposition.
  </p>
  <div style="margin-top:18px;display:flex;gap:60px;">
    <div>
      <div style="border-top:1px solid #2c3e50;width:200px;padding-top:4px;font-size:11px;color:#6b7a8d;">
        Reviewer Signature
      </div>
    </div>
    <div>
      <div style="border-top:1px solid #2c3e50;width:160px;padding-top:4px;font-size:11px;color:#6b7a8d;">
        Date
      </div>
    </div>
    <div>
      <div style="border-top:1px solid #2c3e50;width:160px;padding-top:4px;font-size:11px;color:#6b7a8d;">
        QA Review
      </div>
    </div>
  </div>
</div>

<!-- ── FOOTER ─────────────────────────────────────────── -->
<div class="footer">
  <div>
    <strong style="color:#a8b7c7;">Judith Lavric</strong><br>
    GMP Documentation Specialist<br>
    <a href="https://judithlavric.com">judithlavric.com</a>
  </div>
  <div class="footer-right">
    <a href="https://github.com/judithlavric">github.com/judithlavric</a><br>
    alcoa-batch-record-checker<br>
    <span>Report ID: ALCOA-USP001-{datetime.now().strftime('%Y%m%d')}</span>
  </div>
</div>

</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  GMP ALCOA+ Report Generator")
    print("  Batch: USP-001 | Product: PBS 1X pH 7.4")
    print("=" * 60)

    if not FINDINGS_FILE.exists():
        raise FileNotFoundError(
            f"Findings file not found: {FINDINGS_FILE}\n"
            "Run checker.py first: python checker.py"
        )

    with open(FINDINGS_FILE, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    df = pd.read_csv(BATCH_RECORD_CSV, dtype=str)
    df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

    html = generate_report(payload, df)

    with open(HTML_REPORT, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"\n  Report generated successfully.")
    print(f"  Output: {HTML_REPORT}")
    print(f"  Size  : {HTML_REPORT.stat().st_size / 1024:.1f} KB")
    print(f"\n  Open in browser: open {HTML_REPORT}\n")
