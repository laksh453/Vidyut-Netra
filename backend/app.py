"""
Vidyut Netra - Flask REST API Backend
Telangana Innovation Startup Challenge 2026 (TISC 2026) - Challenge 12: Revenue Assurance Analytics.

Exposes RESTful endpoints for:
1. Data Ingestion & Preprocessing
2. Measurement Reliability Engine
3. AI Anomaly Detection
4. Explainable Evidence Passport Generation
5. Reliability-Aware Inspection Prioritization
6. Inspection Feedback Loop & Active Learning
7. Model Benchmarking & Research Evaluation
8. Reports & Settings
"""

import os
import io
import json
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from database import init_db, get_connection
from synthetic_data import generate_synthetic_smart_meter_data
from preprocessing import validate_raw_dataframe, preprocess_smart_meter_data
from reliability_engine import compute_consumer_reliability
from anomaly_engine import run_anomaly_detection
from evidence_passport import generate_evidence_passport
from prioritization_engine import compute_inspection_prioritization
from feedback_engine import (
    seed_initial_feedback_benchmarks,
    record_field_outcome,
    evaluate_models_benchmark,
    save_field_verification,
    get_field_verification
)

frontend_dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

app = Flask(
    __name__,
    static_folder=frontend_dist_dir if os.path.exists(frontend_dist_dir) else None,
    static_url_path="/"
)
CORS(app)

# In-memory cached active pipeline state for high-performance responsiveness
STATE = {
    "dataset_id": 1,
    "dataset_name": "Synthetic Demonstration Benchmark",
    "raw_df": None,
    "cleaned_df": None,
    "reliability_df": None,
    "reliability_stats": {},
    "anomaly_results": [],
    "anomaly_summary": {},
    "inspection_tasks": [],
    "inspection_summary": {},
    "is_initialized": False
}

SAMPLE_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sample_data",
    "vidyut_netra_synthetic_meters.csv"
)

def run_full_pipeline(df_raw, dataset_name="Synthetic Demonstration Dataset"):
    """
    Executes end-to-end Vidyut Netra processing pipeline:
    Preprocessing -> Reliability Engine -> AI Anomaly Detection -> Prioritization.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Register Dataset
    cursor.execute("""
    INSERT INTO datasets (name, uploaded_at, total_records, status)
    VALUES (?, ?, ?, 'PROCESSING')
    """, (dataset_name, datetime.utcnow().isoformat(), len(df_raw)))
    dataset_id = cursor.lastrowid
    conn.commit()

    # 2. Preprocessing
    cleaned_df, prep_metrics = preprocess_smart_meter_data(df_raw, dataset_id=dataset_id)

    # 3. Measurement Reliability Engine
    rel_df, rel_stats = compute_consumer_reliability(cleaned_df)

    # 4. AI Anomaly Detection Engine
    anom_results, anom_summary = run_anomaly_detection(cleaned_df)

    # 5. Inspection Prioritization Engine
    tasks, task_summary = compute_inspection_prioritization(anom_results, rel_df, cleaned_df)

    # Update database records
    cursor.execute("""
    UPDATE datasets 
    SET total_records = ?, unique_consumers = ?, unique_meters = ?, 
        date_start = ?, date_end = ?, status = 'PROCESSED', summary_json = ?
    WHERE id = ?
    """, (
        prep_metrics["total_records"],
        prep_metrics["unique_consumers"],
        prep_metrics["unique_meters"],
        prep_metrics["date_range"].get("start"),
        prep_metrics["date_range"].get("end"),
        json.dumps(prep_metrics),
        dataset_id
    ))

    # Persist consumer reliability
    cursor.execute("DELETE FROM consumer_reliability WHERE dataset_id = ?", (dataset_id,))
    for _, r in rel_df.iterrows():
        cursor.execute("""
        INSERT INTO consumer_reliability 
        (dataset_id, consumer_id, meter_id, consumer_category, transformer_id, total_slots,
         observed_count, missing_count, reconstructed_count, inconsistent_count, delayed_count,
         reliability_score, qualification_status, qualification_reasons, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dataset_id, r["consumer_id"], r["meter_id"], r["consumer_category"], r["transformer_id"],
            int(r["total_slots"]), int(r["observed_count"]), int(r["missing_count"]),
            int(r["reconstructed_count"]), int(r["inconsistent_count"]), int(r["delayed_count"]),
            float(r["reliability_score"]), r["qualification_status"],
            json.dumps(r["qualification_reasons"]), datetime.utcnow().isoformat()
        ))

    # Persist anomaly results
    cursor.execute("DELETE FROM anomaly_results WHERE dataset_id = ?", (dataset_id,))
    for a in anom_results:
        cursor.execute("""
        INSERT INTO anomaly_results 
        (dataset_id, consumer_id, meter_id, analysis_period, anomaly_score, calibrated_risk_level,
         is_anomaly, detection_method, reasons_json, contributing_features_json,
         alternative_explanations_json, model_name, model_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dataset_id, a["consumer_id"], a["meter_id"], "Recent 30 Days", float(a["anomaly_score"]),
            a["risk_level"], int(a["is_anomaly"]), a["detection_method"],
            json.dumps(a["reasons"]), json.dumps(a["contributing_features"]),
            json.dumps(a["alternative_explanations"]), a["model_name"], a["model_version"],
            datetime.utcnow().isoformat()
        ))

    # Persist inspection tasks
    cursor.execute("DELETE FROM inspection_tasks WHERE dataset_id = ?", (dataset_id,))
    for t in tasks:
        cursor.execute("""
        INSERT INTO inspection_tasks 
        (dataset_id, consumer_id, meter_id, consumer_category, transformer_id, priority_score,
         priority_rank, recommended_action, evidence_qualification, anomaly_score,
         estimated_recoverable_value, inspection_cost, expected_roi, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """, (
            dataset_id, t["consumer_id"], t["meter_id"], t["consumer_category"], t["transformer_id"],
            float(t["priority_score"]), int(t["priority_rank"]), t["recommended_action"],
            t["reliability_status"], float(t["anomaly_score"]), float(t["estimated_recoverable_value"]),
            float(t["inspection_cost"]), float(t["roi_ratio"]), datetime.utcnow().isoformat()
        ))

    conn.commit()
    conn.close()

    # Update in-memory state
    STATE["dataset_id"] = dataset_id
    STATE["dataset_name"] = dataset_name
    STATE["raw_df"] = df_raw
    STATE["cleaned_df"] = cleaned_df
    STATE["reliability_df"] = rel_df
    STATE["reliability_stats"] = rel_stats
    STATE["anomaly_results"] = anom_results
    STATE["anomaly_summary"] = anom_summary
    STATE["inspection_tasks"] = tasks
    STATE["inspection_summary"] = task_summary
    STATE["prep_metrics"] = prep_metrics
    STATE["is_initialized"] = True

    return True

# Initialize database and seed sample data on startup
@app.before_request
def initialize_system():
    if not STATE["is_initialized"]:
        init_db()
        seed_initial_feedback_benchmarks()
        if os.path.exists(SAMPLE_CSV_PATH):
            df_sample = pd.read_csv(SAMPLE_CSV_PATH)
        else:
            df_sample = generate_synthetic_smart_meter_data(output_path=SAMPLE_CSV_PATH)
        run_full_pipeline(df_sample, dataset_name="Vidyut Netra Synthetic Benchmark (TISC 2026)")

# ----------------- API ENDPOINTS -----------------

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ONLINE",
        "service": "VIDYUT NETRA AI Engine",
        "version": "1.2.0-tisc2026",
        "timestamp": datetime.utcnow().isoformat(),
        "is_dataset_loaded": STATE["is_initialized"]
    })

@app.route("/api/data/download-sample", methods=["GET"])
def download_sample_csv():
    if not os.path.exists(SAMPLE_CSV_PATH):
        generate_synthetic_smart_meter_data(output_path=SAMPLE_CSV_PATH)
    return send_file(
        SAMPLE_CSV_PATH,
        mimetype="text/csv",
        as_attachment=True,
        download_name="vidyut_netra_synthetic_meters.csv"
    )

@app.route("/api/data/load-sample", methods=["POST"])
def load_sample_dataset():
    try:
        if not os.path.exists(SAMPLE_CSV_PATH):
            df_sample = generate_synthetic_smart_meter_data(output_path=SAMPLE_CSV_PATH)
        else:
            df_sample = pd.read_csv(SAMPLE_CSV_PATH)

        run_full_pipeline(df_sample, dataset_name="Vidyut Netra Synthetic Demonstration (TISC 2026)")
        return jsonify({
            "success": True,
            "message": "Sample demonstration smart-meter dataset loaded successfully.",
            "metrics": STATE.get("prep_metrics", {})
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/data/upload", methods=["POST"])
def upload_csv():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded. Please select a CSV file."}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"success": False, "error": "Empty filename. Please select a valid CSV file."}), 400

        if not file.filename.lower().endswith(".csv"):
            return jsonify({"success": False, "error": f"Invalid file format: '{file.filename}'. Only standard CSV (.csv) files are supported."}), 400

        # Read CSV with pandas, handling encoding gracefully (utf-8, latin1)
        try:
            df_raw = pd.read_csv(file)
        except UnicodeDecodeError:
            file.seek(0)
            df_raw = pd.read_csv(file, encoding="latin1")

        is_valid, errors = validate_raw_dataframe(df_raw)
        if not is_valid:
            return jsonify({"success": False, "error": " ".join(errors)}), 400

        run_full_pipeline(df_raw, dataset_name=file.filename)
        preview_rows = STATE["cleaned_df"].head(100).to_dict(orient="records") if STATE.get("cleaned_df") is not None else []
        return jsonify({
            "success": True,
            "filename": file.filename,
            "total_records": len(df_raw),
            "unique_consumers": int(df_raw["consumer_id"].nunique()),
            "message": f"Successfully parsed and validated {len(df_raw)} smart-meter records across {df_raw['consumer_id'].nunique()} consumers.",
            "metrics": STATE.get("prep_metrics", {}),
            "records": preview_rows,
            "dataset_name": file.filename
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to parse CSV file: {str(e)}"}), 500

@app.route("/api/data/preview", methods=["GET"])
def get_data_preview():
    if STATE["cleaned_df"] is None or STATE["cleaned_df"].empty:
        return jsonify({"records": [], "metrics": {}})
    
    preview_rows = STATE["cleaned_df"].head(100).to_dict(orient="records")
    return jsonify({
        "records": preview_rows,
        "metrics": STATE.get("prep_metrics", {}),
        "dataset_name": STATE.get("dataset_name", "None")
    })

@app.route("/api/reliability", methods=["GET"])
def get_reliability():
    if STATE["reliability_df"] is None:
        return jsonify({"consumers": [], "portfolio_stats": {}})

    # Optional filter by status: SUFFICIENT, UNCERTAIN, UNRELIABLE
    status_filter = request.args.get("status")
    search = request.args.get("search", "").lower()

    rel_df = STATE["reliability_df"].copy()

    if status_filter:
        rel_df = rel_df[rel_df["qualification_status"] == status_filter.upper()]

    if search:
        rel_df = rel_df[
            rel_df["consumer_id"].str.lower().str.contains(search) |
            rel_df["meter_id"].str.lower().str.contains(search) |
            rel_df["consumer_category"].str.lower().str.contains(search)
        ]

    return jsonify({
        "portfolio_stats": STATE.get("reliability_stats", {}),
        "consumers": rel_df.to_dict(orient="records")
    })

@app.route("/api/reliability/<consumer_id>", methods=["GET"])
def get_consumer_reliability_detail(consumer_id):
    if STATE["reliability_df"] is None:
        return jsonify({"error": "No dataset loaded"}), 404

    c_match = STATE["reliability_df"][STATE["reliability_df"]["consumer_id"] == consumer_id]
    if c_match.empty:
        return jsonify({"error": "Consumer not found"}), 404

    row = c_match.iloc[0].to_dict()
    return jsonify(row)

@app.route("/api/anomaly/run", methods=["POST"])
def trigger_anomaly_detection():
    data = request.json or {}
    contamination = float(data.get("contamination", 0.15))
    if STATE["cleaned_df"] is not None:
        anom_results, anom_summary = run_anomaly_detection(STATE["cleaned_df"], contamination=contamination)
        tasks, task_summary = compute_inspection_prioritization(anom_results, STATE["reliability_df"], STATE["cleaned_df"])
        STATE["anomaly_results"] = anom_results
        STATE["anomaly_summary"] = anom_summary
        STATE["inspection_tasks"] = tasks
        STATE["inspection_summary"] = task_summary

    return jsonify({
        "success": True,
        "summary": STATE.get("anomaly_summary", {}),
        "results_count": len(STATE.get("anomaly_results", []))
    })

@app.route("/api/anomaly/results", methods=["GET"])
def get_anomaly_results():
    search = request.args.get("search", "").lower()
    risk_filter = request.args.get("risk")
    anom_only = request.args.get("anomalies_only") == "true"

    results = STATE.get("anomaly_results", [])
    filtered = []

    # Map reliability status for unified visibility
    rel_map = {}
    if STATE["reliability_df"] is not None:
        for _, r in STATE["reliability_df"].iterrows():
            rel_map[r["consumer_id"]] = r["qualification_status"]

    for r in results:
        r_copy = dict(r)
        r_copy["reliability_status"] = rel_map.get(r["consumer_id"], "UNCERTAIN")

        if anom_only and not r_copy["is_anomaly"]:
            continue
        if risk_filter and r_copy["risk_level"] != risk_filter.upper():
            continue
        if search:
            if search not in r_copy["consumer_id"].lower() and search not in r_copy["meter_id"].lower():
                continue
        filtered.append(r_copy)

    return jsonify({
        "summary": STATE.get("anomaly_summary", {}),
        "results": filtered
    })

@app.route("/api/passport/<consumer_id>", methods=["GET"])
def get_evidence_passport(consumer_id):
    if STATE["cleaned_df"] is None or not STATE["anomaly_results"]:
        return jsonify({"error": "Pipeline has not processed data yet"}), 400

    # Locate anomaly row
    anom_row = next((a for a in STATE["anomaly_results"] if a["consumer_id"] == consumer_id), None)
    if not anom_row:
        return jsonify({"error": f"Consumer {consumer_id} not found in anomaly results"}), 404

    # Locate reliability row
    rel_row = None
    if STATE["reliability_df"] is not None:
        rel_match = STATE["reliability_df"][STATE["reliability_df"]["consumer_id"] == consumer_id]
        if not rel_match.empty:
            rel_row = rel_match.iloc[0].to_dict()

    passport = generate_evidence_passport(consumer_id, STATE["cleaned_df"], rel_row, anom_row)
    return jsonify(passport)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/api/passport/verify", methods=["POST"])
def save_passport_verification():
    data = request.json or {}
    c_id = data.get("consumer_id")
    m_id = data.get("meter_id", "UNKNOWN")
    officer_id = data.get("officer_id") or data.get("inspector_name", "Field Officer")
    date_str = data.get("inspection_date") or datetime.utcnow().strftime("%Y-%m-%d")
    final_outcome = data.get("final_outcome", "Inconclusive")
    checklist = data.get("checklist", [])
    notes = data.get("overall_notes", "")
    attachment_name = data.get("attachment_name", "")
    penalty = float(data.get("penalty_levied", 0.0))
    recovered = float(data.get("recovered_revenue", 0.0))
    meter_rep = int(data.get("meter_replaced", 0))

    if not c_id:
        return jsonify({"error": "consumer_id is required"}), 400

    save_field_verification(
        consumer_id=c_id,
        meter_id=m_id,
        officer_id=officer_id,
        inspection_date=date_str,
        final_outcome=final_outcome,
        checklist=checklist,
        overall_notes=notes,
        attachment_name=attachment_name,
        penalty_levied=penalty,
        recovered_revenue=recovered,
        meter_replaced=meter_rep
    )

    # Mark corresponding task as COMPLETED in in-memory state
    for t in STATE.get("inspection_tasks", []):
        if t["consumer_id"] == c_id:
            t["status"] = "COMPLETED"

    return jsonify({
        "success": True,
        "message": f"Field verification audit for {c_id} recorded persistently and linked to inspection feedback.",
        "consumer_id": c_id,
        "final_outcome": final_outcome
    })

@app.route("/api/passport/attachment", methods=["POST"])
def upload_passport_attachment():
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400

        safe_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename.replace(' ', '_')}"
        save_path = os.path.join(UPLOAD_FOLDER, safe_name)
        file.save(save_path)

        return jsonify({
            "success": True,
            "filename": safe_name,
            "original_name": file.filename,
            "size": os.path.getsize(save_path)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/passport/attachment/<filename>", methods=["GET"])
def get_passport_attachment(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return jsonify({"error": "Attachment not found"}), 404

@app.route("/api/inspections", methods=["GET"])
def get_inspections():
    action_filter = request.args.get("action")
    status_filter = request.args.get("status")

    tasks = STATE.get("inspection_tasks", [])
    filtered = []

    for t in tasks:
        if action_filter and t["recommended_action"] != action_filter.upper():
            continue
        if status_filter and t["status"] != status_filter.upper():
            continue
        filtered.append(t)

    return jsonify({
        "summary": STATE.get("inspection_summary", {}),
        "tasks": filtered
    })

@app.route("/api/inspections/feedback", methods=["POST"])
def submit_inspection_feedback():
    data = request.json or {}
    c_id = data.get("consumer_id")
    m_id = data.get("meter_id", "UNKNOWN")
    inspector = data.get("inspector_name", "Field Officer")
    officer_id = data.get("officer_id", inspector)
    date_str = data.get("inspection_date", datetime.utcnow().strftime("%Y-%m-%d"))
    final_outcome = data.get("final_outcome")
    finding = data.get("finding", "NORMAL_FALSE_ALARM")
    tamper_type = data.get("actual_tamper_type", "")
    penalty = float(data.get("penalty_levied", 0.0))
    recovered = float(data.get("recovered_revenue", 0.0))
    meter_rep = int(data.get("meter_replaced", 0))
    notes = data.get("inspector_notes", "")
    checklist = data.get("checklist_results")
    attachment = data.get("attachment_name", "")

    if not c_id:
        return jsonify({"error": "consumer_id is required"}), 400

    record_field_outcome(
        c_id, m_id, inspector, date_str, finding,
        actual_tamper_type=tamper_type,
        penalty_levied=penalty,
        recovered_revenue=recovered,
        meter_replaced=meter_rep,
        notes=notes,
        officer_id=officer_id,
        final_outcome=final_outcome,
        checklist_results=checklist,
        attachment_name=attachment
    )

    # Update in-memory task status
    for t in STATE.get("inspection_tasks", []):
        if t["consumer_id"] == c_id:
            t["status"] = "COMPLETED"

    return jsonify({"success": True, "message": "Inspection outcome recorded and verified."})

@app.route("/api/inspections/outcomes", methods=["GET"])
def get_inspection_outcomes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, consumer_id, meter_id, inspector_name, officer_id, inspection_date, finding,
           final_outcome, checklist_results_json, actual_tamper_type, penalty_levied,
           recovered_revenue, meter_replaced, attachment_name, inspector_notes, created_at
    FROM inspection_outcomes
    ORDER BY id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({"outcomes": rows, "total": len(rows)})

@app.route("/api/evaluation/metrics", methods=["GET"])
def get_evaluation_metrics():
    if not STATE["anomaly_results"] or STATE["reliability_df"] is None:
        return jsonify({"error": "No pipeline data to evaluate"}), 400

    metrics = evaluate_models_benchmark(STATE["anomaly_results"], STATE["reliability_df"])
    return jsonify(metrics)

@app.route("/api/reports/summary", methods=["GET"])
def get_executive_summary():
    cleaned_df = STATE.get("cleaned_df")
    rel_df = STATE.get("reliability_df")
    tasks = STATE.get("inspection_tasks", [])
    dataset_name = STATE.get("dataset_name", "No Dataset Loaded")
    is_synthetic = bool("synthetic" in dataset_name.lower() or "benchmark" in dataset_name.lower() or "demo" in dataset_name.lower())

    if cleaned_df is None or cleaned_df.empty:
        return jsonify({
            "is_empty": True,
            "dataset_name": dataset_name,
            "is_synthetic": is_synthetic,
            "discom_jurisdiction": "Telangana State Southern & Northern Power Distribution (TSSPDCL / TSNPDCL)",
            "report_date": datetime.utcnow().strftime("%d %B %Y"),
            "total_consumers_monitored": 0,
            "total_meters_monitored": 0,
            "total_readings_processed": 0,
            "total_estimated_recoverable_revenue_inr": 0.0,
            "has_verified_inspections": False,
            "actual_recovered_revenue_inr": None,
            "penalties_levied_inr": None,
            "confirmed_theft_cases": 0,
            "measurement_reliability_rate": 0.0,
            "anomalies_flagged": 0,
            "critical_cases": 0,
            "category_revenue_exposure": [],
            "priority_action_queue": [],
            "field_actions_summary": {}
        })

    # Direct calculations from the current dataset
    current_consumers = set(cleaned_df["consumer_id"].unique())
    total_consumers = len(current_consumers)
    total_meters = int(cleaned_df["meter_id"].nunique())
    total_readings = len(cleaned_df)

    # Actual Measurement Reliability metrics
    if rel_df is not None and not rel_df.empty:
        sufficient_count = int((rel_df["qualification_status"] == "SUFFICIENT").sum())
        uncertain_count = int((rel_df["qualification_status"] == "UNCERTAIN").sum())
        unreliable_count = int((rel_df["qualification_status"] == "UNRELIABLE").sum())
        reliability_rate = round((sufficient_count / total_consumers) * 100, 1) if total_consumers > 0 else 0.0
    else:
        sufficient_count, uncertain_count, unreliable_count, reliability_rate = 0, 0, 0, 0.0

    # Total estimated recoverable revenue from actual prioritized tasks
    total_est_loss = sum(t.get("estimated_recoverable_value", 0.0) for t in tasks)

    # Fetch verified inspection outcomes ONLY for consumers present in the current dataset
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT consumer_id, finding, penalty_levied, recovered_revenue 
    FROM inspection_outcomes
    """)
    all_outcomes = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Filter to current dataset consumers
    dataset_outcomes = [o for o in all_outcomes if o["consumer_id"] in current_consumers]
    has_verified = len(dataset_outcomes) > 0

    if has_verified:
        theft_outcomes = [o for o in dataset_outcomes if o["finding"] == "CONFIRMED_THEFT"]
        actual_recovered = sum(float(o.get("recovered_revenue") or 0.0) for o in dataset_outcomes)
        penalties_levied = sum(float(o.get("penalty_levied") or 0.0) for o in dataset_outcomes)
        confirmed_thefts = len(theft_outcomes)
    else:
        actual_recovered = None
        penalties_levied = None
        confirmed_thefts = 0

    # Dynamic Category Revenue Exposure from actual uploaded data
    category_exposure = []
    categories = sorted(cleaned_df["consumer_category"].dropna().unique())
    for cat in categories:
        cat_consumers = set(cleaned_df[cleaned_df["consumer_category"] == cat]["consumer_id"].unique())
        cat_tasks = [t for t in tasks if t["consumer_id"] in cat_consumers]
        cat_est_loss = sum(float(t.get("estimated_recoverable_value") or 0.0) for t in cat_tasks)
        
        cat_outcomes = [o for o in dataset_outcomes if o["consumer_id"] in cat_consumers]
        if cat_outcomes:
            cat_actual_rec = sum(float(o.get("recovered_revenue") or 0.0) for o in cat_outcomes)
            cat_has_verified = True
        else:
            cat_actual_rec = None
            cat_has_verified = False

        category_exposure.append({
            "category": str(cat),
            "estimated_loss": round(cat_est_loss, 2),
            "actual_recovered": round(cat_actual_rec, 2) if cat_actual_rec is not None else None,
            "has_verified_recovery": cat_has_verified,
            "consumer_count": len(cat_consumers)
        })

    # Priority Action Queue directly from prioritization engine (top 6 ranked)
    priority_queue = tasks[:6] if tasks else []

    return jsonify({
        "is_empty": False,
        "dataset_name": dataset_name,
        "is_synthetic": is_synthetic,
        "discom_jurisdiction": "Telangana State Southern & Northern Power Distribution (TSSPDCL / TSNPDCL)",
        "report_date": datetime.utcnow().strftime("%d %B %Y"),
        "total_consumers_monitored": total_consumers,
        "total_meters_monitored": total_meters,
        "total_readings_processed": total_readings,
        "total_estimated_recoverable_revenue_inr": round(total_est_loss, 2),
        "has_verified_inspections": has_verified,
        "verified_inspections_count": len(dataset_outcomes),
        "actual_recovered_revenue_inr": round(actual_recovered, 2) if actual_recovered is not None else None,
        "penalties_levied_inr": round(penalties_levied, 2) if penalties_levied is not None else None,
        "confirmed_theft_cases": confirmed_thefts,
        "measurement_reliability_rate": reliability_rate,
        "sufficient_count": sufficient_count,
        "uncertain_count": uncertain_count,
        "unreliable_count": unreliable_count,
        "anomalies_flagged": STATE.get("anomaly_summary", {}).get("total_anomalies_flagged", 0),
        "critical_cases": STATE.get("anomaly_summary", {}).get("critical_risk_count", 0),
        "category_revenue_exposure": category_exposure,
        "priority_action_queue": priority_queue,
        "field_actions_summary": STATE.get("inspection_summary", {})
    })

@app.route("/api/settings", methods=["GET", "POST"])
def handle_settings():
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.json or {}
        for key, val in data.items():
            cursor.execute("""
            UPDATE system_settings
            SET setting_value = ?, updated_at = ?
            WHERE setting_key = ?
            """, (str(val) if not isinstance(val, (dict, list)) else json.dumps(val), datetime.utcnow().isoformat(), key))
        conn.commit()

    cursor.execute("SELECT setting_key, setting_value, description FROM system_settings")
    settings = {}
    for r in cursor.fetchall():
        key = r["setting_key"]
        val = r["setting_value"]
        try:
            val = json.loads(val)
        except:
            pass
        settings[key] = {
            "value": val,
            "description": r["description"]
        }
    conn.close()
    return jsonify(settings)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if frontend_dist_dir and os.path.exists(frontend_dist_dir):
        target_file = os.path.join(frontend_dist_dir, path)
        if path != "" and os.path.exists(target_file):
            return send_file(target_file)
        index_file = os.path.join(frontend_dist_dir, "index.html")
        if os.path.exists(index_file):
            return send_file(index_file)
    return jsonify({
        "service": "VIDYUT NETRA AI Engine API",
        "documentation": "Frontend build not detected. Please run 'npm run build' in frontend directory."
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Vidyut Netra Flask API Server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
