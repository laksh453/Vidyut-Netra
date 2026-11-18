"""
Vidyut Netra Measurement Reliability Engine
Core Research Contribution for TISC 2026 - Challenge 12.

Assesses whether meter readings are mathematically and physically suitable
for supporting revenue assurance anomaly investigations before ML flagging.

Categorizes readings into:
1. OBSERVED: Directly available valid reading.
2. MISSING: Required reading is unavailable.
3. RECONSTRUCTED: Separately identified estimated or imputed reading.
4. INCONSISTENT: Violates defined validation rules (negative values, impossible spikes, duplicates).
5. DELAYED: Reading delayed relative to expected transmission schedule.

Computes transparent consumer reliability score and classifies into Evidence Qualification Status:
- SUFFICIENT: Eligible for theft-related inspection prioritization. (NOT proof of theft).
- UNCERTAIN: Requires secondary verification / re-polling.
- UNRELIABLE: Disqualified from theft prioritization. Routed to Meter Technical Maintenance.
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime

DEFAULT_WEIGHTS = {
    "w_observed": 1.0,
    "w_reconstructed": 0.60,
    "w_inconsistent": 2.0,
    "w_missing": 1.2,
    "w_delayed": 0.3
}

DEFAULT_THRESHOLDS = {
    "sufficient": 80.0,
    "uncertain": 60.0
}

def compute_consumer_reliability(cleaned_df, weights=None, thresholds=None):
    """
    Computes measurement reliability metrics and evidence qualification status
    for each consumer in the cleaned dataframe.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    consumer_results = []
    consumers = cleaned_df["consumer_id"].unique()

    for c_id in consumers:
        c_rows = cleaned_df[cleaned_df["consumer_id"] == c_id]
        m_id = c_rows["meter_id"].iloc[0] if len(c_rows) > 0 else "UNKNOWN"
        cat = c_rows["consumer_category"].iloc[0] if "consumer_category" in c_rows.columns else "General"
        tr = c_rows["transformer_id"].iloc[0] if "transformer_id" in c_rows.columns else "DT-UNKNOWN"

        total_slots = len(c_rows)
        if total_slots == 0:
            continue

        cat_counts = c_rows["reading_category"].value_counts().to_dict()
        n_obs = cat_counts.get("OBSERVED", 0)
        n_rec = cat_counts.get("RECONSTRUCTED", 0)
        n_incon = cat_counts.get("INCONSISTENT", 0)
        n_miss = cat_counts.get("MISSING", 0)
        n_del = cat_counts.get("DELAYED", 0)

        # Transparent Reliability Score Formula:
        # Score = 100 * [ (w_obs * n_obs + w_rec * n_rec - w_incon * n_incon - w_miss * n_miss - w_del * n_del) / total_slots ]
        # Clamped to range [0.0, 100.0]
        w_obs = weights.get("w_observed", 1.0)
        w_rec = weights.get("w_reconstructed", 0.60)
        w_incon = weights.get("w_inconsistent", 2.0)
        w_miss = weights.get("w_missing", 1.2)
        w_del = weights.get("w_delayed", 0.3)

        effective_numerator = (
            w_obs * n_obs +
            w_rec * n_rec -
            w_incon * n_incon -
            w_miss * n_miss -
            w_del * n_del
        )
        
        raw_score = (effective_numerator / total_slots) * 100.0
        reliability_score = max(0.0, min(100.0, round(raw_score, 1)))

        # Evidence Qualification Rule Engine
        qualification_reasons = []
        
        # Rule 1: High Inconsistent readings immediately disqualify from SUFFICIENT
        inconsistent_ratio = n_incon / total_slots
        missing_ratio = n_miss / total_slots
        reconstructed_ratio = n_rec / total_slots

        if inconsistent_ratio >= 0.05:
            qualification_reasons.append(f"High inconsistency rate ({inconsistent_ratio*100:.1f}%): contains invalid, negative or duplicate readings.")
        if missing_ratio >= 0.25:
            qualification_reasons.append(f"Significant telemetry blackout ({missing_ratio*100:.1f}% missing intervals).")
        if reconstructed_ratio >= 0.30:
            qualification_reasons.append(f"Excessive imputed data ({reconstructed_ratio*100:.1f}% reconstructed); may mask ground truth.")

        # Determine Qualification Status
        if reliability_score >= thresholds["sufficient"] and inconsistent_ratio < 0.03 and missing_ratio < 0.15:
            qualification_status = "SUFFICIENT"
            qualification_reasons.append("High telemetry integrity; reading series satisfies statistical standards for revenue assurance evaluation.")
        elif reliability_score >= thresholds["uncertain"] and inconsistent_ratio < 0.08:
            qualification_status = "UNCERTAIN"
            qualification_reasons.append("Moderate data quality; auxiliary verification / desktop audit required prior to field deployment.")
        else:
            qualification_status = "UNRELIABLE"
            if not qualification_reasons:
                qualification_reasons.append("Telemetry quality below minimum diagnostic cutoff (<60%); potential meter communication or sensor failure.")

        consumer_results.append({
            "consumer_id": c_id,
            "meter_id": str(m_id),
            "consumer_category": str(cat),
            "transformer_id": str(tr),
            "total_slots": total_slots,
            "observed_count": n_obs,
            "missing_count": n_miss,
            "reconstructed_count": n_rec,
            "inconsistent_count": n_incon,
            "delayed_count": n_del,
            "reliability_score": reliability_score,
            "qualification_status": qualification_status,
            "qualification_reasons": qualification_reasons,
            "observed_pct": round((n_obs / total_slots) * 100, 1),
            "missing_pct": round((n_miss / total_slots) * 100, 1),
            "reconstructed_pct": round((n_rec / total_slots) * 100, 1),
            "inconsistent_pct": round((n_incon / total_slots) * 100, 1),
            "delayed_pct": round((n_del / total_slots) * 100, 1)
        })

    summary_df = pd.DataFrame(consumer_results)
    
    # Portfolio-wide statistics
    portfolio_stats = {
        "total_consumers": len(summary_df),
        "sufficient_count": int((summary_df["qualification_status"] == "SUFFICIENT").sum()),
        "uncertain_count": int((summary_df["qualification_status"] == "UNCERTAIN").sum()),
        "unreliable_count": int((summary_df["qualification_status"] == "UNRELIABLE").sum()),
        "average_reliability_score": round(summary_df["reliability_score"].mean(), 1) if len(summary_df) > 0 else 0.0,
        "category_totals": {
            "OBSERVED": int(summary_df["observed_count"].sum()) if len(summary_df) > 0 else 0,
            "MISSING": int(summary_df["missing_count"].sum()) if len(summary_df) > 0 else 0,
            "RECONSTRUCTED": int(summary_df["reconstructed_count"].sum()) if len(summary_df) > 0 else 0,
            "INCONSISTENT": int(summary_df["inconsistent_count"].sum()) if len(summary_df) > 0 else 0,
            "DELAYED": int(summary_df["delayed_count"].sum()) if len(summary_df) > 0 else 0
        }
    }

    return summary_df, portfolio_stats
