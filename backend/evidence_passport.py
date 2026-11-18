"""
Vidyut Netra Evidence Passport Generator
Module 5: Explainable AI and Standardized Revenue Assurance Dossier.

Generates an audit-ready, legally and operationally rigorous Evidence Passport
for each flagged consumer, upholding ethical guidelines:
- An anomaly is NOT proof of electricity theft.
- Transparent presentation of Measurement Reliability qualification.
- Plausible benign alternative explanations.
- Standardized Physical Verification SOP Checklist for field squads.
"""

from datetime import datetime
import json
import pandas as pd
import numpy as np
from database import get_connection

def generate_evidence_passport(consumer_id, cleaned_df, reliability_row, anomaly_row):
    """
    Assembles the complete Evidence Passport for a consumer.
    """
    c_readings = cleaned_df[cleaned_df["consumer_id"] == consumer_id].copy()
    c_readings["parsed_timestamp"] = pd.to_datetime(c_readings["timestamp"], errors="coerce")
    c_readings = c_readings.sort_values(by="parsed_timestamp").reset_index(drop=True)

    meter_id = anomaly_row.get("meter_id", "UNKNOWN")
    cat = anomaly_row.get("consumer_category", "General")
    tr = anomaly_row.get("transformer_id", "DT-UNKNOWN")

    # Time series history formatted for visualization
    history_points = []
    for _, r in c_readings.iterrows():
        ts_str = str(r["parsed_timestamp"])[:10] if pd.notna(r["parsed_timestamp"]) else str(r["timestamp"])[:10]
        history_points.append({
            "timestamp": ts_str,
            "consumption": float(r["consumption"]) if pd.notna(r["consumption"]) else None,
            "raw_consumption": float(r["raw_consumption"]) if pd.notna(r["raw_consumption"]) else None,
            "voltage": float(r["voltage"]) if pd.notna(r["voltage"]) else 230.0,
            "category": str(r["reading_category"]),
            "is_reconstructed": bool(r["is_reconstructed"])
        })

    # Period
    if len(history_points) > 0:
        period_start = history_points[0]["timestamp"]
        period_end = history_points[-1]["timestamp"]
        analysis_period = f"{period_start} to {period_end}"
    else:
        analysis_period = "Recent 30 Days"

    # Reliability details
    rel_status = reliability_row.get("qualification_status", "UNCERTAIN") if reliability_row else "UNCERTAIN"
    rel_score = reliability_row.get("reliability_score", 0.0) if reliability_row else 0.0
    rel_reasons = reliability_row.get("qualification_reasons", []) if reliability_row else []
    if isinstance(rel_reasons, str):
        try:
            rel_reasons = json.loads(rel_reasons)
        except:
            rel_reasons = [rel_reasons]

    # Anomaly details
    anom_score = anomaly_row.get("anomaly_score", 0.0)
    risk_level = anomaly_row.get("risk_level", "LOW")
    is_anom = anomaly_row.get("is_anomaly", 0)
    reasons = anomaly_row.get("reasons", [])
    contributing_feats = anomaly_row.get("contributing_features", [])
    alt_explanations = anomaly_row.get("alternative_explanations", [])
    model_name = anomaly_row.get("model_name", "VidyutNetra-HybridDetector")
    model_version = anomaly_row.get("model_version", "1.2.0-tisc2026")

    # Default 6-Point Field Verification SOP Checklist Template
    default_sop_checklist = [
        {
            "step": 1,
            "action": "Physical Meter Seal & Box Integrity",
            "instruction": "Inspect terminal cover seals, optical communication port seals, and poly-carbonate meter casing for drill marks, glue, or micro-cracks.",
            "status": "NOT_VERIFIED",
            "notes": "",
            "attachment_name": ""
        },
        {
            "step": 2,
            "action": "Current Transformer (CT) & Potential Transformer (PT) Circuit",
            "instruction": "Test for neutral looping, external shunt wires, or secondary CT shorting clips bypassing the metering element.",
            "status": "NOT_VERIFIED",
            "notes": "",
            "attachment_name": ""
        },
        {
            "step": 3,
            "action": "Clamp-On Reference Meter Verification",
            "instruction": "Measure live active current (A) and line-to-neutral voltage (V) on load side using calibrated reference meter; compare against smart meter LCD display.",
            "status": "NOT_VERIFIED",
            "notes": "",
            "attachment_name": ""
        },
        {
            "step": 4,
            "action": "On-Site Premise & Solar Inverter Verification",
            "instruction": "Check whether consumer has installed rooftop solar PV / battery ESS without bi-directional net metering registration.",
            "status": "NOT_VERIFIED",
            "notes": "",
            "attachment_name": ""
        },
        {
            "step": 5,
            "action": "Occupancy & Operational Activity Status",
            "instruction": "Verify if property is temporarily vacant, under renovation, or subject to seasonal manufacturing shutdown.",
            "status": "NOT_VERIFIED",
            "notes": "",
            "attachment_name": ""
        },
        {
            "step": 6,
            "action": "Tamper Event Memory Extraction",
            "instruction": "Download meter event logs via optical probe (magnetic tamper event, reverse current, neutral disturbance, top cover open timestamps).",
            "status": "NOT_VERIFIED",
            "notes": "",
            "attachment_name": ""
        }
    ]

    # Query persistent database for any saved field verification
    saved_ver = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT officer_id, inspection_date, final_outcome, checklist_json, attachment_name, notes, updated_at
        FROM field_verifications
        WHERE consumer_id = ?
        ORDER BY id DESC LIMIT 1
        """, (consumer_id,))
        row = cursor.fetchone()
        if not row:
            # Check inspection_outcomes as fallback
            cursor.execute("""
            SELECT inspector_name as officer_id, inspection_date, final_outcome, checklist_results_json as checklist_json,
                   attachment_name, inspector_notes as notes, created_at as updated_at
            FROM inspection_outcomes
            WHERE consumer_id = ?
            ORDER BY id DESC LIMIT 1
            """, (consumer_id,))
            row = cursor.fetchone()
        conn.close()

        if row:
            saved_ver = dict(row)
    except Exception as e:
        print(f"Error querying field verification for {consumer_id}: {e}")

    # Merge saved verification checklist if available
    sop_checklist = default_sop_checklist
    if saved_ver and saved_ver.get("checklist_json"):
        try:
            saved_items = json.loads(saved_ver["checklist_json"])
            if isinstance(saved_items, list) and len(saved_items) > 0:
                sop_checklist = []
                for default_item in default_sop_checklist:
                    match = next((item for item in saved_items if item.get("step") == default_item["step"]), None)
                    if match:
                        sop_checklist.append({
                            "step": default_item["step"],
                            "action": default_item["action"],
                            "instruction": default_item["instruction"],
                            "status": match.get("status", "NOT_VERIFIED"),
                            "notes": match.get("notes", ""),
                            "attachment_name": match.get("attachment_name", "")
                        })
                    else:
                        sop_checklist.append(default_item)
        except Exception as e:
            print(f"Error parsing saved checklist: {e}")

    completed_checks_count = sum(1 for c in sop_checklist if c.get("status") in ["PASS", "FAIL"])
    pending_checks_count = sum(1 for c in sop_checklist if c.get("status") not in ["PASS", "FAIL"])

    passport = {
        "passport_id": f"PASSPORT-{consumer_id}-{datetime.utcnow().strftime('%Y%m%d')}",
        "consumer_id": consumer_id,
        "meter_id": meter_id,
        "consumer_category": cat,
        "transformer_id": tr,
        "analysis_period": analysis_period,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        
        # Anomaly Status
        "potential_anomaly_status": "FLAGGED_FOR_INSPECTION" if is_anom else "NORMAL_PATTERN",
        "model_anomaly_score": anom_score,
        "risk_level": risk_level,
        
        # Measurement Reliability Qualification
        "reliability_qualification_status": rel_status,
        "reliability_score": rel_score,
        "reliability_qualification_reasons": rel_reasons,
        "telemetry_breakdown": {
            "observed_count": reliability_row.get("observed_count", 0) if reliability_row else 0,
            "missing_count": reliability_row.get("missing_count", 0) if reliability_row else 0,
            "reconstructed_count": reliability_row.get("reconstructed_count", 0) if reliability_row else 0,
            "inconsistent_count": reliability_row.get("inconsistent_count", 0) if reliability_row else 0,
            "delayed_count": reliability_row.get("delayed_count", 0) if reliability_row else 0,
        },
        
        # Diagnostic Evidence
        "reasons_for_flagging": reasons,
        "important_contributing_features": contributing_feats,
        "plausible_alternative_explanations": alt_explanations,
        
        # Provenance
        "model_name": model_name,
        "model_version": model_version,
        "ethical_disclaimer": "CRITICAL: An unusual consumption pattern is NOT conclusive proof of electricity theft. This passport provides explainable analytical evidence to assist human field inspectors. Every finding must be physically verified.",
        
        # Field Execution
        "sop_verification_checklist": sop_checklist,

        # Persistent Human Verification Audit Summary
        "verification_audit": {
            "is_verified": bool(saved_ver),
            "status": "COMPLETED" if saved_ver and pending_checks_count == 0 else ("IN_PROGRESS" if saved_ver else "PENDING"),
            "officer_id": saved_ver.get("officer_id", "") if saved_ver else "",
            "inspection_date": saved_ver.get("inspection_date", "") if saved_ver else "",
            "final_outcome": saved_ver.get("final_outcome", "") if saved_ver else "",
            "overall_notes": saved_ver.get("notes", "") if saved_ver else "",
            "attachment_name": saved_ver.get("attachment_name", "") if saved_ver else "",
            "completed_checks_count": completed_checks_count,
            "pending_checks_count": pending_checks_count,
            "total_checks_count": len(sop_checklist),
            "updated_at": saved_ver.get("updated_at", "") if saved_ver else ""
        },
        
        # Supporting Trend Data
        "consumption_trend": history_points
    }

    return passport
