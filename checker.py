"""
ALCOA+ Batch Record Compliance Checker
=======================================
Automated GDP/GMP review tool for executed batch record USP-001.
Evaluates all 9 ALCOA+ principles and generates structured findings.

Author : Judith Lavric | GMP Documentation Specialist
Website: judithlavric.com
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

BATCH_RECORD_FILE = BASE_DIR / "data"  / "batch_record_USP_001.csv"
SPECS_FILE        = BASE_DIR / "specs" / "usp_001_specs.json"
FINDINGS_OUTPUT   = OUTPUT_DIR / "findings_USP001.json"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, dict]:
    """Load batch record CSV and specification JSON."""
    df = pd.read_csv(BATCH_RECORD_FILE, dtype=str)
    df.columns = df.columns.str.strip()
    # Strip whitespace from all string cells
    df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

    with open(SPECS_FILE, "r", encoding="utf-8") as fh:
        specs = json.load(fh)

    return df, specs


# ---------------------------------------------------------------------------
# Finding builder
# ---------------------------------------------------------------------------

def make_finding(step_id: str, principle: str, severity: str,
                 observation: str, reference: str) -> dict:
    """Return a standardised finding dictionary."""
    return {
        "step_id": step_id,
        "principle": principle,
        "severity": severity,       # CRITICAL | MAJOR | MINOR
        "observation": observation,
        "regulatory_reference": reference,
    }


# ---------------------------------------------------------------------------
# ALCOA+ check functions – one per principle
# ---------------------------------------------------------------------------

def check_attributable(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    Every entry must be signed by an authorised operator.
    Checks performed_by and checked_by against the authorised operator list.
    """
    findings = []
    authorised = set(specs["authorized_operators"])
    ref = "EU GMP Annex 11 §12; 21 CFR Part 11.10(d); ICH Q7 §6.41"

    for _, row in df.iterrows():
        sid = row["step_id"]

        # Missing checker signature on steps that require one
        if str(row["checked_by"]).strip() in ("", "nan", "NaN"):
            findings.append(make_finding(
                sid, "Attributable", "MAJOR",
                f"Step {sid} ({row['step_name']}): 'checked_by' field is blank. "
                "Second-person verification signature is absent. All manufacturing "
                "entries require independent review and countersignature per GDP requirements.",
                ref
            ))

        # Unauthorised operator ID in performed_by
        operator = row["performed_by"].strip()
        if operator and operator not in authorised:
            findings.append(make_finding(
                sid, "Attributable", "CRITICAL",
                f"Step {sid} ({row['step_name']}): Operator ID '{operator}' is not listed "
                "in the approved operator register for this batch. Entry cannot be attributed "
                "to a qualified, trained individual. Traceability to a specific person is a "
                "fundamental GDP requirement.",
                ref
            ))

    return findings


def check_legible(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    All entries must be clear and readable; no placeholder or ambiguous values.
    Flags 'N/A' used as actual numeric result and 'PENDING' recorded after window close.
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.8; WHO TRS 986 Annex 2 §15.3"

    placeholder_tokens = {"N/A", "TBD", "?", "XX", "PENDING", "---"}

    for _, row in df.iterrows():
        sid = row["step_id"]
        actual = str(row["actual_value"]).strip().upper()

        # PENDING result in a numeric/result column
        if actual in placeholder_tokens:
            severity = "MAJOR" if actual == "PENDING" else "MINOR"
            findings.append(make_finding(
                sid, "Legible", severity,
                f"Step {sid} ({row['step_name']}): 'actual_value' contains placeholder "
                f"token '{row['actual_value']}'. Incomplete or deferred entries in an "
                "executed batch record are not compliant with GDP legibility requirements. "
                "Results must be recorded at time of execution, not populated retrospectively.",
                ref
            ))

    return findings


def check_contemporaneous(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    Timestamps must fall within the production window and be sequential.
    Entries recorded outside the production window indicate backdating or forward-dating.
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.8; 21 CFR 211.68; ISPE GAMP5 §7.4"

    window_start = datetime.fromisoformat(specs["production_window"]["start"])
    window_end   = datetime.fromisoformat(specs["production_window"]["end"])

    for _, row in df.iterrows():
        sid = row["step_id"]
        ts_raw = str(row["timestamp"]).strip()
        if not ts_raw or ts_raw.upper() in ("N/A", ""):
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            findings.append(make_finding(
                sid, "Contemporaneous", "MAJOR",
                f"Step {sid}: Timestamp '{ts_raw}' cannot be parsed as a valid ISO-8601 "
                "datetime. Unreadable timestamps prevent verification of contemporaneous recording.",
                ref
            ))
            continue

        if ts < window_start or ts > window_end:
            # Steps recorded the next day indicate late entry
            days_diff = (ts.date() - window_start.date()).days
            severity = "CRITICAL" if abs(days_diff) > 0 else "MAJOR"
            findings.append(make_finding(
                sid, "Contemporaneous", severity,
                f"Step {sid} ({row['step_name']}): Timestamp {ts_raw} falls outside the "
                f"approved production window ({specs['production_window']['start']} – "
                f"{specs['production_window']['end']}). "
                "Entries recorded outside the production window are indicative of "
                "backdating or late data entry, which represents a significant data integrity risk.",
                ref
            ))

    return findings


def check_original(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    Each step_id must appear exactly once. Duplicate IDs indicate overwriting
    or copy-paste of original entries.
    """
    findings = []
    ref = "EU GMP Annex 11 §10; FDA Data Integrity Guidance 2018 §IV.C"

    counts = df["step_id"].value_counts()
    duplicates = counts[counts > 1]

    for step_id, count in duplicates.items():
        findings.append(make_finding(
            step_id, "Original", "CRITICAL",
            f"Step ID '{step_id}' appears {count} times in the batch record. "
            "Duplicate step identifiers indicate that an original entry has been overwritten "
            "or that a fraudulent duplicate record exists. Original data must be preserved "
            "in its entirety; corrections must follow the single-line strikethrough procedure.",
            ref
        ))

    return findings


def check_accurate(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    Numeric actual values must fall within the validated specification limits.
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.9; ICH Q7 §6.50; 21 CFR 211.192"

    step_specs = specs.get("step_specifications", {})

    for _, row in df.iterrows():
        sid = row["step_id"]
        if sid not in step_specs:
            continue

        spec = step_specs[sid]
        actual_raw = str(row["actual_value"]).strip()

        # Skip non-numeric entries
        try:
            actual = float(actual_raw)
        except ValueError:
            continue

        lo = float(spec["min"])
        hi = float(spec["max"])

        if actual < lo or actual > hi:
            # Distinguish CRITICAL (safety/sterility) vs MAJOR
            is_sterility = "filter" in row["step_name"].lower() or "ph" in row["step_name"].lower()
            severity = "CRITICAL" if is_sterility else "MAJOR"
            findings.append(make_finding(
                sid, "Accurate", severity,
                f"Step {sid} ({row['step_name']}): Recorded {spec['parameter']} of "
                f"{actual} {spec['unit']} is outside the approved specification range "
                f"[{lo}–{hi} {spec['unit']}]. Out-of-specification results must be "
                "investigated under the site's OOS procedure before batch disposition.",
                ref
            ))

    return findings


def check_complete(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    All required fields must be populated for every step.
    Missing or blank mandatory fields render the record incomplete.
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.8; WHO TRS 957 Annex 4 §15.2; 21 CFR 211.188"

    required = specs.get("required_fields", [])

    for _, row in df.iterrows():
        sid = row["step_id"]
        for field in required:
            if field not in row.index:
                continue
            value = str(row[field]).strip()
            if value == "" or value.upper() == "NAN":
                findings.append(make_finding(
                    sid, "Complete", "MAJOR",
                    f"Step {sid} ({row['step_name']}): Required field '{field}' is empty. "
                    "All mandatory fields must be completed at the time of execution. "
                    "Incomplete batch records are not acceptable for clinical manufacturing "
                    "and may prevent batch release.",
                    ref
                ))

    return findings


def check_consistent(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    Cross-step consistency checks: volume transferred to filtration must match
    the volume recorded post-filtration within the defined tolerance.
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.8; ICH Q10 §1.6; 21 CFR 211.192"

    checks = specs.get("volume_consistency_checks", [])
    # Build step_id → actual_value lookup
    value_map: dict[str, float] = {}
    for _, row in df.iterrows():
        try:
            value_map[row["step_id"]] = float(row["actual_value"])
        except (ValueError, TypeError):
            pass

    for chk in checks:
        step_a, step_b = chk["step_a"], chk["step_b"]
        tol = float(chk["tolerance_pct"]) / 100.0

        if step_a not in value_map or step_b not in value_map:
            continue

        val_a = value_map[step_a]
        val_b = value_map[step_b]

        pct_diff = abs(val_a - val_b) / val_a if val_a != 0 else 0

        if pct_diff > tol:
            findings.append(make_finding(
                f"{step_a}/{step_b}", "Consistent", "CRITICAL",
                f"Volume consistency check {chk['check_id']} FAILED: "
                f"{step_a} recorded {val_a} L (pre-filtration) vs {step_b} recorded "
                f"{val_b} L (post-filtration). Discrepancy of "
                f"{pct_diff * 100:.1f}% exceeds the {chk['tolerance_pct']}% tolerance. "
                "Unexplained yield loss of this magnitude requires immediate investigation. "
                "Potential causes include sampling error, unrecorded transfers, or data entry error.",
                ref
            ))

    return findings


def check_enduring(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    Data must be recorded in a durable, non-erasable format.
    Flags mixed data types in columns expected to be numeric (indicative of
    paper corrections without single-line strikethrough, or Excel formula remnants).
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.8; FDA 21 CFR 211.68(b); ALCOA+ Enduring principle"

    # Columns expected to hold numeric or clearly defined values
    numeric_step_ids = set(specs.get("step_specifications", {}).keys())

    for _, row in df.iterrows():
        sid = row["step_id"]
        if sid not in numeric_step_ids:
            continue

        actual = str(row["actual_value"]).strip()
        # Enduring flag: value contains mixed content suggesting an overwrite
        if any(c in actual for c in ["#", "=", "//", "**"]):
            findings.append(make_finding(
                sid, "Enduring", "MAJOR",
                f"Step {sid} ({row['step_name']}): 'actual_value' field contains "
                f"non-standard characters ('{actual}') suggesting a formula, symbol, "
                "or electronic system artefact. Data recorded in batch records must be "
                "permanent and tamper-evident. Any correction must follow the GDP "
                "single-line strikethrough with reason, date, and initials.",
                ref
            ))

    return findings


def check_available(df: pd.DataFrame, specs: dict) -> list[dict]:
    """
    All referenced SOPs and BOMs must exist in the approved document management system.
    Invalid references indicate the step was performed without an approved procedure.
    """
    findings = []
    ref = "EU GMP Chapter 4 §4.2; ICH Q7 §6.10; WHO TRS 986 Annex 2 §14"

    valid_sops = set(specs.get("valid_sop_references", []))
    valid_boms = set(specs.get("valid_bom_references", []))

    for _, row in df.iterrows():
        sid = row["step_id"]
        sop = str(row["sop_reference"]).strip()
        bom = str(row["bom_reference"]).strip()

        if sop and sop not in valid_sops and sop.upper() not in ("N/A", "NAN", ""):
            findings.append(make_finding(
                sid, "Available", "MAJOR",
                f"Step {sid} ({row['step_name']}): SOP reference '{sop}' is not listed "
                "in the approved SOP register for this batch protocol. Steps must be "
                "performed in accordance with current approved procedures. An unrecognised "
                "SOP reference may indicate use of an obsolete, superseded, or unapproved document.",
                ref
            ))

        if bom and bom not in valid_boms and bom.upper() not in ("N/A", "NAN", ""):
            findings.append(make_finding(
                sid, "Available", "MAJOR",
                f"Step {sid} ({row['step_name']}): BOM reference '{bom}' is not found "
                "in the approved materials list for this batch. All components must be "
                "traceable to an approved Bill of Materials to ensure material identity "
                "and traceability in clinical manufacturing.",
                ref
            ))

    return findings


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------

def run_all_checks(df: pd.DataFrame, specs: dict) -> list[dict]:
    """Execute all ALCOA+ checks and return consolidated findings list."""
    all_findings = []

    check_functions = [
        check_attributable,
        check_legible,
        check_contemporaneous,
        check_original,
        check_accurate,
        check_complete,
        check_consistent,
        check_enduring,
        check_available,
    ]

    for fn in check_functions:
        results = fn(df, specs)
        all_findings.extend(results)
        principle = fn.__name__.replace("check_", "").capitalize()
        print(f"  [{principle:>20}]  {len(results)} finding(s)")

    return all_findings


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def build_summary(findings: list[dict]) -> dict:
    """Compute per-principle pass/warn/fail status for dashboard rendering."""
    principles = [
        "Attributable", "Legible", "Contemporaneous", "Original",
        "Accurate", "Complete", "Consistent", "Enduring", "Available"
    ]

    summary = {}
    for p in principles:
        p_findings = [f for f in findings if f["principle"] == p]
        criticals = sum(1 for f in p_findings if f["severity"] == "CRITICAL")
        majors    = sum(1 for f in p_findings if f["severity"] == "MAJOR")
        minors    = sum(1 for f in p_findings if f["severity"] == "MINOR")

        if criticals > 0:
            status = "FAIL"
        elif majors > 0:
            status = "WARN"
        elif minors > 0:
            status = "WARN"
        else:
            status = "PASS"

        summary[p] = {
            "status": status,
            "critical": criticals,
            "major": majors,
            "minor": minors,
            "total": len(p_findings),
        }

    return summary


def overall_result(findings: list[dict]) -> str:
    """Derive overall batch review outcome."""
    if any(f["severity"] == "CRITICAL" for f in findings):
        return "FAIL"
    if any(f["severity"] == "MAJOR" for f in findings):
        return "REVIEW REQUIRED"
    return "PASS"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ALCOA+ Batch Record Compliance Checker")
    print("  Batch: USP-001 | Product: PBS 1X pH 7.4")
    print("=" * 60)

    df, specs = load_data()
    print(f"\n  Loaded {len(df)} steps from batch record.")
    print(f"  Running ALCOA+ checks...\n")

    findings = run_all_checks(df, specs)
    summary  = build_summary(findings)
    result   = overall_result(findings)

    # Persist findings for report generator
    output_payload = {
        "batch_id": specs["batch_id"],
        "product_name": specs["product_name"],
        "manufacturing_site": specs["manufacturing_site"],
        "reviewer": specs["reviewer"],
        "review_date": specs["review_date"],
        "overall_result": result,
        "total_steps": len(df),
        "total_findings": len(findings),
        "critical_count": sum(1 for f in findings if f["severity"] == "CRITICAL"),
        "major_count":    sum(1 for f in findings if f["severity"] == "MAJOR"),
        "minor_count":    sum(1 for f in findings if f["severity"] == "MINOR"),
        "principle_summary": summary,
        "findings": findings,
    }

    with open(FINDINGS_OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(output_payload, fh, indent=2, ensure_ascii=False)

    # Console summary
    print("\n" + "-" * 60)
    print(f"  OVERALL RESULT : {result}")
    print(f"  Total findings : {len(findings)}  "
          f"(CRITICAL: {output_payload['critical_count']}, "
          f"MAJOR: {output_payload['major_count']}, "
          f"MINOR: {output_payload['minor_count']})")
    print("-" * 60)
    print(f"\n  Findings saved to: {FINDINGS_OUTPUT}")
    print("  Run report_generator.py to produce the HTML report.\n")
