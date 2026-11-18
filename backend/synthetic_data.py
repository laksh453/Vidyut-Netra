"""
Vidyut Netra Synthetic Smart-Meter Data Generator
Designed for TISC 2026 - Challenge 12: Revenue Assurance Analytics.

NOTICE:
THIS DATASET CONTAINS SYNTHETIC DEMONSTRATION DATA GENERATED FOR RESEARCH
AND BENCHMARKING PURPOSES. ANOMALOUS CONSUMPTION PATTERNS ARE CONTROLLED
SYNTHETIC EXAMPLES AND MUST NOT BE PRESENTED AS GENUINE ELECTRICITY THEFT CASES.
EVERY ANOMALY REQUIRES QUALIFIED HUMAN PHYSICAL VERIFICATION.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import os

def generate_synthetic_smart_meter_data(num_consumers=30, days=30, output_path=None):
    """
    Generates realistic smart-meter time-series data with controlled quality artifacts
    and behavioral patterns.
    """
    np.random.seed(42)
    random.seed(42)

    categories = [
        {"cat": "Commercial", "base_load": 18.0, "var": 4.5, "v_base": 230, "tariff": 9.5},
        {"cat": "Industrial (LT)", "base_load": 45.0, "var": 10.0, "v_base": 415, "tariff": 8.8},
        {"cat": "Residential (Domestic)", "base_load": 4.2, "var": 1.2, "v_base": 230, "tariff": 6.2},
        {"cat": "Agricultural", "base_load": 12.0, "var": 3.0, "v_base": 230, "tariff": 4.0}
    ]

    transformers = [
        "DT-HYD-CENTRAL-01", "DT-HYD-CENTRAL-02", "DT-SEC-NORTH-04", 
        "DT-WARANGAL-EAST-02", "DT-MEDCHAL-IND-07", "DT-SHAMSHABAD-RUR-03"
    ]

    # Consumer archetype definitions
    # C01-C15: Normal regular consumers
    # C16-C18: Suspicious severe drop (candidate meter bypass / illegal tap)
    # C19-C21: Defective / Decaying meter (hardware drift)
    # C22-C24: Solar Rooftop PV consumer (legitimate daytime drop)
    # C25-C27: High Telemetry Missing / Gateway Drops (Unreliable evidence)
    # C28-C29: Inconsistent & Duplicate records (sensor glitch / retransmission)
    # C30: Vacant Premise / Business Closed (Legitimate low load)

    consumers = []
    for i in range(1, num_consumers + 1):
        c_id = f"TG-DISCOM-{i:04d}"
        m_id = f"EM-{100000 + i}"
        cat_info = categories[(i - 1) % len(categories)]
        t_id = transformers[(i - 1) % len(transformers)]

        if 1 <= i <= 15:
            archetype = "NORMAL"
        elif 16 <= i <= 18:
            archetype = "SEVERE_DROP_SUSPICIOUS"
        elif 19 <= i <= 21:
            archetype = "DEFECTIVE_METER_DRIFT"
        elif 22 <= i <= 24:
            archetype = "SOLAR_ROOFTOP_LEGITIMATE"
        elif 25 <= i <= 27:
            archetype = "TELEMETRY_MISSING_UNRELIABLE"
        elif 28 <= i <= 29:
            archetype = "INCONSISTENT_DUPLICATE_GLITCH"
        else:
            archetype = "VACANT_LEGITIMATE"

        consumers.append({
            "consumer_id": c_id,
            "meter_id": m_id,
            "category": cat_info["cat"],
            "base_load": cat_info["base_load"],
            "load_var": cat_info["var"],
            "v_base": cat_info["v_base"],
            "tariff": cat_info["tariff"],
            "transformer_id": t_id,
            "archetype": archetype
        })

    start_date = datetime(2026, 1, 1, 0, 0, 0)
    records = []

    # Daily aggregation points for 30 days
    for day_idx in range(days):
        current_date = start_date + timedelta(days=day_idx)
        date_str = current_date.strftime("%Y-%m-%d")
        is_weekend = current_date.weekday() >= 5

        for c in consumers:
            c_id = c["consumer_id"]
            m_id = c["meter_id"]
            arch = c["archetype"]
            base = c["base_load"]
            var = c["load_var"]
            v_nom = c["v_base"]
            cat = c["category"]
            tr = c["transformer_id"]
            tariff = c["tariff"]

            # Baseline calculation
            weekend_mod = 0.85 if (is_weekend and cat in ["Commercial", "Industrial (LT)"]) else 1.05 if (is_weekend and cat == "Residential (Domestic)") else 1.0
            daily_cons = max(0.2, np.random.normal(base * weekend_mod, var))
            daily_v = np.random.normal(v_nom, 3.5)
            daily_i = round((daily_cons * 1000) / (daily_v * 0.9), 2) if daily_v > 0 else 0.0

            # Default costs
            est_rec_val = round(daily_cons * tariff * 30 * 0.7, 2) # estimated monthly potential leakage
            insp_cost = 1500.0 if "Industrial" in cat else 1200.0 if "Commercial" in cat else 800.0

            # Apply Archetype behaviors
            if arch == "NORMAL":
                records.append({
                    "consumer_id": c_id,
                    "meter_id": m_id,
                    "timestamp": f"{date_str} 23:00:00",
                    "consumption": round(daily_cons, 2),
                    "voltage": round(daily_v, 1),
                    "current": daily_i,
                    "transformer_id": tr,
                    "consumer_category": cat,
                    "estimated_recoverable_value": est_rec_val,
                    "inspection_cost": insp_cost
                })

            elif arch == "SEVERE_DROP_SUSPICIOUS":
                # Drops abruptly after Day 10 to ~25% of baseline, but voltage and occupancy remain normal!
                if day_idx >= 10:
                    manipulated_cons = round(daily_cons * 0.22, 2)
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": manipulated_cons,
                        "voltage": round(daily_v, 1), # Normal line voltage still recorded
                        "current": round(daily_i * 0.25, 2),
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": round((daily_cons - manipulated_cons) * tariff * 30, 2),
                        "inspection_cost": insp_cost
                    })
                else:
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": round(daily_cons, 2),
                        "voltage": round(daily_v, 1),
                        "current": daily_i,
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": est_rec_val,
                        "inspection_cost": insp_cost
                    })

            elif arch == "DEFECTIVE_METER_DRIFT":
                # Gradual progressive decline down to near zero due to physical meter degradation
                drift_factor = max(0.05, 1.0 - (day_idx / float(days)) * 0.9)
                degraded_cons = round(daily_cons * drift_factor, 2)
                records.append({
                    "consumer_id": c_id,
                    "meter_id": m_id,
                    "timestamp": f"{date_str} 23:00:00",
                    "consumption": degraded_cons,
                    "voltage": round(daily_v, 1),
                    "current": round(daily_i * drift_factor, 2),
                    "transformer_id": tr,
                    "consumer_category": cat,
                    "estimated_recoverable_value": round((daily_cons - degraded_cons) * tariff * 30, 2),
                    "inspection_cost": insp_cost
                })

            elif arch == "SOLAR_ROOFTOP_LEGITIMATE":
                # Daytime solar generation reduces net grid draw by 50-60%, perfectly stable pattern
                solar_cons = round(daily_cons * 0.45, 2)
                records.append({
                    "consumer_id": c_id,
                    "meter_id": m_id,
                    "timestamp": f"{date_str} 23:00:00",
                    "consumption": solar_cons,
                    "voltage": round(daily_v + 4.0, 1), # Slightly elevated voltage due to solar reverse feed
                    "current": round(daily_i * 0.5, 2),
                    "transformer_id": tr,
                    "consumer_category": cat,
                    "estimated_recoverable_value": round(solar_cons * tariff * 10, 2),
                    "inspection_cost": insp_cost
                })

            elif arch == "TELEMETRY_MISSING_UNRELIABLE":
                # 45% of readings simply not received due to cellular/RF gateway failure
                if random.random() > 0.45:
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": round(daily_cons, 2),
                        "voltage": round(daily_v, 1),
                        "current": daily_i,
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": est_rec_val,
                        "inspection_cost": insp_cost
                    })
                # Else reading is omitted (MISSING)

            elif arch == "INCONSISTENT_DUPLICATE_GLITCH":
                # Inconsistent negative readings, absurd spikes, and duplicate records
                if day_idx in [5, 12]:
                    # Inconsistent negative consumption!
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": -12.5,
                        "voltage": round(daily_v, 1),
                        "current": daily_i,
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": est_rec_val,
                        "inspection_cost": insp_cost
                    })
                elif day_idx in [18]:
                    # Absurd impossible spike (>10x transformer limit)
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": 989.0,
                        "voltage": round(daily_v, 1),
                        "current": 450.0,
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": est_rec_val,
                        "inspection_cost": insp_cost
                    })
                else:
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": round(daily_cons, 2),
                        "voltage": round(daily_v, 1),
                        "current": daily_i,
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": est_rec_val,
                        "inspection_cost": insp_cost
                    })

                # Duplicate record injection on day 7 & 15
                if day_idx in [7, 15]:
                    records.append({
                        "consumer_id": c_id,
                        "meter_id": m_id,
                        "timestamp": f"{date_str} 23:00:00",
                        "consumption": round(daily_cons, 2),
                        "voltage": round(daily_v, 1),
                        "current": daily_i,
                        "transformer_id": tr,
                        "consumer_category": cat,
                        "estimated_recoverable_value": est_rec_val,
                        "inspection_cost": insp_cost
                    })

            elif arch == "VACANT_LEGITIMATE":
                # Vacant flat/factory: baseline near 0.1 kWh for security light
                records.append({
                    "consumer_id": c_id,
                    "meter_id": m_id,
                    "timestamp": f"{date_str} 23:00:00",
                    "consumption": 0.25,
                    "voltage": round(daily_v, 1),
                    "current": 0.12,
                    "transformer_id": tr,
                    "consumer_category": cat,
                    "estimated_recoverable_value": 0.0,
                    "inspection_cost": insp_cost
                })

    df = pd.DataFrame(records)
    
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Synthetic dataset generated with {len(df)} records at {output_path}")

    return df

if __name__ == "__main__":
    out_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_data", "vidyut_netra_synthetic_meters.csv")
    generate_synthetic_smart_meter_data(output_path=out_file)
