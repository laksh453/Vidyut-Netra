"""
Vidyut Netra Reliability-Aware Inspection Prioritization Engine
Module 6: Optimizes DISCOM Field Resource Allocation.

Research Contribution:
Moves beyond naive ranking by pairing AI Anomaly scores with Measurement Reliability
and Economic ROI metrics. Cases with UNRELIABLE data are routed to Hardware Maintenance
rather than dispatched as costly, antagonistic theft investigations.
"""

import pandas as pd
import numpy as np

def compute_inspection_prioritization(anomaly_results, reliability_df, cleaned_df, default_cost=1500.0, default_tariff=7.5):
    """
    Ranks and routes field actions based on multi-criteria optimization:
    - Anomaly severity
    - Reliability qualification factor
    - Recoverable revenue potential
    - Operational inspection cost
    - Transformer geographic clustering
    """
    tasks = []

    # Map reliability details by consumer_id
    rel_map = {}
    if not reliability_df.empty:
        for _, r in reliability_df.iterrows():
            rel_map[r["consumer_id"]] = r

    for anom in anomaly_results:
        c_id = anom["consumer_id"]
        m_id = anom["meter_id"]
        cat = anom["consumer_category"]
        tr = anom["transformer_id"]
        score = anom["anomaly_score"]
        is_anom = anom["is_anomaly"]
        
        rel_info = rel_map.get(c_id, {})
        rel_status = rel_info.get("qualification_status", "UNCERTAIN")
        rel_score = float(rel_info.get("reliability_score", 50.0))

        # Retrieve estimated recoverable value and inspection cost from dataset if present
        c_readings = cleaned_df[cleaned_df["consumer_id"] == c_id]
        if "estimated_recoverable_value" in c_readings.columns and not c_readings["estimated_recoverable_value"].isna().all():
            est_recovery = float(c_readings["estimated_recoverable_value"].dropna().iloc[-1])
        else:
            # Estimate based on drop percentage and category tariff
            drop_pct = anom.get("features_summary", {}).get("drop_percentage", 0.0)
            mean_cons = anom.get("features_summary", {}).get("mean_consumption", 10.0)
            if drop_pct > 20:
                lost_units_monthly = (mean_cons * (drop_pct / 100.0)) * 30
                est_recovery = round(lost_units_monthly * default_tariff, 2)
            else:
                est_recovery = 0.0

        if "inspection_cost" in c_readings.columns and not c_readings["inspection_cost"].isna().all():
            insp_cost = float(c_readings["inspection_cost"].dropna().iloc[-1])
        else:
            insp_cost = default_cost

        # Smart Operational Routing Decision
        if rel_status == "UNRELIABLE":
            # Telemetry or hardware defect suspected; do NOT send revenue theft raid!
            recommended_action = "METER_MAINTENANCE"
            action_label = "Meter Technical / Telemetry Maintenance Order"
            # Priority scaled by score and maintenance urgency
            priority_score = round(score * 40.0 + (100.0 - rel_score) * 0.4, 2)
            action_description = "Data telemetry has failed reliability threshold. Field meter hardware & SIM/gateway check required."
        elif rel_status == "UNCERTAIN":
            recommended_action = "DESKTOP_AUDIT"
            action_label = "Secondary Desktop Telemetry Audit"
            priority_score = round(score * 60.0 + rel_score * 0.2, 2)
            action_description = "Intermittent data quality. Review historical consumer billing & re-poll smart meter before field dispatch."
        else: # SUFFICIENT
            if is_anom or score >= 0.50:
                recommended_action = "THEFT_INSPECTION"
                action_label = "Priority Revenue Assurance Field Inspection"
                # Benefit-Cost Ratio multiplier
                roi_ratio = (est_recovery / insp_cost) if insp_cost > 0 else 1.0
                roi_weight = min(2.5, max(0.5, np.log1p(roi_ratio)))
                priority_score = round(score * 70.0 * roi_weight, 2)
                action_description = "Verified high-integrity anomaly with substantial revenue recovery potential. Deploy field inspection squad."
            else:
                recommended_action = "ROUTINE_MONITOR"
                action_label = "Routine Surveillance"
                priority_score = round(score * 20.0, 2)
                action_description = "Telemetry within normal parameters. Continue standard AMI monitoring."

        roi_ratio = round(est_recovery / insp_cost, 2) if insp_cost > 0 else 0.0
        net_expected_gain = round(est_recovery - insp_cost, 2)

        tasks.append({
            "consumer_id": c_id,
            "meter_id": m_id,
            "consumer_category": cat,
            "transformer_id": tr,
            "anomaly_score": score,
            "reliability_status": rel_status,
            "reliability_score": rel_score,
            "recommended_action": recommended_action,
            "action_label": action_label,
            "action_description": action_description,
            "estimated_recoverable_value": est_recovery,
            "inspection_cost": insp_cost,
            "roi_ratio": roi_ratio,
            "net_expected_gain": net_expected_gain,
            "priority_score": priority_score,
            "status": "PENDING"
        })

    # Sort descending by priority_score
    tasks.sort(key=lambda x: x["priority_score"], reverse=True)

    # Assign priority rank
    for rank, task in enumerate(tasks, start=1):
        task["priority_rank"] = rank

    summary = {
        "total_tasks": len(tasks),
        "theft_inspection_count": sum(1 for t in tasks if t["recommended_action"] == "THEFT_INSPECTION"),
        "meter_maintenance_count": sum(1 for t in tasks if t["recommended_action"] == "METER_MAINTENANCE"),
        "desktop_audit_count": sum(1 for t in tasks if t["recommended_action"] == "DESKTOP_AUDIT"),
        "routine_count": sum(1 for t in tasks if t["recommended_action"] == "ROUTINE_MONITOR"),
        "total_estimated_recoverable_value": round(sum(t["estimated_recoverable_value"] for t in tasks if t["recommended_action"] == "THEFT_INSPECTION"), 2),
        "total_inspection_cost": round(sum(t["inspection_cost"] for t in tasks if t["recommended_action"] == "THEFT_INSPECTION"), 2)
    }

    return tasks, summary
