"""Detect flat / non-informative sensors in FD001.

A sensor is useful for prognostics only if it *moves as the engine degrades*. We
therefore classify by signal-to-noise: the drift between the healthy window (early
cycles) and the failure window (last cycles before run-to-failure), measured in units
of the healthy-window noise (std). Sensors whose drift is below the noise floor — and
the truly constant sensors — carry no degradation signal and are dropped.

This is computed, not hardcoded, and the evidence is persisted to
build/flat_sensors.json.

Run as a module:  python -m src.data.detect_flat_sensors
"""
from __future__ import annotations

import json

from src import config
from src.data import load_cmapss

HEALTHY_WINDOW = 20      # first N cycles == normal operation
FAILURE_WINDOW = 20      # last N cycles before failure
SNR_THRESHOLD = 1.0      # informative if drift >= 1 healthy-noise sigma
CONSTANT_STD = 1e-6      # below this the sensor is effectively constant


def compute_flat_sensors(db_path=None) -> dict:
    con = load_cmapss.connect(db_path)
    try:
        healthy = con.execute(
            f"SELECT * FROM {config.TABLE_TRAIN} WHERE time_in_cycles <= {HEALTHY_WINDOW}"
        ).df()
        failure = con.execute(
            f"""
            WITH mx AS (
                SELECT unit_number, MAX(time_in_cycles) AS maxc
                FROM {config.TABLE_TRAIN} GROUP BY unit_number
            )
            SELECT t.* FROM {config.TABLE_TRAIN} t
            JOIN mx ON t.unit_number = mx.unit_number
            WHERE t.time_in_cycles > mx.maxc - {FAILURE_WINDOW}
            """
        ).df()
    finally:
        con.close()

    rows = {}
    for col in config.SENSOR_COLUMNS:
        h_mean = float(healthy[col].mean())
        h_std = float(healthy[col].std(ddof=0))
        f_mean = float(failure[col].mean())
        drift = abs(f_mean - h_mean)
        snr = (drift / h_std) if h_std > CONSTANT_STD else 0.0
        is_flat = (h_std <= CONSTANT_STD) or (snr < SNR_THRESHOLD)
        rows[col] = {
            "healthy_mean": round(h_mean, 6),
            "healthy_std": round(h_std, 6),
            "failure_mean": round(f_mean, 6),
            "drift": round(drift, 6),
            "snr": round(snr, 4),
            "is_flat": bool(is_flat),
        }

    flat = sorted(int(c.split("_")[1]) for c, v in rows.items() if v["is_flat"])
    result = {
        "method": "healthy-vs-failure drift / healthy noise (SNR)",
        "snr_threshold": SNR_THRESHOLD,
        "flat_sensor_ids": flat,
        "per_sensor": rows,
    }

    config.ensure_build_dir()
    config.FLAT_SENSORS_JSON.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    res = compute_flat_sensors()
    print("Flat (non-informative) sensors in FD001:", res["flat_sensor_ids"])
    informative = [i for i in range(1, 22) if i not in res["flat_sensor_ids"]]
    print("Informative sensors:", informative)
