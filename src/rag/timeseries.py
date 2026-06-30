"""Bounded, safe time-series query tools over the FD001 sensor data.

These are the only ways the system can touch the telemetry — a small set of read-only,
parameterized functions (NOT free-form SQL). Each returns structured data plus a
`query_handle` (cited provenance) and a short `result_summary` for the prompt.

Thresholds come straight from the Phase-1 asset hierarchy, so telemetry alarms and the
maintenance docs agree by construction.
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.data import load_cmapss
from src.data.asset_hierarchy import load_hierarchy

N_ENGINES = 100  # FD001 train trajectories


def _hier():
    return load_hierarchy().set_index("sensor_id")


def engine_exists(engine: int) -> bool:
    return isinstance(engine, int) and 1 <= engine <= N_ENGINES


def sensor_exists(sensor: int) -> bool:
    return isinstance(sensor, int) and 1 <= sensor <= config.N_SENSORS


def _last_cycle(con, engine: int) -> int:
    return con.execute(
        f"SELECT MAX(time_in_cycles) FROM {config.TABLE_TRAIN} WHERE unit_number = ?",
        [engine],
    ).fetchone()[0]


def sensor_trend(engine: int, sensor: int, last_n: int = 50) -> dict:
    """Recent trajectory of one sensor for one engine."""
    handle = f"telemetry:engine{engine}/sensor{sensor}/trend(last_n={last_n})"
    if not engine_exists(engine) or not sensor_exists(sensor):
        return {"ok": False, "query_handle": handle,
                "result_summary": f"No data: engine {engine} / sensor {sensor} not found."}
    col = f"sensor_{sensor}"
    sym = _hier().loc[sensor, "symbol"]
    con = load_cmapss.connect()
    try:
        rows = con.execute(
            f"""SELECT time_in_cycles, {col} FROM {config.TABLE_TRAIN}
                WHERE unit_number = ? ORDER BY time_in_cycles DESC LIMIT ?""",
            [engine, last_n],
        ).fetchall()
    finally:
        con.close()
    rows = rows[::-1]  # chronological
    values = [r[1] for r in rows]
    direction = "flat"
    if len(values) >= 2:
        delta = values[-1] - values[0]
        rng = (max(values) - min(values)) or 1e-9
        if abs(delta) > 0.05 * rng:
            direction = "rising" if delta > 0 else "falling"
    summary = (
        f"Engine {engine} {sym} (sensor {sensor}) over last {len(rows)} cycles: "
        f"{values[0]:.2f} → {values[-1]:.2f} ({direction})."
    )
    return {
        "ok": True, "query_handle": handle, "engine": engine, "sensor": sensor,
        "symbol": sym, "series": [{"cycle": r[0], "value": r[1]} for r in rows],
        "start": values[0], "end": values[-1], "direction": direction,
        "result_summary": summary,
    }


def _status_for(hier, sym_row, value: float) -> dict:
    direction = sym_row["alarm_direction"]
    thr = sym_row["alarm_threshold"]
    in_alarm = False
    if direction == "high" and pd.notna(thr):
        in_alarm = value >= thr
    elif direction == "low" and pd.notna(thr):
        in_alarm = value <= thr
    return {
        "sensor": int(sym_row.name), "symbol": sym_row["symbol"], "value": round(value, 2),
        "nominal_min": sym_row["nominal_min"], "nominal_max": sym_row["nominal_max"],
        "alarm_threshold": (None if pd.isna(thr) else thr),
        "alarm_direction": direction, "in_alarm": bool(in_alarm),
        "informative": bool(sym_row["is_informative"]),
    }


def sensor_status(engine: int, sensor: int | None = None, at_cycle: int | None = None) -> dict:
    """Value vs nominal/alarm for one sensor (or all informative sensors) at a cycle.

    Defaults to the engine's last recorded cycle.
    """
    scope = f"sensor{sensor}" if sensor else "all"
    if not engine_exists(engine) or (sensor is not None and not sensor_exists(sensor)):
        return {"ok": False,
                "query_handle": f"telemetry:engine{engine}/{scope}/status",
                "result_summary": f"No data: engine {engine} / sensor {sensor} not found."}
    hier = _hier()
    con = load_cmapss.connect()
    try:
        cycle = at_cycle or _last_cycle(con, engine)
        row = con.execute(
            f"SELECT * FROM {config.TABLE_TRAIN} WHERE unit_number = ? AND time_in_cycles = ?",
            [engine, cycle],
        ).df()
    finally:
        con.close()
    handle = f"telemetry:engine{engine}/{scope}/status@cycle{cycle}"
    if row.empty:
        return {"ok": False, "query_handle": handle,
                "result_summary": f"No data at cycle {cycle} for engine {engine}."}

    sensor_ids = [sensor] if sensor else [i for i in hier.index if hier.loc[i, "is_informative"]]
    statuses = [_status_for(hier, hier.loc[sid], float(row[f"sensor_{sid}"].iloc[0]))
                for sid in sensor_ids]
    alarms = [s for s in statuses if s["in_alarm"]]
    if sensor:
        s = statuses[0]
        summary = (f"Engine {engine} {s['symbol']} at cycle {cycle}: {s['value']} "
                   f"({'IN ALARM' if s['in_alarm'] else 'nominal'}; "
                   f"nominal {s['nominal_min']}–{s['nominal_max']}).")
    else:
        summary = (f"Engine {engine} at cycle {cycle}: "
                   f"{len(alarms)} of {len(statuses)} informative sensors in alarm"
                   + (": " + ", ".join(a["symbol"] for a in alarms) if alarms else "."))
    return {"ok": True, "query_handle": handle, "engine": engine, "cycle": cycle,
            "statuses": statuses, "alarms": alarms, "result_summary": summary}


def engine_overview(engine: int) -> dict:
    """Total cycles + which sensors are in alarm at the engine's last cycle."""
    handle = f"telemetry:engine{engine}/overview"
    if not engine_exists(engine):
        return {"ok": False, "query_handle": handle,
                "result_summary": f"No data: engine {engine} not found."}
    con = load_cmapss.connect()
    try:
        cycles = _last_cycle(con, engine)
    finally:
        con.close()
    status = sensor_status(engine)  # last cycle, all informative
    alarms = status["alarms"]
    summary = (f"Engine {engine}: {cycles} operational cycles recorded; "
               f"{len(alarms)} sensors in alarm at last cycle"
               + (" (" + ", ".join(a["symbol"] for a in alarms) + ")." if alarms else "."))
    return {"ok": True, "query_handle": handle, "engine": engine, "n_cycles": cycles,
            "alarms": alarms, "result_summary": summary}
