"""Build the asset hierarchy — the single source of truth for the project.

One row per sensor: identity (from sensor_meta) + data-derived nominal range and
alarm threshold. Ranges are computed from the *healthy* operating window (early
cycles); alarm direction is inferred by comparing the healthy window to the
failure window (last cycles before run-to-failure).

Every numeric value the maintenance corpus cites must trace back to this table.

Run as a module:  python -m src.data.asset_hierarchy
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.data import load_cmapss
from src.data.detect_flat_sensors import compute_flat_sensors
from src.data.sensor_meta import SENSORS, sensor_column

HEALTHY_WINDOW = 20   # first N cycles of each engine == normal operation
FAILURE_WINDOW = 20    # last N cycles before failure (train set runs to failure)
ALARM_MARGIN_FRAC = 0.5  # alarm threshold sits this fraction of the healthy spread beyond nominal


def _healthy_and_failure_frames(con):
    healthy = con.execute(
        f"SELECT * FROM {config.TABLE_TRAIN} WHERE time_in_cycles <= {HEALTHY_WINDOW}"
    ).df()
    # max cycle per engine, then keep the last FAILURE_WINDOW cycles of each
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
    return healthy, failure


def build_hierarchy(db_path=None) -> pd.DataFrame:
    flat = compute_flat_sensors(db_path)
    flat_ids = set(flat["flat_sensor_ids"])

    con = load_cmapss.connect(db_path)
    try:
        healthy, failure = _healthy_and_failure_frames(con)
    finally:
        con.close()

    records = []
    for s in SENSORS:
        col = sensor_column(s.sensor_id)
        informative = s.sensor_id not in flat_ids

        nominal_min = round(float(healthy[col].quantile(0.01)), 2)
        nominal_max = round(float(healthy[col].quantile(0.99)), 2)
        spread = nominal_max - nominal_min

        if not informative or spread == 0:
            alarm_threshold = None
            alarm_direction = "none"
        else:
            rises = float(failure[col].mean()) > float(healthy[col].mean())
            alarm_direction = "high" if rises else "low"
            if rises:
                alarm_threshold = round(nominal_max + ALARM_MARGIN_FRAC * spread, 2)
            else:
                alarm_threshold = round(nominal_min - ALARM_MARGIN_FRAC * spread, 2)

        records.append(
            {
                "sensor_id": s.sensor_id,
                "symbol": s.symbol,
                "description": s.description,
                "unit": s.unit,
                "subsystem": s.subsystem,
                "nominal_min": nominal_min,
                "nominal_max": nominal_max,
                "alarm_threshold": alarm_threshold,
                "alarm_direction": alarm_direction,
                "is_informative": informative,
            }
        )

    df = pd.DataFrame.from_records(records)
    config.ensure_build_dir()
    df.to_csv(config.ASSET_HIERARCHY_CSV, index=False)
    return df


def load_hierarchy() -> pd.DataFrame:
    return pd.read_csv(config.ASSET_HIERARCHY_CSV)


if __name__ == "__main__":
    df = build_hierarchy()
    print(df.to_string(index=False))
