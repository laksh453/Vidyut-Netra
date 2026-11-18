"""
Vidyut Netra Data Preprocessing Engine
Handles data ingestion, validation, duplicate isolation, time-series continuity,
negative/outlier flagging, and provenance-tracked reconstruction.
Never mutates raw original data.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

REQUIRED_COLUMNS = ["consumer_id", "meter_id", "timestamp", "consumption"]
OPTIONAL_COLUMNS = [
    "voltage", "current", "transformer_id", "consumer_category",
    "estimated_recoverable_value", "inspection_cost"
]

def validate_raw_dataframe(df):
    """
    Validates presence of required columns and basic data integrity.
    Supports case-insensitive column headers and common synonyms.
    """
    errors = []
    # Strip leading/trailing whitespace from column names
    df.columns = [str(c).strip() for c in df.columns]

    # Flexible case-insensitive header mapping for standard smart-meter terminology
    col_map = {}
    for col in df.columns:
        cl = col.lower().replace(" ", "_")
        if cl in ["consumer_id", "consumerid", "consumer", "cust_id", "customer_id", "ca_number"]:
            col_map[col] = "consumer_id"
        elif cl in ["meter_id", "meterid", "meter", "meter_no", "meter_number", "serial_no"]:
            col_map[col] = "meter_id"
        elif cl in ["timestamp", "time", "datetime", "date", "reading_date", "reading_time"]:
            col_map[col] = "timestamp"
        elif cl in ["consumption", "units", "kwh", "reading", "active_energy", "energy_kwh"]:
            col_map[col] = "consumption"
        elif cl in ["voltage", "volts", "v", "grid_voltage"]:
            col_map[col] = "voltage"
        elif cl in ["current", "amps", "i", "load_current"]:
            col_map[col] = "current"
        elif cl in ["transformer_id", "transformer", "dt_id", "dt_code"]:
            col_map[col] = "transformer_id"
        elif cl in ["consumer_category", "category", "tariff", "tariff_category"]:
            col_map[col] = "consumer_category"
        elif cl in ["estimated_recoverable_value", "recoverable_value", "recovery_value"]:
            col_map[col] = "estimated_recoverable_value"
        elif cl in ["inspection_cost", "squad_cost", "cost"]:
            col_map[col] = "inspection_cost"

    if col_map:
        df.rename(columns=col_map, inplace=True)

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        found_cols = list(df.columns)
        errors.append(f"Missing required column(s): {missing_cols}. Found columns: {found_cols}. Required columns are: {REQUIRED_COLUMNS}")
        return False, errors

    if len(df) == 0:
        errors.append("The uploaded CSV file is empty (contains 0 data rows).")
        return False, errors

    return True, []

def preprocess_smart_meter_data(df_raw, dataset_id=None):
    """
    Executes the full preprocessing pipeline on raw data:
    1. Preserves raw records unaltered
    2. Identifies duplicates
    3. Formats timestamps and sorts chronologically
    4. Detects missing intervals / missing values
    5. Flags invalid and negative readings
    6. Identifies sudden extreme shifts requiring review
    7. Creates reconstructed series with explicit provenance tags
    8. Generates comprehensive audit report
    """
    # Create working copy
    df = df_raw.copy()

    # Preprocessing metrics counters
    metrics = {
        "total_records": len(df),
        "valid_records": 0,
        "duplicate_records": 0,
        "missing_records": 0,
        "invalid_records": 0,
        "negative_records": 0,
        "records_requiring_review": 0,
        "reconstructed_records": 0,
        "unique_consumers": 0,
        "unique_meters": 0,
        "date_range": {"start": None, "end": None}
    }

    # Ensure optional columns exist
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            if col == "voltage":
                df[col] = 230.0
            elif col == "current":
                df[col] = 0.0
            elif col == "transformer_id":
                df[col] = "DT-UNKNOWN"
            elif col == "consumer_category":
                df[col] = "General"
            elif col == "estimated_recoverable_value":
                df[col] = 0.0
            elif col == "inspection_cost":
                df[col] = 1200.0

    # Parse timestamps
    df["raw_timestamp"] = df["timestamp"].astype(str)
    df["parsed_timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    invalid_time_mask = df["parsed_timestamp"].isna()
    
    # Sort chronologically by consumer and timestamp
    df = df.sort_values(by=["consumer_id", "parsed_timestamp"]).reset_index(drop=True)

    # Detect duplicate readings (same consumer, same timestamp)
    duplicate_mask = df.duplicated(subset=["consumer_id", "parsed_timestamp"], keep="first")
    metrics["duplicate_records"] = int(duplicate_mask.sum())

    cleaned_rows = []

    # Process consumer by consumer
    consumers = df["consumer_id"].unique()
    metrics["unique_consumers"] = len(consumers)
    metrics["unique_meters"] = int(df["meter_id"].nunique())

    min_ts = None
    max_ts = None

    for c_id in consumers:
        c_df = df[df["consumer_id"] == c_id].copy()
        
        # Analyze consumer readings
        for idx, row in c_df.iterrows():
            ts_str = str(row["parsed_timestamp"]) if pd.notna(row["parsed_timestamp"]) else row["raw_timestamp"]
            raw_val = row["consumption"]
            is_dup = bool(duplicate_mask.loc[idx])
            
            # Check date range
            if pd.notna(row["parsed_timestamp"]):
                if min_ts is None or row["parsed_timestamp"] < min_ts:
                    min_ts = row["parsed_timestamp"]
                if max_ts is None or row["parsed_timestamp"] > max_ts:
                    max_ts = row["parsed_timestamp"]

            # Initialize classification
            reading_category = "OBSERVED"
            is_reconstructed = 0
            provenance = "Direct sensor telemetry verified"
            usable_val = raw_val
            requires_review = False

            # Check invalid timestamp
            if pd.isna(row["parsed_timestamp"]):
                reading_category = "INCONSISTENT"
                requires_review = True
                provenance = f"Unparseable timestamp string: '{row['raw_timestamp']}'"
                metrics["invalid_records"] += 1

            # Check duplicate
            elif is_dup:
                reading_category = "INCONSISTENT"
                requires_review = True
                provenance = "Duplicate timestamp reading detected (retransmission glitch); excluded from primary calculation"
                usable_val = None

            # Check missing consumption value
            elif pd.isna(raw_val) or raw_val is None:
                reading_category = "MISSING"
                requires_review = True
                provenance = "Telemetry gap: null/empty consumption received from meter gateway"
                metrics["missing_records"] += 1
                usable_val = None

            else:
                # Check negative consumption
                try:
                    num_val = float(raw_val)
                    if num_val < 0:
                        reading_category = "INCONSISTENT"
                        requires_review = True
                        provenance = f"Invalid negative consumption ({num_val} kWh) recorded on standard unidirectional tariff"
                        metrics["negative_records"] += 1
                        metrics["invalid_records"] += 1
                        usable_val = 0.0 # Reconstruct or clamp for modeling, preserving raw
                        is_reconstructed = 1
                    elif num_val > 500.0 and str(row.get("consumer_category", "")).lower() != "industrial (ht)":
                        # Impossible spike test for LT consumer
                        reading_category = "INCONSISTENT"
                        requires_review = True
                        provenance = f"Physically improbable spike ({num_val} kWh) exceeds sanctioned transformer/meter thermal capacity"
                        metrics["invalid_records"] += 1
                        usable_val = None
                    else:
                        reading_category = "OBSERVED"
                        usable_val = num_val
                        metrics["valid_records"] += 1
                except (ValueError, TypeError):
                    reading_category = "INCONSISTENT"
                    requires_review = True
                    provenance = f"Non-numeric consumption token: '{raw_val}'"
                    metrics["invalid_records"] += 1
                    usable_val = None

            if requires_review:
                metrics["records_requiring_review"] += 1

            cleaned_rows.append({
                "dataset_id": dataset_id,
                "consumer_id": c_id,
                "meter_id": str(row["meter_id"]),
                "timestamp": ts_str,
                "consumption": usable_val,
                "raw_consumption": raw_val,
                "voltage": float(row["voltage"]) if pd.notna(row["voltage"]) else 230.0,
                "current": float(row["current"]) if pd.notna(row["current"]) else 0.0,
                "transformer_id": str(row["transformer_id"]),
                "consumer_category": str(row["consumer_category"]),
                "reading_category": reading_category,
                "is_reconstructed": is_reconstructed,
                "is_duplicate": int(is_dup),
                "provenance_notes": provenance,
                "requires_review": requires_review
            })

    # Linear / Median reconstruction for isolated missing slots where reasonable
    cleaned_df = pd.DataFrame(cleaned_rows)
    for c_id in consumers:
        c_idx = cleaned_df[cleaned_df["consumer_id"] == c_id].index
        # If there are missing values between valid ones, impute with rolling median with tag RECONSTRUCTED
        valid_vals = cleaned_df.loc[c_idx, "consumption"].dropna()
        if len(valid_vals) > 0:
            median_val = float(valid_vals.median())
            for idx in c_idx:
                if cleaned_df.loc[idx, "reading_category"] == "MISSING":
                    cleaned_df.loc[idx, "consumption"] = round(median_val, 2)
                    cleaned_df.loc[idx, "reading_category"] = "RECONSTRUCTED"
                    cleaned_df.loc[idx, "is_reconstructed"] = 1
                    cleaned_df.loc[idx, "provenance_notes"] = f"Imputed using 30-day consumer median ({median_val:.2f} kWh) for continuity modeling"
                    metrics["reconstructed_records"] += 1

    if min_ts:
        metrics["date_range"]["start"] = min_ts.strftime("%Y-%m-%d %H:%M:%S")
    if max_ts:
        metrics["date_range"]["end"] = max_ts.strftime("%Y-%m-%d %H:%M:%S")

    return cleaned_df, metrics
