"""
Vidyut Netra Database Management Module
Uses SQLite with structured relational schema and JSON capability for research metadata.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vidyut_netra.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Datasets metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS datasets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        total_records INTEGER DEFAULT 0,
        unique_consumers INTEGER DEFAULT 0,
        unique_meters INTEGER DEFAULT 0,
        date_start TEXT,
        date_end TEXT,
        status TEXT DEFAULT 'UPLOADED',
        summary_json TEXT
    )
    """)

    # Raw Readings (Preserving original telemetry with zero modification)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        consumption REAL,
        voltage REAL,
        current REAL,
        transformer_id TEXT,
        consumer_category TEXT,
        estimated_recoverable_value REAL,
        inspection_cost REAL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    )
    """)

    # Cleaned and Reconstructed Readings with explicit Provenance
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cleaned_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        consumption REAL,
        raw_consumption REAL,
        voltage REAL,
        current REAL,
        transformer_id TEXT,
        consumer_category TEXT,
        reading_category TEXT NOT NULL, -- OBSERVED, MISSING, RECONSTRUCTED, INCONSISTENT, DELAYED
        is_reconstructed INTEGER DEFAULT 0,
        is_duplicate INTEGER DEFAULT 0,
        provenance_notes TEXT,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    )
    """)

    # Consumer Measurement Reliability Assessment
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consumer_reliability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        consumer_category TEXT,
        transformer_id TEXT,
        total_slots INTEGER DEFAULT 0,
        observed_count INTEGER DEFAULT 0,
        missing_count INTEGER DEFAULT 0,
        reconstructed_count INTEGER DEFAULT 0,
        inconsistent_count INTEGER DEFAULT 0,
        delayed_count INTEGER DEFAULT 0,
        reliability_score REAL NOT NULL,
        qualification_status TEXT NOT NULL, -- SUFFICIENT, UNCERTAIN, UNRELIABLE
        qualification_reasons TEXT, -- JSON array
        updated_at TEXT NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    )
    """)

    # AI Anomaly Detection Results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS anomaly_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        analysis_period TEXT,
        anomaly_score REAL NOT NULL, -- 0.0 to 1.0 unsupervised score
        calibrated_risk_level TEXT NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
        is_anomaly INTEGER NOT NULL, -- 0 or 1 binary flag
        detection_method TEXT NOT NULL,
        reasons_json TEXT,
        contributing_features_json TEXT,
        alternative_explanations_json TEXT,
        model_name TEXT,
        model_version TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    )
    """)

    # Evidence Passports (Full metadata dossier)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_passports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        passport_data_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    )
    """)

    # Inspection Prioritization Tasks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inspection_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        consumer_category TEXT,
        transformer_id TEXT,
        priority_score REAL NOT NULL,
        priority_rank INTEGER,
        recommended_action TEXT NOT NULL, -- THEFT_INSPECTION, METER_MAINTENANCE, DESKTOP_AUDIT
        evidence_qualification TEXT NOT NULL,
        anomaly_score REAL NOT NULL,
        estimated_recoverable_value REAL DEFAULT 0,
        inspection_cost REAL DEFAULT 1500,
        expected_roi REAL DEFAULT 0,
        status TEXT DEFAULT 'PENDING', -- PENDING, SCHEDULED, COMPLETED, CANCELLED
        assigned_inspector TEXT,
        scheduled_date TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
    )
    """)

    # Inspection Outcomes & Feedback Loop (Closing the loop for ML re-training)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inspection_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspection_id INTEGER,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        inspector_name TEXT NOT NULL,
        officer_id TEXT,
        inspection_date TEXT NOT NULL,
        finding TEXT NOT NULL, -- CONFIRMED_THEFT, FAULTY_METER, LEGITIMATE_DROP, NORMAL_FALSE_ALARM, ACCESS_DENIED
        final_outcome TEXT,    -- Confirmed technical issue, Confirmed meter issue, Legitimate consumption variation, Suspected irregularity requiring further investigation, Inconclusive
        checklist_results_json TEXT,
        actual_tamper_type TEXT,
        penalty_levied REAL DEFAULT 0,
        recovered_revenue REAL DEFAULT 0,
        meter_replaced INTEGER DEFAULT 0,
        attachment_name TEXT,
        inspector_notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (inspection_id) REFERENCES inspection_tasks(id)
    )
    """)

    # Field Verifications Table (Dedicated audit checklist records)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS field_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consumer_id TEXT NOT NULL,
        meter_id TEXT NOT NULL,
        officer_id TEXT NOT NULL,
        inspection_date TEXT NOT NULL,
        final_outcome TEXT NOT NULL,
        checklist_json TEXT NOT NULL,
        attachment_name TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Run safe column additions if inspection_outcomes was created earlier without new columns
    cursor.execute("PRAGMA table_info(inspection_outcomes)")
    existing_cols = [r[1] for r in cursor.fetchall()]
    new_cols = [
        ("officer_id", "TEXT"),
        ("final_outcome", "TEXT"),
        ("checklist_results_json", "TEXT"),
        ("attachment_name", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE inspection_outcomes ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                pass

    # Configurable System Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL,
        description TEXT,
        updated_at TEXT NOT NULL
    )
    """)

    # Insert default settings if empty
    default_settings = [
        ("reliability_weights", json.dumps({"w_observed": 1.0, "w_reconstructed": 0.65, "w_inconsistent": 2.0, "w_missing": 1.0, "w_delayed": 0.3}), "Weights for Measurement Reliability score calculation"),
        ("qualification_thresholds", json.dumps({"sufficient": 80.0, "uncertain": 60.0}), "Cutoffs for SUFFICIENT, UNCERTAIN, and UNRELIABLE evidence"),
        ("tariff_rate_inr", "7.5", "Standard electricity tariff per kWh in INR (TSSPDCL / TSNPDCL commercial/domestic blended)"),
        ("default_inspection_cost", "1500", "Estimated field inspection cost per visit in INR"),
        ("model_contamination", "0.15", "Expected contamination proportion for Isolation Forest anomaly detection")
    ]

    for key, val, desc in default_settings:
        cursor.execute("""
        INSERT OR IGNORE INTO system_settings (setting_key, setting_value, description, updated_at)
        VALUES (?, ?, ?, ?)
        """, (key, val, desc, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Vidyut Netra SQLite database initialized successfully.")
